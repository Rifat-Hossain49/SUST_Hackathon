"""Text + number normalization, including Bangla support.

The investigator must read English, Bangla, and mixed "Banglash" complaints. Two
things matter for matching the complaint to a transaction:
  1. Bangla numerals (৫০০০) must be read as 5000 so amounts can be compared.
  2. We must extract plausible *amounts* from free text without mistaking phone
     numbers, account IDs, or timestamps for amounts.
"""
from __future__ import annotations

import re

# Bangla (Bengali) digits ০১২৩৪৫৬৭৮৯ -> 0-9
_BN_DIGITS = {ord(b): a for b, a in zip("০১২৩৪৫৬৭৮৯", "0123456789")}
# Any character in the Bengali Unicode block.
_BANGLA_RE = re.compile(r"[ঀ-৿]")
# A run of digits, after comma-stripping. We cap length to avoid phone/account ids.
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def normalize_digits(text: str) -> str:
    """Map Bangla numerals to ASCII digits. Leaves everything else untouched."""
    return text.translate(_BN_DIGITS) if text else text


def contains_bangla(text: str) -> bool:
    return bool(text) and bool(_BANGLA_RE.search(text))


def reply_language(declared: str | None, complaint: str) -> str:
    """Which language to answer in. Prefer the script actually used in the
    complaint (so a Bangla complaint always gets a Bangla reply, per the spec),
    then the declared language, else English."""
    if contains_bangla(complaint):
        return "bn"
    if declared and declared.strip().lower() == "bn":
        return "bn"
    return "en"


def normalize_text(text: str) -> str:
    """Lowercased, Bangla-digits-normalized text for keyword matching."""
    return normalize_digits(text or "").lower()


def extract_amounts(text: str) -> set[float]:
    """Plausible monetary amounts mentioned in the complaint.

    Strategy: normalize Bangla digits, strip thousands separators, then take
    numeric tokens of at most 6 digits (longer runs are phone numbers / account
    or transaction IDs, never amounts). Matching is later done against the actual
    transaction amounts, so an incidental small number (e.g. "2pm") is harmless
    unless a real transaction happens to equal it.
    """
    if not text:
        return set()
    t = normalize_digits(text)
    t = re.sub(r"(?<=\d),(?=\d)", "", t)  # 15,000 -> 15000
    out: set[float] = set()
    for m in _NUM_RE.finditer(t):
        # Skip tokens glued to other digits via separators that signal an ID
        # (e.g. inside +8801719876543 the long run is already one token).
        whole = m.group()
        int_part = whole.split(".")[0]
        if len(int_part) > 6:  # phone / account / id, not an amount
            continue
        try:
            out.add(float(whole))
        except ValueError:
            continue
    return out
