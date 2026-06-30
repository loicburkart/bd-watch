"""Step 05 — Review.

Apply guardrails to a draft and decide: auto-send, human review, or discard.

Owner: TODO
Inputs:  OutreachDraft
Outputs: ReviewedOutreach
"""

from __future__ import annotations

from ..schemas import OutreachDraft, ReviewedOutreach


def review(draft: OutreachDraft) -> ReviewedOutreach:
    """Guardrail: never auto-send unless confidence is high and there are no flags.

    TODO: add content checks (length, tone, no fabrication) before sending.
    """
    if draft.confidence == "high" and not draft.flags:
        return ReviewedOutreach(draft=draft, decision="auto_send")
    return ReviewedOutreach(
        draft=draft,
        decision="human_review",
        notes=f"confidence={draft.confidence}, flags={draft.flags or 'none'}",
    )
