"""Pydantic models — the exact API contract (API Contract & Schema — 15 pts).

Enum values must match the problem statement EXACTLY. Any case/spelling/plural
variant is scored as a schema violation, so these are the single source of truth
for every string the service emits.

Input models are deliberately lenient (extra fields ignored, optional fields,
amounts coerced) so the service degrades gracefully on malformed/edge-case input
instead of rejecting the whole request — only `ticket_id` and `complaint` are
truly required.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ----------------------------- Output enums --------------------------------
class EvidenceVerdict(str, Enum):
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    INSUFFICIENT_DATA = "insufficient_data"


class CaseType(str, Enum):
    WRONG_TRANSFER = "wrong_transfer"
    PAYMENT_FAILED = "payment_failed"
    REFUND_REQUEST = "refund_request"
    DUPLICATE_PAYMENT = "duplicate_payment"
    MERCHANT_SETTLEMENT_DELAY = "merchant_settlement_delay"
    AGENT_CASH_IN_ISSUE = "agent_cash_in_issue"
    PHISHING_OR_SOCIAL_ENGINEERING = "phishing_or_social_engineering"
    OTHER = "other"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Department(str, Enum):
    CUSTOMER_SUPPORT = "customer_support"
    DISPUTE_RESOLUTION = "dispute_resolution"
    PAYMENTS_OPS = "payments_ops"
    MERCHANT_OPERATIONS = "merchant_operations"
    AGENT_OPERATIONS = "agent_operations"
    FRAUD_RISK = "fraud_risk"


# ----------------------------- Input models --------------------------------
class TransactionEntry(BaseModel):
    """One recent transaction. All fields optional + coerced so a single bad
    entry never fails the whole request."""

    model_config = ConfigDict(extra="ignore")

    transaction_id: Optional[str] = None
    timestamp: Optional[str] = None
    type: Optional[str] = None
    amount: Optional[float] = None
    counterparty: Optional[str] = None
    status: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v: Any) -> Optional[float]:
        if v is None or isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            try:
                return float(v.replace(",", "").strip())
            except ValueError:
                return None
        return None


class AnalyzeTicketRequest(BaseModel):
    """POST /analyze-ticket request body. Only ticket_id + complaint required."""

    model_config = ConfigDict(extra="ignore")

    ticket_id: str
    complaint: str
    language: Optional[str] = None
    channel: Optional[str] = None
    user_type: Optional[str] = None
    campaign_context: Optional[str] = None
    transaction_history: list[TransactionEntry] = Field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None

    @field_validator("transaction_history", mode="before")
    @classmethod
    def _none_to_empty(cls, v: Any) -> Any:
        return [] if v is None else v


# ----------------------------- Output model --------------------------------
class AnalyzeTicketResponse(BaseModel):
    ticket_id: str
    relevant_transaction_id: Optional[str]
    evidence_verdict: EvidenceVerdict
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
