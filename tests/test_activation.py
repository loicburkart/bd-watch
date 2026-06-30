"""Full test suite for the database-activation use case.

Exercises the activation feeder end to end against an Excel fixture that mirrors the
real ``Deal_Reminders`` export (4 deals + a blank row + a colour legend row), then
through the drafter and review steps.

The fixture (``tests/fixtures/deal_reminders.xlsx``) is an anonymized copy of the real
file's structure so the suite is portable. To additionally run against the real export,
set ``BD_WATCH_REAL_CRM=/path/to/Deal_Reminders_vLightNoEmail.xlsx``.

Note: a deal cell may list several people ("Eric MOREAU / Caroline PETIT"). They share
one deal, so the feeder keeps a single request carrying all of them as ``recipients``;
the drafter then produces one shared email + one 1-to-1 LinkedIn message per recipient.
So 4 deals across 4 companies yield 4 requests.
"""

from __future__ import annotations

import json
import os
import types
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
    """One request per deal, so keying by company is unambiguous."""
    return {r.contact.company: r for r in requests}


# --------------------------------------------------------------------------- #
# Row filtering & request count
# --------------------------------------------------------------------------- #

def test_parses_expected_requests(requests):
    # 4 deals -> 4 requests (the multi-person row stays a single request).
    assert len(requests) == 4
    assert len({r.contact.company for r in requests}) == 4


def test_skips_blank_and_legend_rows(requests):
    companies = {r.contact.company for r in requests}
    assert not any("stale" in c.lower() for c in companies)
    assert not any("legend" in c.lower() for c in companies)


def test_every_request_is_well_formed(requests):
    for r in requests:
        assert isinstance(r, DraftRequest)
        assert r.contact.full_name and r.contact.company
        assert r.recipients  # at least one recipient
        assert r.trigger.type == TriggerType.DORMANT_RELATIONSHIP
        assert r.contact.language == "fr"
        assert r.assets.sender_name  # assets loaded


# --------------------------------------------------------------------------- #
# Multi-contact handling: one request, several recipients
# --------------------------------------------------------------------------- #

def test_multi_contact_cell_kept_as_one_request(requests):
    lacprod = [r for r in requests if r.contact.company == "Lacprod"]
    assert len(lacprod) == 1
    assert set(lacprod[0].recipients) == {"Eric MOREAU", "Caroline PETIT"}


def test_single_contact_defaults_recipients(by_company):
    r = by_company["Aquatech Group"]
    assert r.recipients == ["Camille BERNARD"]


# --------------------------------------------------------------------------- #
# Field mapping
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "company,seniority,relationship,last_date",
    [
        ("Aquatech Group", "Director", Relationship.DORMANT, "2026-06-15"),
        ("Northstar Capital", "C-level", Relationship.DORMANT, "2026-06-15"),
        ("Lacprod", "Manager", Relationship.DORMANT, "2026-06-11"),
        ("Mutuelle Assur", "C-level", Relationship.EXISTING_CLIENT, "2026-06-19"),
    ],
)
def test_field_mapping(by_company, company, seniority, relationship, last_date):
    r = by_company[company]
    assert r.contact.seniority == seniority
    assert r.contact.relationship == relationship
    assert r.contact.last_interaction == last_date
    assert r.contact.known_priorities  # scope captured as a priority


# --------------------------------------------------------------------------- #
# Classification logic
# --------------------------------------------------------------------------- #

def test_relationship_classified_by_recency(by_company):
    # 11 days quiet -> still active; >= 14 -> dormant.
    assert by_company["Mutuelle Assur"].contact.relationship == Relationship.EXISTING_CLIENT
    assert by_company["Lacprod"].contact.relationship == Relationship.DORMANT


def test_salience_high_for_recent_window(requests):
    assert all(r.trigger.salience == Salience.HIGH for r in requests)


# --------------------------------------------------------------------------- #
# Trigger grounding (the point of the activation use case)
# --------------------------------------------------------------------------- #

def test_trigger_summary_is_grounded(by_company):
    summary = by_company["Aquatech Group"].trigger.summary.lower()
    assert "days since" in summary
    assert "recent discussions" in summary or "last action" in summary


def test_trigger_carries_real_history(by_company):
    assert "budget" in by_company["Lacprod"].trigger.summary.lower()


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


def test_instruction_lists_all_recipients(by_company):
    instruction = step04_draft._build_instruction(by_company["Lacprod"])
    assert "Eric MOREAU" in instruction
    assert "Caroline PETIT" in instruction


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
# Shared email + per-recipient LinkedIn
# --------------------------------------------------------------------------- #

def test_mock_email_shared_and_linkedin_per_recipient(by_company):
    out = step04_draft.draft(by_company["Lacprod"])  # mock path (no API key)
    # One LinkedIn message per recipient, addressed individually.
    assert {li.recipient for li in out.linkedin} == {"Eric MOREAU", "Caroline PETIT"}
    # The shared email greets both contacts together (first names, FR).
    assert "Bonjour Eric, Caroline," in out.email.body


def test_single_recipient_gets_one_linkedin(by_company):
    out = step04_draft.draft(by_company["Aquatech Group"])
    assert len(out.linkedin) == 1
    assert out.linkedin[0].recipient == "Camille BERNARD"


# --------------------------------------------------------------------------- #
# Live drafter: signature is appended by the system, in the contact's language
# --------------------------------------------------------------------------- #

def _fake_anthropic(payload: dict):
    """A stand-in anthropic module whose client returns ``payload`` as JSON."""

    class _Messages:
        def create(self, **_kwargs):
            text = json.dumps(payload)
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=text)])

    class _Client:
        def __init__(self, *_a, **_k):
            self.messages = _Messages()

    return types.SimpleNamespace(Anthropic=_Client)


_PAYLOAD = {
    "email": {"subject": "Suite à nos échanges", "body": "Bonjour, voici le corps du message.", "cta": "Un point de 15 minutes ?"},
    "linkedin": [
        {"recipient": "Eric MOREAU", "message": "Message pour Eric."},
        {"recipient": "Caroline PETIT", "message": "Message pour Caroline."},
    ],
    "rationale": "angle",
    "confidence": "high",
    "flags": [],
}


def _force_live(monkeypatch, payload=_PAYLOAD):
    monkeypatch.setattr(step04_draft, "anthropic", _fake_anthropic(payload))
    monkeypatch.setattr(
        step04_draft,
        "settings",
        types.SimpleNamespace(
            has_databricks=False, has_llm=True, anthropic_api_key="test", model="test-model"
        ),
    )


def test_signature_appended_in_french(monkeypatch, by_company):
    _force_live(monkeypatch)
    req = by_company["Aquatech Group"]  # language == "fr"
    out = step04_draft.draft(req)
    assert "Bien à vous," in out.email.body
    assert req.assets.sender_name in out.email.body
    # The model body must not be discarded.
    assert "corps du message" in out.email.body


def test_signature_appended_in_english(monkeypatch):
    _force_live(monkeypatch)
    en_req = feeders.cold_feeder()[0]  # cold sample is in English
    out = step04_draft.draft(en_req)
    assert "Best," in out.email.body
    assert "Bien à vous," not in out.email.body


def test_live_linkedin_list_preserved_per_recipient(monkeypatch, by_company):
    _force_live(monkeypatch)
    out = step04_draft.draft(by_company["Lacprod"])
    assert {li.recipient for li in out.linkedin} == {"Eric MOREAU", "Caroline PETIT"}
    assert {li.message for li in out.linkedin} == {"Message pour Eric.", "Message pour Caroline."}


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
