"""Central config. Reads from environment (.env) with sane defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv optional; env vars still work without it
    pass


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    model: str = os.environ.get("BD_WATCH_MODEL", "claude-sonnet-4-6")

    crm_api_base: str = os.environ.get("CRM_API_BASE", "")
    crm_api_key: str = os.environ.get("CRM_API_KEY", "")
    news_api_key: str = os.environ.get("NEWS_API_KEY", "")

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
