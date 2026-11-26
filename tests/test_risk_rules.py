from __future__ import annotations

import re
from pathlib import Path

from contract_risk_analyzer.config.settings import load_yaml
from contract_risk_analyzer.data.schemas import Clause, ClausePrediction
from contract_risk_analyzer.risk.rules import RiskRule, detect_risk_flags


def test_yaml_integrity_and_ledgar_labels() -> None:
    config = load_yaml("configs/risk_rules.yaml")
    rules = config.get("rules", [])
    assert rules, "Rules list should not be empty"

    labels_file = Path("reports/ledgar_labels.txt")
    assert labels_file.exists(), "ledgar_labels.txt must exist"
    valid_labels = set()
    for line in labels_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            valid_labels.add(line.split(":", 1)[1].strip())
        else:
            valid_labels.add(line)

    severity_weights = config.get("severity_weights", {})
    assert severity_weights, "severity_weights must exist"

    seen_flag_types = set()
    for r in rules:
        ft = r["flag_type"]
        assert ft not in seen_flag_types, f"Duplicate flag_type found: {ft}"
        seen_flag_types.add(ft)

        sev = r["severity"]
        assert sev in severity_weights, f"Unknown severity '{sev}' in rule '{ft}'"

        for label in r.get("labels", []):
            assert label in valid_labels, f"Label '{label}' in rule '{ft}' not found in ledgar_labels.txt"

        for pat in r.get("regex_patterns", []):
            try:
                re.compile(pat)
            except re.error as e:
                raise AssertionError(f"Regex '{pat}' in rule '{ft}' failed to compile: {e}") from e


def test_word_boundaries_assigned_does_not_trigger_assign() -> None:
    # Rule with pattern "assign"
    rule = RiskRule(
        flag_type="TEST_ASSIGN",
        severity="medium",
        patterns=["assign"],
        require_pattern=True,
    )
    # Clause with "assigned" should NOT trigger
    clause_assigned = Clause(clause_id="c1", text="The rights are assigned to buyer.", source_document_id="d1")
    # Clause with "assign" should trigger
    clause_assign = Clause(clause_id="c2", text="Party shall not assign without consent.", source_document_id="d1")

    assert not any(p.search(clause_assigned.text) for p in rule._compiled_patterns)
    assert any(p.search(clause_assign.text) for p in rule._compiled_patterns)


def test_exclude_patterns_block_flag() -> None:
    clause = Clause(
        clause_id="c1",
        text="The company shall be liable for all losses, provided that aggregate liability shall not exceed fees paid.",
        source_document_id="d1",
    )
    # UNLIMITED_LIABILITY matches "liable for all losses" but has exclude_patterns "shall not exceed" and "aggregate liability"
    flags = detect_risk_flags([clause], [])
    assert not any(f.flag_type == "UNLIMITED_LIABILITY" for f in flags)


def test_require_pattern_true_with_label_only_produces_no_flag() -> None:
    # Rule requiring pattern
    clause = Clause(
        clause_id="c1",
        text="The agreement is effective from the signing date for one year.",
        source_document_id="d1",
    )
    # Model predicts Terminations, but clause has no risky termination pattern
    prediction = ClausePrediction(
        clause_id="c1",
        predicted_label="Terminations",
        confidence=0.95,
        model_name="test",
    )
    flags = detect_risk_flags([clause], [prediction])
    # TERMINATION_WITHOUT_CAUSE requires pattern, so it must not trigger
    assert not any(f.flag_type == "TERMINATION_WITHOUT_CAUSE" for f in flags)


def test_one_flag_per_clause_per_rule() -> None:
    clause = Clause(
        clause_id="c1",
        text="unlimited liability, person shall be solely liable and jointly and severally liable.",
        source_document_id="d1",
    )
    flags = detect_risk_flags([clause], [])
    unlimited_flags = [f for f in flags if f.flag_type == "UNLIMITED_LIABILITY"]
    assert len(unlimited_flags) <= 1


def test_known_clause_triggers_termination_flag() -> None:
    clause = Clause(
        clause_id="c1",
        text="Either party may terminate this Agreement without cause upon 30 days notice.",
        source_document_id="d1",
    )
    prediction = ClausePrediction(
        clause_id="c1",
        predicted_label="Terminations",
        confidence=0.9,
        top_k_labels=[("Terminations", 0.9)],
        model_name="test",
    )
    flags = detect_risk_flags([clause], [prediction])
    assert any(flag.flag_type == "TERMINATION_WITHOUT_CAUSE" for flag in flags)
