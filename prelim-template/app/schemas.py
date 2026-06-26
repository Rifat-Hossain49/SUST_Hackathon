"""Request/response schema and enums (API Contract — worth 15 pts).

==============================  PLACEHOLDER  ==============================
This models a generic "support / transaction case review" copilot, which is
the most likely shape of the bKash-sponsored prelim. When the official Problem
Statement is released, replace the field NAMES, TYPES and ENUM VALUES here to
match it EXACTLY — schema mistakes make otherwise-correct reasoning unscoreable.
The rest of the codebase reads/writes through these models, so this file is the
single place you edit for the contract.
=========================================================================
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class Decision(str, Enum):
    """Final review outcome. Replace with the official enum values."""

    APPROVE = "APPROVE"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Evidence(BaseModel):
    """A single piece of evidence the decision was grounded in."""

    field: str = Field(..., description="Which input signal this came from")
    observation: str = Field(..., description="What was observed, in plain language")


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    """Incoming case. Most fields optional so malformed/partial input is handled
    gracefully (rubric: 'handle empty or missing optional input data safely')."""

    # Reject unknown fields? No — be lenient so the judge's extra fields don't 422.
    model_config = ConfigDict(extra="ignore")

    case_id: Optional[str] = Field(default=None, description="Opaque case identifier")
    customer_message: str = Field(default="", description="Free-text from the customer")
    category: Optional[str] = Field(default=None)
    transaction: Optional[dict[str, Any]] = Field(
        default=None, description="e.g. {amount, currency, merchant, status, channel}"
    )
    history: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Prior events/tickets for this customer"
    )
    context: Optional[dict[str, Any]] = Field(default=None, description="Any extra context")


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    case_id: Optional[str] = None
    decision: Decision
    risk_level: RiskLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    escalate_to_human: bool
    evidence: list[Evidence] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    # Human-readable outputs (Response Quality — 10 pts)
    summary: str
    next_action: str
    customer_reply: str


class HealthResponse(BaseModel):
    status: str = "ok"
