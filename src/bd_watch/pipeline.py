"""Pipeline orchestrator + CLI entrypoint.

Wires the steps together: watch -> qualify -> contact -> draft -> review.

Run:
    python -m bd_watch.pipeline                # full pipeline
    python -m bd_watch.pipeline --qualify-only # steps 01+02 only (signals view)
"""

from __future__ import annotations

import argparse
import sys

from .assets import load_emerton_assets, load_style_reference
from .schemas import DraftRequest, QualifiedTrigger, ReviewedOutreach
from .steps import (
    step01_watch,
    step02_qualify,
    step03_contact,
    step04_draft,
    step05_review,
)


def run() -> list[ReviewedOutreach]:
    """Run the full pipeline on whatever step 01 surfaces."""
    assets = load_emerton_assets()
    style = load_style_reference()

    results: list[ReviewedOutreach] = []
    for qt in step02_qualify.qualify(step01_watch.detect_triggers()):
        contact = step03_contact.identify_contact(qt)
        request = DraftRequest(
            trigger=qt.trigger, contact=contact, assets=assets, style=style
        )
        draft = step04_draft.draft(request)
        results.append(step05_review.review(draft))
    return results


def _print_qualified(qualified: list[QualifiedTrigger]) -> None:
    score_label = {1.0: "P1 ★", 0.6: "P2  ", 0.3: "P3  "}
    print(f"\n{'─'*70}")
    print(f"  BD Watch — {len(qualified)} signal(s) qualifié(s) par la matrice 3D")
    print(f"{'─'*70}\n")
    for qt in qualified:
        t = qt.trigger
        label = score_label.get(qt.score, f"{qt.score:.1f}")
        print(f"  [{label}]  {t.company or 'unknown'}")
        print(f"           {t.summary[:80]}")
        print(f"           secteur={t.sector}  geo={t.geography}  fonction={t.contact_function}")
        if t.source_url:
            print(f"           {t.source_url}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(prog="bd-watch")
    parser.add_argument(
        "--qualify-only",
        action="store_true",
        help="Run steps 01+02 only: fetch signals and show what passes the matrix.",
    )
    args = parser.parse_args()

    triggers = step01_watch.detect_triggers()
    qualified = step02_qualify.qualify(triggers)

    if args.qualify_only:
        _print_qualified(qualified)
        return

    assets = load_emerton_assets()
    style = load_style_reference()
    results: list[ReviewedOutreach] = []
    for qt in qualified:
        contact = step03_contact.identify_contact(qt)
        request = DraftRequest(trigger=qt.trigger, contact=contact, assets=assets, style=style)
        draft = step04_draft.draft(request)
        results.append(step05_review.review(draft))

    print(f"bd-watch pipeline — {len(results)} outreach item(s)\n")
    for i, r in enumerate(results, 1):
        d = r.draft
        print(f"=== Item {i} | decision: {r.decision} ===")
        print(f"To      : {d.email.subject}")
        print(f"Email   :\n{d.email.body}\n")
        print(f"LinkedIn: {d.linkedin_message}")
        print(f"Review  : confidence={d.confidence}, flags={d.flags or 'none'}")
        if r.notes:
            print(f"Notes   : {r.notes}")
        print()


if __name__ == "__main__":
    main()
