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

    # Databricks serving endpoint (OpenAI-compatible). Preferred when fully set.
    databricks_host: str = os.environ.get("DATABRICKS_HOST", "")
    databricks_token: str = os.environ.get("DATABRICKS_TOKEN", "")
    databricks_endpoint: str = os.environ.get("DATABRICKS_ENDPOINT", "")

    crm_api_base: str = os.environ.get("CRM_API_BASE", "")
    crm_api_key: str = os.environ.get("CRM_API_KEY", "")
    # CRM deal export consumed by the activation feeder (.csv or .xlsx).
    crm_export_path: str = os.environ.get("CRM_EXPORT_PATH", str(_DEFAULT_CRM_EXPORT))
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

    @property
    def has_databricks(self) -> bool:
        return bool(self.databricks_host and self.databricks_token and self.databricks_endpoint)


settings = Settings()
