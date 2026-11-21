"""Website AI agent server.

Serves the chat widget (/widget.js), the chat API (/api/chat) and a demo website (/).

    uvicorn server:app --port 8000
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.brain import LLMError, run_turn
from agent.config import ROOT, get_settings
from agent.knowledge import format_excerpts, load_knowledge
from agent.leads import build_payload, is_ready, missing_detail, send_lead

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("website_agent")

settings = get_settings()
store = load_knowledge(settings.knowledge_file)
log.info("Loaded %d knowledge chunks from %s; AI provider: %s (%s)",
         len(store.chunks), settings.knowledge_file.name, settings.provider, settings.model)

SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_MESSAGE_CHARS = 1000


@dataclass
class Session:
    history: list[dict] = field(default_factory=list)
    lead: dict[str, str] = field(default_factory=dict)
    lead_sent: bool = False
    awaiting_ok: bool = False  # the last reply asked whether the details may be sent
    last_seen: float = field(default_factory=time.time)


sessions: dict[str, Session] = {}


_WORD = re.compile(r"[a-z0-9@.]{3,}")


def _typed_new_words(message: str, new_value: str, old_value: str) -> bool:
    """True if the visitor typed part of a detail in this message that wasn't known before.

    Comparing words the visitor typed (not the model's wording) means a model that rephrases
    "after 3pm" as "after 3 pm" on the next turn doesn't count as new information.
    """
    typed = set(_WORD.findall(message.lower()))
    known = set(_WORD.findall(old_value.lower()))
    return any(word in typed and word not in known for word in _WORD.findall(new_value.lower()))


def get_session(session_id: str | None) -> tuple[str, Session]:
    now = time.time()
    for key in [k for k, s in sessions.items() if now - s.last_seen > SESSION_TTL_SECONDS]:
        del sessions[key]
    if not session_id or session_id not in sessions:
        session_id = uuid.uuid4().hex
        sessions[session_id] = Session()
    session = sessions[session_id]
    session.last_seen = now
    return session_id, session


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    lead_sent: bool


app = FastAPI(title="Website AI Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    session_id, session = get_session(body.session_id)
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Empty message")

    if len(session.history) >= settings.max_messages_per_session * 2:
        reply = f"This chat has reached its length limit. To continue, please {settings.front_desk_contact}."
        return ChatResponse(session_id=session_id, reply=reply, lead_sent=session.lead_sent)

    # Search with the previous visitor message too, so short follow-ups ("and for kids?") still match.
    previous = next((m["content"] for m in reversed(session.history) if m["role"] == "user"), "")
    hits = store.search(f"{previous} {message}".strip(), k=settings.top_k)

    try:
        turn = run_turn(settings, message, format_excerpts(hits), session.history, session.lead, session.lead_sent)
    except LLMError as exc:
        log.warning("AI provider failed: %s", exc)
        reply = f"Sorry, I can't answer right now. Please try again in a minute, or {settings.front_desk_contact}."
        return ChatResponse(session_id=session_id, reply=reply, lead_sent=session.lead_sent)

    # Contact details that are new in this message. A message that adds details is not a "yes".
    added = [
        key for key in ("name", "email", "phone", "preferred_time")
        if _typed_new_words(message, turn.lead.get(key, ""), session.lead.get(key, ""))
    ]
    for key, value in turn.lead.items():
        if value:
            session.lead[key] = value
    reply = turn.reply
    asked_before = session.awaiting_ok
    session.awaiting_ok = turn.asking_permission

    if turn.visitor_confirmed and not session.lead_sent:
        # The model's judgement alone is not enough to send someone's details: the previous reply
        # must have asked for permission and this message must not be adding new details.
        if not asked_before or added:
            reply = "Got it, I've noted that. Shall I send your request to the front desk now?"
            session.awaiting_ok = True
        elif is_ready(session.lead):
            payload = build_payload(settings, session.lead, turn.summary_for_team, [*session.history, {"role": "user", "content": message}])
            if send_lead(settings, payload):
                session.lead_sent = True
                log.info("Lead sent for session %s", session_id[:8])
            else:
                reply = (
                    "Sorry, I couldn't pass your details to the team just now. "
                    f"Please {settings.front_desk_contact}, or try again in a few minutes."
                )
        else:
            # The model thought it was done but a detail is missing or the email looks wrong.
            reply = f"Before I send this, could you give me {missing_detail(session.lead)}?"

    session.history.append({"role": "user", "content": message})
    session.history.append({"role": "assistant", "content": reply})
    return ChatResponse(session_id=session_id, reply=reply, lead_sent=session.lead_sent)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "provider": settings.provider, "chunks": len(store.chunks)}


@app.get("/widget.js")
def widget() -> FileResponse:
    return FileResponse(ROOT / "static" / "widget.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache"})


DEMO_SITE = ROOT / "demo_site"
if DEMO_SITE.is_dir():
    app.mount("/", StaticFiles(directory=Path(DEMO_SITE), html=True), name="demo_site")
