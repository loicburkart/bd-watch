"""RSS scraper — nomination trigger detection.

Public API
----------
load_config(path)                          Load targeting_config.yaml. Uses _DEFAULT_CONFIG if path=None.
fetch_nominations(config, lookback_hours)  Fetch + parse + filter → list[RawSignal]

Note on dates: Google News RSS reports the date the article was *re-surfaced* by
Google, not always the original publication date. Articles from months or years ago
can appear with a recent RSS date. We filter on this RSS date (best we can do without
fetching each article URL), so occasional stale articles may slip through.
"""

from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

try:
    import feedparser  # type: ignore
except ImportError:
    feedparser = None  # type: ignore

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

from ..schemas import RawSignal


# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = Path(__file__).parents[3] / "nominations_module" / "targeting_config.yaml"

_GOOGLE_NEWS_URL = "https://news.google.com/rss/search?q={query}&hl=fr&gl=FR&ceid=FR:fr"
_USER_AGENT = "Mozilla/5.0 (compatible; BD-Watch/1.0)"
_DELAY_SECONDS = 1.2  # between RSS requests, avoid rate-limiting

# Role acronym → canonical contact_function (targeting_matrix P1 values)
_ROLE_TO_FUNCTION: dict[str, str] = {
    "CDO": "it", "CTO": "it", "CIO": "it", "DSI": "it",
    "CMO": "marketing",
    "CFO": "finance", "DAF": "finance",
    "CHRO": "rh", "DRH": "rh",
    "COO": "operations",
    "CSCO": "supply_chain",
    "CSO": "strategie", "CEO": "strategie",
    "DG": "strategie", "PDG": "strategie", "DGA": "strategie",
    "MD": "strategie",
    "CCO": "sales",
}

_KEYWORD_TO_FUNCTION: dict[str, str] = {
    "directeur marketing": "marketing",
    "chief marketing": "marketing",
    "directeur supply chain": "supply_chain",
    "directeur logistique": "supply_chain",
    "directeur financier": "finance",
    "directeur commercial": "sales",
    "directeur des opérations": "operations",
    "directeur innovation": "rd",
    "directeur digital": "it",
    "directeur des systèmes": "it",
    "directeur data": "it",
    "chief data officer": "it",
    "directeur intelligence artificielle": "it",
    "directeur de l'intelligence artificielle": "it",
    "head of data": "it",
    "directeur de la transformation": "strategie",
    "directeur stratégie": "strategie",
    "directeur des ressources humaines": "rh",
    "directeur rh": "rh",
    "operating partner": "strategie",
    "managing director": "strategie",
    "vice-président": "strategie",
    "vice président": "strategie",
    "directeur général": "strategie",
    "président-directeur": "strategie",
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(path: Optional[Path] = None) -> dict:
    """Load targeting_config.yaml. Falls back to empty dict if missing."""
    target = path or _DEFAULT_CONFIG
    if yaml is None:
        print("[rss] WARNING: pyyaml not installed — using empty config", file=sys.stderr)
        return {}
    if not target.exists():
        print(f"[rss] WARNING: config not found at {target}", file=sys.stderr)
        return {}
    with open(target, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# RSS fetching
# ---------------------------------------------------------------------------

def _fetch_feed(url: str, source_name: str) -> list[dict]:
    if feedparser is None:
        print("[rss] ERROR: feedparser not installed. Run: pip install feedparser", file=sys.stderr)
        return []
    try:
        feed = feedparser.parse(url, agent=_USER_AGENT)
        if feed.bozo and not feed.entries:
            print(f"[rss] WARN {source_name}: {feed.bozo_exception}", file=sys.stderr)
            return []
        return [
            {
                "title": e.get("title", ""),
                "description": e.get("summary", ""),
                "url": e.get("link", ""),
                "published_parsed": e.get("published_parsed"),
                "source": source_name,
            }
            for e in feed.entries
        ]
    except Exception as exc:
        print(f"[rss] ERROR {source_name}: {exc}", file=sys.stderr)
        return []


def _fetch_all(config: dict) -> list[dict]:
    entries: list[dict] = []

    for query in config.get("rss_queries", []):
        url = _GOOGLE_NEWS_URL.format(query=quote_plus(query))
        new = _fetch_feed(url, f"Google News / {query}")
        print(f"  {query[:55]!r:60s} → {len(new)} entries", file=sys.stderr)
        entries.extend(new)
        time.sleep(_DELAY_SECONDS)

    for src in config.get("direct_rss_sources", []):
        if not src.get("enabled", True):
            continue
        new = _fetch_feed(src["url"], src["name"])
        print(f"  {src['name']:60s} → {len(new)} entries", file=sys.stderr)
        entries.extend(new)
        time.sleep(_DELAY_SECONDS)

    return entries


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(published_parsed) -> Optional[datetime]:
    if published_parsed is None:
        return None
    try:
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _is_recent(entry: dict, lookback_hours: int) -> bool:
    """Filter on RSS publication date.

    Caveat: Google News reports the *re-surfacing* date, not the original article
    date. Stale articles can pass this filter. Scoring / relevance filtering is
    the responsibility of Step 2 (targeting matrix), not this scraper.
    """
    dt = _parse_date(entry.get("published_parsed"))
    if dt is None:
        return True  # keep if date unknown
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    return dt >= cutoff


# ---------------------------------------------------------------------------
# Nomination detection
# ---------------------------------------------------------------------------

def _build_nomination_regex(config: dict) -> re.Pattern:
    patterns = (
        config.get("nomination_patterns_fr", []) +
        config.get("nomination_patterns_en", [])
    )
    if not patterns:
        patterns = ["nommé", "nomination", "appointed", "named", "rejoint"]
    escaped = [re.escape(p) for p in patterns]
    return re.compile("|".join(escaped), re.IGNORECASE)


def _build_role_regex(config: dict) -> re.Pattern:
    roles: list[str] = []
    for group in config.get("target_roles", {}).values():
        roles.extend(group)
    if not roles:
        roles = list(_ROLE_TO_FUNCTION.keys())
    # Longest match first; wrap pure-acronym tokens in word boundaries
    roles.sort(key=len, reverse=True)
    parts = []
    for role in roles:
        if re.match(r"^[A-Z]{2,6}$", role):
            parts.append(r"\b" + re.escape(role) + r"\b")
        else:
            parts.append(re.escape(role))
    return re.compile("|".join(parts), re.IGNORECASE)


def _extract_roles(text: str, role_regex: re.Pattern) -> list[str]:
    return list(dict.fromkeys(m.group(0).upper() for m in role_regex.finditer(text)))


# ---------------------------------------------------------------------------
# Dimension detection (sector / geography) — feeds RawSignal fields
# ---------------------------------------------------------------------------

def _detect_dimension(
    text_lower: str,
    p1_keywords: list[str],
    p2_keywords: list[str],
) -> str:
    """Return the first matching keyword (canonical label), or 'unknown'."""
    for kw in p1_keywords:
        if kw.lower() in text_lower:
            return kw.lower()
    for kw in p2_keywords:
        if kw.lower() in text_lower:
            return kw.lower()
    return "unknown"


# ---------------------------------------------------------------------------
# HTML stripping
# ---------------------------------------------------------------------------

_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG.sub("", text).strip()


# ---------------------------------------------------------------------------
# Company extraction (best-effort heuristic)
# ---------------------------------------------------------------------------

_DE_PATTERN = re.compile(
    r"\b(?:de|chez|du groupe|du|pour)\s+([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜ][A-Za-zÀ-ÿ&\-\.]+(?:\s+[A-Z][A-Za-zÀ-ÿ&\-\.]+){0,3})",
    re.UNICODE,
)
_APPOINTS_PATTERN = re.compile(
    r"^([A-ZÀÂÄ][A-Za-zÀ-ÿ&\-\.]+(?:\s+[A-Z][A-Za-zÀ-ÿ&\-\.]+){0,2})\s+(?:appoints|names|hires|promotes)",
)


def _extract_company(title: str) -> str:
    m = _DE_PATTERN.search(title)
    if m:
        return m.group(1).strip()
    m = _APPOINTS_PATTERN.match(title)
    if m:
        return m.group(1).strip()
    return "unknown"


def _lookup_company_sector(company: str, company_map: dict[str, str]) -> str:
    """Look up sector from company name using the config dict. Case-insensitive substring match."""
    if not company or company == "unknown" or not company_map:
        return "unknown"
    key = company.lower().strip()
    # Exact match first
    if key in company_map:
        return company_map[key]
    # Substring match: map key must appear inside extracted company name
    # e.g. "Ajinomoto France" → key contains "ajinomoto" ✓
    # Avoids "France" matching "mcdonald's france" (wrong direction)
    for name, sector in company_map.items():
        if len(name) >= 4 and name in key:
            return sector
    return "unknown"


def _infer_function(matched_roles: list[str], text_lower: str) -> str:
    for role in matched_roles:
        fn = _ROLE_TO_FUNCTION.get(role.upper())
        if fn:
            return fn
    for kw, fn in _KEYWORD_TO_FUNCTION.items():
        if kw in text_lower:
            return fn
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_nominations(config: dict, lookback_hours: int = 24) -> list[RawSignal]:
    """Fetch RSS feeds and return nomination RawSignals, sorted by date desc.

    Scoring is intentionally absent — that is Step 2's responsibility (targeting matrix).
    """
    nomination_regex = _build_nomination_regex(config)
    role_regex = _build_role_regex(config)

    p1_sectors = config.get("target_sectors", {}).get("P1", [])
    p2_sectors = config.get("target_sectors", {}).get("P2", [])
    p1_geos = config.get("target_geographies", {}).get("P1", [])
    p2_geos = config.get("target_geographies", {}).get("P2", [])
    company_map: dict[str, str] = config.get("company_sector_map", {})

    entries = _fetch_all(config)

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
        text = f"{title} {description}"
        text_lower = text.lower()

        is_nom = bool(nomination_regex.search(text))
        matched_roles = _extract_roles(text, role_regex)

        if not is_nom and not matched_roles:
            continue

        pub_dt = _parse_date(entry.get("published_parsed"))
        company = _extract_company(title)

        sector = _detect_dimension(text_lower, p1_sectors, p2_sectors)
        if sector == "unknown":
            sector = _lookup_company_sector(company, company_map)

        sig = RawSignal(
            company=company,
            sector=sector,
            geography=_detect_dimension(text_lower, p1_geos, p2_geos),
            contact_function=_infer_function(matched_roles, text_lower),
            trigger=title,
            source=entry.get("source", "unknown"),
            date=pub_dt.date().isoformat() if pub_dt else datetime.now(timezone.utc).date().isoformat(),
            url=url,
        )
        # Extra metadata for the CLI output and debugging (not part of RawSignal contract)
        sig._matched_roles = matched_roles  # type: ignore[attr-defined]
        sig._description = description[:300]  # type: ignore[attr-defined]
        sig._published_at = pub_dt.isoformat() if pub_dt else None  # type: ignore[attr-defined]

        results.append(sig)

    # Most recent first (by RSS date)
    results.sort(key=lambda s: s._published_at or "", reverse=True)  # type: ignore[attr-defined]
    return results
