# Scam-risk classifier (`ml/`)

This model predicts the probability that a job listing is a **scam**. It's trained on EMSCAD (`data/fake_job_postings.csv`, Kaggle, 2012–2014). A scam probability is **not** a ghost-job probability.

The full write-up is in [`docs/model-card.md`](../docs/model-card.md), and the data audit in [`AUDIT.md`](AUDIT.md).

## Commands (from the repo root)

```
pip install -r ml/requirements.txt
python -m ml.split                                   # split + cleaned CSV (done; rerun only if the data changes)
python -m ml.run train --model logreg                # baseline, about 1 minute
python -m ml.run train --model lgbm                  # LightGBM: tune, calibrate, threshold, about 40 minutes
python -m ml.run evaluate --model lgbm --split val   # report -> ml/reports/metrics_lgbm_val.json
python -m ml.run score --model lgbm postings.csv     # score new listings (raw Kaggle columns)
python -m ml.fairness                                # by country / industry / job type / remote / logo
python -m unittest discover -s ml/tests -t .         # all tests
```

**The test split has been used for its one final evaluation** (`ml/reports/metrics_lgbm_test.json`). Don't tune anything against it.

Trained models are saved to `ml/models/<name>_v1.joblib`. This folder is git-ignored, so train them locally.

## Files

| File | Person | Role |
|---|---|---|
| `cleaning.py`, `split.py`, `audit.py`, `AUDIT.md` | 1 | Cleaning, the group-aware split, the data audit |
| `preprocessing.py`, `modeling.py` | 2 | Shared features (TF-IDF, one-hot encoding, missing-value flags); logistic baseline |
| `lgbm.py` | 3 | LightGBM: tuning on CV folds, sigmoid calibration, threshold |
| `evaluate.py`, `run.py`, `fairness.py` | 4 | Metrics (PR-AUC, group bootstrap), the entry point, the fairness breakdown |
| `explain.py` | | Per-field reasons (TreeSHAP); leaves out fields a live page can't show |
| `granite.py` | | IBM Granite one-sentence summary from the reasons, with a wording check and template fallback |

## Results

| | PR-AUC (95% CI) | Precision / recall at threshold | Brier (base rate = 0.046) |
|---|---|---|---|
| logreg, validation | 0.573 (0.40–0.83) | 82% / 44% | 0.049 |
| lgbm, validation | 0.620 (0.46–0.82) | 62% / 62% | 0.027 |
| **lgbm, test (final)** | **0.739 (0.57–0.89)** | **66% / 68%**; flags 5% of listings | **0.023** |

The threshold is the best-F1 cutoff on validation (team decision), so validation's own precision and recall are optimistic. Test is the honest number.

## Limitations

The full list is in `docs/model-card.md`. The main ones:

- Validation and test have only 122 scams each, so the intervals are wide.
- The model leans on company-description text (35% of its signal) and the logo.
- Genuine remote, part-time and no-logo listings are wrongly flagged more often (8–11% vs 1.8% overall).
- Scams with a logo and polished text are mostly missed.
- The 2012–2014 data may not reflect today's scams.
