# Part 4 Progress: Active Model Metrics & Comparison Tab

## 1. Metrics Data Source Analysis
- **Previous implementation**: The System Metrics tab in `src/contract_risk_analyzer/web/index.html` had all baseline benchmark values hard-coded directly into HTML markup (`83.07%`, `0.7826`, `models/baseline_tfidf.joblib`, `~1.8 ms`). The `/metrics` endpoint previously only returned runtime session counters (`analyzed_clauses`, `analyzed_documents`, `average_latency_ms`, `total_risk_flags`).
- **New implementation**:
  - `src/contract_risk_analyzer/api/benchmark.py` dynamically loads `reports/metrics_legalpro_test_trainer.json` and `reports/metrics_tfidf.json`.
  - `/metrics` returns the runtime counters, the active backend, the active model name, and the full structured benchmark payload (`cards`, `comparison_table`, `specs`, `fallback_active`, `fallback_reason`).
  - `web/index.html` and `web/app.js` render everything dynamically from `/metrics` with zero hard-coded numbers.

## 2. Benchmark Comparison Table
| Metric | TF-IDF + LogReg | LegalPro-BERT | Change |
|---|---|---|---|
| Test Accuracy | 83.07% | **87.05%** | +3.98 pts |
| Test Macro F1 | 0.7826 | **0.8014** | +1.88 pts |
| Test Weighted F1 | 0.8332 | **0.8647** | +3.15 pts |
| Test Micro F1 | 0.8307 | **0.8705** | +3.98 pts |
| Top-3 Accuracy | — | **95.82%** | — |
| *Legal-BERT, LexGLUE paper (published)* | *micro-F1: 0.882* | *macro-F1: 0.830* | *Reference* |

## 3. Active Model Specifications (LegalPro-BERT)
- **Architecture**: BERT-base-cased (12 layers, 768 hidden, ~108M params) + 100-class classification head
- **Training dataset**: LexGLUE LEDGAR (US SEC EDGAR contract filings)
- **Model Checkpoint**: `AmitTewari/test_trainer` @ `3fadda4002fc230b2195e1fe4c499af158418838` (≈413 MB, Apache-2.0)
- **Inference Latency**: 4.2 ms/clause on GPU (T4), 31.45 ms/clause on laptop CPU
- **Max Input Length**: 512 tokens
- **Fallback**: TF-IDF + LogReg (`models/baseline_tfidf.joblib`), with amber fallback notification if triggered
- **Jurisdiction Scope**: English-language commercial contracts. Not validated for non-English or foreign jurisdictions.

## 4. Tests Added
- `test_metrics_legalpro_backend`: verifies `/metrics` returns LegalPro metrics (`87.05%`, `LegalPro-BERT`) when `CONTRACT_RISK_CLASSIFIER=legalpro`.
- `test_metrics_tfidf_backend`: verifies `/metrics` returns TF-IDF metrics (`83.07%`, `TF-IDF + Logistic Regression`) when `CONTRACT_RISK_CLASSIFIER=tfidf`.
