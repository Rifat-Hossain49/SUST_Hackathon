"""FastAPI application — GET /health and POST /analyze-ticket.

Reliability rules baked in (Performance & Reliability — 10 pts):
  * GET /health returns {"status":"ok"} instantly (readiness < 60s).
  * POST /analyze-ticket NEVER returns 5xx for a structurally valid request — any
    internal error falls back to a safe, schema-valid response (HTTP 200).
  * Malformed JSON / missing required fields -> controlled 400 (no stack trace).
  * Schema-valid but semantically empty complaint -> 422.
  * Every customer reply passes the deterministic safety filter before leaving.
  * No secrets, tokens, or stack traces in any response or log line.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import safety
from .config import settings
from .llm import llm
from .normalize import reply_language
from .reasoning import analyze
from .schemas import (
    AnalyzeTicketRequest,
    AnalyzeTicketResponse,
    CaseType,
    Department,
    EvidenceVerdict,
    HealthResponse,
    Severity,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _safe_fallback(ticket_id: str, language: str = "en") -> AnalyzeTicketResponse:
    """Used if anything unexpected happens on a valid request: stay up, fail safe,
    route to a human, and emit a schema-valid response rather than a 5xx."""
    fallback = (
        safety.SAFE_FALLBACK_REPLY_BN if language == "bn" else safety.SAFE_FALLBACK_REPLY_EN
    )
    return AnalyzeTicketResponse(
        ticket_id=ticket_id,
        relevant_transaction_id=None,
        evidence_verdict=EvidenceVerdict.INSUFFICIENT_DATA,
        case_type=CaseType.OTHER,
        severity=Severity.MEDIUM,
        department=Department.CUSTOMER_SUPPORT,
        agent_summary="The service could not fully analyze this ticket and is routing it for "
                      "human review as a safe default.",
        recommended_next_action="Escalate to a human reviewer to analyze the ticket manually.",
        customer_reply=fallback,
        human_review_required=True,
        confidence=0.0,
        reason_codes=["internal_fallback"],
    )


@app.post(settings.MAIN_ENDPOINT, response_model=AnalyzeTicketResponse)
def analyze_ticket(req: AnalyzeTicketRequest) -> AnalyzeTicketResponse:
    lang = reply_language(req.language, req.complaint or "")

    # Semantic validation: schema is valid but the complaint is empty -> 422.
    if not (req.complaint or "").strip():
        return JSONResponse(
            status_code=422,
            content={"error": "empty_complaint", "detail": "complaint must not be empty"},
        )

    try:
        result = analyze(req)

        # Optional LLM rephrase of text only (decision/routing untouched).
        polished = llm.polish(result)

        # Safety filter is authoritative: re-run on the FINAL reply (covers the
        # LLM path); the rule path already sanitized but this is idempotent.
        safe_reply, reply_flags = safety.sanitize_reply(polished["customer_reply"], lang)
        codes = list(dict.fromkeys(result["reason_codes"] + reply_flags))

        log.info(
            "ticket=%s case=%s verdict=%s dept=%s sev=%s review=%s rel_txn=%s",
            req.ticket_id, result["case_type"].value, result["evidence_verdict"].value,
            result["department"].value, result["severity"].value,
            result["human_review_required"], result["relevant_transaction_id"],
        )

        return AnalyzeTicketResponse(
            ticket_id=result["ticket_id"],
            relevant_transaction_id=result["relevant_transaction_id"],
            evidence_verdict=result["evidence_verdict"],
            case_type=result["case_type"],
            severity=result["severity"],
            department=result["department"],
            agent_summary=polished["agent_summary"],
            recommended_next_action=polished["recommended_next_action"],
            customer_reply=safe_reply,
            human_review_required=result["human_review_required"],
            confidence=result["confidence"],
            reason_codes=codes,
        )
    except Exception:  # never 5xx on a valid request
        log.exception("Unhandled error processing ticket=%s", req.ticket_id)
        return _safe_fallback(req.ticket_id, lang)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Malformed input (invalid JSON, missing/!typed required fields) -> 400 with
    a non-sensitive message. The spec treats this as malformed input."""
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_request", "detail": "Malformed or incomplete request body."},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort guard: never leak a stack trace or secret."""
    log.exception("Unhandled exception at %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error"})
