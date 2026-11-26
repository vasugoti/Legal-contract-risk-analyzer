from __future__ import annotations

from contract_risk_analyzer.data.schemas import Clause, ClausePrediction, RiskFlag
from contract_risk_analyzer.risk.report import generate_risk_report
from contract_risk_analyzer.risk.scoring import (
    calculate_overall_risk_score,
    calculate_risk_score,
    load_config,
)


def _flag(
    severity: str,
    confidence: float,
    flag_type: str = "TEST",
    clause_id: str = "c1",
) -> RiskFlag:
    return RiskFlag(
        flag_id=f"{flag_type}-{clause_id}-{severity}-{confidence}",
        clause_id=clause_id,
        flag_type=flag_type,
        severity=severity,  # type: ignore[arg-type]
        reason="Potential risk indicator.",
        evidence_text="evidence",
        confidence=confidence,
    )


def test_no_flags_scores_zero() -> None:
    score = calculate_overall_risk_score([], total_clauses=50)
    assert score == 0.0
    report = generate_risk_report("doc-empty", [], [])
    assert report.overall_risk_score == 0.0
    assert report.total_clauses == 0
    assert report.risk_level == "Low"


def test_thousand_low_flags_score_leq_25() -> None:
    # 1000 low flags across 1000 clauses
    flags = [_flag("low", 0.9, flag_type=f"LOW_{i % 5}", clause_id=f"c{i}") for i in range(1000)]
    config = load_config("configs/risk_rules.yaml")
    breakdown = calculate_risk_score(flags, total_clauses=1000, config=config)
    assert breakdown.overall_score <= 25.0
    assert breakdown.ceiling == 25.0


def test_same_risks_in_10x_longer_contract_changes_by_less_than_10_points() -> None:
    flags = [
        _flag("medium", 0.85, flag_type="PAYMENT_RISK", clause_id="c1"),
        _flag("high", 0.90, flag_type="AUTO_RENEWAL", clause_id="c2"),
    ]
    score_short = calculate_overall_risk_score(flags, total_clauses=10)
    score_long = calculate_overall_risk_score(flags, total_clauses=100)
    assert abs(score_short - score_long) < 10.0


def test_any_critical_flag_scores_at_least_40() -> None:
    flags = [_flag("critical", 0.70, flag_type="UNLIMITED_LIABILITY", clause_id="c1")]
    score = calculate_overall_risk_score(flags, total_clauses=10)
    assert score >= 40.0


def test_score_stays_between_0_and_100() -> None:
    # Empty
    assert 0.0 <= calculate_overall_risk_score([], total_clauses=10) <= 100.0

    # Many critical flags
    critical_flags = [
        _flag("critical", 1.0, flag_type=f"CRIT_{i}", clause_id=f"c{i}")
        for i in range(50)
    ]
    score_high = calculate_overall_risk_score(critical_flags, total_clauses=50)
    assert 0.0 <= score_high <= 100.0


def test_multiple_high_severity_flags_increase_total_risk() -> None:
    one = calculate_overall_risk_score([_flag("critical", 0.9, flag_type="C1")])
    two = calculate_overall_risk_score([
        _flag("critical", 0.9, flag_type="C1"),
        _flag("high", 0.9, flag_type="H1"),
    ])
    assert two > one


def test_report_disclaimer_always_present() -> None:
    clause = Clause(clause_id="c1", text="Customer shall pay invoices.", source_document_id="d1")
    prediction = ClausePrediction(
        clause_id="c1",
        predicted_label="Payments",
        confidence=0.8,
        top_k_labels=[("Payments", 0.8)],
        model_name="test",
    )
    report = generate_risk_report("d1", [clause], [prediction])
    assert "not legal advice" in report.disclaimer.lower()
