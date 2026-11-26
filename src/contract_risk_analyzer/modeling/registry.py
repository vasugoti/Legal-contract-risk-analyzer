from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from contract_risk_analyzer.modeling.baseline_tfidf import TfidfLogisticBaseline

DEFAULT_MODEL_CONFIG = "configs/ledgar_sra.yaml"


@lru_cache(maxsize=4)
def _load_local_model_cached(resolved_path: str) -> TfidfLogisticBaseline:
    return TfidfLogisticBaseline.load(resolved_path)


def load_local_model(path: str | Path) -> TfidfLogisticBaseline:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Model artifact not found: {resolved}")
    return _load_local_model_cached(str(resolved))


@lru_cache(maxsize=4)
def _load_legalpro_model_cached(config_path: str, fallback_on_failure: bool) -> Any:
    from contract_risk_analyzer.modeling.legalpro import load_legalpro_classifier

    return load_legalpro_classifier(config_path=config_path, fallback_on_failure=fallback_on_failure)


def load_legalpro_model(
    config_path: str | Path | None = None,
    fallback_on_failure: bool = True,
) -> Any:
    target_config = config_path or os.getenv("CONTRACT_RISK_MODEL_CONFIG", DEFAULT_MODEL_CONFIG)
    resolved = str(Path(target_config).expanduser())
    return _load_legalpro_model_cached(resolved, fallback_on_failure)


@lru_cache(maxsize=4)
def _load_onnx_model_cached(model_dir: str, fallback_on_failure: bool) -> Any:
    from contract_risk_analyzer.modeling.onnx_classifier import load_onnx_classifier

    return load_onnx_classifier(model_dir=model_dir, fallback_on_failure=fallback_on_failure)


def load_onnx_model(
    model_dir: str | Path | None = None,
    fallback_on_failure: bool = True,
) -> Any:
    target_dir = model_dir or os.getenv("CONTRACT_RISK_ONNX_DIR", "NLP/LEDGAR_SRA_ONNX")
    resolved = str(Path(target_dir).expanduser())
    return _load_onnx_model_cached(resolved, fallback_on_failure)


def clear_model_cache() -> None:
    _load_local_model_cached.cache_clear()
    _load_legalpro_model_cached.cache_clear()
    _load_onnx_model_cached.cache_clear()
