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
