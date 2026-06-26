"""API contract, schema, and reliability tests (15 + 10 pts)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.schemas import CaseType, Department, EvidenceVerdict, Severity

client = TestClient(app)
EP = settings.MAIN_ENDPOINT

_VALID = {
    "ticket_id": "TKT-X",
    "complaint": "I sent 5000 taka to a wrong number.",
    "transaction_history": [
        {"transaction_id": "TXN-1", "timestamp": "2026-04-14T14:08:22Z",
         "type": "transfer", "amount": 5000, "counterparty": "+8801719876543", "status": "completed"}
    ],
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_response_has_all_required_fields_and_valid_enums():
    body = client.post(EP, json=_VALID).json()
    for f in ["ticket_id", "relevant_transaction_id", "evidence_verdict", "case_type",
              "severity", "department", "agent_summary", "recommended_next_action",
              "customer_reply", "human_review_required"]:
        assert f in body, f
    assert body["ticket_id"] == "TKT-X"  # echoed
    assert body["evidence_verdict"] in {e.value for e in EvidenceVerdict}
    assert body["case_type"] in {e.value for e in CaseType}
    assert body["severity"] in {e.value for e in Severity}
    assert body["department"] in {e.value for e in Department}
    assert isinstance(body["human_review_required"], bool)
    assert 0.0 <= body["confidence"] <= 1.0


def test_missing_required_field_is_400():
    # No complaint -> malformed (missing required field) -> 400.
    r = client.post(EP, json={"ticket_id": "T-1"})
    assert r.status_code == 400


def test_empty_complaint_is_422():
    r = client.post(EP, json={"ticket_id": "T-2", "complaint": "   "})
    assert r.status_code == 422


def test_malformed_json_does_not_crash():
    r = client.post(EP, content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code in (400, 422)


def test_unknown_fields_are_ignored():
    payload = dict(_VALID, surprise_field={"x": 1}, another="ignored")
    r = client.post(EP, json=payload)
    assert r.status_code == 200


def test_empty_transaction_history_is_ok():
    r = client.post(EP, json={"ticket_id": "T-3",
                              "complaint": "Someone called asking for my OTP, is this a scam?",
                              "transaction_history": []})
    assert r.status_code == 200
    assert r.json()["relevant_transaction_id"] is None


def test_garbage_transaction_entry_degrades_gracefully():
    # A malformed transaction entry must not 5xx the whole request.
    payload = {
        "ticket_id": "T-4",
        "complaint": "I sent 5000 to a wrong number.",
        "transaction_history": [{"transaction_id": "TXN-1", "amount": "not-a-number"}],
    }
    r = client.post(EP, json=payload)
    assert r.status_code == 200
