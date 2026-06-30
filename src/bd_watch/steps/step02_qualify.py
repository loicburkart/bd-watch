"""Step 02 — Qualify.

Score and filter triggers; keep the ones worth acting on.

Owner: TODO
Inputs:  list[Trigger]
Outputs: list[QualifiedTrigger]
"""

from __future__ import annotations

from ..schemas import QualifiedTrigger, Salience, Trigger

_SALIENCE_SCORE = {Salience.HIGH: 0.9, Salience.MEDIUM: 0.6, Salience.LOW: 0.3}


def qualify(triggers: list[Trigger], threshold: float = 0.5) -> list[QualifiedTrigger]:
    """Keep triggers above ``threshold``.

    TODO: replace the naive salience mapping with real scoring (recency, account
    value, fit with our offers, etc.).
    """
    qualified: list[QualifiedTrigger] = []
    for t in triggers:
        score = _SALIENCE_SCORE.get(t.salience, 0.5)
        if score >= threshold:
            qualified.append(
                QualifiedTrigger(
                    trigger=t,
                    score=score,
                    reason=f"{t.salience.value} salience {t.type.value}",
                )
            )
    return qualified
