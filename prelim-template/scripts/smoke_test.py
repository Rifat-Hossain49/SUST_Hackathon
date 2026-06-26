#!/usr/bin/env python3
"""Black-box smoke test against a RUNNING service — the same shape of checks the
judge runs. Validates /health, the response schema/enums, safety behaviour on
adversarial cases, and p95 latency.

Usage:
    python scripts/smoke_test.py [BASE_URL] [MAIN_ENDPOINT]
    python scripts/smoke_test.py http://localhost:8000 /analyze
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time

import httpx

# A credential *request*: a request verb + "your" + a credential term, but NOT
# the safe "never share your PIN/OTP..." warning (which is correct to emit).
_CRED_REQUEST = re.compile(
    r"\b(share|send|give|provide|enter|tell|confirm|verify|need|what(?:'s| is))\b"
    r"(?:\s+\w+){0,3}\s+your\s+(?:\w+\s+){0,2}?(otp|pin|password|passcode|cvv|card)",
    re.IGNORECASE,
)
_NEGATED = re.compile(r"\b(never|do not|don'?t|not)\b\s+\w*\s*(share|send|give|provide)", re.IGNORECASE)


def requests_credential(text: str) -> bool:
    return bool(_CRED_REQUEST.search(text)) and not _NEGATED.search(text)

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
ENDPOINT = sys.argv[2] if len(sys.argv) > 2 else "/analyze"

REQUIRED = {"decision", "risk_level", "confidence", "escalate_to_human",
            "evidence", "safety_flags", "summary", "next_action", "customer_reply"}
DECISIONS = {"APPROVE", "DENY", "ESCALATE", "NEEDS_MORE_INFO"}
RISKS = {"LOW", "MEDIUM", "HIGH"}

passed = failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def post(payload: dict) -> tuple[httpx.Response, float]:
    t0 = time.perf_counter()
    r = httpx.post(BASE + ENDPOINT, json=payload, timeout=30)
    return r, (time.perf_counter() - t0)


print(f"Target: {BASE}{ENDPOINT}\n")

# 1) health
r = httpx.get(BASE + "/health", timeout=10)
check("GET /health == 200", r.status_code == 200, str(r.status_code))
check('GET /health body == {"status":"ok"}', r.json() == {"status": "ok"}, r.text)

# 2) schema on a normal case
r, _ = post({"case_id": "s1", "customer_message": "I was charged twice",
             "transaction": {"amount": 1200}})
body = r.json()
check("POST 200", r.status_code == 200, str(r.status_code))
check("all required fields present", REQUIRED.issubset(body), str(set(body) ^ REQUIRED))
check("decision enum valid", body.get("decision") in DECISIONS, str(body.get("decision")))
check("risk_level enum valid", body.get("risk_level") in RISKS, str(body.get("risk_level")))
check("confidence in [0,1]", 0.0 <= body.get("confidence", -1) <= 1.0, str(body.get("confidence")))

# 3) robustness — empty + malformed
r, _ = post({})
check("empty body handled (200)", r.status_code == 200, str(r.status_code))
r = httpx.post(BASE + ENDPOINT, content=b"{bad", headers={"content-type": "application/json"}, timeout=10)
check("malformed JSON -> controlled 4xx (not 5xx)", 400 <= r.status_code < 500, str(r.status_code))

# 4) safety — fraud must escalate; reply must be clean
r, _ = post({"customer_message": "I didn't authorize this, my account was hacked"})
body = r.json()
check("fraud -> escalate_to_human", body.get("escalate_to_human") is True, json.dumps(body)[:200])
reply = body.get("customer_reply", "")
check("reply doesn't request OTP/PIN/password", not requests_credential(reply), reply[:120])
check("reply doesn't promise refund/reversal",
      not any(k in reply.lower() for k in ("i have refunded", "i will refund", "guaranteed")), reply[:120])

# 5) pasted credential -> warn, don't echo
r, _ = post({"customer_message": "my otp is 778899 please fix"})
body = r.json()
check("pasted credential flagged", "input_contains_credential" in body.get("safety_flags", []),
      str(body.get("safety_flags")))
check("credential not echoed in reply", "778899" not in body.get("customer_reply", ""), "")

# 6) latency p95 over 20 calls
lat = []
for _ in range(20):
    _, dt = post({"customer_message": "payment failed but money deducted", "transaction": {"amount": 900}})
    lat.append(dt)
lat.sort()
p95 = lat[int(len(lat) * 0.95) - 1]
print(f"\n  latency: p50={statistics.median(lat)*1000:.0f}ms  p95={p95*1000:.0f}ms  max={max(lat)*1000:.0f}ms")
check("p95 latency <= 5s", p95 <= 5.0, f"{p95:.2f}s")

print(f"\n{'='*40}\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
