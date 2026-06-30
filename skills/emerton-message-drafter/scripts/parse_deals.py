#!/usr/bin/env python3
"""Normalise a contacts Excel into clean JSON rows for the outreach drafter.

Self-contained (only needs openpyxl). Detects the input type, skips placeholder/legend/
empty rows, drops duplicate contacts, splits multi-person cells, and infers relationship
and seniority. Prints JSON to stdout.

Three input shapes are recognised (detected from the header):
  - known_clients : CRM deal export (re-engagement / activation)
  - new_prospects : cold leads tied to an external trigger
  - lost_deals    : lost-deal post-mortem (re-engagement after a loss)

For lost_deals, the "Post-Mortem Context" and "Suggested Next Step" columns are INTERNAL
strategy notes. They are emitted under *_internal keys and must never be quoted to the
recipient — they only inform the angle. See references/input_lost_deals.md.

Usage:
    python parse_deals.py <file.xlsx>
"""

from __future__ import annotations

import json
import re
import sys

PLACEHOLDERS = {"", "—", "–", "-", "n/a", "na", "tbd", ".", "none", "unknown"}
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
    if any(k in r for k in ("ceo", "cfo", "coo", "cto", "cio", "cdo", "cdaio", "caio",
                            "ccmo", "cmo", "chief", "president", "partner", "directeur général")):
        return "C-level"
    if "vp" in r or "vice president" in r:
        return "VP"
    if any(k in r for k in ("director", "directeur", "dir.", "head of", "head ", "dsi")):
        return "Director"
    return "Manager"


def _split_names(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"\s*(?:/|&|;|\bet\b|\band\b)\s*", raw)
    out = []
    for p in parts:
        # drop stray 'None'/placeholder tokens inside a name (e.g. "Sabrina CHEUNG None")
        toks = [t for t in p.split() if t.lower() not in PLACEHOLDERS]
        name = " ".join(toks).strip()
        if name:
            out.append(name)
    return out


def _full_name(row: dict) -> str:
    single = _clean(row.get("Contact Name"))
    if single:
        return single
    return " ".join(p for p in [_clean(row.get("First Name")), _clean(row.get("Last Name"))] if p).strip()


def _detect_type(header: list[str]) -> str:
    h = " | ".join(header).lower()
    if "post-mortem" in h or "suggested next step" in h or "deal info" in h:
        return "lost_deals"
    if "interaction history" in h or "days since" in h:
        return "known_clients"
    return "new_prospects"


def _parse_deal_info(s: str) -> tuple[str, str, str]:
    """Split 'scope\\n€amount • Lost dd/mm/yyyy' into (scope, amount_internal, lost_date)."""
    s = _clean(s)
    scope = amount = lost = ""
    if s:
        scope = s.splitlines()[0].strip()
        m = re.search(r"(€[\s\d.,·]+)", s)
        if m:
            amount = m.group(1).strip()
        m2 = re.search(r"lost\s+(\d{2}/\d{2}/\d{4})", s, re.I)
        if m2:
            lost = m2.group(1)
    return scope, amount, lost


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

    input_type = _detect_type(header)

    out, seen, skipped, dups, no_contact = [], set(), 0, 0, 0
    for rec in records:
        name = _full_name(rec)
        company = _clean(rec.get("Company"))
        deal_id = _clean(rec.get("#"))

        # Drop legend/footer rows (non-numeric # when a # column exists).
        if deal_id and _to_int(deal_id) is None:
            skipped += 1
            continue

        recipients = _split_names(name)

        # For known_clients / new_prospects a missing name is unusable -> skip.
        # For lost_deals we keep it (flagged no_contact) so triage stays visible.
        if not recipients and input_type != "lost_deals":
            skipped += 1
            continue

        # Dedup by contact for client/prospect lists; lost-deals keep every distinct
        # deal (one contact can have several separate lost deals), so the deal id is
        # part of the key there.
        if input_type == "lost_deals":
            key = (company.lower(), name.lower(), deal_id)
        else:
            key = (company.lower(), name.lower())
        if recipients and key in seen:
            dups += 1
            continue
        if recipients:
            seen.add(key)

        role = _clean(rec.get("Contact Role")) or _clean(rec.get("Title"))
        days = _to_int(_clean(rec.get("Days Since")))
        priority = _clean(rec.get("Priority"))

        item = {
            "company": company,
            "recipients": recipients,
            "role": role,
            "seniority": _seniority(role),
            "contact_email": _clean(rec.get("Contact Email")),
            "priority": priority,
            "scope": _clean(rec.get("Scope of Discussion")),
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

        elif input_type == "lost_deals":
            scope, amount, lost = _parse_deal_info(rec.get("Deal Info (scope | amount | lost)"))
            item["relationship"] = "dormant"
            item["deal_status"] = "lost"
            item["scope"] = scope
            item["deal_amount_internal"] = amount            # internal — do NOT cite to recipient
            item["lost_date"] = lost                          # internal — never mention the loss
            item["proj_type"] = _clean(rec.get("Proj Type"))
            item["reengagement_window"] = _clean(rec.get("Re-engagement Window"))
            item["timing"] = _clean(rec.get("Timing"))
            item["collab_potential"] = _clean(rec.get("Collab Potential"))
            item["post_mortem_context_internal"] = _clean(rec.get("Post-Mortem Context"))
            item["suggested_next_step_internal"] = _clean(rec.get("Suggested Next Step"))
            triage = []
            if not recipients:
                triage.append("no_contact")
                no_contact += 1
            if priority.upper().startswith("P4") or "archive" in item["suggested_next_step_internal"].lower():
                triage.append("archive_candidate")
            if "too early" in item["timing"].lower():
                triage.append("hold_until_window")
            if triage:
                item["triage"] = triage

        else:  # new_prospects
            item["relationship"] = "cold"

        out.append(item)

    counts = {"contacts": len(out), "skipped": skipped, "duplicates": dups}
    if input_type == "lost_deals":
        counts["no_contact"] = no_contact

    print(json.dumps(
        {"input_type": input_type, "counts": counts, "rows": out},
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
