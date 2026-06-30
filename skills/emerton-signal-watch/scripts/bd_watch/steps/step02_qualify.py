"""Step 02 — Qualify.

Score triggers against the 3D targeting matrix (targeting_matrix.json).
Rule: global score = min(sector_score, geo_score, function_score).
A trigger must be P1 on all 3 axes to reach the default threshold.

Scoring per dimension:
  P1 → 1.0  |  P2 → 0.6  |  P3 → 0.3  |  unknown → 0.0
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..schemas import QualifiedTrigger, Trigger

_REPO_ROOT = Path(__file__).parents[3]
_MATRIX_FILES = {
    "default": _REPO_ROOT / "targeting_matrix.json",
    "broad": _REPO_ROOT / "targeting_matrix_broad.json",
}

_LEVEL_SCORE = {"P1": 1.0, "P2": 0.6, "P3": 0.3}


def _load_matrix() -> dict:
    key = os.environ.get("TARGETING_MATRIX", "default").lower()
    path = _MATRIX_FILES.get(key, _MATRIX_FILES["default"])
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("matrix", {})


def _dim_score(value: str, dim: dict) -> float:
    """Return the priority score for *value* within a matrix dimension."""
    v = value.lower().strip()
    for level, score in _LEVEL_SCORE.items():
        for entry in dim.get(level, []):
            if v == entry["canonical"]:
                return score
            if v in [s.lower() for s in entry.get("synonyms", [])]:
                return score
    return 0.0


def qualify(triggers: list[Trigger], threshold: float = 0.5) -> list[QualifiedTrigger]:
    """Keep triggers whose 3D matrix score >= threshold."""
    matrix = _load_matrix()
    dim_sector = matrix.get("sectoriel", {})
    dim_geo = matrix.get("geographique", {})
    dim_func = matrix.get("fonctionnel", {})

    qualified: list[QualifiedTrigger] = []
    for t in triggers:
        s_sector = _dim_score(t.sector, dim_sector)
        s_geo = _dim_score(t.geography, dim_geo)
        s_func = _dim_score(t.contact_function, dim_func)
        # Sector P1 (score=1.0) → bypass geo/func filter: core sector is always relevant
        # Otherwise → worst-case min across all 3 dimensions
        score = 1.0 if s_sector == 1.0 else min(s_sector, s_geo, s_func)
        if score >= threshold:
            reason = (
                f"sector={t.sector}({s_sector:.1f}) "
                f"geo={t.geography}({s_geo:.1f}) "
                f"func={t.contact_function}({s_func:.1f})"
            )
            qualified.append(QualifiedTrigger(trigger=t, score=score, reason=reason))
    return qualified
