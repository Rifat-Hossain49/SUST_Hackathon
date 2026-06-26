"""Deterministic safety guardrails (Safety & Escalation — 20 pts, hard rules).

These run on EVERY generated customer-facing string, regardless of whether the
text came from the rule engine or the LLM. Rules are deterministic so safety is
never traded for an LLM's confidence. Penalties they prevent (from the rubric):
  * asking for PIN/OTP/password/credentials .......... -15
  * promising unauthorized / irreversible actions .... -10
  * directing users to suspicious third parties ....... -10

`sanitize_reply()` returns (safe_text, flags). If the text trips a hard rule it
is replaced with a safe fallback rather than patched, so nothing unsafe leaks.
"""
from __future__ import annotations

import re

# --- Patterns -------------------------------------------------------------
# Secret credentials we must NEVER request (and must warn users not to share).
_CREDENTIAL_TERMS = re.compile(
    r"\b(pin|otp|one[\s-]?time[\s-]?(?:password|code|pin)|password|passcode|"
    r"cvv|cvc|card\s*number|full\s*card|security\s*code|secret|"
    r"mpin|tpin|login\s*code|verification\s*code)\b",
    re.IGNORECASE,
)
# Verbs that, near a credential term, mean we are *requesting* it.
_REQUEST_VERBS = re.compile(
    r"\b(share|send|give|provide|tell|enter|type|confirm|verify|reply\s+with|"
    r"what(?:'s| is)\s+your|need\s+your|provide\s+me)\b",
    re.IGNORECASE,
)
# Negation that turns a request verb into a safe warning ("never share your PIN").
_NEGATION = re.compile(r"\b(never|do\s+not|don'?t|not|avoid)\b", re.IGNORECASE)
# Claims of having performed an action the copilot has no authority to perform.
_UNAUTHORIZED_PROMISE = re.compile(
    r"\b(i\s+have\s+(?:refunded|reversed|cancelled|canceled|unblocked|unlocked|"
    r"reset|approved|processed|credited|charged|deleted)|"
    r"your\s+(?:refund|money|account)\s+(?:has|have)\s+been\s+"
    r"(?:processed|refunded|reversed|credited|restored|unblocked)|"
    r"i\s+(?:will|'ll)\s+(?:refund|reverse|unblock|guarantee|ensure)|"
    r"guaranteed?|rest\s+assured\s+(?:your|the)\s+(?:money|refund)|"
    r"100%\s+(?:safe|guaranteed|refund))\b",
    re.IGNORECASE,
)
# Suspicious / non-official contact channels.
_URL = re.compile(r"https?://[^\s]+|\bwww\.[^\s]+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_THIRD_PARTY = re.compile(
    r"\b(whatsapp|telegram|messenger|gmail|yahoo|outlook|google\s*form|"
    r"click\s+(?:this|the)\s+link|dm\s+(?:me|us)|agent\s+number)\b",
    re.IGNORECASE,
)
# PII to redact from logs and (defensively) from echoed text.
_LONG_DIGITS = re.compile(r"\b\d{6,}\b")  # card/account/OTP-like runs

# Flags
FLAG_INPUT_CREDENTIAL = "input_contains_credential"
FLAG_REQUESTED_CREDENTIAL = "blocked_credential_request"
FLAG_UNAUTHORIZED_PROMISE = "blocked_unauthorized_promise"
FLAG_SUSPICIOUS_CHANNEL = "blocked_suspicious_channel"

SAFE_FALLBACK_REPLY = (
    "Thanks for reaching out. We've logged your case and a support specialist "
    "will review it. For your security, never share your PIN, OTP, password, or "
    "full card number with anyone. If you need to act now, please use only the "
    "official bKash app or the verified helpline."
)


def input_has_credential(text: str) -> bool:
    """True if the *customer's* message appears to contain a secret credential.
    We must not echo it, and should warn the user not to share it."""
    return bool(text) and bool(_CREDENTIAL_TERMS.search(text)) and bool(
        re.search(r"\b\d{3,8}\b", text)
    )


def requests_credential(text: str) -> bool:
    """True if OUR text asks the customer for a secret credential (forbidden).

    A request verb near a credential term counts as a request — UNLESS it is
    negated ("never share your PIN", "do not send your OTP"), which is the safe
    warning we *want* to emit.
    """
    if not _CREDENTIAL_TERMS.search(text):
        return False
    for m in _CREDENTIAL_TERMS.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 20]
        vm = _REQUEST_VERBS.search(window)
        if not vm:
            continue
        # If a negation immediately precedes the request verb, it's a warning.
        prefix = window[max(0, vm.start() - 18): vm.start()]
        if _NEGATION.search(prefix):
            continue
        return True
    return False


def promises_unauthorized_action(text: str) -> bool:
    return bool(_UNAUTHORIZED_PROMISE.search(text))


def directs_to_suspicious_channel(text: str) -> bool:
    return bool(_URL.search(text) or _PHONE.search(text) or _THIRD_PARTY.search(text))


def redact_pii(text: str) -> str:
    """Mask long digit runs (cards/accounts/OTP) — use before logging."""
    if not text:
        return text
    return _LONG_DIGITS.sub("[REDACTED]", text)


def sanitize_reply(text: str) -> tuple[str, list[str]]:
    """Validate a customer-facing reply. Returns (safe_text, flags).

    If any hard rule fires, the text is replaced with a safe fallback so the
    service cannot emit an unsafe reply even if upstream logic misbehaves.
    """
    flags: list[str] = []
    unsafe = False

    if requests_credential(text):
        flags.append(FLAG_REQUESTED_CREDENTIAL)
        unsafe = True
    if promises_unauthorized_action(text):
        flags.append(FLAG_UNAUTHORIZED_PROMISE)
        unsafe = True
    if directs_to_suspicious_channel(text):
        flags.append(FLAG_SUSPICIOUS_CHANNEL)
        unsafe = True

    if unsafe:
        return SAFE_FALLBACK_REPLY, flags
    return text.strip(), flags
