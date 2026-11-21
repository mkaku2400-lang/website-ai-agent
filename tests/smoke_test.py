"""Quick checks that need no API key. Run: python tests/smoke_test.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.brain import LLMError, _parse, build_user_message  # noqa: E402
from agent.config import get_settings  # noqa: E402
from agent.knowledge import load_knowledge  # noqa: E402
from agent.leads import build_payload, is_ready, missing_detail  # noqa: E402

settings = get_settings()
store = load_knowledge(settings.knowledge_file)
failures = 0


def check(name: str, ok: bool) -> None:
    global failures
    print(("PASS " if ok else "FAIL ") + name)
    failures += not ok


check("knowledge split into FAQ entries", len(store.chunks) >= 15)
for question, expected in [
    ("how much is teeth whitening", "whitening"),
    ("are you open on saturday", "opening hours"),
    ("do you take my insurance", "insurance"),
    ("my tooth broke, what do I do", "emergency"),
    ("can I pay monthly", "payment plans"),
]:
    top = store.search(question, k=1)
    check(f"search '{question}' finds {expected}", bool(top) and expected in top[0].chunk.title.lower())

check("lead needs name, email and need", not is_ready({"name": "Ana", "email": "ana@x.com"}))
check("lead with all three is ready", is_ready({"name": "Ana", "email": "ana@example.com", "need": "cleaning"}))
check("broken email is not ready", not is_ready({"name": "Ana", "email": "ana@example", "need": "cleaning"}))
check("missing name asked first", missing_detail({"email": "a@b.co"}) == "your name")

payload = build_payload(
    settings,
    {"name": "Ana Ruiz", "email": "ana@example.com", "phone": "555 123", "need": "cleaning", "preferred_time": "Tuesday"},
    "Ana wants a cleaning.",
    [{"role": "user", "content": "Can I book a cleaning?"}],
)
check("payload matches n8n webhook fields", {"name", "email", "message", "source", "business"} <= payload.keys())
check("payload carries phone and time", "Phone: 555 123" in payload["message"] and "Tuesday" in payload["message"])

turn = _parse('{"reply":"Hi","name":"","email":"","phone":"","need":"","preferred_time":"","visitor_confirmed":false,"summary_for_team":""}')
check("valid model JSON parses", turn.reply == "Hi" and not turn.visitor_confirmed)
try:
    _parse("not json")
    check("invalid JSON is rejected", False)
except LLMError:
    check("invalid JSON is rejected", True)

from server import _typed_new_words  # noqa: E402

check("phone typed in this message counts as new", _typed_new_words("my phone is 555 0147", "555 0147", ""))
check("plain yes adds nothing", not _typed_new_words("Yes, please send it", "Tuesday after 3 pm", "Tuesday after 3pm"))
check("model rewording is not new", not _typed_new_words("ok", "Tue or Thu after 3pm", "Tuesday or Thursday after 3pm"))

check("prompt shows request status", "already sent" in build_user_message("hi", "", {}, True))

print("\nAll checks passed." if not failures else f"\n{failures} check(s) failed.")
sys.exit(1 if failures else 0)
