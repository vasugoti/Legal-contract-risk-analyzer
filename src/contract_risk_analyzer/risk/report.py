from __future__ import annotations

from collections import Counter
from typing import Any

from contract_risk_analyzer.config.settings import load_yaml
from contract_risk_analyzer.data.schemas import Clause, ClausePrediction, RiskFlag, RiskReport
from contract_risk_analyzer.risk.rules import detect_risk_flags
from contract_risk_analyzer.risk.scoring import (
    SEVERITY_ORDER,
    calculate_overall_risk_score,
    calculate_risk_score,
    severity_breakdown,
)


def _build_recommendations(flags: list[RiskFlag], config: dict[str, Any]) -> list[str]:
    gen_recs = config.get("general_recommendations", {})
    if not flags:
        no_flags_msg = gen_recs.get(
            "no_flags",
            "No configured risk indicators were detected. A quick human review is still recommended.",
        )
        return [str(no_flags_msg)] if isinstance(no_flags_msg, str) else list(no_flags_msg)

    # Sort critical -> high -> medium -> low
    order_map = {s: i for i, s in enumerate(reversed(SEVERITY_ORDER))}  # critical: 0, high: 1, ...
    sorted_flags = sorted(flags, key=lambda f: order_map.get(str(f.severity).lower(), 99))

    recs: list[str] = []
    seen_recs: set[str] = set()

    for f in sorted_flags:
        rec = (f.recommendation or "").strip()
        if rec and rec not in seen_recs:
            seen_recs.add(rec)
            recs.append(rec)

    # Followed by general_recommendations.always
    always_list = gen_recs.get("always", [])
    for alw in always_list:
        alw_str = str(alw).strip()
        if alw_str and alw_str not in seen_recs:
            seen_recs.add(alw_str)
            recs.append(alw_str)

    return recs


def generate_risk_report(
    document_id: str,
    clauses: list[Clause],
    predictions: list[ClausePrediction],
    config_path: str = "configs/risk_rules.yaml",
) -> RiskReport:
    config = load_yaml(config_path)
    flags = detect_risk_flags(clauses, predictions, config_path=config_path)
    label_counts = Counter(prediction.predicted_label for prediction in predictions)

    total_clauses = len(clauses)
    score = calculate_overall_risk_score(flags, config_path=config_path, total_clauses=total_clauses)
    breakdown = calculate_risk_score(flags, total_clauses=total_clauses, config=config)

    summary = (
        f"Analyzed {total_clauses} clauses and detected {len(flags)} potential risk indicators. "
        "Findings require human review."
    )

    band = breakdown.band or {}
    risk_level = band.get("name")
    risk_color = band.get("color")
    risk_action = band.get("action")

    return RiskReport(
        document_id=document_id,
        summary=summary,
        total_clauses=total_clauses,
        predicted_clause_types=dict(label_counts),
        risk_flags=flags,
        overall_risk_score=score,
        severity_breakdown=severity_breakdown(flags),
        recommendations=_build_recommendations(flags, config),
        disclaimer=str(config.get("disclaimer", "")),
        risk_level=risk_level,
        risk_color=risk_color,
        risk_action=risk_action,
        worst_severity=breakdown.worst_severity,
        category_breakdown=breakdown.categories,
    )
