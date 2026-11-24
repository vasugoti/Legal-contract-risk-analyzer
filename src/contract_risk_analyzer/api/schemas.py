from __future__ import annotations

from typing import Any

from typing import Any
from pydantic import BaseModel, Field

from contract_risk_analyzer.data.schemas import RiskFlag, RiskReport, SearchResult


class ClauseAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)


class ClauseAnalyzeResponse(BaseModel):
    predicted_label: str
    confidence: float
    top_k_labels: list[tuple[str, float]]
    risk_flags: list[RiskFlag]
    disclaimer: str


class DocumentAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)
    document_id: str = "api-document"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResponse(BaseModel):
    results: list[SearchResult]


class MetricsResponse(BaseModel):
    analyzed_clauses: int
    analyzed_documents: int
    average_latency_ms: float
    total_risk_flags: int
    active_backend: str = "legalpro"
    active_model_name: str = "LegalPro-BERT"
    benchmark: dict[str, Any] = Field(default_factory=dict)


class ModelInfoResponse(BaseModel):
    model_name: str
    active_backend: str = "legalpro"
    model_id: str | None = None
    revision: str | None = None
    num_labels: int = 100
    max_length: int | None = None
    fallback_active: bool = False
    fallback_reason: str | None = None
    mock_mode: bool = False
    model_loaded: bool = True
    disclaimer: str = ""


class DocumentAnalyzeResponse(RiskReport):
    pass
