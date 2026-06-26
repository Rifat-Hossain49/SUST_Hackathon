# Codex Prelim API — Safe, Evidence-Grounded Support Copilot

A FastAPI service template for the **bKash presents SUST CSE Carnival 2026 —
Codex Community Hackathon** preliminary round (AI/API challenge). It is built
directly to the published rubric: correct JSON contract, evidence-based
reasoning, hard safety guardrails, reliable/fast execution, and a clean Docker
fallback.

> **The example domain (transaction / support-case review) is a placeholder.**
> When the official Problem Statement is released, edit two files —
> [`app/schemas.py`](app/schemas.py) (field names, types, enums) and
> [`app/reasoning.py`](app/reasoning.py) (the decision policy) — and set
> `MAIN_ENDPOINT` to the official route. Everything else (health, error
> handling, safety filter, Docker, deploy) carries over unchanged.

## Architecture

```
            ┌──────────── FastAPI (app/main.py) ────────────┐
  request → │ GET /health → {"status":"ok"}                 │
   (JSON)   │ POST <MAIN_ENDPOINT>                           │
            │   1. validate (Pydantic, app/schemas.py)      │
            │   2. reason   (rules, app/reasoning.py) ◄──35% │ → decision, risk,
            │   3. polish   (optional LLM, app/llm.py)       │   evidence, escalate
            │   4. SAFETY filter (app/safety.py) ◄──────20% │ → safe customer text
            │   5. respond  (strict JSON, app/schemas.py)   │
            └───────────────────────────────────────────────┘
```

**Hybrid rule + AI (recommended by the rubric):** deterministic rules own the
*decision, risk, escalation, and safety*; the LLM (optional, off by default)
only rewrites the human-readable text — and that text is still run through the
safety filter. The service is fully functional with **no paid API**.

## API

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /analyze`  (path configurable via `MAIN_ENDPOINT`)

Request (all fields except `customer_message` optional; extras ignored):
```json
{
  "case_id": "CASE-1042",
  "customer_message": "Payment failed but the amount was deducted.",
  "category": "transaction",
  "transaction": { "amount": 1500, "currency": "BDT", "status": "failed" },
  "history": [],
  "context": {}
}
```

Response:
```json
{
  "case_id": "CASE-1042",
  "decision": "APPROVE",
  "risk_level": "MEDIUM",
  "confidence": 0.78,
  "escalate_to_human": false,
  "evidence": [
    { "field": "customer_message", "observation": "Describes a standard, potentially self-resolvable issue." },
    { "field": "transaction.amount", "observation": "Transaction amount is 1500." }
  ],
  "safety_flags": [],
  "summary": "Customer describes a standard transaction issue suitable for routine handling.",
  "next_action": "Proceed with the standard resolution workflow; verify transaction status before any adjustment.",
  "customer_reply": "Thanks for the details. We're reviewing your transaction and will follow up through the official bKash app..."
}
```

`decision ∈ {APPROVE, DENY, ESCALATE, NEEDS_MORE_INFO}`,
`risk_level ∈ {LOW, MEDIUM, HIGH}`.

## Run locally

**Docker (recommended — matches the judge's environment):**
```bash
docker build -t codex-prelim-api .
docker run -p 8000:8000 codex-prelim-api
# or: docker compose up --build
```

**Python (3.11+):**
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Smoke-test a running instance (schema + safety + p95 latency):
```bash
pip install -r requirements-dev.txt
python scripts/smoke_test.py http://localhost:8000 /analyze
pytest -q
```

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `MAIN_ENDPOINT` | `/analyze` | Path of the main endpoint — set to the official route |
| `USE_LLM` | `false` | Enable optional Claude text polishing |
| `ANTHROPIC_API_KEY` | – | Your key (only if `USE_LLM=true`); set in the host env, never committed |
| `MODEL_NAME` | `claude-haiku-4-5` | Fast/cheap tier; use `claude-opus-4-8` for higher quality |
| `LLM_TIMEOUT_SECONDS` | `4.0` | Hard LLM timeout; on timeout we fall back to rule text |
| `ESCALATE_CONFIDENCE_BELOW` | `0.55` | Below this confidence, route to a human |

See [`.env.example`](.env.example). **No real secrets are committed** — keys are
injected from the deployment platform's environment.

## AI / model usage

Hybrid. Rule-based logic (`app/reasoning.py`) produces every decision and runs
fully offline. An **optional** Claude call (`app/llm.py`, off by default) only
rewrites the summary / next-action / customer-reply for readability, behind a
4-second timeout with automatic fallback to the rule-engine text. The
deterministic safety filter validates the final reply regardless of source.

## Safety logic

Deterministic guardrails in [`app/safety.py`](app/safety.py) run on every
customer-facing string:
- **Never requests** PIN / OTP / password / CVV / card number (and warns the
  user if they paste one).
- **Never promises** refunds, reversals, unblocks, or guaranteed/irreversible
  outcomes — only recommends review.
- **Only routes to official channels** — strips links, phone numbers, and
  third-party contacts.
- Uncertain or high-risk cases set `escalate_to_human=true`.
- PII (long digit runs) is redacted from logs.

If any hard rule trips, the reply is replaced with a safe fallback rather than
patched, so unsafe text cannot leak.

## Reliability

- `GET /health` answers instantly (liveness < 60s).
- A structurally valid request never returns 5xx — internal errors fall back to
  a safe `ESCALATE` response (HTTP 200).
- Malformed JSON returns a controlled `422`, no stack trace.
- CPU-only, no GPU, no model weights baked in — image well under 1 GB; binds to
  `0.0.0.0`.

## Deployment

Portable to any reachable host (Render, Railway, Fly.io, AWS EC2, Poridhi VM).
Submit the public base URL + this repo. For the Docker fallback:
```bash
docker build -t hackathon-team .
docker run -p 8000:8000 --env-file judging.env hackathon-team
```

## Known limitations

- The decision policy and schema are **placeholders** illustrating the rubric's
  expected shape; they must be aligned to the official Problem Statement.
- Rule-based reasoning uses keyword/heuristic signals — robust and fast, but
  less nuanced than the optional LLM path on ambiguous free text.
- Safety patterns are tuned for English (with common local terms); extend for
  Bangla/Banglish if the hidden tests include them.
