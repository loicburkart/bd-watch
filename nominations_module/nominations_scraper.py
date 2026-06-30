#!/usr/bin/env python3
"""
nominations_scraper.py — Standalone CLI for BD Watch Step 1 (nominations).

Fetches nomination triggers from Google News RSS + direct sources,
writes output/nominations_today.json in RawSignal format.

Scoring is NOT done here — that is Step 2's job (targeting_matrix.json).

Usage:
    python nominations_scraper.py
    python nominations_scraper.py --dry-run --lookback 72
    python nominations_scraper.py --output /tmp/test.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow importing the src package without installing it
_REPO_ROOT = Path(__file__).parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from bd_watch.scrapers.rss import fetch_nominations, load_config  # noqa: E402

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "targeting_config.yaml"
OUTPUT_DIR = SCRIPT_DIR / "output"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BD Watch — Nominations scraper")
    p.add_argument("--lookback", type=int, default=None, help="Lookback window in hours (overrides config)")
    p.add_argument("--dry-run", action="store_true", help="Fetch + process but do not write output file")
    p.add_argument("--output", type=Path, default=None, help="Output JSON path (default: output/nominations_today.json)")
    p.add_argument("--config", type=Path, default=CONFIG_FILE, help="Config YAML path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[BD Watch] Nominations scraper — {run_at}", file=sys.stderr)

    config = load_config(args.config)
    lookback = args.lookback or config.get("lookback_hours", 1440)
    print(f"[BD Watch] Config: {args.config}  Lookback: {lookback}h", file=sys.stderr)

    print("[BD Watch] Fetching feeds...", file=sys.stderr)
    signals = fetch_nominations(config, lookback_hours=lookback)

    nominations = [
        {
            # RawSignal fields — these feed directly into Step 2 (targeting matrix)
            "company": s.company,
            "sector": s.sector,
            "geography": s.geography,
            "contact_function": s.contact_function,
            "trigger": s.trigger,
            "source": s.source,
            "date": s.date,
            "url": s.url,
            # Extra context for review / debugging (not part of Step 2 contract)
            "description": s._description,  # type: ignore[attr-defined]
            "published_at": s._published_at,  # type: ignore[attr-defined]
            "matched_roles": s._matched_roles,  # type: ignore[attr-defined]
        }
        for s in signals
    ]

    output = {
        "run_at": run_at,
        "lookback_hours": lookback,
        "total_found": len(nominations),
        "nominations": nominations,
    }

    if args.dry_run:
        print("\n[DRY RUN] Output preview (first 3):", file=sys.stderr)
        preview = {**output, "nominations": nominations[:3]}
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return

    output_path = args.output or (OUTPUT_DIR / "nominations_today.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[BD Watch] Written: {output_path}  ({len(nominations)} nominations)", file=sys.stderr)

    if nominations:
        print("\nTop results (most recent first):", file=sys.stderr)
        for nom in nominations[:5]:
            print(f"  [{nom['date']}] {nom['trigger'][:80]}", file=sys.stderr)
            print(f"         roles={nom['matched_roles']}  company={nom['company']}", file=sys.stderr)
    else:
        print("[BD Watch] No nominations found in the lookback window.", file=sys.stderr)


if __name__ == "__main__":
    main()
