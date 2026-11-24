# Part 1: Timing Results

| Backend | Startup Load (s) | 1st Request (s) | 2nd Request (s) | ms/clause (warm) |
|---------|-------------------|-----------------|-----------------|-------------------|
| **legalpro** | 10.581 | 0.045 | 0.033 | 31.45 (batch-20) |
| **tfidf** | 0.299 | 0.027 | 0.002 | 1.99 |

**Singleton reuse confirmed**: 1st request time (45ms) is much less than startup (10.6s),
proving lifespan warm-up works and requests reuse the loaded model via `lru_cache`.

LegalPro CPU ms/clause saved to `reports/metrics_legalpro_test_trainer.json`.
