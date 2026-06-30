"""MergerMarket scraper — Playwright + dedicated Chrome profile.

The scraper reuses a persistent Chrome profile stored in CHROME_PROFILE_DIR
(default: ~/.bd-watch/chrome_profile). On first use run --setup to log in; the
session is then saved and reused on every subsequent --scrape call.

CLI usage:
    uv run python -m bd_watch.scrapers.mergermarket --setup      # one-time login
    uv run python -m bd_watch.scrapers.mergermarket --scrape     # fetch signals
    uv run python -m bd_watch.scrapers.mergermarket --dump-html  # save DOM for selector debug
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from ..schemas import RawSignal

_SOURCE = "MergerMarket"
_DEFAULT_PROFILE = str(Path.home() / ".bd-watch" / "chrome_profile")


# --------------------------------------------------------------------------- #
# Targeting matrix — loaded once at import time
# --------------------------------------------------------------------------- #

def _load_matrix() -> dict:
    root = Path(__file__).parent.parent.parent.parent  # …/bd-watch/
    path = root / "targeting_matrix.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


_MATRIX = _load_matrix()


def _build_lookup(dimension: str) -> dict[str, str]:
    """Return {synonym_lower: canonical} for all P1/P2/P3 entries in a dimension."""
    lookup: dict[str, str] = {}
    dim = _MATRIX.get("matrix", {}).get(dimension, {})
    for priority in ("P1", "P2", "P3"):
        for entry in dim.get(priority, []):
            canonical = entry["canonical"]
            for syn in entry.get("synonyms", []):
                lookup[syn.lower()] = canonical
    return lookup


_SECTOR_LOOKUP = _build_lookup("sectoriel")
_GEO_LOOKUP = _build_lookup("geographique")
_FUNC_LOOKUP = _build_lookup("fonctionnel")


# --------------------------------------------------------------------------- #
# Classification helpers
# --------------------------------------------------------------------------- #

def _classify(text: str, lookup: dict[str, str]) -> str:
    t = text.lower()
    for syn in sorted(lookup, key=len, reverse=True):  # longest match first
        pattern = r"\b" + re.escape(syn) + r"\b"
        if re.search(pattern, t):
            return lookup[syn]
    return "unknown"


def _extract_company(title: str) -> str:
    """First capitalised run of words before a known action verb (incl. 'to <verb>')."""
    m = re.match(
        r"([A-Z][A-Za-z0-9\s&\-'\.]+?)"
        r"(?=\s+(?:to\s+)?(?:"
        r"acqui\w*|mak\w+|seek\w*|rais\w*|appoint\w*|merg\w*|name\w*|join\w*|"
        r"call\w*|announc\w*|report\w*|complet\w*|clos\w*|sell\w*|bu[iy]\w*|"
        r"fil\w*|launch\w*|plan\w*|progress\w*|valu\w*|back\w*|fund\w*|tie\w*|"
        r"receiv\w*|divest\w*|notif\w*|scout\w*|list\w+|IPO\w*|float\w*"
        r"))",
        title,
    )
    if m:
        return m.group(1).strip()
    words = title.split()
    return " ".join(words[: min(3, len(words))])


def _parse_relative_date(text: str) -> str:
    """Convert 'X minutes ago' / 'an hour ago' / 'yesterday' to ISO yyyy-mm-dd."""
    now = datetime.now()
    t = text.lower().strip()
    if not t or "just now" in t or "second" in t or "minute" in t:
        return now.strftime("%Y-%m-%d")
    if "hour" in t:
        return now.strftime("%Y-%m-%d")
    if "yesterday" in t:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\s+day", t)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    for fmt in ("%d %b %Y", "%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return now.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Playwright launch helper
# --------------------------------------------------------------------------- #

def _playwright_import():
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
        return sync_playwright
    except ImportError:
        print(
            "playwright not installed.\n"
            "Run: pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)


def _launch_context(profile_dir: str, headless: bool):
    sync_playwright = _playwright_import()
    Path(profile_dir).mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        profile_dir,
        channel="chrome",
        headless=headless,
        viewport={"width": 1440, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
    )
    return p, ctx


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def setup(url: str, profile_dir: str = _DEFAULT_PROFILE) -> None:
    """Open a headed Chrome window so the user can log in to MergerMarket.

    The session is persisted to profile_dir for subsequent headless runs.
    """
    print(f"Opening Chrome → {url}")
    print("Log in to MergerMarket, navigate to your news feed,")
    print("then come back here and press Enter to save the session.")
    p, ctx = _launch_context(profile_dir, headless=False)
    page = ctx.new_page()
    page.goto(url, timeout=30_000)
    input("\nPress Enter once you are logged in… ")
    ctx.close()
    p.stop()
    print(f"Session saved to: {profile_dir}")


def dump_html(url: str, profile_dir: str = _DEFAULT_PROFILE) -> str:
    """Fetch the page and save the full HTML for CSS selector inspection."""
    out_dir = Path(__file__).parent.parent.parent.parent / "data" / "scratch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / "mm_debug.html")

    p, ctx = _launch_context(profile_dir, headless=False)
    page = ctx.new_page()
    page.goto(url, wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(3_000)
    html = page.content()
    ctx.close()
    p.stop()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML saved → {out_path}  ({len(html):,} chars)")
    return out_path


def scrape(
    url: str,
    profile_dir: str = _DEFAULT_PROFILE,
    max_articles: int = 50,
    headless: bool = False,
    filter_relevant: bool = True,
    sector_override: str = "",
) -> list[RawSignal]:
    """Scrape the MergerMarket news feed and return classified RawSignal objects.

    Args:
        url: Full URL of the MergerMarket page to scrape (set in MERGERMARKET_URL).
        profile_dir: Path to the Chrome profile with saved session.
        max_articles: Maximum number of articles to process.
        headless: Run without visible browser. Set False if Cloudflare blocks.
        filter_relevant: Drop signals where sector == "unknown".
    """
    p, ctx = _launch_context(profile_dir, headless=headless)
    signals: list[RawSignal] = []

    try:
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        # Wait for the React feed to render
        try:
            page.wait_for_selector('a[data-testid="feed-item"]', timeout=10_000)
        except Exception:
            pass

        containers = page.query_selector_all('a[data-testid="feed-item"]')

        if not containers:
            print(
                "Warning: no article containers found with current selectors.\n"
                "Run --dump-html to inspect the DOM and update selectors.",
                file=sys.stderr,
            )

        for el in containers[:max_articles]:
            try:
                title_el = el.query_selector('div[data-testid="headline"]')
                if not title_el:
                    continue
                title = title_el.inner_text().strip()
                if not title or len(title) < 10:
                    continue

                href = el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://mergermarket.ionanalytics.com" + href

                date_el = el.query_selector('span[data-testid="publish-date"]')
                date_text = date_el.inner_text().strip() if date_el else ""
                iso_date = _parse_relative_date(date_text) if date_text else datetime.now().strftime("%Y-%m-%d")

                sector = sector_override or _classify(title, _SECTOR_LOOKUP)
                geography = _classify(title, _GEO_LOOKUP)
                contact_function = _classify(title, _FUNC_LOOKUP)

                if filter_relevant and sector == "unknown":
                    continue

                signals.append(RawSignal(
                    company=_extract_company(title),
                    sector=sector,
                    geography=geography,
                    contact_function=contact_function,
                    trigger=title,
                    source=_SOURCE,
                    date=iso_date,
                    url=href,
                ))
            except Exception:
                continue
    finally:
        ctx.close()
        p.stop()

    return signals


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="MergerMarket scraper — Playwright + persistent Chrome profile"
    )
    parser.add_argument("--setup", action="store_true", help="First-time login (headed)")
    parser.add_argument("--scrape", action="store_true", help="Run scraper and print signals")
    parser.add_argument("--dump-html", action="store_true", help="Save page HTML for selector debug")
    parser.add_argument("--url", default="", help="Override MERGERMARKET_URL for this run")
    parser.add_argument("--profile", default="", help="Override CHROME_PROFILE_DIR for this run")
    parser.add_argument("--headless", action="store_true", help="Run without visible browser (may be blocked)")
    parser.add_argument("--filter", action="store_true", help="Drop signals where sector is unrecognised (useful for generic feeds)")
    parser.add_argument("--sector", default="", help="Force sector for all signals (e.g. 'food' when URL is already sector-filtered)")
    parser.add_argument("--geo", default="", help="Force geography for all signals (e.g. 'france')")
    args = parser.parse_args()

    # Resolve URL and profile from args or environment
    from ..config import settings  # noqa: PLC0415
    url = args.url or settings.mergermarket_url
    profile = args.profile or settings.chrome_profile_dir

    if not url:
        print(
            "Error: set MERGERMARKET_URL in .env or pass --url <url>",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.setup:
        setup(url, profile)
    elif args.dump_html:
        dump_html(url, profile)
    elif args.scrape:
        signals = scrape(
            url,
            profile_dir=profile,
            headless=args.headless,
            filter_relevant=args.filter,
            sector_override=args.sector,
        )
        print(f"\n{len(signals)} signal(s) found:\n")
        for s in signals:
            print(json.dumps(asdict(s), ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
