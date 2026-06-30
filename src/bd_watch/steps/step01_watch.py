"""Step 01 — Watch.

Scan CRM, client news and the sector press; emit raw Triggers.

Owner: Benjamin
Inputs:  none (pulls from configured sources via config)
Outputs: list[Trigger]

Sources currently wired:
- Google News RSS (nominations) — always active, requires feedparser + pyyaml
- MergerMarket (Playwright scraper) — set MERGERMARKET_URL in .env to activate
"""

from __future__ import annotations

from ..config import settings
from ..schemas import RawSignal, Salience, Trigger, TriggerType


# --------------------------------------------------------------------------- #
# RawSignal → Trigger conversion
# --------------------------------------------------------------------------- #

_APPOINTMENT_KEYWORDS = [
    "appoint", "appointed", "appointment", "named", "promoted",
    "joins as", "new ceo", "new cfo", "new cdo", "new coo", "new cso", "new chro",
    "nomination", "nommé", "prend la direction", "rejoint",
]
_FUNDING_KEYWORDS = [
    "funding", "raises", "series", "capital raise", "backed",
    "seed financing", "investment round", "levée de fonds",
]


def _infer_trigger_type(text: str) -> TriggerType:
    t = text.lower()
    if any(kw in t for kw in _APPOINTMENT_KEYWORDS):
        return TriggerType.NEW_APPOINTMENT
    if any(kw in t for kw in _FUNDING_KEYWORDS):
        return TriggerType.FUNDING_ROUND
    return TriggerType.PRESS_ARTICLE


def _raw_to_trigger(sig: RawSignal) -> Trigger:
    return Trigger(
        type=_infer_trigger_type(sig.trigger),
        summary=sig.trigger,
        source_url=sig.url,
        date=sig.date,
        company=sig.company,
        salience=Salience.HIGH,
    )


# --------------------------------------------------------------------------- #
# Source collectors
# --------------------------------------------------------------------------- #

def _from_mergermarket() -> list[RawSignal]:
    if not settings.mergermarket_url:
        return []
    from ..scrapers.mergermarket import scrape  # noqa: PLC0415
    return scrape(
        settings.mergermarket_url,
        settings.chrome_profile_dir,
        filter_relevant=False,
        sector_override="food",
    )


def _from_rss() -> list[RawSignal]:
    from ..scrapers.rss import fetch_nominations, load_config  # noqa: PLC0415
    config = load_config()
    return fetch_nominations(config, lookback_hours=24)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def detect_triggers() -> list[Trigger]:
    """Return candidate reasons to reach out from all configured sources."""
    signals: list[RawSignal] = []
    signals += _from_mergermarket()
    signals += _from_rss()

    if signals:
        return [_raw_to_trigger(s) for s in signals]

    # Fallback mock so the pipeline runs end to end without any source configured
    return [
        Trigger(
            type=TriggerType.NEW_APPOINTMENT,
            summary="Marie Dupont has just been appointed CDO of Acme Retail.",
            source_url="https://linkedin.com/posts/acme-retail-cdo",
            date="2026-06-28",
            company="Acme Retail",
            salience=Salience.HIGH,
        )
    ]
