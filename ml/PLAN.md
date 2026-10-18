# Plan: Fake Job Posting Fraud Classifier

## Problem and approach

Build a standalone Python training/evaluation script that predicts the probability a posting is fraudulent using the predictive features in `ibmz/data/fake_job_postings.csv`. This is a scam/fraud classification task, distinct from RealRole's ghost-job scoring target. The CSV has 17,880 rows, 17 columns, and 866 positive examples (about 4.8%); its `fraudulent` column is the label.

Use the complete feature set while excluding `fraudulent` (the target) and `job_id` (an identifier, not a meaningful posting attribute). Create leakage-safe preprocessing for structured and text fields. Compare an interpretable, sparse logistic-regression baseline against one stronger model that can consume the same information. Produce calibrated probabilities, report threshold-independent and threshold-dependent metrics suited to an imbalanced dataset, and save reproducible metrics and model artifacts.

This is a planning-only update. Do not create or modify repository files, branches, or commits until implementation is explicitly requested. When the team is ready, map the four assignments below to the actual contributors and agree on shared interfaces before parallel coding.

## Four-person work split

Assignments use generic labels until the team supplies names. Each contributor owns a separable deliverable; the team agrees on dataset split, feature handling, model API, and output formats before work starts.

### Person 1 — Data audit and evaluation design

- Inspect schema, dtypes, missingness, label encoding, duplicates, and text/identifier characteristics.
- Investigate duplicate postings and company overlap; recommend stratified or group-aware split based on actual data evidence.
- Define a fixed, reproducible train/validation/test split and document leakage risks and limits.
- Deliver a concise audit and split specification for the other contributors.

### Person 2 — Feature preprocessing and baseline

- Implement leakage-safe preprocessing for mixed structured and text fields using scikit-learn pipelines.
- Preserve all predictive columns except the `fraudulent` target and `job_id` identifier; handle missing data and sparse text features.
- Implement a class-weighted logistic-regression baseline and focused preprocessing/input-validation tests.
- Coordinate the shared pipeline and prediction interface with Person 3.

### Person 3 — Stronger model and probability calibration

- Implement and compare one stronger model using the same feature representation and split strategy as the baseline.
- Compare candidate models using training-only cross-validation/validation data, avoiding holdout-driven selection.
- Calibrate probabilities and define an operating threshold using validation data only.
- Deliver the selected fitted pipeline/model and the rationale for model choice and calibration.

### Person 4 — Evaluation, outputs, documentation, and integration

- Implement final holdout evaluation and machine-readable metrics reporting, using the split agreed by Person 1.
- Report PR-AUC as primary, plus ROC-AUC, precision, recall, F1, confusion matrix, prevalence, Brier score, and threshold trade-offs.
- Integrate both model pipelines into a configurable, reproducible Python training/evaluation entry point; save model and metrics artifacts.
- Add end-to-end tests and usage/model-limitations documentation, including that fraud probability is not a ghost-job probability.
- Record any new ML dependencies in a dedicated dependency file and the project's required open-source library list; do not add ML packages to unrelated collection requirements.

### Integration order and shared decisions

1. Person 1 completes the data audit and proposes the split/grouping strategy.
2. All four agree on the split, feature exclusion policy, probability/prediction interface, artifact paths, and metric report schema.
3. Persons 2 and 3 implement baseline and stronger-model pipelines in parallel against that interface.
4. Person 4 integrates the pipelines, runs the final holdout evaluation, and adds end-to-end outputs/docs.
5. All contributors review the final metrics and limitations before considering the model complete.

## Proposed tasks

1. **Inspect and validate inputs** (Person 1)
   - Confirm column types, missingness, label encoding, duplicates, and text/identifier characteristics.
   - Define input feature groups from observed data; retain all predictive columns, excluding only the target and row identifier.
   - Check for repeated postings/company overlap that could leak across evaluation folds; document and use a group-aware split if a reliable grouping key is available.
2. **Build leakage-safe preprocessing and model comparison** (Persons 2 and 3)
   - Impute missing structured values, encode categorical/binary values, and vectorize available text fields within a scikit-learn pipeline so transformations are fitted only on training data.
   - Fit a class-weighted logistic-regression baseline and one stronger model using the same features and split strategy.
   - Use stratified cross-validation on training data for model selection; reserve a final holdout for one-time evaluation.
3. **Evaluate probability quality and produce outputs** (Person 3 for calibration; Person 4 for final evaluation)
   - Report PR-AUC as the primary metric, alongside ROC-AUC, precision, recall, F1, confusion matrix, and class prevalence.
   - Calibrate predicted probabilities and report a calibration metric (e.g. Brier score); select and document an operating threshold using validation data, not the final test set.
   - Save the fitted pipeline and a machine-readable metrics report; make the script's data and output paths configurable and document a reproducible invocation.
4. **Add focused tests and documentation** (Persons 2 and 4)
   - Test input validation, feature/target separation, preprocessing on missing/mixed data, probability output shape/range, and metric generation.
   - Document intended use, evaluation design, threshold choice, limitations, and that this fraud score is not a ghost-job probability.
   - Record any new ML dependencies in a dedicated dependency file and the project's required open-source library list; do not add ML packages to the unrelated collection requirements.

## Notes and considerations

- The positive class is approximately 4.8%, so accuracy alone is misleading; emphasize precision-recall behavior and report the chosen threshold's trade-offs.
- Keep all preprocessing inside training folds to prevent leakage. Investigate duplicate postings and company overlap before deciding whether ordinary stratification is sufficient.
- Do not feed `job_id` or `fraudulent` into the model. Preserve useful content from every other feature, including sparse and text-heavy fields.
- The dataset README identifies this as a Kaggle real/fake posting dataset and explicitly cautions that it is not ground truth for ghost jobs.
- Keep generated model binaries and other large outputs out of source control unless the project explicitly decides otherwise.
- The actual contributor names and their availability are not yet specified; the four labels above describe responsibilities only.

## Shared contract (proposed by Person 4 — needs team sign-off)

This is integration step 2: the interfaces Persons 2 and 3 build against. Person 1's half (split, feature
exclusion) is settled in `ml/AUDIT.md`. Nothing here changes Person 1's code. Per `START-HERE.md`, agree
these with the team before relying on them.

### Handing over predictions (the only thing Person 4 strictly needs)

Write a CSV with `job_id` and `y_prob` covering every row of the split being scored, then:

```
python -m ml.evaluate --predictions preds.csv --split val --name logreg \
    --threshold 0.31 --threshold-source "train OOF, recall 0.80"
```

This keeps Persons 2–4 decoupled: no imports across workstreams, and a model can be evaluated without
Person 4 being able to refit it. `ml/evaluate.py` validates coverage and refuses partial predictions.

### Handing over a fitted model (needed to refit per CV fold)

Each model module exposes an unfitted factory, so Person 4 can refit it inside folds:

```python
def build_model() -> sklearn.pipeline.Pipeline: ...   # unfitted
# the fitted result must satisfy: predict_proba(X)[:, 1] -> (n,) floats in [0, 1]
# X is load_split() output subset to FEATURE_COLS; the pipeline does its own imputing/encoding/vectorizing
```

### Threshold

**Decided 2026-10-17: the cut-off maximizing F1 on the validation split, for every model.** This is Person 3's
`ml.lgbm.choose_threshold`, and `ml/run.py` applies the same rule to the baseline. It is consistent with
LightGBM's calibration, which is also fitted on validation. The cost: validation has only 122 fraud rows, so the
cut-off is somewhat noisy, and validation precision/recall at that cut-off are optimistic. The test split, scored
once with `--final`, gives the honest numbers. (Considered and not chosen: 80% recall on train out-of-fold
predictions, 612 fraud rows, which is less noisy but on the uncalibrated scale.) If `--threshold` is omitted,
the report says so, in words, in `threshold.chosen_on`.

### Artifact paths

| What | Where | In git? |
|---|---|---|
| Metrics report | `ml/reports/metrics_<name>.json` | yes — it is the deliverable |
| Fitted model | `ml/models/<name>_v1.joblib` (Person 3's path, adopted for all models) | no — git-ignored |

### Metrics report

`ml/evaluate.py` writes it; `schema_version` is `"1"`. Top level: `model`, `split`, `rows`, `groups`,
`prevalence`, `threshold`, `ranking`, `at_threshold`, `operating_points`, `calibration`, `bootstrap`,
`versions`, `generated_utc`. Two things worth knowing before reading one:

- **PR-AUC's floor is the prevalence (~4.85%), not 0.5.** `ranking.pr_auc_lift_over_prevalence` is the
  honest "better than guessing" number. ROC-AUC is reported but reads flatteringly: ~17k negatives mean an
  FPR small enough to keep ROC-AUC near 0.98 can still leave most flags wrong. Quote `at_threshold.precision`.
- **Intervals resample groups, not rows,** because `ml/AUDIT.md` found no company with both real and
  fraudulent postings — the label is effectively per-company, so test's 122 fraud rows are far fewer
  independent observations than 122. A row bootstrap would report intervals that are too narrow.

### Two notes for Person 3 before picking the stronger model

- **s390x.** `START-HERE.md` puts the server on IBM LinuxONE. XGBoost and LightGBM publish no s390x wheels
  on PyPI. `sklearn.ensemble.HistGradientBoostingClassifier` is competitive on tabular + sparse data and
  adds **no new dependency**, so it is the safe choice; anything else needs a build checked on the box first.
- Log any new package in `docs/open-source.md` (competition rule). `ml/evaluate.py` added none — pandas,
  NumPy and scikit-learn are already listed. `joblib` arrives with scikit-learn but should be listed by
  whoever first imports it directly.
