"""Deterministic safety guardrails (Safety & Escalation — 20 pts, hard rules).

These run on the final customer-facing reply, regardless of whether the text came
from the rule templates or the optional LLM. Rules are deterministic so safety is
never traded for a model's confidence. Penalties they prevent (from the rubric):

  * asking for PIN/OTP/password/full card number .......... -15
  * confirming an unauthorized refund/reversal/unblock ..... -10
  * directing the customer to a suspicious third party ...... -10
  * 2+ critical violations across hidden cases ............. NOT eligible for top-40

Design notes:
  * Credential detection is NEGATION-AWARE in both English and Bangla, because
    every safe reply *proactively* warns "do not share your PIN or OTP" — that
    warning must pass, while an actual request ("send your OTP") must be blocked.
  * The refund-promise blocker targets customer-facing COMMITMENTS ("we will
    refund you", "your refund has been processed") and deliberately allows the
    sanctioned phrasing "any eligible amount will be returned through official
    channels" and internal operational steps ("initiate the reversal flow").
"""
from __future__ import annotations

import re

# --------------------------- credential terms ------------------------------
# English + Bangla secret-credential vocabulary we must never request.
_CREDENTIAL_TERMS = re.compile(
    r"(?:\b(?:pin|otp|one[\s-]?time[\s-]?(?:password|code|pin)|password|passcode|"
    r"cvv|cvc|card\s*number|full\s*card|security\s*code|secret\s*code|"
    r"mpin|tpin|login\s*code|verification\s*code)\b"
    r"|পিন|ওটিপি|পাসওয়ার্ড|গোপন\s*(?:নম্বর|কোড|পিন)|সিকিউরিটি\s*কোড)",
    re.IGNORECASE,
)
# Verbs that, near a credential term, mean we are *requesting* it (EN + BN).
_REQUEST_VERBS = re.compile(
    r"(?:\b(?:share|send|give|provide|tell|enter|type|confirm|verify|ask(?:ing)?|"
    r"reply\s+with|what(?:'s| is)\s+your|need\s+your|provide\s+me)\b"
    r"|শেয়ার|দিন|দাও|বলুন|বলো|পাঠান|লিখুন|জানান|প্রদান)",
    re.IGNORECASE,
)
# English negation (appears BEFORE the verb: "never share", "do not send").
_NEG_EN = re.compile(r"\b(never|do\s+not|don'?t|not|avoid|without)\b", re.IGNORECASE)
# Bangla negation particle (appears AFTER the verb: "শেয়ার করবেন না"). It must be
# a STANDALONE token — matching "না" as a substring would wrongly fire on common
# words like "আপনার" (your) / "ঘটনা" (event), disabling real detection.
_NEG_BN = re.compile(r"(?:^|[\s।,;:?])(না|নয়|নেই|কখনো|কখনই)(?:[\s।,;:?!]|$)")

# ----------------------- unauthorized promise ------------------------------
# Customer-facing commitments to a financial action we cannot authorize.
# NOTE: deliberately does NOT match "any eligible amount will be returned ..."
# nor operational phrasing like "initiate the reversal flow".
_UNAUTHORIZED_PROMISE = re.compile(
    r"\b(?:"
    r"we\s+(?:will|'ll|have|are\s+going\s+to)\s+(?:refund(?:ed)?|reverse[ds]?|unblock(?:ed)?|"
    r"return\s+your\s+money|credit\s+(?:you|your))|"
    r"i\s+(?:will|'ll|have|'ve)\s+(?:refund(?:ed)?|reverse[ds]?|unblock(?:ed)?|credited)|"
    r"your\s+(?:refund|money|account|balance)\s+(?:has|have|will)\s+(?:been\s+)?"
    r"(?:processed|refunded|reversed|credited|restored|unblocked|returned\s+to\s+you)|"
    r"(?:refund|reversal)\s+(?:has\s+been|is)\s+(?:approved|processed|confirmed|completed)|"
    r"you\s+will\s+(?:be\s+refunded|get\s+(?:a\s+)?(?:full\s+)?refund|receive\s+(?:a\s+)?refund)|"
    r"guaranteed?\s+refund|100%\s+(?:refund|guaranteed)"
    r")\b"
    r"|ফেরত\s*(?:দেব|দেবো|দিয়ে\s*দিয়েছি|দেওয়া\s*হয়েছে|দিচ্ছি)",
    re.IGNORECASE,
)

# ----------------------- suspicious channels -------------------------------
_URL = re.compile(r"https?://[^\s]+|\bwww\.[^\s]+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{8,}\d)(?!\w)")
_THIRD_PARTY = re.compile(
    r"\b(whatsapp|telegram|messenger|viber|imo|signal|gmail|yahoo|outlook|"
    r"google\s*form|click\s+(?:this|the|here)|dm\s+(?:me|us)|agent\s+number|"
    r"this\s+number|personal\s+number)\b",
    re.IGNORECASE,
)
# Long digit runs (card/account/OTP-like) to mask in logs.
_LONG_DIGITS = re.compile(r"\b\d{6,}\b")

# Flags surfaced in reason_codes / logs.
FLAG_REQUESTED_CREDENTIAL = "blocked_credential_request"
FLAG_UNAUTHORIZED_PROMISE = "blocked_unauthorized_promise"
FLAG_SUSPICIOUS_CHANNEL = "blocked_suspicious_channel"

SAFE_FALLBACK_REPLY_EN = (
    "Thank you for reaching out. We have logged your case and a support specialist "
    "will review it through official support channels. Please do not share your PIN, "
    "OTP, or password with anyone."
)
SAFE_FALLBACK_REPLY_BN = (
    "আপনার সাথে যোগাযোগ করার জন্য ধন্যবাদ। আমরা আপনার কেসটি নথিভুক্ত করেছি এবং একজন "
    "বিশেষজ্ঞ অফিসিয়াল চ্যানেলের মাধ্যমে এটি পর্যালোচনা করবেন। অনুগ্রহ করে কারো সাথে আপনার "
    "পিন, ওটিপি বা পাসওয়ার্ড শেয়ার করবেন না।"
)


def requests_credential(text: str) -> bool:
    """True if OUR text *asks* the customer for a secret credential (forbidden).

    A request verb near a credential term counts as a request — UNLESS negated
    ("never share your PIN", "শেয়ার করবেন না"), which is the safe warning we want.
    """
    if not text or not _CREDENTIAL_TERMS.search(text):
        return False
    for m in _CREDENTIAL_TERMS.finditer(text):
        window = text[max(0, m.start() - 70): m.end() + 40]
        vm = _REQUEST_VERBS.search(window)
        if not vm:
            continue
        # English negation precedes the verb ("never share"); Bangla negation
        # follows it ("শেয়ার করবেন না"). Check the relevant side for each.
        before = window[max(0, vm.start() - 24): vm.start()]
        after = window[vm.end(): vm.end() + 30]
        if _NEG_EN.search(before) or _NEG_BN.search(after):
            continue
        return True
    return False


def promises_unauthorized_action(text: str) -> bool:
    return bool(text) and bool(_UNAUTHORIZED_PROMISE.search(text))


def directs_to_suspicious_channel(text: str) -> bool:
    if not text:
        return False
    return bool(_URL.search(text) or _PHONE.search(text) or _THIRD_PARTY.search(text))


def redact_pii(text: str) -> str:
    """Mask long digit runs (cards/accounts/OTP) before logging."""
    return _LONG_DIGITS.sub("[REDACTED]", text) if text else text


def sanitize_reply(text: str, language: str = "en") -> tuple[str, list[str]]:
    """Validate a customer-facing reply. Returns (safe_text, flags).

    If any hard rule fires, the reply is REPLACED with a safe fallback (in the
    right language) so the service cannot emit an unsafe customer reply even if
    upstream logic or the optional LLM misbehaves.
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
        fallback = SAFE_FALLBACK_REPLY_BN if language == "bn" else SAFE_FALLBACK_REPLY_EN
        return fallback, flags
    return (text or "").strip(), flags
