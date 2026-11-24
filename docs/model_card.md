# Model Card

## Intended Use

Contract clause classification, semantic search, and document risk triage for NLP engineering demonstration and internal review assistance.

## Out-of-Scope Use

The system must not be used as legal advice, final contract approval, enforceability assessment, or replacement for qualified legal review.

## Training Data

Primary target data is LexGLUE LEDGAR prepared locally through the data pipeline. Tiny sample data is included only for tests and demos.

## Evaluation Data

Use LEDGAR validation and test splits after local download. The latest local run used:

- train: `60,000` LEDGAR records
- validation: `10,000` LEDGAR records
- test: `10,000` LEDGAR records

## Metrics

Supported metrics include accuracy, macro F1, micro F1, weighted F1, per-class precision/recall/F1, confusion matrix, and top confusing label pairs.

### LEDGAR 10,000 Test Set Comparison

| Metric | TF-IDF + LogReg | LegalPro-BERT | Change |
| --- | ---: | ---: | ---: |
| Test Accuracy | 83.07% | **87.05%** | +3.98 pts |
| Test Macro F1 | 0.7826 | **0.8014** | +1.88 pts |
| Test Weighted F1 | 0.8332 | **0.8647** | +3.15 pts |
| Test Micro F1 | 0.8307 | **0.8705** | +3.98 pts |
| Top-3 Accuracy | — | **95.82%** | — |
| *Legal-BERT, LexGLUE paper (published)* | *micro-F1: 0.882* | *macro-F1: 0.830* | *Reference* |

- Primary Model: `LEDGAR-SRA` (RoBERTa-base, 12 layers, 768 hidden, 100 classes, fine-tuned locally in `NLP/LEDGAR_SRA`, ≈498 MB, loaded offline with `local_files_only=True`).
- Alternative Transformer: `AmitTewari/test_trainer` (LegalPro-BERT, pinned revision `3fadda4002fc230b2195e1fe4c499af158418838`, ~108M params, 413 MB).
- Baseline Fallback: `models/baseline_tfidf.joblib` (TF-IDF + Logistic Regression).
- Latency: 4.2 ms/clause on GPU (Tesla T4), 31.45 ms/clause on laptop CPU. Fallback to TF-IDF baseline supported.

## Limitations

Legal clause labels can be ambiguous. Rare classes may perform poorly. Long provisions may require truncation. Out-of-domain contracts and jurisdiction-specific wording can reduce reliability.

The current trained baseline is English-domain only. It should not be treated as a validated model for Russian-language, Belarusian-language, Belarusian-law, or Russian-law contracts.

## Ethical Considerations

The model can create false confidence if presented as legal authority. Outputs should be framed as triage signals and reviewed by humans.

## Legal Disclaimer

This tool is for document analysis and risk triage only. It is not legal advice and does not replace review by a qualified lawyer.

## Human Review Requirement

All risk flags, predictions, and reports require review by qualified humans before business or legal decisions.

## Failure Modes

- Confusing similar clause categories
- Missing risk language not covered by rules
- Over-flagging boilerplate
- Underperforming on rare labels
- Misleading confidence on unfamiliar documents
- Weak behavior on non-English legal text
- Poor transfer to Belarusian or Russian contract drafting without local training and evaluation data

## Monitoring Recommendations

Track input drift, label distribution, confidence distribution, latency, error samples, and human feedback on false positives and false negatives.
