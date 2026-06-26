"""Deterministic text templates for the three free-text fields.

`customer_reply` is bilingual (English / Bangla) and switches to match the
complaint's language. `recommended_next_action` stays English because it is
internal guidance for the support agent (the public samples keep it English even
for a Bangla complaint — see SAMPLE-07).

Every customer reply is pre-vetted against the Section 8 safety rules:
  * proactively warns "do not share your PIN/OTP" (a negated, safe mention),
  * never promises a refund — uses "any eligible amount will be returned through
    official channels",
  * directs only to official channels.
"""
from __future__ import annotations

from .schemas import CaseType, EvidenceVerdict

_PIN_WARN_EN = "Please do not share your PIN or OTP with anyone."
_PIN_WARN_BN = "অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
_ELIGIBLE_EN = "any eligible amount will be returned through official channels"
_ELIGIBLE_BN = "প্রযোজ্য যেকোনো পরিমাণ অফিসিয়াল চ্যানেলের মাধ্যমে ফেরত দেওয়া হবে"


# ----------------------------- customer_reply ------------------------------
def customer_reply(case_type: CaseType, verdict: EvidenceVerdict,
                   txn_id: str | None, language: str = "en") -> str:
    bn = language == "bn"
    t = txn_id  # may be None
    ct = case_type

    if ct is CaseType.PHISHING_OR_SOCIAL_ENGINEERING:
        if bn:
            return ("কোনো তথ্য শেয়ার করার আগে যোগাযোগ করার জন্য ধন্যবাদ। আমরা কখনোই আপনার পিন, "
                    "ওটিপি বা পাসওয়ার্ড চাই না। কেউ নিজেকে আমাদের প্রতিনিধি দাবি করলেও এগুলো কারো "
                    "সাথে শেয়ার করবেন না। আমাদের ফ্রড টিমকে বিষয়টি জানানো হয়েছে।")
        return ("Thank you for reaching out before sharing any information. We never ask for "
                "your PIN, OTP, or password under any circumstances. Please do not share these "
                "with anyone, even if they claim to be from us. Our fraud team has been notified "
                "of this incident.")

    if ct is CaseType.WRONG_TRANSFER:
        if t:
            if bn:
                return (f"আপনার লেনদেন {t} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের ডিসপিউট টিম কেসটি "
                        f"পর্যালোচনা করে অফিসিয়াল সাপোর্ট চ্যানেলের মাধ্যমে আপনার সাথে যোগাযোগ করবে। "
                        f"{_PIN_WARN_BN}")
            return (f"We have noted your concern about transaction {t}. Our dispute team will "
                    f"review the case and contact you through official support channels. {_PIN_WARN_EN}")
        if bn:
            return ("আপনার বর্ণনার সাথে একাধিক লেনদেন মিলতে পারে। সঠিক লেনদেনটি শনাক্ত করতে অনুগ্রহ "
                    f"করে প্রাপকের নম্বরটি জানান। {_PIN_WARN_BN}")
        return ("Thank you for reaching out. We can see more than one transaction that could "
                "match your description. Could you share the recipient's number so we can "
                f"identify the correct transaction? {_PIN_WARN_EN}")

    if ct is CaseType.PAYMENT_FAILED:
        if bn:
            ref = f"লেনদেন {t}" if t else "ব্যর্থ লেনদেনটি"
            return (f"{ref} এর কারণে অনাকাঙ্ক্ষিতভাবে ব্যালেন্স কেটে নেওয়া হয়ে থাকতে পারে বলে আমরা "
                    f"অবগত হয়েছি। আমাদের পেমেন্ট টিম কেসটি পর্যালোচনা করবে এবং {_ELIGIBLE_BN}। {_PIN_WARN_BN}")
        ref = f"transaction {t}" if t else "the failed payment you reported"
        return (f"We have noted that {ref} may have caused an unexpected balance deduction. "
                f"Our payments team will review the case and {_ELIGIBLE_EN}. {_PIN_WARN_EN}")

    if ct is CaseType.DUPLICATE_PAYMENT:
        if bn:
            ref = f"লেনদেন {t}" if t else "সম্ভাব্য ডুপ্লিকেট পেমেন্টটি"
            return (f"{ref} এর জন্য একটি সম্ভাব্য ডুপ্লিকেট পেমেন্ট আমরা চিহ্নিত করেছি। আমাদের পেমেন্ট "
                    f"টিম বিলারের সাথে যাচাই করবে এবং {_ELIGIBLE_BN}। {_PIN_WARN_BN}")
        ref = f"transaction {t}" if t else "the possible duplicate payment"
        return (f"We have noted the possible duplicate payment for {ref}. Our payments team will "
                f"verify with the biller and {_ELIGIBLE_EN}. {_PIN_WARN_EN}")

    if ct is CaseType.REFUND_REQUEST:
        if bn:
            return ("যোগাযোগ করার জন্য ধন্যবাদ। সম্পন্ন হওয়া মার্চেন্ট পেমেন্টের রিফান্ড মার্চেন্টের "
                    "নিজস্ব নীতির উপর নির্ভর করে, তাই অনুগ্রহ করে অফিসিয়াল চ্যানেলের মাধ্যমে সরাসরি "
                    f"মার্চেন্টের সাথে যোগাযোগ করুন। সাহায্য প্রয়োজন হলে আমাদের জানান। {_PIN_WARN_BN}")
        return ("Thank you for reaching out. Refunds for completed merchant payments depend on "
                "the merchant's own policy, so we recommend contacting the merchant directly "
                f"through official channels. If you need help reaching them, please reply and we "
                f"will guide you. {_PIN_WARN_EN}")

    if ct is CaseType.MERCHANT_SETTLEMENT_DELAY:
        if bn:
            ref = f"সেটেলমেন্ট {t}" if t else "বিলম্বিত সেটেলমেন্টের"
            return (f"{ref} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের মার্চেন্ট অপারেশন্স টিম ব্যাচ স্ট্যাটাস "
                    "যাচাই করে অফিসিয়াল চ্যানেলের মাধ্যমে প্রত্যাশিত সেটেলমেন্ট সময় জানাবে।")
        ref = f"settlement {t}" if t else "the delayed settlement"
        return (f"We have noted your concern about {ref}. Our merchant operations team will check "
                "the batch status and update you on the expected settlement time through official "
                "channels.")

    if ct is CaseType.AGENT_CASH_IN_ISSUE:
        if bn:
            ref = f"লেনদেন {t}" if t else "ক্যাশ-ইন লেনদেনটি"
            return (f"{ref} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল এটি দ্রুত যাচাই "
                    f"করবে এবং অফিসিয়াল চ্যানেলের মাধ্যমে আপনাকে জানাবে। {_PIN_WARN_BN}")
        ref = f"transaction {t}" if t else "the cash-in you reported"
        return (f"We have noted your concern about {ref}. Our agent operations team will verify it "
                f"quickly and update you through official support channels. {_PIN_WARN_EN}")

    # other / vague / insufficient
    if bn:
        return ("যোগাযোগ করার জন্য ধন্যবাদ। দ্রুত সাহায্য করতে অনুগ্রহ করে লেনদেন আইডি, সংশ্লিষ্ট "
                f"পরিমাণ এবং সমস্যাটির সংক্ষিপ্ত বিবরণ জানান। {_PIN_WARN_BN}")
    return ("Thank you for reaching out. To help you faster, please share the transaction ID, the "
            f"amount involved, and a short description of what went wrong. {_PIN_WARN_EN}")


# ------------------------- recommended_next_action -------------------------
def next_action(case_type: CaseType, verdict: EvidenceVerdict, txn_id: str | None) -> str:
    t = txn_id or "the relevant transaction"
    ct = case_type

    if ct is CaseType.PHISHING_OR_SOCIAL_ENGINEERING:
        return ("Escalate to the fraud_risk team immediately. Confirm to the customer that the "
                "company never asks for OTP. Log the reported number for fraud pattern analysis.")
    if ct is CaseType.WRONG_TRANSFER:
        if verdict is EvidenceVerdict.INCONSISTENT:
            return ("Flag for human review. Verify with the customer whether this was genuinely a "
                    "wrong transfer, given the established transaction pattern with this recipient.")
        if verdict is EvidenceVerdict.INSUFFICIENT_DATA:
            return ("Reply to the customer to identify the correct transaction (recipient number, "
                    "amount, time). Do not initiate a dispute until the transaction is confirmed.")
        return (f"Verify {t} details with the customer and initiate the wrong-transfer dispute "
                "workflow per policy.")
    if ct is CaseType.PAYMENT_FAILED:
        return (f"Investigate {t} ledger status. If the balance was deducted on a failed payment, "
                "initiate the automatic reversal flow within standard SLA.")
    if ct is CaseType.DUPLICATE_PAYMENT:
        return (f"Verify the suspected duplicate with payments_ops. If the biller confirms only one "
                f"payment was received, initiate reversal of {t} per policy.")
    if ct is CaseType.REFUND_REQUEST:
        return ("Inform the customer that refund eligibility depends on the merchant's policy. "
                "Provide guidance on contacting the merchant directly for a refund.")
    if ct is CaseType.MERCHANT_SETTLEMENT_DELAY:
        return ("Route to merchant_operations to verify the settlement batch status. If the batch "
                "is delayed, communicate a revised ETA to the merchant.")
    if ct is CaseType.AGENT_CASH_IN_ISSUE:
        return (f"Investigate {t} pending status with agent operations. Confirm the settlement "
                "state and resolve within the standard cash-in SLA.")
    return ("Reply to the customer asking for specific details: which transaction, what amount, "
            "what went wrong, and the approximate time.")
