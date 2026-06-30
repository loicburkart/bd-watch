"""Central config. Reads from environment (.env) with sane defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv optional; env vars still work without it
    pass

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CRM_EXPORT = _REPO_ROOT / "data" / "samples" / "crm_deals_sample.csv"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    model: str = os.environ.get("BD_WATCH_MODEL", "claude-sonnet-4-6")

    crm_api_base: str = os.environ.get("CRM_API_BASE", "")
    crm_api_key: str = os.environ.get("CRM_API_KEY", "")
    # CRM deal export consumed by the activation feeder (.csv or .xlsx).
    crm_export_path: str = os.environ.get("CRM_EXPORT_PATH", str(_DEFAULT_CRM_EXPORT))
    news_api_key: str = os.environ.get("NEWS_API_KEY", "")

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
