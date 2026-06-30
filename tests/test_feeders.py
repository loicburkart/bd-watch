"""Tests for the two feeders."""

from bd_watch import feeders
from bd_watch.schemas import DraftRequest, Relationship, TriggerType


def test_cold_feeder_returns_requests():
    reqs = feeders.cold_feeder()
    assert reqs and all(isinstance(r, DraftRequest) for r in reqs)
    assert all(r.contact.relationship == Relationship.COLD for r in reqs)


def test_activation_feeder_reads_sample_csv():
    reqs = feeders.activation_feeder()  # default = data/samples/crm_deals_sample.csv
    assert reqs and all(isinstance(r, DraftRequest) for r in reqs)
    # Every activation request is a re-engagement of a known contact.
    assert all(r.trigger.type == TriggerType.DORMANT_RELATIONSHIP for r in reqs)
    assert all(
        r.contact.relationship in (Relationship.DORMANT, Relationship.EXISTING_CLIENT)
        for r in reqs
    )
    # The grounded summary should carry real CRM context, not a generic line.
    assert any("days since" in r.trigger.summary.lower() for r in reqs)


def test_activation_feeder_classifies_by_recency():
    reqs = {r.contact.company: r for r in feeders.activation_feeder()}
    # Helios Capital is 5 days quiet -> still an active client.
    assert reqs["Helios Capital"].contact.relationship == Relationship.EXISTING_CLIENT
    # Lacto Group is 19 days quiet -> dormant.
    assert reqs["Lacto Group"].contact.relationship == Relationship.DORMANT


def test_activation_feeder_missing_file_is_graceful(tmp_path):
    assert feeders.activation_feeder(str(tmp_path / "nope.csv")) == []
