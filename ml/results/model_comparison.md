# NexGuard — Model Comparison

- Generated: 2026-07-22T14:19:40.553029+00:00
- Dataset: `hdfs_sample.log`  ·  threshold: 0.5
- Best by F1: **LSTM** (F1 = 1.0000)

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC | FPR | FNR | p95 ms | sess/s | alerts/10k |
|---|---|---|---|---|---|---|---|---|---|---|
| LSTM | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 16.934 | 80.6 | 1428.6 |
| Transformer | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 28.942 | 45.5 | 1428.6 |
| IsolationForest | 0.1429 | 1.0 | 0.25 | 0.5 | 0.1429 | 1.0 | 0.0 | 51.725 | 31.8 | 10000.0 |
| Ensemble | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 94.195 | 15.9 | 1428.6 |

> ROC-AUC / PR-AUC use continuous scores; FPR × session volume = the
> analyst's daily false-alert load. Prefer higher recall at acceptable FPR
> for a SOC that cannot miss incidents.
