from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MODEL_ID = "AmitTewari/test_trainer"
DEFAULT_REVISION = "3fadda4002fc230b2195e1fe4c499af158418838"


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
