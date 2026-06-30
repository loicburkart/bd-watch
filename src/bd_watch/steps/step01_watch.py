"""Step 01 — Watch.

Scan CRM, client news and the sector press; emit raw Triggers.

Owner: TODO
Inputs:  none (pulls from CRM / news sources via config)
Outputs: list[Trigger]
"""

from __future__ import annotations

from ..schemas import Salience, Trigger, TriggerType


def detect_triggers() -> list[Trigger]:
    """Return candidate reasons to reach out.

    TODO: connect CRM + news/press sources. For now, returns a mock trigger so the
    pipeline runs end to end.
    """
    return [
        Trigger(
            type=TriggerType.NEW_APPOINTMENT,
            summary="Marie Dupont has just been appointed CDO of Acme Retail.",
            source_url="https://linkedin.com/posts/acme-retail-cdo",
            date="2026-06-28",
            company="Acme Retail",
            salience=Salience.HIGH,
        )
    ]
