"""Full test suite for the database-activation use case.

Exercises the activation feeder end to end against an Excel fixture that mirrors the
real ``Deal_Reminders`` export (4 deals + a blank row + a colour legend row), then
through the drafter and review steps.

The fixture (``tests/fixtures/deal_reminders.xlsx``) is an anonymized copy of the real
file's structure so the suite is portable. To additionally run against the real export,
set ``BD_WATCH_REAL_CRM=/path/to/Deal_Reminders_vLightNoEmail.xlsx``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from bd_watch import feeders
from bd_watch.steps import step04_draft, step05_review
from bd_watch.schemas import (
    DraftRequest,
    Relationship,
    ReviewedOutreach,
    Salience,
    TriggerType,
)

FIXTURE = str(Path(__file__).parent / "fixtures" / "deal_reminders.xlsx")


@pytest.fixture(scope="module")
def requests() -> list[DraftRequest]:
    return feeders.activation_feeder(FIXTURE)


@pytest.fixture(scope="module")
def by_company(requests) -> dict[str, DraftRequest]:
    return {r.contact.company: r for r in requests}


# --------------------------------------------------------------------------- #
# Row filtering
# --------------------------------------------------------------------------- #

def test_only_real_deals_are_parsed(requests):
    # 4 deals; the blank row and the "Legend:" footer must be skipped.
    assert len(requests) == 4
    companies = {r.contact.company for r in requests}
    assert "Aquatech Group" in companies
    assert not any("stale" in c.lower() for c in companies)
    assert not any("legend" in c.lower() for c in companies)


def test_every_request_is_well_formed(requests):
    for r in requests:
        assert isinstance(r, DraftRequest)
        assert r.contact.full_name
        assert r.contact.company
        assert r.trigger.type == TriggerType.DORMANT_RELATIONSHIP
        assert r.contact.language == "fr"
        assert r.assets.sender_name  # assets loaded


# --------------------------------------------------------------------------- #
# Field mapping
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "company,name,seniority,relationship,last_date",
    [
        ("Aquatech Group", "Camille BERNARD", "Director", Relationship.DORMANT, "2026-06-15"),
        ("Northstar Capital", "Damien LEROY", "C-level", Relationship.DORMANT, "2026-06-15"),
        ("Lacprod", "Eric MOREAU / Caroline PETIT", "Manager", Relationship.DORMANT, "2026-06-11"),
        ("Mutuelle Assur", "Olivier GIRARD", "C-level", Relationship.EXISTING_CLIENT, "2026-06-19"),
    ],
)
def test_field_mapping(by_company, company, name, seniority, relationship, last_date):
    r = by_company[company]
    assert r.contact.full_name == name
    assert r.contact.seniority == seniority
    assert r.contact.relationship == relationship
    assert r.contact.last_interaction == last_date
    assert r.contact.known_priorities  # scope captured as a priority


def test_multi_contact_name_preserved(by_company):
    assert by_company["Lacprod"].contact.full_name == "Eric MOREAU / Caroline PETIT"


# --------------------------------------------------------------------------- #
# Classification logic
# --------------------------------------------------------------------------- #

def test_relationship_classified_by_recency(by_company):
    # 11 days quiet -> still active; >= 14 -> dormant.
    assert by_company["Mutuelle Assur"].contact.relationship == Relationship.EXISTING_CLIENT
    assert by_company["Lacprod"].contact.relationship == Relationship.DORMANT


def test_salience_high_for_recent_window(requests):
    # All fixture deals fall in the 7..30 day window.
    assert all(r.trigger.salience == Salience.HIGH for r in requests)


# --------------------------------------------------------------------------- #
# Trigger grounding (the point of the activation use case)
# --------------------------------------------------------------------------- #

def test_trigger_summary_is_grounded(by_company):
    summary = by_company["Aquatech Group"].trigger.summary.lower()
    assert "days since" in summary
    assert "recent discussions" in summary or "last action" in summary


def test_trigger_carries_real_history(by_company):
    s = by_company["Lacprod"].trigger.summary.lower()
    assert "budget" in s  # the actual blocker from the deal history


def test_source_url_references_deal(by_company):
    assert by_company["Aquatech Group"].trigger.source_url.startswith("crm://deal/")


# --------------------------------------------------------------------------- #
# Unit helpers
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "role,expected",
    [
        ("CEO", "C-level"),
        ("CDAIO", "C-level"),
        ("Chief Data Officer", "C-level"),
        ("VP Analytics", "VP"),
        ("Marketing & Commercial Performance Dir.", "Director"),
        ("Head of Data", "Director"),
        ("Digital Lab team", "Manager"),
        ("", "Manager"),
    ],
)
def test_infer_seniority(role, expected):
    assert feeders._infer_seniority(role) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-06-15 00:00:00", "2026-06-15"),
        ("2026-06-15", "2026-06-15"),
        ("15/06/2026", "2026-06-15"),
        ("", None),
    ],
)
def test_norm_date(raw, expected):
    assert feeders._norm_date(raw) == expected


def test_to_int_handles_garbage():
    assert feeders._to_int("19") == 19
    assert feeders._to_int("Legend:") is None
    assert feeders._to_int("") is None


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #

def test_missing_export_is_graceful(tmp_path):
    assert feeders.activation_feeder(str(tmp_path / "nope.xlsx")) == []


def test_unsupported_format_raises(tmp_path):
    bad = tmp_path / "deals.txt"
    bad.write_text("not a spreadsheet")
    with pytest.raises(ValueError):
        feeders.activation_feeder(str(bad))


# --------------------------------------------------------------------------- #
# Prompt assembly + pipeline integration
# --------------------------------------------------------------------------- #

def test_instruction_includes_crm_context(by_company):
    instruction = step04_draft._build_instruction(by_company["Mutuelle Assur"])
    assert "Mutuelle Assur" in instruction
    assert "Olivier GIRARD" in instruction
    assert "existing_client" in instruction
    assert "RFP" in instruction  # grounded history reached the prompt


def test_adaptation_rules_match_relationship(by_company):
    rules = step04_draft._build_adaptation_rules(by_company["Aquatech Group"])
    assert "FR" in rules
    assert "dormant" in rules.lower()


def test_requests_flow_through_drafter_and_review(requests):
    # No API key in CI -> mock drafts, which are flagged and must not auto-send.
    for req in requests:
        reviewed = step05_review.review(step04_draft.draft(req))
        assert isinstance(reviewed, ReviewedOutreach)
        assert reviewed.decision != "auto_send"
        assert reviewed.draft.confidence in {"low", "medium", "high"}


# --------------------------------------------------------------------------- #
# Optional: run against the real export when provided
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    not os.environ.get("BD_WATCH_REAL_CRM"),
    reason="set BD_WATCH_REAL_CRM to the real export path to run this test",
)
def test_real_export_parses():
    reqs = feeders.activation_feeder(os.environ["BD_WATCH_REAL_CRM"])
    assert reqs, "no deals parsed from real export"
    assert all(r.trigger.type == TriggerType.DORMANT_RELATIONSHIP for r in reqs)
    assert all(r.contact.company for r in reqs)
