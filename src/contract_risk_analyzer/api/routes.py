from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter

from contract_risk_analyzer.api.benchmark import build_benchmark_payload
from contract_risk_analyzer.api.schemas import (
    ClauseAnalyzeRequest,
    ClauseAnalyzeResponse,
    DocumentAnalyzeRequest,
    MetricsResponse,
    ModelInfoResponse,
    SearchRequest,
    SearchResponse,
)
from contract_risk_analyzer.config.settings import load_yaml, resolve_path
from contract_risk_analyzer.data.schemas import Clause
from contract_risk_analyzer.modeling.status import get_model_runtime_status
from contract_risk_analyzer.modeling.predict import analyze_document_text, predict_clauses
from contract_risk_analyzer.modeling.registry import load_legalpro_model, load_local_model, load_onnx_model
from contract_risk_analyzer.retrieval.index import build_clause_index
from contract_risk_analyzer.retrieval.search import search_index
from contract_risk_analyzer.risk.rules import detect_risk_flags
from contract_risk_analyzer.utils.io import read_jsonl

router = APIRouter()


@dataclass
class ServiceMetrics:
    analyzed_clauses: int = 0
    analyzed_documents: int = 0
    total_latency_ms: float = 0.0
    total_requests: int = 0
    total_risk_flags: int = 0

    @property
    def average_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return round(self.total_latency_ms / self.total_requests, 2)


metrics = ServiceMetrics()


def _mock_mode() -> bool:
    return os.getenv("CONTRACT_RISK_MOCK_MODEL", "false").lower() in {"1", "true", "yes"}


def _classifier_backend() -> str:
    return (
        os.getenv("CONTRACT_RISK_BACKEND")
        or os.getenv("CONTRACT_RISK_CLASSIFIER", "legalpro")
    ).strip().lower()


def _model_path() -> str | None:
    return os.getenv("CONTRACT_RISK_MODEL_PATH")


def _disclaimer() -> str:
    return str(load_yaml("configs/risk_rules.yaml")["disclaimer"])


def _record_latency(start: float) -> None:
    metrics.total_latency_ms += (time.perf_counter() - start) * 1000
    metrics.total_requests += 1


def get_active_classifier() -> Any:
    """Load and return the configured active classifier."""
    if _mock_mode():
        return None
    backend = _classifier_backend()
    if backend == "onnx":
        target = _model_path() or os.getenv("CONTRACT_RISK_ONNX_DIR", "NLP/LEDGAR_SRA_ONNX")
        return load_onnx_model(target)
    if backend == "tfidf":
        target = _model_path() or "models/baseline_tfidf.joblib"
        return load_local_model(target)
    target_cfg = _model_path() or os.getenv("CONTRACT_RISK_MODEL_CONFIG", "configs/ledgar_sra.yaml")
    return load_legalpro_model(target_cfg)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    mock = _mock_mode()
    if mock:
        return ModelInfoResponse(
            model_name="deterministic_mock_model",
            active_backend="mock",
            mock_mode=True,
            model_loaded=True,
            disclaimer=_disclaimer(),
        )

    backend = _classifier_backend()
    if backend == "tfidf":
        path = _model_path() or "models/baseline_tfidf.joblib"
        loaded = resolve_path(path).exists()
        return ModelInfoResponse(
            model_name="tfidf_logistic_regression",
            active_backend="tfidf",
            model_id=None,
            revision=None,
            num_labels=100,
            max_length=None,
            fallback_active=False,
            fallback_reason=None,
            mock_mode=False,
            model_loaded=loaded,
            disclaimer=_disclaimer(),
        )

    # LegalPro backend (default)
    get_active_classifier()
    status = get_model_runtime_status()
    return ModelInfoResponse(
        model_name=status.model_name,
        active_backend=status.active_backend,
        model_id=status.model_id,
        revision=status.revision,
        num_labels=status.num_labels,
        max_length=status.max_length,
        fallback_active=status.fallback_active,
        fallback_reason=status.fallback_reason,
        mock_mode=False,
        model_loaded=status.model_loaded,
        disclaimer=_disclaimer(),
    )


@router.post("/analyze/clause", response_model=ClauseAnalyzeResponse)
def analyze_clause(request: ClauseAnalyzeRequest) -> ClauseAnalyzeResponse:
    start = time.perf_counter()
    clause = Clause(
        clause_id="api-clause-1",
        text=request.text,
        source_document_id="api-clause",
        start_char=0,
        end_char=len(request.text),
    )
    predictions = predict_clauses(
        [clause],
        model_path=_model_path(),
        mock=_mock_mode(),
        backend=_classifier_backend(),
    )
    flags = detect_risk_flags([clause], predictions)
    metrics.analyzed_clauses += 1
    metrics.total_risk_flags += len(flags)
    _record_latency(start)
    prediction = predictions[0]
    return ClauseAnalyzeResponse(
        predicted_label=prediction.predicted_label,
        confidence=prediction.confidence,
        top_k_labels=prediction.top_k_labels,
        risk_flags=flags,
        disclaimer=_disclaimer(),
    )


@router.post("/analyze/document")
def analyze_document(request: DocumentAnalyzeRequest):
    start = time.perf_counter()
    report = analyze_document_text(
        request.text,
        document_id=request.document_id,
        model_path=_model_path(),
        mock=_mock_mode(),
        backend=_classifier_backend(),
    )
    metrics.analyzed_documents += 1
    metrics.analyzed_clauses += report.total_clauses
    metrics.total_risk_flags += len(report.risk_flags)
    _record_latency(start)
    return report


@router.post("/search/similar", response_model=SearchResponse)
def search_similar(request: SearchRequest) -> SearchResponse:
    start = time.perf_counter()
    results = []
    try:
        index_path = os.getenv("CONTRACT_RISK_RETRIEVAL_INDEX", "models/retrieval")
        results = search_index(index_path, request.query, top_k=request.top_k)
        if not results:
            sample_file = resolve_path("data/samples/sample_clauses.jsonl")
            if sample_file.exists():
                records = read_jsonl(sample_file)
                index = build_clause_index(records)
                results = index.search(request.query, top_k=request.top_k)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Similarity search unavailable or skipped: %s", exc)
        results = []
    _record_latency(start)
    return SearchResponse(results=results)


@router.get("/metrics", response_model=MetricsResponse)
def service_metrics() -> MetricsResponse:
    backend = _classifier_backend()
    if backend != "tfidf" and not _mock_mode():
        get_active_classifier()
    status = get_model_runtime_status()
    fallback_active = status.fallback_active if backend == "legalpro" else False
    fallback_reason = status.fallback_reason if backend == "legalpro" else None

    benchmark = build_benchmark_payload(
        active_backend=backend,
        fallback_active=fallback_active,
        fallback_reason=fallback_reason,
        model_name=status.model_name,
    )
    return MetricsResponse(
        analyzed_clauses=metrics.analyzed_clauses,
        analyzed_documents=metrics.analyzed_documents,
        average_latency_ms=metrics.average_latency_ms,
        total_risk_flags=metrics.total_risk_flags,
        active_backend=benchmark["effective_backend"],
        active_model_name=benchmark["active_model_name"],
        benchmark=benchmark,
    )
