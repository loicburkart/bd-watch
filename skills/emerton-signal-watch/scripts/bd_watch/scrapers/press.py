"""Press & M&A scraper — strategy / transformation / deal trigger detection.

Multi-provider extension of Step 01, alongside `rss.py` (nominations).

Public API
----------
fetch_press_signals(config, lookback_hours)  Fetch + filter all providers → list[RawSignal]

Providers (see `_PRESS_PROVIDERS`)
- google_news : Google News RSS, one feed per `press_google_queries` entry.
- actusnews   : direct RSS feeds listed in `press_direct_sources` (regulated FR press releases).

No sector filtering happens here — qualification is Step 2's job (targeting matrix).
All low-level helpers are reused from `rss.py`; this module only adds press-specific
keyword filtering and provider wiring.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from ..schemas import RawSignal
from .rss import (
    _DELAY_SECONDS,
    _GOOGLE_NEWS_URL,
    _detect_dimension,
    _extract_company,
    _fetch_feed,
    _is_recent,
    _lookup_company_sector,
    _parse_date,
    _strip_html,
    load_config,  # re-exported for convenience / symmetry with rss.py
)

__all__ = ["fetch_press_signals", "load_config"]


# ---------------------------------------------------------------------------
# Press / M&A keywords (defaults; overridable via config)
# ---------------------------------------------------------------------------

_MA_KEYWORDS_FR = [
    "acquisition", "fusion", "rachat", "cession", "lbo", "levée de fonds",
    "prise de participation", "opa", "cède", "acquiert", "reprend", "private equity",
]
_MA_KEYWORDS_EN = [
    "acquisition", "merger", "buyout", "takeover", "stake", "raises", "acquires",
]
_DATA_KEYWORDS_FR = [
    "stratégie data", "stratégie ia", "stratégie intelligence artificielle",
    "intelligence artificielle", "gouvernance des données", "data-driven",
    "transformation data", "chief data officer", "data strategy",
]
_STRATEGY_KEYWORDS_FR = [
    "plan stratégique", "transformation", "restructuration",
    "développement", "réorganisation", "feuille de route",
]

# signal_type → canonical contact_function (targeting_matrix P1 values)
_TYPE_TO_FUNCTION = {"ma": "finance", "data": "it", "strategy": "strategie"}

_ACTUSNEWS_DEFAULT = [{"name": "Actusnews Wire", "url": "https://www.actusnews.com/fr/rss", "enabled": True}]


def _is_press_signal(text_lower: str, config: dict) -> tuple[bool, str]:
    """Return (passes, signal_type) where signal_type is 'ma' | 'data' | 'strategy' | ''.

    Priority: M&A → data → strategy. Data is checked before strategy because
    "stratégie data" / "stratégie IA" would otherwise be swallowed by the generic
    "stratégie" strategy keyword.
    """
    ma_kw = config.get("ma_keywords_fr", _MA_KEYWORDS_FR) + config.get("ma_keywords_en", _MA_KEYWORDS_EN)
    if any(kw.lower() in text_lower for kw in ma_kw):
        return True, "ma"
    data_kw = config.get("data_keywords_fr", _DATA_KEYWORDS_FR)
    if any(kw.lower() in text_lower for kw in data_kw):
        return True, "data"
    strat_kw = config.get("strategy_keywords_fr", _STRATEGY_KEYWORDS_FR)
    if any(kw.lower() in text_lower for kw in strat_kw):
        return True, "strategy"
    return False, ""


# ---------------------------------------------------------------------------
# Providers — each returns list[dict] in the shape produced by _fetch_feed
# ---------------------------------------------------------------------------

def _provider_google_news(config: dict) -> list[dict]:
    entries: list[dict] = []
    for query in config.get("press_google_queries", []):
        url = _GOOGLE_NEWS_URL.format(query=quote_plus(query))
        new = _fetch_feed(url, f"Google News / {query}")
        print(f"  {query[:55]!r:60s} → {len(new)} entries", file=sys.stderr)
        entries.extend(new)
        time.sleep(_DELAY_SECONDS)
    return entries


def _provider_actusnews(config: dict) -> list[dict]:
    entries: list[dict] = []
    for src in config.get("press_direct_sources", _ACTUSNEWS_DEFAULT):
        if not src.get("enabled", True):
            continue
        new = _fetch_feed(src["url"], src["name"])
        print(f"  {src['name']:60s} → {len(new)} entries", file=sys.stderr)
        entries.extend(new)
        time.sleep(_DELAY_SECONDS)
    return entries


# (name, provider_fn) — add a source future = add a provider here
_PRESS_PROVIDERS = [
    ("google_news", _provider_google_news),
    ("actusnews", _provider_actusnews),
]


# ---------------------------------------------------------------------------
# Company extraction — actusnews titles are "NOM SOCIÉTÉ : sujet"
# ---------------------------------------------------------------------------

def _extract_company_press(title: str, source: str) -> str:
    """Actusnews titles lead with the issuer name before ' : '. Fall back to the
    generic heuristic for Google News titles."""
    if "actusnews" in source.lower() and " : " in title:
        candidate = title.split(" : ", 1)[0].strip()
        if candidate:
            return candidate
    return _extract_company(title)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_press_signals(config: dict, lookback_hours: int = 1440) -> list[RawSignal]:
    """Fetch press / M&A signals from all providers, sorted by date desc.

    Scoring is intentionally absent — that is Step 2's responsibility (targeting matrix).
    """
    p1_sectors = config.get("target_sectors", {}).get("P1", [])
    p2_sectors = config.get("target_sectors", {}).get("P2", [])
    p1_geos = config.get("target_geographies", {}).get("P1", [])
    p2_geos = config.get("target_geographies", {}).get("P2", [])
    company_map: dict[str, str] = config.get("company_sector_map", {})

    entries: list[dict] = []
    for name, provider in _PRESS_PROVIDERS:
        print(f"[press] provider: {name}", file=sys.stderr)
        entries.extend(provider(config))

    seen_urls: set[str] = set()
    results: list[RawSignal] = []

    for entry in entries:
        url = entry.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        if not _is_recent(entry, lookback_hours):
            continue

        title = entry.get("title", "")
        description = _strip_html(entry.get("description", ""))
        text_lower = f"{title} {description}".lower()

        passes, signal_type = _is_press_signal(text_lower, config)
        if not passes:
            continue

        source = entry.get("source", "unknown")
        company = _extract_company_press(title, source)

        sector = _detect_dimension(text_lower, p1_sectors, p2_sectors)
        if sector == "unknown":
            sector = _lookup_company_sector(company, company_map)

        pub_dt = _parse_date(entry.get("published_parsed"))

        sig = RawSignal(
            company=company,
            sector=sector,
            geography=_detect_dimension(text_lower, p1_geos, p2_geos),
            contact_function=_TYPE_TO_FUNCTION[signal_type],
            trigger=title,
            source=source,
            date=pub_dt.date().isoformat() if pub_dt else datetime.now(timezone.utc).date().isoformat(),
            url=url,
        )
        # Extra metadata for the CLI output and debugging (not part of RawSignal contract)
        sig._signal_type = signal_type  # type: ignore[attr-defined]
        sig._description = description[:300]  # type: ignore[attr-defined]
        sig._published_at = pub_dt.isoformat() if pub_dt else None  # type: ignore[attr-defined]

        results.append(sig)

    results.sort(key=lambda s: s._published_at or "", reverse=True)  # type: ignore[attr-defined]
    return results
