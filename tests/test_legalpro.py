from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from contract_risk_analyzer.config.settings import load_yaml
from contract_risk_analyzer.data.schemas import Clause
from contract_risk_analyzer.modeling.ledgar_labels import (
    ID_TO_LABEL,
    LEDGAR_LABELS,
    get_ledgar_label,
    get_ledgar_labels,
)
from contract_risk_analyzer.modeling.legalpro import (
    LegalProClassifier,
    get_model_runtime_status,
    load_legalpro_classifier,
)
from contract_risk_analyzer.modeling.predict import predict_clauses
from contract_risk_analyzer.modeling.registry import clear_model_cache


def test_ledgar_labels_mapping() -> None:
    labels = get_ledgar_labels()
    assert len(labels) == 100
    assert len(LEDGAR_LABELS) == 100
    assert ID_TO_LABEL[47] == "Governing Laws"
    assert get_ledgar_label(47) == "Governing Laws"
    assert get_ledgar_label(999) == "LABEL_999"


def test_legalpro_config() -> None:
    cfg = load_yaml("configs/legalpro.yaml")
    assert cfg["model"]["model_id"] == "AmitTewari/test_trainer"
    assert cfg["model"]["revision"] == "3fadda4002fc230b2195e1fe4c499af158418838"
    assert cfg["model"]["self_check"]["expected_label"] == "Governing Laws"


def test_model_id_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MODEL_ID", "custom/legal-model")
    with patch("contract_risk_analyzer.modeling.legalpro.AutoTokenizer.from_pretrained"), \
         patch("contract_risk_analyzer.modeling.legalpro.AutoModelForSequenceClassification.from_pretrained") as mock_mod:
        mock_cfg = MagicMock()
        mock_cfg.num_labels = 100
        mock_mod.return_value.config = mock_cfg
        clf = LegalProClassifier(revision="rev123")
        assert clf.model_id == "custom/legal-model"


def test_startup_self_check_fallback_on_mismatch() -> None:
    with patch("contract_risk_analyzer.modeling.legalpro.LegalProClassifier") as mock_cls:
        instance = MagicMock()
        instance.self_check.return_value = False  # simulated failure
        mock_cls.return_value = instance

        # Fallback should return baseline model
        model = load_legalpro_classifier("configs/legalpro.yaml", fallback_on_failure=True)
        assert hasattr(model, "pipeline") or hasattr(model, "predict_clauses")
        assert model.model_name == "tfidf_logistic_regression"

        status = get_model_runtime_status()
        assert status.fallback_active is True
        assert "Self-check expected" in str(status.fallback_reason)


def test_startup_self_check_raises_when_no_fallback() -> None:
    with patch("contract_risk_analyzer.modeling.legalpro.LegalProClassifier") as mock_cls:
        instance = MagicMock()
        instance.self_check.return_value = False
        mock_cls.return_value = instance

        with pytest.raises(RuntimeError, match="LegalPro model setup failed"):
            load_legalpro_classifier("configs/legalpro.yaml", fallback_on_failure=False)


def test_predict_clauses_mocked_backend_switch(monkeypatch) -> None:
    clause = Clause(clause_id="c1", text="This is a test clause.", source_document_id="d1")

    # Mock mode
    mock_preds = predict_clauses([clause], mock=True)
    assert mock_preds[0].model_name == "deterministic_mock_model"

    # TFIDF backend
    tfidf_preds = predict_clauses([clause], backend="tfidf")
    assert tfidf_preds[0].model_name == "tfidf_logistic_regression"

    # LegalPro backend with mocked model
    with patch("contract_risk_analyzer.modeling.legalpro.LegalProClassifier") as mock_cls:
        instance = MagicMock()
        instance.self_check.return_value = True
        instance.predict_clauses.return_value = [
            MagicMock(predicted_label="Governing Laws", confidence=0.95, model_name="LegalPro-BERT")
        ]
        mock_cls.return_value = instance
        clear_model_cache()
        lp_preds = predict_clauses([clause], backend="legalpro")
        assert lp_preds[0].predicted_label == "Governing Laws"
        assert lp_preds[0].model_name == "LegalPro-BERT"


@pytest.mark.integration
def test_real_checkpoint_self_check() -> None:
    # Run self-check against the real AmitTewari/test_trainer model
    classifier = LegalProClassifier()
    assert classifier.self_check() is True


@pytest.mark.integration
def test_ledgar_labels_match_lexglue_dataset() -> None:
    import datasets

    ds = datasets.load_dataset("coastalcph/lex_glue", "ledgar")
    dataset_names = ds["train"].features["label"].names
    assert len(dataset_names) == 100
    assert dataset_names == LEDGAR_LABELS
    for idx, name in enumerate(dataset_names):
        assert ID_TO_LABEL[idx] == name
