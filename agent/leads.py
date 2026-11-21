"""Hand a finished lead to the team: an n8n webhook, plus a local log for auditing."""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .config import ROOT, Settings

log = logging.getLogger("website_agent.leads")

LEAD_LOG = ROOT / "data" / "leads.jsonl"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def is_ready(lead: dict[str, str]) -> bool:
    """A lead can go to the team once we know who it is, how to reply and what they want."""
    return bool(lead.get("name") and lead.get("need") and EMAIL.match(lead.get("email", "")))


def missing_detail(lead: dict[str, str]) -> str:
    """Wording for the first thing still needed before a lead can be sent."""
    if not lead.get("name"):
        return "your name"
    if not EMAIL.match(lead.get("email", "")):
        return "your email address (the one you typed doesn't look complete)" if lead.get("email") else "your email address"
    return "a few words about what you need"


def build_payload(settings: Settings, lead: dict[str, str], summary: str, transcript: list[dict]) -> dict:
    lines = [summary or lead.get("need", "")]
    if lead.get("preferred_time"):
        lines.append(f"Preferred time: {lead['preferred_time']}")
    if lead.get("phone"):
        lines.append(f"Phone: {lead['phone']}")
    asked = [m["content"] for m in transcript if m["role"] == "user"][-4:]
    if asked:
        lines.append("")
        lines.append("What they wrote in the chat:")
        lines.extend(f"- {text}" for text in asked)
    # Field names match the n8n AI Lead Inbox webhook (Project 4).
    return {
        "name": lead["name"],
        "email": lead["email"],
        "company": "",
        "budget": "Not given",
        "message": "\n".join(lines),
        "source": "website chat",
        "business": settings.business_name,
        "sign_off": settings.lead_sign_off,
    }


def send_lead(settings: Settings, payload: dict) -> bool:
    """Send the lead to n8n. Returns False if it could not be delivered."""
    LEAD_LOG.parent.mkdir(exist_ok=True)
    record = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    delivered = True
    if settings.lead_webhook_url:
        request = urllib.request.Request(
            settings.lead_webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                delivered = 200 <= response.status < 300
        except (urllib.error.URLError, TimeoutError) as exc:
            log.warning("Lead webhook failed: %s", exc)
            delivered = False
    record["delivered"] = delivered
    with LEAD_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return delivered
