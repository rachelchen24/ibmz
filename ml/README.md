# Fraud classifier (`ml/`)

This model predicts the probability that a job posting is a **scam**. It's trained on EMSCAD (`data/fake_job_postings.csv`, Kaggle, 2012–2014). A fraud probability is **not** a ghost-job probability.

## Commands (from the repo root)

```
pip install -r ml/requirements.txt
python -m ml.split                                   # split + cleaned CSV (already done; rerun only if the data changes)
python -m ml.run train --model logreg                # baseline, about 1 minute
python -m ml.run train --model lgbm                  # LightGBM: tune, calibrate, threshold, about 40 minutes
python -m ml.run evaluate --model lgbm --split val   # report -> ml/reports/metrics_lgbm_val.json
python -m ml.run score --model lgbm postings.csv     # score new postings (raw Kaggle columns)
python -m ml.run evaluate --model lgbm --split test --final   # the ONE holdout evaluation, at the very end
python -m unittest discover -s ml/tests -t .         # all tests
```

Trained models are saved to `ml/models/<name>_v1.joblib`. This folder is git-ignored, so train them locally.

## Who wrote what

| File | Person | Role |
|---|---|---|
| `cleaning.py`, `split.py`, `audit.py`, `AUDIT.md` | 1 | Cleaning, the group-aware split, the data audit |
| `preprocessing.py`, `modeling.py` | 2 | Shared features (TF-IDF, one-hot encoding, missing-value flags); logistic baseline |
| `lgbm.py` | 3 | LightGBM: tuning on CV folds, sigmoid calibration, threshold |
| `evaluate.py`, `run.py` | 4 | Metrics (PR-AUC, group bootstrap), the entry point |

## Validation results (split v1)

| Model | PR-AUC (95% CI) | Precision at 50% recall | Brier (always guessing the 4.85% base rate = 0.046) |
|---|---|---|---|
| logreg | 0.573 (0.40–0.83) | 54% | 0.049, uncalibrated |
| lgbm | 0.620 (0.46–0.82) | 71% | 0.027 |

## Limitations

The full list is in `AUDIT.md` § "Leakage risks". The main ones:

- Validation has only 122 fraud postings, so the confidence intervals are wide.
- Part of the model's lift comes from `company_profile` text: CV PR-AUC drops from 0.68 to 0.62 without it.
- The 2012–2014 data may not reflect today's scams.
- Both models' thresholds are the best-F1 cut-off on validation (team decision), so their validation precision and recall are optimistic. The one `--final` test run gives the honest numbers.
