from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from contract_risk_analyzer.config.settings import resolve_path
from contract_risk_analyzer.data.schemas import ClausePrediction
from contract_risk_analyzer.modeling.status import _RUNTIME_STATUS

logger = logging.getLogger(__name__)

DEFAULT_SELF_CHECK_TEXT = (
    "This Agreement shall be governed by and construed in accordance with the laws "
    "of the State of Delaware, without giving effect to any principles of conflicts of law."
)
DEFAULT_SELF_CHECK_EXPECTED = "Governing Laws"


class ONNXClassifier:
    """Lightweight ONNX INT8 sequence classifier for LEDGAR 100 contract clause categories.
    
    Zero dependencies on torch or transformers. Uses onnxruntime (1 CPU thread)
    and tokenizers.
    """

    def __init__(
        self,
        model_dir: str | Path = "NLP/LEDGAR_SRA_ONNX",
        model_name: str | None = None,
        max_length: int = 512,
        batch_size: int = 2,
    ) -> None:
        self.model_dir = resolve_path(model_dir)
        self.model_name = model_name or "LEDGAR-SRA-ONNX-INT8"
        self.max_length = max_length
        self.batch_size = batch_size

        onnx_model_path = self.model_dir / "model_int8.onnx"
        if not onnx_model_path.exists():
            raise FileNotFoundError(f"ONNX model file not found at {onnx_model_path}")

        tokenizer_path = self.model_dir / "tokenizer.json"
        if not tokenizer_path.exists():
            raise FileNotFoundError(f"Tokenizer file not found at {tokenizer_path}")

        config_path = self.model_dir / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")

        # 1. Load label mapping
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        raw_id2label = cfg.get("id2label", {})
        self.id2label = {int(k): v for k, v in raw_id2label.items()}
        self.label2id = {v: int(k) for k, v in self.id2label.items()}
        self._classes = np.array([self.id2label.get(i, f"LABEL_{i}") for i in range(len(self.id2label))])

        # 2. Load Tokenizer
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(max_length=self.max_length)
        # Standard RoBERTa padding: token_id 1 is <pad>
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")

        # 3. Load ONNX Runtime Inference Session (1 CPU thread)
        sess_opts = ort.SessionOptions()
        sess_opts.intra_op_num_threads = 1
        sess_opts.inter_op_num_threads = 1
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(onnx_model_path),
            sess_opts,
            providers=["CPUExecutionProvider"],
        )

    @property
    def classes_(self) -> np.ndarray:
        return self._classes

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, len(self._classes)))

        all_probs: list[np.ndarray] = []
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            encodings = self.tokenizer.encode_batch(batch_texts)
            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            logits = self.session.run(
                ["logits"],
                {"input_ids": input_ids, "attention_mask": attention_mask},
            )[0]

            # Numerically stable softmax
            shift_logits = logits - np.max(logits, axis=1, keepdims=True)
            exp_logits = np.exp(shift_logits)
            probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
            all_probs.append(probs)

        return np.vstack(all_probs)

    def predict(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        probabilities = self.predict_proba(texts)
        top_indices = np.argmax(probabilities, axis=1)
        return [self.id2label.get(int(idx), f"LABEL_{idx}") for idx in top_indices]

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
        preds = self.predict([text])
        if not preds:
            return False
        return preds[0] == expected_label


def load_onnx_classifier(
    model_dir: str | Path = "NLP/LEDGAR_SRA_ONNX",
    fallback_on_failure: bool = True,
) -> Any:
    """Load ONNX INT8 classifier with startup self-check."""
    resolved_dir = resolve_path(model_dir)
    try:
        classifier = ONNXClassifier(model_dir=resolved_dir)
        passed = classifier.self_check()
        if passed:
            logger.info("ONNX classifier startup self-check passed: 'Governing Laws'.")
            _RUNTIME_STATUS.active_backend = "onnx"
            _RUNTIME_STATUS.model_name = classifier.model_name
            _RUNTIME_STATUS.model_id = str(resolved_dir)
            _RUNTIME_STATUS.revision = None
            _RUNTIME_STATUS.num_labels = len(classifier.id2label)
            _RUNTIME_STATUS.max_length = classifier.max_length
            _RUNTIME_STATUS.fallback_active = False
            _RUNTIME_STATUS.fallback_reason = None
            _RUNTIME_STATUS.model_loaded = True
            return classifier

        reason = "ONNX startup self-check failed to match expected label 'Governing Laws'."
        logger.warning(reason)
    except Exception as exc:
        reason = f"ONNX model load error: {exc}"
        logger.warning(reason)

    if not fallback_on_failure:
        raise RuntimeError(f"ONNX model setup failed: {reason}")

    from contract_risk_analyzer.modeling.registry import load_local_model

    fallback_path = "models/baseline_tfidf.joblib"
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
