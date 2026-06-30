#!/usr/bin/env python3
"""Generate a human-review file of activation drafts from a CRM export.

Runs the activation feeder -> drafter for every deal and writes a Markdown review
file. With ANTHROPIC_API_KEY set, drafts are produced live by the model; without it,
the drafter returns mock output (clearly flagged).

Usage:
    python scripts/generate_review.py
    python scripts/generate_review.py --export /path/to/Deal_Reminders.xlsx
    python scripts/generate_review.py --out reviews/my_review.md

Output is written under reviews/ (git-ignored).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# Allow running directly (python scripts/generate_review.py) without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bd_watch import feeders  # noqa: E402
from bd_watch.config import settings  # noqa: E402
from bd_watch.steps import step04_draft, step05_review  # noqa: E402


def _render(req, reviewed) -> str:
    d = reviewed.draft
    c = req.contact
    flags = ", ".join(d.flags) if d.flags else "none"
    return f"""\
## {c.company} — {c.full_name}

- **Role / seniority:** {c.title} ({c.seniority})
- **Relationship:** {c.relationship.value} | **Last contact:** {c.last_interaction or 'n/a'} | **Language:** {c.language}
- **Trigger context:** {req.trigger.summary}
- **Review decision:** `{reviewed.decision}` | **confidence:** {d.confidence} | **flags:** {flags}

**Email — subject:** {d.email.subject}

{d.email.body}

_CTA: {d.email.cta}_

**LinkedIn:**

{d.linkedin_message}

**Rationale (internal):** {d.rationale}

---
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate activation drafts for review")
    parser.add_argument("--export", default=settings.crm_export_path, help="CRM export path (.csv/.xlsx)")
    parser.add_argument("--out", default="reviews/activation_drafts_review.md", help="output markdown path")
    args = parser.parse_args()

    requests = feeders.activation_feeder(args.export)
    if not requests:
        print(f"No deals found in {args.export!r}. Nothing to generate.", file=sys.stderr)
        sys.exit(1)

    mode = "LIVE (Claude)" if settings.has_llm else "MOCK (no API key)"
    blocks = []
    for req in requests:
        reviewed = step05_review.review(step04_draft.draft(req))
        blocks.append(_render(req, reviewed))

    header = (
        f"# Activation drafts — for review\n\n"
        f"- Source: `{args.export}`\n"
        f"- Generated: {dt.datetime.now():%Y-%m-%d %H:%M} | Mode: {mode}\n"
        f"- Deals: {len(requests)}\n\n"
        f"> Drafts with confidence below `high` or any flags are routed to human review.\n\n---\n\n"
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(blocks), encoding="utf-8")
    print(f"Wrote {len(requests)} drafts to {out_path} [{mode}]")


if __name__ == "__main__":
    main()
