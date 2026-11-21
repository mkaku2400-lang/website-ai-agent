"""Settings, read from .env / environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

_PLACEHOLDER_MARKERS = ("your", "xxx", "changeme", "replace")


def _clean_key(value: str | None) -> str:
    value = (value or "").strip().strip('"').strip("'")
    if not value or any(marker in value.lower() for marker in _PLACEHOLDER_MARKERS):
        return ""
    return value


@dataclass(frozen=True)
class Settings:
    business_name: str
    knowledge_file: Path
    front_desk_contact: str  # shown when something goes wrong, so a visitor is never stuck
    lead_webhook_url: str  # n8n webhook that receives finished leads; empty = only log them
    lead_sign_off: str  # name the n8n reply drafts are signed with
    allowed_origins: list[str]
    anthropic_api_key: str
    openai_api_key: str
    gemini_api_key: str
    preferred_provider: str
    anthropic_model: str
    openai_model: str
    gemini_model: str
    top_k: int
    max_messages_per_session: int

    @property
    def provider(self) -> str | None:
        keys = {"anthropic": self.anthropic_api_key, "openai": self.openai_api_key, "gemini": self.gemini_api_key}
        if keys.get(self.preferred_provider):
            return self.preferred_provider
        return next((name for name, key in keys.items() if key), None)

    @property
    def model(self) -> str:
        return {"openai": self.openai_model, "gemini": self.gemini_model}.get(self.provider, self.anthropic_model)


def get_settings() -> Settings:
    knowledge = os.getenv("KNOWLEDGE_FILE", "knowledge/northgate_dental_faq.md").strip()
    knowledge_path = Path(knowledge) if Path(knowledge).is_absolute() else ROOT / knowledge
    origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
    return Settings(
        business_name=os.getenv("BUSINESS_NAME", "Northgate Family Dental").strip(),
        knowledge_file=knowledge_path,
        front_desk_contact=os.getenv("FRONT_DESK_CONTACT", "call (555) 014-2290").strip(),
        lead_webhook_url=os.getenv("LEAD_WEBHOOK_URL", "").strip(),
        lead_sign_off=os.getenv("LEAD_SIGN_OFF", "Northgate Family Dental front desk").strip(),
        allowed_origins=origins or ["*"],
        anthropic_api_key=_clean_key(os.getenv("ANTHROPIC_API_KEY")),
        openai_api_key=_clean_key(os.getenv("OPENAI_API_KEY")),
        gemini_api_key=_clean_key(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        preferred_provider=os.getenv("LLM_PROVIDER", "anthropic").strip().lower(),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip(),
        top_k=max(1, int(os.getenv("TOP_K", "4") or 4)),
        max_messages_per_session=max(4, int(os.getenv("MAX_MESSAGES_PER_SESSION", "30") or 30)),
    )
