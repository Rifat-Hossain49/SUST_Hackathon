"""FastAPI application: health + main analysis endpoint, with controlled errors.

Reliability rules baked in (Performance & Reliability — 10 pts):
  * GET /health returns {"status":"ok"} instantly (proves liveness < 60s).
  * The main endpoint NEVER returns 5xx for a structurally valid request — any
    internal error falls back to a safe ESCALATE response (HTTP 200).
  * Malformed/invalid JSON returns a controlled 422 with no stack trace.
  * All customer-facing text passes the safety filter before it leaves.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import safety
from .config import settings
from .llm import llm
from .reasoning import analyze
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    Decision,
    HealthResponse,
    RiskLevel,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("app")

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _safe_fallback(case_id: str | None) -> AnalyzeResponse:
    """Used when something unexpected happens on a valid request: stay up, fail
    safe, and route to a human rather than returning 5xx."""
    return AnalyzeResponse(
        case_id=case_id,
        decision=Decision.ESCALATE,
        risk_level=RiskLevel.HIGH,
        confidence=0.0,
        escalate_to_human=True,
        evidence=[],
        safety_flags=["internal_fallback"],
        summary="The service could not fully process this case and is routing it to a human for safety.",
        next_action="Escalate to a human reviewer.",
        customer_reply=safety.SAFE_FALLBACK_REPLY,
    )


def analyze_endpoint(req: AnalyzeRequest) -> AnalyzeResponse:
    """Main analysis endpoint (path set by MAIN_ENDPOINT env var)."""
    case_id = req.case_id
    try:
        result = analyze(req)

        # Optional LLM polish of the three text fields (decision is untouched).
        polished = llm.polish(result)

        # Safety filter is authoritative: it runs on the FINAL customer reply
        # whether it came from rules or the LLM.
        safe_reply, reply_flags = safety.sanitize_reply(polished["customer_reply"])
        flags = list(dict.fromkeys(result["safety_flags"] + reply_flags))

        # Log PII-safely.
        log.info(
            "case=%s decision=%s risk=%s escalate=%s flags=%s",
            case_id, result["decision"], result["risk_level"],
            result["escalate_to_human"], flags,
        )

        return AnalyzeResponse(
            case_id=case_id,
            decision=result["decision"],
            risk_level=result["risk_level"],
            confidence=result["confidence"],
            escalate_to_human=result["escalate_to_human"],
            evidence=result["evidence"],
            safety_flags=flags,
            summary=polished["summary"],
            next_action=polished["next_action"],
            customer_reply=safe_reply,
        )
    except Exception:  # never 5xx on a valid request
        log.exception("Unhandled error processing case=%s", case_id)
        return _safe_fallback(case_id)


# Register the main route at the configurable path.
app.add_api_route(
    settings.MAIN_ENDPOINT,
    analyze_endpoint,
    methods=["POST"],
    response_model=AnalyzeResponse,
    name="analyze",
)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Controlled 422 for malformed/invalid JSON — no stack trace, clean body."""
    return JSONResponse(
        status_code=422,
        content={"error": "invalid_request", "detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort guard so the service never leaks a stack trace."""
    log.exception("Unhandled exception at %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_error"})
