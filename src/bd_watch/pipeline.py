"""Pipeline orchestrator + CLI entrypoint.

Architecture: two feeders, one drafter.

    cold_feeder ─┐
                 ├─> DraftRequest ─> step04_draft.draft ─> step05_review.review
    activation ──┘

Run:
    python -m bd_watch.pipeline
"""

from __future__ import annotations

from .feeders import activation_feeder, cold_feeder
from .schemas import DraftRequest, ReviewedOutreach
from .steps import step04_draft, step05_review


def gather_requests() -> list[DraftRequest]:
    """Collect draft requests from every feeder."""
    return cold_feeder() + activation_feeder()


def run() -> list[ReviewedOutreach]:
    """Run the full pipeline: feeders -> drafter -> review."""
    return [
        step05_review.review(step04_draft.draft(req)) for req in gather_requests()
    ]


def main() -> None:
    results = run()
    print(f"bd-watch pipeline — {len(results)} outreach item(s)\n")
    for i, r in enumerate(results, 1):
        d = r.draft
        print(f"=== Item {i} | decision: {r.decision} ===")
        print(f"Subject : {d.email.subject}")
        print(f"Email   :\n{d.email.body}\n")
        for li in d.linkedin:
            print(f"LinkedIn → {li.recipient}: {li.message}")
        print(f"Review  : confidence={d.confidence}, flags={d.flags or 'none'}")
        if r.notes:
            print(f"Notes   : {r.notes}")
        print()


if __name__ == "__main__":
    main()
