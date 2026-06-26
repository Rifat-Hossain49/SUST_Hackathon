"""Black-box smoke test — exercises a RUNNING service the way the judge harness
will. Validates /health, schema + enum correctness, the evidence-reasoning fields
against the public expected outputs, the Section 8 safety rules, malformed-input
handling, and p95 latency.

Usage:
    python scripts/smoke_test.py [BASE_URL]
    python scripts/smoke_test.py http://localhost:8000
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
EP = BASE + "/analyze-ticket"
ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests" / "data" / "sample_cases.json").read_text("utf-8"))["cases"]

ENUMS = {
    "evidence_verdict": {"consistent", "inconsistent", "insufficient_data"},
    "case_type": {"wrong_transfer", "payment_failed", "refund_request", "duplicate_payment",
                  "merchant_settlement_delay", "agent_cash_in_issue",
                  "phishing_or_social_engineering", "other"},
    "severity": {"low", "medium", "high", "critical"},
    "department": {"customer_support", "dispute_resolution", "payments_ops",
                   "merchant_operations", "agent_operations", "fraud_risk"},
}
REQUIRED = ["ticket_id", "relevant_transaction_id", "evidence_verdict", "case_type", "severity",
            "department", "agent_summary", "recommended_next_action", "customer_reply",
            "human_review_required"]

# Use the service's own negation-aware safety logic when the package is importable
# (run from the repo root). This correctly treats a "do NOT share your PIN/OTP"
# warning as safe, unlike a naive substring scan. Falls back to a simple heuristic
# for pure remote use where the package is not on the path.
sys.path.insert(0, str(ROOT))
try:
    from app import safety as _safety

    def asks_credential(r): return _safety.requests_credential(r)
    def bad_promise(r): return _safety.promises_unauthorized_action(r)
    def bad_channel(r): return _safety.directs_to_suspicious_channel(r)
except Exception:
    import re as _re
    _REQ = _re.compile(r"(?<!not )(?<!never )(?:share|send|enter|provide|give|tell us)\s+your\s+"
                       r"(?:pin|otp|password)", _re.I)
    _PROM = _re.compile(r"\b(we will refund you|your refund has been processed|i have refunded|"
                        r"we have refunded|you will get a full refund|i have reversed)\b", _re.I)
    _CHAN = _re.compile(r"https?://|whatsapp|telegram", _re.I)

    def asks_credential(r): return bool(_REQ.search(r))
    def bad_promise(r): return bool(_PROM.search(r))
    def bad_channel(r): return bool(_CHAN.search(r))

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def main():
    print(f"Target: {BASE}")
    # 1. health
    try:
        r = httpx.get(BASE + "/health", timeout=10)
        check("GET /health == {'status':'ok'}", r.status_code == 200 and r.json() == {"status": "ok"},
              f"got {r.status_code} {r.text[:80]}")
    except Exception as e:
        check("GET /health reachable", False, str(e))
        print("Service unreachable; aborting."); sys.exit(1)

    latencies = []
    for c in CASES:
        cid, exp = c["id"], c["expected_output"]
        t0 = time.perf_counter()
        r = httpx.post(EP, json=c["input"], timeout=35)
        latencies.append(time.perf_counter() - t0)
        if r.status_code != 200:
            check(f"{cid} status 200", False, f"got {r.status_code}"); continue
        b = r.json()
        check(f"{cid} ticket_id echoed", b.get("ticket_id") == c["input"]["ticket_id"])
        check(f"{cid} all required fields", all(k in b for k in REQUIRED),
              f"missing {[k for k in REQUIRED if k not in b]}")
        check(f"{cid} enums valid",
              all(b.get(k) in ENUMS[k] for k in ENUMS), {k: b.get(k) for k in ENUMS})
        # Evidence reasoning (functional equivalence on the graded fields)
        check(f"{cid} relevant_transaction_id", b.get("relevant_transaction_id") == exp["relevant_transaction_id"],
              f"got {b.get('relevant_transaction_id')} want {exp['relevant_transaction_id']}")
        check(f"{cid} evidence_verdict", b.get("evidence_verdict") == exp["evidence_verdict"],
              f"got {b.get('evidence_verdict')} want {exp['evidence_verdict']}")
        check(f"{cid} case_type", b.get("case_type") == exp["case_type"],
              f"got {b.get('case_type')} want {exp['case_type']}")
        check(f"{cid} department", b.get("department") == exp["department"],
              f"got {b.get('department')} want {exp['department']}")
        check(f"{cid} severity", b.get("severity") == exp["severity"],
              f"got {b.get('severity')} want {exp['severity']}")
        check(f"{cid} human_review_required", b.get("human_review_required") == exp["human_review_required"],
              f"got {b.get('human_review_required')} want {exp['human_review_required']}")
        # Safety (negation-aware)
        reply = b.get("customer_reply") or ""
        check(f"{cid} reply has no credential request", not asks_credential(reply))
        check(f"{cid} reply makes no unauthorized promise", not bad_promise(reply))
        check(f"{cid} reply uses official channels only", not bad_channel(reply))

    # malformed input handling
    r = httpx.post(EP, content=b"{bad json", headers={"content-type": "application/json"}, timeout=10)
    check("malformed JSON -> 4xx (no crash)", 400 <= r.status_code < 500, f"got {r.status_code}")
    r = httpx.post(EP, json={"ticket_id": "X"}, timeout=10)
    check("missing complaint -> 400", r.status_code == 400, f"got {r.status_code}")
    r = httpx.post(EP, json={"ticket_id": "X", "complaint": "  "}, timeout=10)
    check("empty complaint -> 422", r.status_code == 422, f"got {r.status_code}")

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1] * 1000
    p50 = latencies[len(latencies) // 2] * 1000
    print(f"\nlatency: p50={p50:.0f}ms  p95={p95:.0f}ms  max={max(latencies)*1000:.0f}ms  (full credit <= 5000ms)")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
