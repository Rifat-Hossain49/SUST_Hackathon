from app import safety
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
EP = settings.MAIN_ENDPOINT


# --- unit-level guardrails --------------------------------------------------
def test_blocks_credential_request():
    bad = "To verify, please share your OTP and PIN with me."
    safe, flags = safety.sanitize_reply(bad)
    assert safety.FLAG_REQUESTED_CREDENTIAL in flags
    # The unsafe request is replaced wholesale with the safe fallback (which may
    # mention OTP/PIN only inside a "never share these" warning).
    assert safe == safety.SAFE_FALLBACK_REPLY
    assert "share your otp" not in safe.lower()


def test_blocks_unauthorized_promise():
    bad = "Good news — I have refunded your money and reversed the charge."
    safe, flags = safety.sanitize_reply(bad)
    assert safety.FLAG_UNAUTHORIZED_PROMISE in flags
    assert safe == safety.SAFE_FALLBACK_REPLY


def test_blocks_suspicious_channel():
    bad = "Please message us on WhatsApp at +8801712345678 or click http://bit.ly/x"
    safe, flags = safety.sanitize_reply(bad)
    assert safety.FLAG_SUSPICIOUS_CHANNEL in flags


def test_allows_clean_reply():
    good = "We've logged your case and a specialist will review it via the official app."
    safe, flags = safety.sanitize_reply(good)
    assert flags == []
    assert safe == good


def test_never_share_warning_is_not_flagged_as_request():
    # The safe warning contains "share" near "PIN/OTP" but is negated — must pass.
    warn = ("Thanks. For your security, never share your PIN, OTP, or password "
            "with anyone. Could you share the transaction ID and date?")
    assert not safety.requests_credential(warn)
    safe, flags = safety.sanitize_reply(warn)
    assert safety.FLAG_REQUESTED_CREDENTIAL not in flags
    assert safe == warn.strip()


def test_redacts_pii():
    assert safety.redact_pii("card 4111111111111111 otp 123456") == "card [REDACTED] otp [REDACTED]"


def test_input_credential_detected():
    assert safety.input_has_credential("my otp is 483920")
    assert not safety.input_has_credential("my transaction failed")


# --- end-to-end: fraud case must escalate, never auto-approve ---------------
def test_fraud_case_escalates_and_reply_is_safe():
    r = client.post(EP, json={"case_id": "f1",
                              "customer_message": "I didn't make this transaction, my account was hacked!"})
    body = r.json()
    assert body["escalate_to_human"] is True
    assert body["decision"] == "ESCALATE"
    # reply must not request credentials or promise unauthorized action
    reply = body["customer_reply"].lower()
    assert "your otp" not in reply
    assert "i have refunded" not in reply


def test_pasted_credential_triggers_warning_not_echo():
    r = client.post(EP, json={"customer_message": "my pin is 1234 and otp 998877, help"})
    body = r.json()
    assert safety.FLAG_INPUT_CREDENTIAL in body["safety_flags"]
    assert "1234" not in body["customer_reply"]
    assert body["escalate_to_human"] is True
