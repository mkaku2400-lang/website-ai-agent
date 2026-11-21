# Website AI Agent: answers visitors and hands real leads to your team

A chat assistant that sits on any website with one `<script>` tag. It answers visitors' questions using only the business's own information (FAQ, price list, policies), and when someone wants an appointment, a quote or a call-back, it collects their name, email and request, asks permission, and sends the lead to an n8n workflow that sorts it and drafts the reply.

The demo runs on a fictional dental clinic. Names, prices and contact details are made up.

## What it does

- **Answers from the business's information only.** It never invents prices, hours or availability. When something isn't covered it says so and offers to pass the question on.
- **Collects leads in the conversation.** Name, email and what they need, plus phone and preferred times if offered. It asks for one or two details at a time, never a form.
- **Asks before sending.** Details go to the team only after the visitor agrees. The server checks that name, email and request are all there and the email looks valid before anything is sent.
- **Never books on its own.** It can't see the calendar, so it never says an appointment is confirmed. The team confirms by email.
- **Hands off to n8n.** Finished leads are POSTed to the [n8n AI Lead Inbox](https://github.com/mkaku2400-lang/n8n-ai-lead-inbox), which rates them hot, warm, cold or spam and drafts the reply. Every lead is also written to `data/leads.jsonl`.
- **Works with Claude, OpenAI or Gemini.** Each chat turn returns structured JSON (the reply plus the lead fields), so lead capture doesn't depend on parsing free text.

## How it fits together

```
Website  ──<script src="/widget.js">──►  chat widget (shadow DOM, no styles leak in or out)
                                               │ POST /api/chat
                                               ▼
                                   FastAPI server (server.py)
                     search the FAQ ──► AI model (JSON: reply + lead fields)
                                               │ visitor agreed and details complete
                                               ▼
                         n8n webhook ──► AI Lead Inbox: rate, draft reply, save
```

## Run it locally

1. Python 3.10 or newer.
2. Install:
   ```
   python -m venv .venv
   .venv\Scripts\activate          (macOS/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add one API key (`GEMINI_API_KEY` has a free tier: https://aistudio.google.com/apikey).
4. Optional: run the n8n AI Lead Inbox and keep `LEAD_WEBHOOK_URL=http://localhost:5678/webhook/lead`. Without it, leave the URL empty and leads are only logged.
5. Start the server:
   ```
   uvicorn server:app --port 8000
   ```
6. Open http://localhost:8000 and click "Ask a question" in the corner.

Checks that need no API key: `python tests/smoke_test.py`

## Use it for another business

1. Replace `knowledge/northgate_dental_faq.md` with the business's own FAQ. Write it as `Q:` / `A:` pairs for the most precise answers; a PDF also works (`KNOWLEDGE_FILE=knowledge/faq.pdf`).
2. Set `BUSINESS_NAME`, `FRONT_DESK_CONTACT` and `LEAD_SIGN_OFF` in `.env`.
3. Put the script tag on their site, pointing at wherever the server runs:
   ```html
   <script src="https://chat.example.com/widget.js"
           data-title="Business name" data-color="#0f766e" defer></script>
   ```
   Optional attributes: `data-subtitle`, `data-greeting`, `data-placeholder`, `data-position="left"`.
4. Set `ALLOWED_ORIGINS` to the site's address so other sites can't use the server.

## Files

| Path | What it is |
|---|---|
| `server.py` | API, sessions, lead hand-off, serves the widget and the demo site |
| `agent/brain.py` | One chat turn with Claude, OpenAI or Gemini, returning JSON |
| `agent/knowledge.py`, `agent/retrieval/` | FAQ loading and search (from the PDF support chatbot project) |
| `agent/leads.py` | Lead checks, the n8n payload and the local log |
| `static/widget.js` | The embeddable chat widget, no dependencies |
| `demo_site/index.html` | Fictional clinic website used in the demo |
| `knowledge/northgate_dental_faq.md` | The clinic's information the assistant answers from |

## Notes for a production setup

- Sessions are kept in memory, which is fine for one server process. For several processes, move them to Redis or a database.
- Put the server behind HTTPS and set `ALLOWED_ORIGINS`.
- Search is keyword based and runs offline. For large or loosely worded documents, swap in semantic embeddings (`agent/retrieval/embeddings.py` explains how).
