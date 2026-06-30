#!/usr/bin/env python3
"""Normalise a contacts Excel into clean JSON rows for the outreach drafter.

Self-contained (only needs openpyxl). Detects the input type (known clients vs new
prospects), skips placeholder/legend/empty rows, drops duplicate contacts, and infers
relationship + seniority. Prints JSON to stdout.

Usage:
    python parse_deals.py <file.xlsx>
"""

from __future__ import annotations

import json
import re
import sys

PLACEHOLDERS = {"", "—", "–", "-", "n/a", "na", "tbd", "."}
DORMANT_AFTER_DAYS = 14


def _clean(v) -> str:
    s = ("" if v is None else str(v)).strip()
    return "" if s.lower() in PLACEHOLDERS else s


def _to_int(v: str):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _seniority(role: str) -> str:
    r = role.lower()
    if any(k in r for k in ("ceo", "cfo", "coo", "cto", "cio", "cdo", "cdaio", "caio", "chief", "president", "partner")):
        return "C-level"
    if "vp" in r or "vice president" in r:
        return "VP"
    if any(k in r for k in ("director", "directeur", "dir.", "head of", "head ")):
        return "Director"
    return "Manager"


def _split_names(raw: str) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in re.split(r"\s*(?:/|&|;|\bet\b|\band\b)\s*", raw) if p.strip()]


def _full_name(row: dict) -> str:
    single = _clean(row.get("Contact Name"))
    if single:
        return single
    return " ".join(p for p in [_clean(row.get("First Name")), _clean(row.get("Last Name"))] if p).strip()


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python parse_deals.py <file.xlsx>", file=sys.stderr)
        sys.exit(2)

    import openpyxl  # lazy import

    wb = openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        print(json.dumps({"input_type": "unknown", "rows": []}))
        return
    header = [(_clean(c) or f"col{i}") for i, c in enumerate(rows[0])]
    records = [dict(zip(header, r)) for r in rows[1:]]

    is_known = any("Interaction History" in h or "Days Since" in h for h in header)
    input_type = "known_clients" if is_known else "new_prospects"

    out, seen, skipped, dups = [], set(), 0, 0
    for rec in records:
        name = _full_name(rec)
        company = _clean(rec.get("Company"))
        deal_id = _clean(rec.get("#"))
        if not name or (deal_id and _to_int(deal_id) is None):
            skipped += 1
            continue
        key = (company.lower(), name.lower())
        if key in seen:
            dups += 1
            continue
        seen.add(key)

        days = _to_int(_clean(rec.get("Days Since")))
        role = _clean(rec.get("Contact Role")) or _clean(rec.get("Title"))
        item = {
            "company": company,
            "recipients": _split_names(name),
            "role": role,
            "seniority": _seniority(role),
            "scope": _clean(rec.get("Scope of Discussion")),
            "priority": _clean(rec.get("Priority")),
            "next_step": _clean(rec.get("Next Step")),
            "last_action": _clean(rec.get("Last Action")),
            "last_action_date": _clean(rec.get("Last Action Date"))[:10],
            "days_since": days,
            "interaction_history": _clean(rec.get("Interaction History")),
            "recent_summary": _clean(rec.get("Summary of Recent Discussions")),
            "notes": _clean(rec.get("Additional Info")),
            "trigger_type": _clean(rec.get("Trigger Type")),
            "trigger_summary": _clean(rec.get("Trigger Summary")),
        }
        if input_type == "known_clients":
            item["relationship"] = (
                "existing_client" if days is not None and days < DORMANT_AFTER_DAYS else "dormant"
            )
            if days is not None and days > 180:
                item["flag"] = "very_stale"
        else:
            item["relationship"] = "cold"
        out.append(item)

    print(json.dumps(
        {"input_type": input_type, "counts": {"contacts": len(out), "skipped": skipped, "duplicates": dups}, "rows": out},
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
