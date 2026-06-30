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


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    model: str = os.environ.get("BD_WATCH_MODEL", "claude-sonnet-4-6")

    crm_api_base: str = os.environ.get("CRM_API_BASE", "")
    crm_api_key: str = os.environ.get("CRM_API_KEY", "")
    news_api_key: str = os.environ.get("NEWS_API_KEY", "")

    # Step 01 — sources
    rss_lookback_hours: int = int(os.environ.get("RSS_LOOKBACK_HOURS", "1440"))  # 60 days

    # MergerMarket — disabled by default, set MERGERMARKET_ENABLED=true to activate
    mergermarket_enabled: bool = os.environ.get("MERGERMARKET_ENABLED", "false").lower() == "true"
    mergermarket_url: str = os.environ.get("MERGERMARKET_URL", "")
    chrome_profile_dir: str = os.environ.get("CHROME_PROFILE_DIR", "") or str(
        Path.home() / ".bd-watch" / "chrome_profile"
    )

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)


settings = Settings()
