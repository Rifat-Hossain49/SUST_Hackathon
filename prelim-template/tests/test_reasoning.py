from app.reasoning import analyze
from app.schemas import AnalyzeRequest, Decision, RiskLevel


def test_standard_issue_proceeds():
    out = analyze(AnalyzeRequest(customer_message="I was double charged for one payment",
                                 transaction={"amount": 500}))
    assert out["decision"] in (Decision.APPROVE, Decision.ESCALATE)
    assert out["risk_level"] in (RiskLevel.MEDIUM, RiskLevel.HIGH)
    assert out["evidence"]  # decision must be grounded in evidence


def test_fraud_is_high_risk_and_escalated():
    out = analyze(AnalyzeRequest(customer_message="This is fraud, I never authorized it"))
    assert out["decision"] == Decision.ESCALATE
    assert out["risk_level"] == RiskLevel.HIGH
    assert out["escalate_to_human"] is True


def test_high_amount_is_high_risk():
    out = analyze(AnalyzeRequest(customer_message="payment issue", transaction={"amount": 200000}))
    assert out["risk_level"] == RiskLevel.HIGH


def test_empty_needs_more_info():
    out = analyze(AnalyzeRequest())
    assert out["decision"] == Decision.NEEDS_MORE_INFO
    assert out["escalate_to_human"] is True  # low confidence -> human


def test_low_confidence_routes_to_human():
    out = analyze(AnalyzeRequest(customer_message="hello"))
    assert out["confidence"] < 0.55
    assert out["escalate_to_human"] is True
