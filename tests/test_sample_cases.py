"""Validate the service against all 10 public worked cases.

Grading is by functional equivalence (per the problem statement): the same
relevant_transaction_id, evidence_verdict, case_type, department, comparable
severity, correct human_review_required, and a customer_reply that respects the
Section 8 safety rules. We assert exactly those.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import safety
from app.config import settings
from app.main import app

client = TestClient(app)
EP = settings.MAIN_ENDPOINT

_CASES = json.loads((Path(__file__).parent / "data" / "sample_cases.json").read_text("utf-8"))["cases"]


def _ids(case):
    return case["id"]


@pytest.mark.parametrize("case", _CASES, ids=_ids)
def test_sample_case_functional_equivalence(case):
    inp = case["input"]
    exp = case["expected_output"]
    r = client.post(EP, json=inp)
    assert r.status_code == 200, r.text
    got = r.json()

    # ticket_id echoed
    assert got["ticket_id"] == inp["ticket_id"]
    # The four exactly-graded reasoning fields
    assert got["relevant_transaction_id"] == exp["relevant_transaction_id"], case["id"]
    assert got["evidence_verdict"] == exp["evidence_verdict"], case["id"]
    assert got["case_type"] == exp["case_type"], case["id"]
    assert got["department"] == exp["department"], case["id"]
    # Severity + human review (graded as part of evidence reasoning)
    assert got["severity"] == exp["severity"], case["id"]
    assert got["human_review_required"] == exp["human_review_required"], case["id"]


@pytest.mark.parametrize("case", _CASES, ids=_ids)
def test_sample_case_reply_is_safe(case):
    r = client.post(EP, json=case["input"])
    body = r.json()
    reply = body["customer_reply"]
    nxt = body["recommended_next_action"]
    # Hard safety rules on the customer-facing reply.
    assert not safety.requests_credential(reply), case["id"]
    assert not safety.promises_unauthorized_action(reply), case["id"]
    assert not safety.directs_to_suspicious_channel(reply), case["id"]
    # The unauthorized-promise rule also covers recommended_next_action.
    assert not safety.promises_unauthorized_action(nxt), case["id"]
    # Non-empty, useful text.
    assert reply.strip() and body["agent_summary"].strip() and nxt.strip()


def test_bangla_case_replies_in_bangla():
    # SAMPLE-07 is a Bangla complaint; the reply must be in Bangla.
    case = next(c for c in _CASES if c["id"] == "SAMPLE-07")
    body = client.post(EP, json=case["input"]).json()
    from app.normalize import contains_bangla
    assert contains_bangla(body["customer_reply"])
