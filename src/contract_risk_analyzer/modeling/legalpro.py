from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from contract_risk_analyzer.config.settings import load_yaml, resolve_path
from contract_risk_analyzer.data.schemas import ClausePrediction
from contract_risk_analyzer.modeling.ledgar_labels import ID_TO_LABEL, LABEL_TO_ID, LEDGAR_LABELS

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "AmitTewari/test_trainer"
DEFAULT_REVISION = "3fadda4002fc230b2195e1fe4c499af158418838"
DEFAULT_SELF_CHECK_TEXT = (
    "This Agreement shall be governed by and construed in accordance with the laws "
    "of the State of Delaware, without giving effect to any principles of conflicts of law."
)
DEFAULT_SELF_CHECK_EXPECTED = "Governing Laws"


@dataclass
class ModelRuntimeStatus:
    active_backend: str = "legalpro"
    model_name: str = "LegalPro-BERT"
    model_id: str | None = DEFAULT_MODEL_ID
    revision: str | None = DEFAULT_REVISION
    num_labels: int = 100
    max_length: int | None = 512
    fallback_active: bool = False
    fallback_reason: str | None = None
    model_loaded: bool = False


_RUNTIME_STATUS = ModelRuntimeStatus()


def get_model_runtime_status() -> ModelRuntimeStatus:
    """Return runtime metadata and fallback status for active model."""
    return _RUNTIME_STATUS


class LegalProClassifier:
    """Sequence classifier for LEDGAR 100 contract clause categories (supports local folder or Hugging Face)."""

    def __init__(
        self,
        model_id: str | None = None,
        model_path: str | Path | None = None,
        model_name: str | None = None,
        revision: str | None = None,
        max_length: int = 512,
        batch_size: int = 16,
        device: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        self.model_path = resolve_path(model_path) if model_path else None
        if self.model_path is not None:
            self.model_id = str(model_path)
            self.revision = None
            self.model_name = model_name or "LEDGAR-SRA (RoBERTa, fine-tuned on LEDGAR)"
        else:
            self.model_id = os.getenv("CONTRACT_RISK_MODEL_ID") or model_id or DEFAULT_MODEL_ID
            self.revision = revision or DEFAULT_REVISION
            self.model_name = model_name or f"LegalPro-BERT ({self.model_id})"

        self.max_length = max_length
        self.batch_size = batch_size

        if device is not None:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer, self.model = self._load_model_and_tokenizer(local_files_only=local_files_only)
        self.model.to(self.device)
        self.model.eval()

        if hasattr(self.model.config, "id2label") and self.model.config.id2label:
            sample_val = next(iter(self.model.config.id2label.values()), "")
            if not str(sample_val).startswith("LABEL_"):
                self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}
                self.label2id = {v: int(k) for k, v in self.id2label.items()}
                self._classes = np.array([self.id2label.get(i, f"LABEL_{i}") for i in range(len(self.id2label))])
            else:
                self.id2label = dict(ID_TO_LABEL)
                self.label2id = dict(LABEL_TO_ID)
                self._classes = np.array(LEDGAR_LABELS)
        else:
            self.id2label = dict(ID_TO_LABEL)
            self.label2id = dict(LABEL_TO_ID)
            self._classes = np.array(LEDGAR_LABELS)

    def _load_model_and_tokenizer(
        self, local_files_only: bool = False
    ) -> tuple[Any, Any]:
        """Load tokenizer and model with automatic local/offline fallback."""
        if self.model_path is not None:
            load_target = str(self.model_path)
            tokenizer = AutoTokenizer.from_pretrained(load_target, local_files_only=True)
            model = AutoModelForSequenceClassification.from_pretrained(load_target, local_files_only=True)
            return tokenizer, model

        kwargs: dict[str, Any] = {"revision": self.revision}
        if local_files_only or os.getenv("HF_HUB_OFFLINE") == "1":
            kwargs["local_files_only"] = True

        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model_id, **kwargs)
            model = AutoModelForSequenceClassification.from_pretrained(self.model_id, **kwargs)
        except Exception as exc:
            # If network error or sandbox restriction, retry with local_files_only
            if not kwargs.get("local_files_only"):
                logger.warning(
                    "Failed to load %s online (%s); retrying with local_files_only=True",
                    self.model_id,
                    exc,
                )
                kwargs["local_files_only"] = True
                tokenizer = AutoTokenizer.from_pretrained(self.model_id, **kwargs)
                model = AutoModelForSequenceClassification.from_pretrained(self.model_id, **kwargs)
            else:
                raise

        # Remap model config id2label to LEDGAR if generic LABEL_X
        if getattr(model.config, "num_labels", None) == 100 or len(ID_TO_LABEL) == 100:
            model.config.id2label = dict(ID_TO_LABEL)
            model.config.label2id = dict(LABEL_TO_ID)

        return tokenizer, model

    @property
    def classes_(self) -> np.ndarray:
        return self._classes

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, len(self._classes)))

        all_probs: list[np.ndarray] = []
        with torch.no_grad():
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i : i + self.batch_size]
                inputs = self.tokenizer(
                    batch_texts,
                    truncation=True,
                    padding=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                logits = self.model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).cpu().numpy()
                all_probs.append(probs)

        return np.vstack(all_probs)

    def predict(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        probabilities = self.predict_proba(texts)
        top_indices = np.argmax(probabilities, axis=1)
        return [self.id2label.get(idx, f"LABEL_{idx}") for idx in top_indices]

    def predict_clauses(
        self, clause_ids: list[str], texts: list[str], top_k: int = 3
    ) -> list[ClausePrediction]:
        if not texts:
            return []

        probabilities = self.predict_proba(texts)
        outputs: list[ClausePrediction] = []
        for clause_id, proba in zip(clause_ids, probabilities, strict=True):
            top_indices = np.argsort(proba)[::-1][:top_k]
            top_labels = [
                (self.id2label.get(int(idx), f"LABEL_{idx}"), float(proba[idx]))
                for idx in top_indices
            ]
            outputs.append(
                ClausePrediction(
                    clause_id=clause_id,
                    predicted_label=top_labels[0][0],
                    confidence=round(top_labels[0][1], 4),
                    top_k_labels=top_labels,
                    model_name=self.model_name,
                )
            )
        return outputs

    def self_check(
        self,
        text: str = DEFAULT_SELF_CHECK_TEXT,
        expected_label: str = DEFAULT_SELF_CHECK_EXPECTED,
    ) -> bool:
        """Verify startup self-check on governing-law text."""
        preds = self.predict([text])
        if not preds:
            return False
        return preds[0] == expected_label


def load_legalpro_classifier(
    config_path: str | Path = "configs/legalpro.yaml",
    fallback_on_failure: bool = True,
) -> Any:
    """Load classifier with startup self-check and TF-IDF fallback."""
    cfg_file = resolve_path(config_path)
    cfg: dict[str, Any] = {}
    if cfg_file.exists():
        cfg = load_yaml(cfg_file).get("model", {})

    model_path = cfg.get("model_path")
    model_name = cfg.get("model_name")
    model_id = os.getenv("CONTRACT_RISK_MODEL_ID") or cfg.get("model_id")
    if not model_path and not model_id:
        model_id = DEFAULT_MODEL_ID
    revision = cfg.get("revision", DEFAULT_REVISION if not model_path else None)
    max_length = int(cfg.get("max_length", 512))
    batch_size = int(cfg.get("batch_size", 16))
    fallback_path = cfg.get("fallback_model_path", "models/baseline_tfidf.joblib")

    self_check_cfg = cfg.get("self_check", {})
    check_text = self_check_cfg.get("text", DEFAULT_SELF_CHECK_TEXT)
    expected_label = self_check_cfg.get("expected_label", DEFAULT_SELF_CHECK_EXPECTED)

    target_desc = str(model_path) if model_path else str(model_id)

    try:
        classifier = LegalProClassifier(
            model_id=model_id,
            model_path=model_path,
            model_name=model_name,
            revision=revision,
            max_length=max_length,
            batch_size=batch_size,
        )
        passed = classifier.self_check(text=check_text, expected_label=expected_label)
        if passed:
            logger.info("Classifier startup self-check passed: '%s'.", expected_label)
            _RUNTIME_STATUS.active_backend = "legalpro"
            _RUNTIME_STATUS.model_name = classifier.model_name
            _RUNTIME_STATUS.model_id = str(model_path) if model_path else classifier.model_id
            _RUNTIME_STATUS.revision = classifier.revision
            _RUNTIME_STATUS.num_labels = len(classifier.id2label)
            _RUNTIME_STATUS.max_length = classifier.max_length
            _RUNTIME_STATUS.fallback_active = False
            _RUNTIME_STATUS.fallback_reason = None
            _RUNTIME_STATUS.model_loaded = True
            return classifier

        reason = f"Self-check expected '{expected_label}' but prediction did not match."
        logger.warning(
            "Classifier startup self-check failed for model '%s': %s "
            "Falling back to TF-IDF baseline at '%s'.",
            target_desc,
            reason,
            fallback_path,
        )
    except Exception as exc:
        reason = f"Model load error: {exc}"
        logger.warning(
            "Classifier model '%s' failed to load (%s). Falling back to TF-IDF baseline at '%s'.",
            target_desc,
            exc,
            fallback_path,
        )

    if not fallback_on_failure:
        raise RuntimeError(f"LegalPro model setup failed and fallback_on_failure is False: {reason}")

    from contract_risk_analyzer.modeling.registry import load_local_model

    fallback_model = load_local_model(fallback_path)
    _RUNTIME_STATUS.active_backend = "tfidf"
    _RUNTIME_STATUS.model_name = "tfidf_logistic_regression"
    _RUNTIME_STATUS.model_id = None
    _RUNTIME_STATUS.revision = None
    _RUNTIME_STATUS.num_labels = len(getattr(fallback_model, "classes_", [])) or 100
    _RUNTIME_STATUS.max_length = None
    _RUNTIME_STATUS.fallback_active = True
    _RUNTIME_STATUS.fallback_reason = reason
    _RUNTIME_STATUS.model_loaded = True
    return fallback_model
