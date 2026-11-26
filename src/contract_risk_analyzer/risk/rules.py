from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from contract_risk_analyzer.config.settings import load_yaml
from contract_risk_analyzer.data.schemas import Clause, ClausePrediction, RiskFlag

logger = logging.getLogger(__name__)


@dataclass
class RiskRule:
    flag_type: str
    severity: str
    title: str = ""
    labels: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    regex_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    require_pattern: bool = True
    min_confidence: float | None = None
    reason: str = "Potential risk indicator may require human review."
    recommendation: str = ""
    _compiled_patterns: list[re.Pattern[str]] = field(default_factory=list, init=False, repr=False)
    _compiled_regex: list[re.Pattern[str]] = field(default_factory=list, init=False, repr=False)
    _compiled_exclude: list[re.Pattern[str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled_patterns = [
            re.compile(rf"\b{re.escape(p)}\b", re.IGNORECASE) for p in self.patterns if p
        ]
        self._compiled_regex = [
            re.compile(p, re.IGNORECASE) for p in self.regex_patterns if p
        ]
        self._compiled_exclude = [
            re.compile(p, re.IGNORECASE) for p in self.exclude_patterns if p
        ]


def load_risk_config(config_path: str = "configs/risk_rules.yaml") -> dict[str, Any]:
    return load_yaml(config_path)


def load_rules(config_path: str = "configs/risk_rules.yaml") -> list[RiskRule]:
    config = load_risk_config(config_path)
    known_fields = {
        "flag_type",
        "severity",
        "title",
        "labels",
        "patterns",
        "regex_patterns",
        "exclude_patterns",
        "require_pattern",
        "min_confidence",
        "reason",
        "recommendation",
    }
    rules: list[RiskRule] = []
    for raw_rule in config.get("rules", []):
        filtered_kwargs = {}
        for k, v in raw_rule.items():
            if k in known_fields:
                filtered_kwargs[k] = v
            else:
                logger.warning(
                    "Ignoring unknown key '%s' in rule for flag_type '%s'",
                    k,
                    raw_rule.get("flag_type"),
                )
        rules.append(RiskRule(**filtered_kwargs))
    return rules


def _stable_flag_id(clause_id: str, flag_type: str, evidence: str) -> str:
    digest = hashlib.sha1(f"{clause_id}:{flag_type}:{evidence}".encode()).hexdigest()[:10]
    return f"flag-{digest}"


def detect_risk_flags(
    clauses: list[Clause],
    predictions: list[ClausePrediction],
    config_path: str = "configs/risk_rules.yaml",
) -> list[RiskFlag]:
    config = load_risk_config(config_path)
    matching_cfg = config.get("matching", {})
    default_min_conf = float(matching_cfg.get("default_min_confidence", 0.55))
    pattern_only_conf = float(matching_cfg.get("pattern_only_confidence", 0.70))
    label_and_pattern_conf = float(matching_cfg.get("label_and_pattern_confidence", 0.90))

    rules = load_rules(config_path)
    prediction_by_clause = {prediction.clause_id: prediction for prediction in predictions}
    flags: list[RiskFlag] = []

    # At most one flag per (clause_id, flag_type)
    seen_clause_flag: set[tuple[str, str]] = set()

    for clause in clauses:
        prediction = prediction_by_clause.get(clause.clause_id)
        predicted_label = (prediction.predicted_label if prediction else "").strip()
        model_conf = float(prediction.confidence) if prediction else 0.5
        norm_pred_label = predicted_label.lower()

        for rule in rules:
            if (clause.clause_id, rule.flag_type) in seen_clause_flag:
                continue

            # 1. Exclude patterns: if any matches, skip this rule for this clause
            if any(exc_re.search(clause.text) for exc_re in rule._compiled_exclude):
                continue

            # 2. Pattern matching
            matched_literals = [
                rule.patterns[i]
                for i, p_re in enumerate(rule._compiled_patterns)
                if p_re.search(clause.text)
            ]
            matched_regex = [
                rule.regex_patterns[i]
                for i, r_re in enumerate(rule._compiled_regex)
                if r_re.search(clause.text)
            ]
            all_matched_patterns = matched_literals + matched_regex
            pattern_hit = len(all_matched_patterns) > 0

            # 3. Label matching: exact case-insensitive equality with predicted label
            rule_min_conf = rule.min_confidence if rule.min_confidence is not None else default_min_conf
            has_exact_label = any(norm_pred_label == lbl.strip().lower() for lbl in rule.labels if lbl)
            label_hit = bool(has_exact_label and model_conf >= rule_min_conf)

            # 4. Trigger condition
            if rule.require_pattern:
                triggered = pattern_hit
            else:
                triggered = pattern_hit or label_hit

            if not triggered:
                continue

            # 5. Flag confidence calculation
            if pattern_hit and label_hit:
                flag_conf = max(model_conf, label_and_pattern_conf)
            elif pattern_hit:
                flag_conf = pattern_only_conf
            else:
                flag_conf = model_conf

            evidence = all_matched_patterns[0] if pattern_hit else predicted_label

            flag = RiskFlag(
                flag_id=_stable_flag_id(clause.clause_id, rule.flag_type, evidence),
                clause_id=clause.clause_id,
                flag_type=rule.flag_type,
                severity=rule.severity,  # type: ignore[arg-type]
                reason=rule.reason,
                evidence_text=clause.text[:500],
                confidence=round(min(1.0, max(0.0, flag_conf)), 4),
                title=rule.title,
                recommendation=rule.recommendation,
                metadata={
                    "matched_patterns": all_matched_patterns,
                    "matched_label": label_hit,
                    "predicted_label": predicted_label,
                    "model_confidence": model_conf,
                    "requires_human_review": True,
                },
            )
            flags.append(flag)
            seen_clause_flag.add((clause.clause_id, rule.flag_type))

    return flags
