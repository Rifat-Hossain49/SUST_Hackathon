"""Gemini polish layer tests without making any external API calls."""
from __future__ import annotations

import json
from urllib import error

from app.config import settings
from app.llm import LLMClient
from app.schemas import CaseType, Department, EvidenceVerdict, Severity


_RESULT = {
    "ticket_id": "T-LLM",
    "relevant_transaction_id": "TXN-1",
    "evidence_verdict": EvidenceVerdict.CONSISTENT,
    "case_type": CaseType.PAYMENT_FAILED,
    "severity": Severity.HIGH,
    "department": Department.PAYMENTS_OPS,
    "agent_summary": "Draft summary.",
    "recommended_next_action": "Draft next action.",
    "customer_reply": "Draft reply. Please do not share your PIN or OTP with anyone.",
    "human_review_required": False,
    "confidence": 0.9,
    "reason_codes": ["payment_failed"],
}


def test_gemini_polish_parses_json_response(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    polished = {
        "agent_summary": "Polished summary.",
        "recommended_next_action": "Polished next action.",
        "customer_reply": "Polished reply. Please do not share your PIN or OTP with anyone.",
    }
    response_body = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(polished)}]}}
        ]
    }

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self):
            return json.dumps(response_body).encode("utf-8")

    def fake_urlopen(_request, timeout):
        assert timeout == settings.LLM_TIMEOUT_SECONDS
        return FakeResponse()

    monkeypatch.setattr("app.llm.request.urlopen", fake_urlopen)

    assert LLMClient().polish(_RESULT) == polished


def test_gemini_polish_falls_back_on_api_error(monkeypatch):
    monkeypatch.setattr(settings, "USE_LLM", True)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    def fake_urlopen(_request, timeout):
        raise error.URLError("no network in tests")

    monkeypatch.setattr("app.llm.request.urlopen", fake_urlopen)

    assert LLMClient().polish(_RESULT) == {
        "agent_summary": _RESULT["agent_summary"],
        "recommended_next_action": _RESULT["recommended_next_action"],
        "customer_reply": _RESULT["customer_reply"],
    }
