"""Smoke tests for the skeleton. Run: pytest"""

from bd_watch import pipeline
from bd_watch.schemas import ReviewedOutreach


def test_pipeline_runs_end_to_end():
    results = pipeline.run()
    assert isinstance(results, list)
    assert all(isinstance(r, ReviewedOutreach) for r in results)


def test_stub_draft_routes_to_human_review():
    # The step 04 stub emits a flag, so review must not auto-send.
    results = pipeline.run()
    assert results, "pipeline produced no items"
    assert all(r.decision != "auto_send" for r in results)
