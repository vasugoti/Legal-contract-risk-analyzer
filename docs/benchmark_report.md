# Benchmark Report

This report keeps benchmarks modest and reproducible. The numbers below are local measurements, not universal claims about production latency.

## Environment

- OS: Windows 11
- Python: `3.12.8`
- Model: TF-IDF + Logistic Regression baseline trained on LEDGAR
- Model artifact: `models/baseline_tfidf.joblib`
- Model artifact size: `40.17 MB`
- Benchmark input: committed sample contract and sample clauses

## Baseline Training

The baseline was trained on the real LEDGAR splits:

- train: `60,000` records
- validation: `10,000` records
- test: `10,000` records

Observed terminal wall time for the training command was about `161 seconds` in this workspace.

Command:

```bash
python scripts/train_baseline.py --config configs/baseline.yaml
```

## Evaluation Metrics

### LEDGAR 10,000 Test Set Comparison

| Metric | TF-IDF + LogReg | LegalPro-BERT | Change |
| --- | ---: | ---: | ---: |
| Test Accuracy | 83.07% | **87.05%** | +3.98 pts |
| Test Macro F1 | 0.7826 | **0.8014** | +1.88 pts |
| Test Weighted F1 | 0.8332 | **0.8647** | +3.15 pts |
| Test Micro F1 | 0.8307 | **0.8705** | +3.98 pts |
| Top-3 Accuracy | — | **95.82%** | — |
| *Legal-BERT, LexGLUE paper (published)* | *micro-F1: 0.882* | *macro-F1: 0.830* | *Reference* |

- LegalPro-BERT checkpoint: `AmitTewari/test_trainer` @ `3fadda4002fc230b2195e1fe4c499af158418838` (fine-tuned BERT-base-cased, 100 LEDGAR labels)
- Evaluated on the 10,000 provision LEDGAR test split.
- Inference latency: 4.2 ms/clause on GPU (Tesla T4) and 31.45 ms/clause on laptop CPU.
- Local TF-IDF baseline evaluation: validation macro F1 `0.7737`, test accuracy `0.8307`, test macro F1 `0.7826`.

Command:

```bash
python scripts/evaluate_model.py --config configs/baseline.yaml --model models/baseline_tfidf.joblib
```

## Latency Measurements

Measured with the trained local baseline model unless noted otherwise.

| Measurement | Mean | p95 | Notes |
| --- | ---: | ---: | --- |
| Baseline inference per clause | `2.951 ms` | `3.369 ms` | Six sample clauses, model already loaded |
| Document analysis | `47.431 ms` | `114.984 ms` | Sample contract, cached local model |
| Retrieval index build | `2.058 ms` | n/a | Tiny sample clause set |
| Retrieval search | `0.522 ms` | `0.715 ms` | TF-IDF retrieval over sample clause set |
| API `/analyze/clause`, mock mode | `16.249 ms` | `17.650 ms` | FastAPI TestClient, in-process |
| API `/analyze/clause`, model-backed | `35.278 ms` | `43.733 ms` | FastAPI TestClient, cached local model after warmup |

## Interpretation

The baseline model itself is fast once loaded. The API uses lazy local model caching, so the first model-backed request pays the load cost and later requests reuse the same artifact.

The retrieval benchmark is intentionally small because tests and demos must not require a large embedding index. A realistic retrieval benchmark should be repeated on a larger clause corpus.

## Reproduce

```bash
python -m pip install -e ".[data,dev]"
python scripts/download_data.py --dataset ledgar
python scripts/train_baseline.py --config configs/baseline.yaml
python scripts/evaluate_model.py --config configs/baseline.yaml --model models/baseline_tfidf.joblib
python scripts/analyze_document.py --input data/samples/sample_contract.txt --output data/outputs/risk_report_real_model.json --model models/baseline_tfidf.joblib
```
