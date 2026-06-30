"""Feeders — the two front doors into the drafter.

Both use cases converge on the same output, a list of ``DraftRequest`` objects, so a
single drafter (step 04) handles both. Each feeder is responsible for producing a
well-formed request; the drafter never needs to know where it came from.

    cold_feeder()        external triggers (news / press / appointments) -> cold outreach
    activation_feeder()  the CRM export (quiet deals) -> re-engagement of known contacts

Add a feeder by writing a function that returns ``list[DraftRequest]`` and wiring it
into ``pipeline.run``.
"""

from __future__ import annotations

import csv
import datetime as _dt
import logging
import os
import re
from typing import Iterable

from .assets import load_emerton_assets, load_style_reference
from .config import settings
from .schemas import (
    ContactProfile,
    DraftRequest,
    EmertonAssets,
    Relationship,
    Salience,
    StyleReference,
    Trigger,
    TriggerType,
)
from .steps import step01_watch, step02_qualify, step03_contact

logger = logging.getLogger(__name__)

# A deal quiet for at least this many days is treated as dormant rather than active.
DORMANT_AFTER_DAYS = 14
# Default writing language for CRM-sourced contacts. The CRM accounts are French, so
# the activation use case defaults to French (flip to "en" if preferred).
DEFAULT_LANGUAGE = "fr"
# Keep the grounding context bounded so prompts stay lean.
MAX_SUMMARY_CHARS = 800


# --------------------------------------------------------------------------- #
# Feeder 1 — cold contact (external triggers)
# --------------------------------------------------------------------------- #

def cold_feeder() -> list[DraftRequest]:
    """Turn externally detected triggers into draft requests (cold outreach)."""
    assets = load_emerton_assets()
    style = load_style_reference()
    requests: list[DraftRequest] = []
    for qt in step02_qualify.qualify(step01_watch.detect_triggers()):
        contact = step03_contact.identify_contact(qt)
        requests.append(
            DraftRequest(trigger=qt.trigger, contact=contact, assets=assets, style=style)
        )
    return requests


# --------------------------------------------------------------------------- #
# Feeder 2 — database activation (CRM export)
# --------------------------------------------------------------------------- #

def activation_feeder(path: str | None = None) -> list[DraftRequest]:
    """Turn rows of a CRM deal export into re-engagement draft requests.

    Supports ``.csv`` and ``.xlsx``. Returns an empty list (with a warning) if the
    export is missing, so the pipeline degrades gracefully.
    """
    path = path or settings.crm_export_path
    if not path or not os.path.exists(path):
        logger.warning("CRM export not found at %r; activation feeder produced nothing.", path)
        return []

    assets = load_emerton_assets()
    style = load_style_reference()
    requests: list[DraftRequest] = []
    seen: set[tuple[str, str]] = set()
    for row in _read_rows(path):
        for req in _row_to_request(row, assets, style):
            key = (req.contact.company.lower(), req.contact.full_name.lower())
            if key in seen:
                logger.info("Skipping duplicate CRM contact: %s @ %s", req.contact.full_name, req.contact.company)
                continue
            seen.add(key)
            requests.append(req)
    return requests


# --------------------------------------------------------------------------- #
# CRM row -> DraftRequest
# --------------------------------------------------------------------------- #

def _row_to_request(
    row: dict[str, str], assets: EmertonAssets, style: StyleReference
) -> list[DraftRequest]:
    company = _get(row, "Company")
    names_raw = _full_name(row)
    deal_id = _get(row, "#")

    # Skip rows with no identifiable contact or company (placeholder/junk rows), and
    # non-numeric "#" rows (legends/footers). A message needs a real recipient.
    if not company and not names_raw:
        return []
    if not names_raw:
        return []
    if not deal_id or _to_int(deal_id) is None:
        return []

    role = _get(row, "Contact Role")
    scope = _get(row, "Scope of Discussion")
    priority = _get(row, "Priority")
    next_step = _get(row, "Next Step")
    last_action = _get(row, "Last Action")
    last_date = _norm_date(_get(row, "Last Action Date"))
    days = _to_int(_get(row, "Days Since"))
    history = _get(row, "Interaction History")
    recent = _get(row, "Summary of Recent Discussions")
    extra = _get(row, "Additional Info")

    # Build a grounded trigger summary from the real CRM context. This is Emerton's
    # INTERNAL record (our perspective): the drafter must attribute internal steps to
    # us, not to the contact (see step 04, principle 7).
    parts: list[str] = ["[Emerton internal CRM record — our perspective, not necessarily known to the contact]"]
    if scope:
        parts.append(f"Open topic: {scope}.")
    if priority:
        parts.append(f"Internal priority: {priority}.")
    if days is not None:
        parts.append(f"{days} days since our last contact.")
    if next_step:
        parts.append(f"Our intended next step: {next_step}")
    if last_action:
        parts.append(f"Our last action: {last_action}.")
    if recent:
        parts.append(f"Our summary of recent discussions: {recent}")
    if history:
        parts.append(f"Our interaction log: {history}")
    if extra:
        parts.append(f"Our notes: {extra}")
    summary = " ".join(parts)[:MAX_SUMMARY_CHARS] or f"Re-engage {company}."

    relationship = (
        Relationship.DORMANT
        if days is None or days >= DORMANT_AFTER_DAYS
        else Relationship.EXISTING_CLIENT
    )
    salience = _salience_from(priority, days)

    trigger = Trigger(
        type=TriggerType.DORMANT_RELATIONSHIP,
        summary=summary,
        source_url=f"crm://deal/{deal_id}",
        date=last_date or "",
        company=company,
        salience=salience,
    )

    # A deal cell may list several people (e.g. "Eric GRESSIER / Caroline SIZARET").
    # They share one deal context, so we keep a single request: the email greets all of
    # them together, and step 04 produces one 1-to-1 LinkedIn message per recipient.
    recipients = _split_names(names_raw)
    contact = ContactProfile(
        full_name=", ".join(recipients) if recipients else "Unknown",
        title=role,
        company=company,
        seniority=_infer_seniority(role),
        language=DEFAULT_LANGUAGE,
        relationship=relationship,
        last_interaction=last_date,
        known_priorities=[scope] if scope else [],
    )
    return [
        DraftRequest(
            trigger=trigger,
            contact=contact,
            assets=assets,
            style=style,
            recipients=recipients or [contact.full_name],
        )
    ]


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #

def _read_rows(path: str) -> Iterable[dict[str, str]]:
    """Read a CRM export into a list of header-keyed string dicts (.csv or .xlsx)."""
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as fh:
            return [{(k or "").strip(): (v or "") for k, v in r.items()} for r in csv.DictReader(fh)]

    if path.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl  # imported lazily; only needed for Excel exports

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(c).strip() if c is not None else "" for c in rows[0]]
        out: list[dict[str, str]] = []
        for r in rows[1:]:
            out.append({header[i]: ("" if v is None else str(v)) for i, v in enumerate(r) if i < len(header)})
        return out

    raise ValueError(f"Unsupported CRM export format: {path}")


def _split_names(raw: str) -> list[str]:
    """Split a contact cell into individual people.

    Handles common delimiters ("/", "&", ";", " et ", " and "). A label without a
    delimiter (e.g. "Digital Lab team") is returned as a single entry.
    """
    if not raw:
        return []
    parts = re.split(r"\s*(?:/|&|;|\bet\b|\band\b)\s*", raw)
    return [p.strip() for p in parts if p.strip()]


# Values that mean "empty" in the export (placeholder dashes, etc.).
_PLACEHOLDERS = {"", "—", "–", "-", "n/a", "na", "tbd", "."}


def _get(row: dict[str, str], key: str) -> str:
    v = (row.get(key) or "").strip()
    return "" if v.lower() in _PLACEHOLDERS else v


def _full_name(row: dict[str, str]) -> str:
    """Contact name from either a single 'Contact Name' column or First/Last columns."""
    single = _get(row, "Contact Name")
    if single:
        return single
    parts = [_get(row, "First Name"), _get(row, "Last Name")]
    return " ".join(p for p in parts if p).strip()


def _salience_from(priority: str, days: int | None) -> Salience:
    p = priority.lower()
    if p.startswith("p1"):
        return Salience.HIGH
    if p.startswith("p2"):
        return Salience.MEDIUM
    if p.startswith(("p3", "p4")):
        return Salience.LOW
    return Salience.HIGH if days is not None and 7 <= days <= 30 else Salience.MEDIUM


def _to_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _norm_date(value: str) -> str | None:
    """Normalise a date-ish string to ISO yyyy-mm-dd; fall back to the first 10 chars."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return _dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value[:10]


def _infer_seniority(role: str) -> str:
    r = (role or "").lower()
    if any(k in r for k in ("ceo", "cfo", "coo", "cto", "cio", "cdo", "cdaio", "chief", "president", "partner")):
        return "C-level"
    if "vp" in r or "vice president" in r:
        return "VP"
    if any(k in r for k in ("director", "dir.", "head of", "head ")):
        return "Director"
    return "Manager"
