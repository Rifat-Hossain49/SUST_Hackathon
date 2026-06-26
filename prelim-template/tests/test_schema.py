from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)
EP = settings.MAIN_ENDPOINT

REQUIRED = {
    "decision", "risk_level", "confidence", "escalate_to_human",
    "evidence", "safety_flags", "summary", "next_action", "customer_reply",
}
DECISIONS = {"APPROVE", "DENY", "ESCALATE", "NEEDS_MORE_INFO"}
RISKS = {"LOW", "MEDIUM", "HIGH"}


def test_response_has_all_fields_and_valid_enums():
    r = client.post(EP, json={"case_id": "t1", "customer_message": "I was double charged",
                              "transaction": {"amount": 1200}})
    assert r.status_code == 200
    body = r.json()
    assert REQUIRED.issubset(body)
    assert body["decision"] in DECISIONS
    assert body["risk_level"] in RISKS
    assert 0.0 <= body["confidence"] <= 1.0


def test_empty_body_is_handled_safely():
    r = client.post(EP, json={})
    assert r.status_code == 200
    assert r.json()["decision"] in DECISIONS


def test_malformed_json_returns_controlled_422():
    r = client.post(EP, content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert "error" in r.json()


def test_unexpected_extra_fields_are_ignored_not_crashed():
    r = client.post(EP, json={"customer_message": "hi", "weird_extra": [1, 2, 3], "nested": {"a": 1}})
    assert r.status_code == 200
