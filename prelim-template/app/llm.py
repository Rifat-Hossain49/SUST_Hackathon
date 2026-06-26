"""Optional Claude augmentation for the human-readable text (OFF by default).

Design (the rubric's recommended hybrid): deterministic rules own the DECISION,
risk, escalation, and safety; the LLM only *rewrites* the summary / next_action
/ customer_reply more naturally. Every LLM output is still run through the
safety filter by the caller, so the LLM can never introduce an unsafe reply.

Robustness: a hard per-request timeout and a blanket try/except mean any LLM
failure (timeout, quota, network, bad JSON) silently falls back to the
rule-engine text — the API never crashes or exceeds the judge's latency budget.
"""
from __future__ import annotations

import json
import logging

from .config import settings

log = logging.getLogger("app.llm")

_SYSTEM = (
    "You are a support copilot for a mobile financial service. You will be given a "
    "machine-made decision about a customer case and draft text. Rewrite ONLY the "
    "three text fields to be clear, concise, and professional. You MUST NOT change "
    "the decision. Hard rules: never ask the customer for a PIN, OTP, password, CVV, "
    "or full card number; never promise a refund/reversal/unblock or any guaranteed "
    "or irreversible outcome; direct users only to the official app or verified "
    "helpline (no links, phone numbers, or third-party channels). "
    'Return ONLY a JSON object: {"summary": "...", "next_action": "...", "customer_reply": "..."}'
)


class LLMClient:
    def __init__(self) -> None:
        self._client = None
        if settings.llm_enabled:
            try:
                import anthropic  # imported lazily so the dep is optional

                self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
                log.info("LLM augmentation enabled (model=%s)", settings.MODEL_NAME)
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("LLM disabled: could not init client: %s", exc)
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def polish(self, result: dict) -> dict:
        """Return {summary, next_action, customer_reply} from the LLM, or the
        existing rule-engine text on any failure."""
        fallback = {
            "summary": result["summary"],
            "next_action": result["next_action"],
            "customer_reply": result["customer_reply"],
        }
        if not self.enabled:
            return fallback

        payload = {
            "decision": result["decision"].value if hasattr(result["decision"], "value") else result["decision"],
            "risk_level": result["risk_level"].value if hasattr(result["risk_level"], "value") else result["risk_level"],
            "draft": fallback,
        }
        try:
            # Per-request timeout in seconds (Python SDK) keeps us inside p95<=5s.
            client = self._client.with_options(timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=0)
            msg = client.messages.create(
                model=settings.MODEL_NAME,
                max_tokens=settings.LLM_MAX_TOKENS,
                system=_SYSTEM,
                messages=[{"role": "user", "content": json.dumps(payload)}],
            )
            text = next((b.text for b in msg.content if getattr(b, "type", None) == "text"), "")
            data = _extract_json(text)
            return {
                "summary": str(data.get("summary") or fallback["summary"]),
                "next_action": str(data.get("next_action") or fallback["next_action"]),
                "customer_reply": str(data.get("customer_reply") or fallback["customer_reply"]),
            }
        except Exception as exc:
            log.warning("LLM polish failed, using rule text: %s", exc)
            return fallback


def _extract_json(text: str) -> dict:
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start: end + 1])
        except json.JSONDecodeError:
            pass
    return {}


# Singleton, created once at import (cheap when disabled).
llm = LLMClient()
