# QueueStorm Investigator

**SUST CSE Carnival 2026 · Codex Community Hackathon · Online Preliminary**

A safe, evidence-grounded **support copilot API** for a digital-finance campaign
surge. It reads one customer complaint plus a short snippet of that customer's
recent transactions, decides **which transaction the complaint refers to**, judges
**whether the data supports the complaint**, classifies and routes the case, and
drafts a **safe customer reply** — one that never asks for a PIN/OTP and never
promises a refund it cannot authorize.

It is an **investigator, not a classifier**: the complaint says one thing, the
transaction data may say another, and the service decides what is true.

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/health` | Returns `{"status":"ok"}` (readiness probe). |
| `POST` | `/analyze-ticket` | Analyzes one ticket and returns the structured response below. |

### Request (example)
```json
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today. Please help.",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "transaction_history": [
    {"transaction_id":"TXN-9101","timestamp":"2026-04-14T14:08:22Z","type":"transfer","amount":5000,"counterparty":"+8801719876543","status":"completed"}
  ]
}
```

### Response (example)
```json
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT via TXN-9101 to +8801719876543, which they now believe was the wrong recipient.",
  "recommended_next_action": "Verify TXN-9101 details with the customer and initiate the wrong-transfer dispute workflow per policy.",
  "customer_reply": "We have noted your concern about transaction TXN-9101. Our dispute team will review the case and contact you through official support channels. Please do not share your PIN or OTP with anyone.",
  "human_review_required": true,
  "confidence": 0.9,
  "reason_codes": ["wrong_transfer", "transaction_match", "evidence_consistent"]
}
```

**HTTP codes:** `200` success · `400` malformed/missing required fields · `422`
schema-valid but semantically empty complaint · `500` internal error (never leaks
a stack trace). A structurally valid request **never** returns 5xx — on an
unexpected internal error the service returns a safe, schema-valid fallback that
routes the case to a human.

See [`sample_output.json`](sample_output.json) for the service's actual response to
all 10 public sample cases.

---

## Quick start

### Run with Docker (recommended)
```bash
# Option 1 — pull the published image
docker pull rifathosain/queuestorm-investigator:latest
docker run -p 8000:8000 rifathosain/queuestorm-investigator:latest

# Option 2 — build locally
docker build -t queuestorm-investigator .
docker run -p 8000:8000 queuestorm-investigator

# verify (either option):
curl http://localhost:8000/health        # -> {"status":"ok"}
```
Or `docker compose up --build`. Full copy-paste steps are in [`RUNBOOK.md`](RUNBOOK.md).

### Run locally (no Docker)
```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Test
```bash
pip install -r requirements-dev.txt
pytest -q                          # 41 unit/integration tests incl. all 10 sample cases
python scripts/smoke_test.py http://localhost:8000   # black-box checks + p95 latency
```

---

## Tech stack

- **Python 3.12**, **FastAPI**, **Pydantic v2**, **Uvicorn** — small, fast, async.
- **Deterministic rule engine** for all decisions (no model weights, CPU-only).
- **Optional** Gemini REST call for LLM text polish (off by default; see MODELS).
- **Docker** image on `python:3.12-slim` (~250 MB, well under the 5 GB guidance).

## Architecture & AI approach

The request flows through a small, auditable pipeline:

```
complaint + transaction_history
        │
        ▼
 normalize  →  reasoning (investigator)  →  replies (templates)  →  safety filter  →  response
 (Bangla       • match relevant txn          • EN/BN customer        (hard rules,
  digits,      • evidence_verdict              reply + agent           last word)
  amounts,     • case_type / department        next action
  language)    • severity / human_review
```

**Why rule-based (hybrid-ready).** Decisions — the part that is automatically
scored — are **deterministic**. This makes them reproducible, debuggable, immune to
prompt injection in the complaint text, and fast (p95 in milliseconds, far under the
5 s full-credit threshold). An LLM is **not required** to score well here, and a
non-deterministic model in the decision path would risk both latency and unsafe
output. An optional Gemini layer can rephrase the free-text fields for fluency
using the complaint, transaction history, and deterministic decision as context,
but the deterministic safety filter always runs last.

**The investigator logic (Evidence Reasoning).**
1. **Relevant transaction** — extract amounts from the complaint (incl. Bangla
   numerals), match against `transaction_history`. Exactly one match → that
   transaction. Multiple matches to *different* recipients → ambiguous → `null`
   (we do not guess). A duplicate pair (same amount + counterparty) → point at the
   *second* (the suspected duplicate charge).
2. **Evidence verdict** — `consistent` when the data supports the complaint;
   `inconsistent` when it contradicts it (e.g. a "wrong transfer" to a recipient
   the customer has paid repeatedly = an established recipient); `insufficient_data`
   when no transaction matches, the history is empty, or the match is ambiguous.
3. **Classify & route** — `case_type` from prioritized EN+BN signals, mapped to the
   owning `department`; `severity` from case type and verdict; `human_review_required`
   for disputes with a concrete transaction, all critical (phishing) cases, and
   high-value cases.

**Multilingual.** English, Bangla, and mixed *Banglish* complaints are handled
natively. Bangla numerals (`২০০০` → 2000) are normalized for matching, and the
`customer_reply` is returned **in the language of the complaint** (agent-facing
fields stay English for the support team).

## Safety logic (the hard rules)

Every customer reply passes a deterministic filter ([`app/safety.py`](app/safety.py))
that runs **regardless of how the text was produced**. It blocks, and replaces with a
safe fallback, any reply that would:

| Rule | Penalty avoided | How we handle it |
|---|---|---|
| Ask for PIN/OTP/password/card number | **−15** | Detected in EN **and** Bangla, **negation-aware** so the *required* "do **not** share your PIN/OTP" warning passes while an actual request is blocked. |
| Confirm an unauthorized refund/reversal/unblock | **−10** | Customer-facing promises ("we will refund you") are blocked; the sanctioned *"any eligible amount will be returned through official channels"* and internal operational steps ("initiate the reversal flow") are allowed. |
| Direct to a suspicious third party | **−10** | URLs, phone numbers, and third-party apps (WhatsApp/Telegram/…) are blocked; only official channels are allowed. |
| Prompt injection in the complaint | schema/safety | Decisions are rule-based and the reply is template-based, so embedded "instructions" cannot move a scored field or inject text into the reply. |

Replies also **proactively** warn the customer never to share their PIN/OTP — a safe,
negated mention that reinforces good security hygiene.

## MODELS

| Model | Where it runs | Role | Why |
|---|---|---|---|
| **None (deterministic rules)** | In-process, CPU-only | **All decisions + all text, by default** | Reproducible, injection-proof, p95 ≈ ms, zero cost, no API key. The spec explicitly allows rule-based solutions and an LLM is not required to score well. |
| **`gemini-3.5-flash`** *(primary, optional)* | Google Gemini API | Rephrase the 3 free-text fields only | First model tried when `USE_LLM=true` + `GEMINI_API_KEY` is set. Produces professional, context-aware summaries and customer replies. |
| **`gemini-2.0-flash-lite`** *(fallback 1)* | Google Gemini API | Same role as above | Tried automatically if the primary model returns HTTP 429 (quota/rate-limit). Sits under a separate free-tier quota. |
| **`gemini-1.5-flash-8b`** *(fallback 2)* | Google Gemini API | Same role as above | Last model in the chain before falling back to deterministic text. Smallest quota footprint. |

**Latency guarantee.** All three models share one 4-second deadline (`LLM_TIMEOUT_SECONDS`).
Quota errors (HTTP 429/413) come back in milliseconds, so switching models adds negligible
latency. A network timeout always stops the chain immediately — no retry — so total
wall-clock time is always bounded. The model chain is configurable via `LLM_FALLBACK_MODELS`.

**Cost reasoning.** The default configuration makes **zero external calls** and costs
nothing to run. The optional Gemini call is a quality enhancement, not a dependency;
decisions and safety never rely on it. The API key is supplied only through the
deployment environment (the Poridhi VM's `runtime.env` file) and never committed
to the repository.

## Deployment

The service is deployed on a **Poridhi VM** via GitHub Actions CI/CD
(`.github/workflows/ci-cd.yml`). On every push to `main`:

1. Tests run (`pytest -q`).
2. The Docker image is built and pushed to DockerHub as
   `rifathosain/queuestorm-investigator:latest`.
3. The workflow SSHes into the VM and calls `scripts/deploy_vm.sh`, which pulls
   the new image and restarts the container.

The Gemini API key and all LLM settings (`USE_LLM`, `GEMINI_API_KEY`, `MODEL_NAME`,
`LLM_FALLBACK_MODELS`, etc.) are configured directly in the VM's
`~/queuestorm-investigator/runtime.env` file — not as GitHub Secrets — so they
persist across deploys and are never written to CI logs or the repository.

## Assumptions

- Output is graded by **functional equivalence**, not exact string match (per the
  problem statement): the four key fields exact, `severity` comparable, a safe reply.
- `transaction_history` is small (2–5 entries) and amounts are whole BDT.
- A complaint amount that matches exactly one transaction identifies it; ties to
  different recipients are genuinely ambiguous and should not be guessed.
- "High value" for unconditional human review is ≥ 50,000 BDT (kept above the
  largest public sample, 15,000, so the rule is purely additive).

## Known limitations

- Transaction matching keys primarily on **amount** (plus type/recipient signals);
  a complaint that states no amount and is vague returns `insufficient_data` by
  design rather than guessing.
- Inconsistency detection covers the documented "established recipient" pattern;
  other contradictions default to `consistent` to avoid false accusations.
- Bangla NLP is keyword/heuristic-based in the default path; optional Gemini
  polish can improve wording nuance if enabled.
- `confidence` is a heuristic calibration, not a probabilistic estimate.

## Repository layout
```
app/            FastAPI service
  main.py         endpoints + error handling
  schemas.py      request/response models + the 8 enums
  reasoning.py    the investigator (evidence reasoning)
  replies.py      EN/BN reply + next-action templates
  safety.py       deterministic safety guardrails
  normalize.py    Bangla digits, amount extraction, language detection
  llm.py          optional Gemini polish with model fallback chain
  config.py       env-var configuration
tests/          41 tests incl. all 10 public sample cases
scripts/        smoke_test.py (black-box) + deploy_vm.sh + sample-output generator
Dockerfile, docker-compose.yml, requirements*.txt, .env.example
RUNBOOK.md      copy-paste deploy/run steps
sample_output.json   service output for all 10 public cases
```
