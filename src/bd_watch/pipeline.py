"""Pipeline orchestrator + CLI entrypoint.

Wires the steps together: watch -> qualify -> contact -> draft -> review.

Run:
    python -m bd_watch.pipeline
"""

from __future__ import annotations

from .assets import load_emerton_assets, load_style_reference
from .schemas import DraftRequest, ReviewedOutreach
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


def main() -> None:
    results = run()
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
