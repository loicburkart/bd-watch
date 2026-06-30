"""Standalone runner — BD-Watch signals (steps 01+02 only).

Scrapes nomination/press signals (Google News RSS) and scores them against the
3D targeting matrix, then prints the qualified signals. No LLM, no tokens; the
only network call is the RSS fetch. Self-contained: run from this directory.

    python run_signals.py                 # JSON (default)
    python run_signals.py --format text   # human-readable
"""

from __future__ import annotations

import argparse
import json

from bd_watch.steps import step01_watch, step02_qualify


def _to_dict(qt) -> dict:
    t = qt.trigger
    return {
        "company": t.company,
        "summary": t.summary,
        "type": t.type.value,
        "sector": t.sector,
        "geography": t.geography,
        "contact_function": t.contact_function,
        "salience": t.salience.value,
        "date": t.date,
        "source_url": t.source_url,
        "score": qt.score,
        "reason": qt.reason,
    }


def main() -> None:
    p = argparse.ArgumentParser(prog="bd-watch-signals")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.add_argument("--threshold", type=float, default=0.5,
                   help="Min 3D-matrix score to keep (0.5 default; 0.3 includes P3).")
    args = p.parse_args()

    triggers = step01_watch.detect_triggers()
    qualified = step02_qualify.qualify(triggers, threshold=args.threshold)

    if args.format == "json":
        print(json.dumps(
            {"count": len(qualified), "signals": [_to_dict(qt) for qt in qualified]},
            ensure_ascii=False, indent=2,
        ))
        return

    label = {1.0: "P1 ★", 0.6: "P2  ", 0.3: "P3  "}
    print(f"\n{'─' * 70}")
    print(f"  BD Watch — {len(qualified)} signal(s) qualifié(s) par la matrice 3D")
    print(f"{'─' * 70}\n")
    for qt in qualified:
        t = qt.trigger
        print(f"  [{label.get(qt.score, f'{qt.score:.1f}')}]  {t.company or 'unknown'}")
        print(f"           {t.summary[:80]}")
        print(f"           secteur={t.sector}  geo={t.geography}  fonction={t.contact_function}")
        if t.source_url:
            print(f"           {t.source_url}")
        print()


if __name__ == "__main__":
    main()
