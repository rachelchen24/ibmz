# Data audit and split specification (Person 1)

Dataset: `data/fake_job_postings.csv` (EMSCAD via Kaggle, CC0), 17,880 rows × 18 columns. The label `fraudulent` marks scam postings. It is **not** a ghost-job label.

Every number below comes from `python -m ml.audit` (full report: `ml/reports/data_audit.json`).

## How to use it

```python
from ml.split import load_split
df = load_split()                     # 17,599 cleaned rows + group_id, split, cv_fold
train = df[df.split == "train"]       # model fitting; cv_fold 0-4 for cross-validation
val   = df[df.split == "val"]         # calibration and threshold choice only
test  = df[df.split == "test"]        # one final evaluation, by Person 4
from ml.cleaning import FEATURE_COLS, TARGET, TEXT_COLS, CATEGORICAL_COLS, BINARY_COLS
```

`load_split()` checks the CSV's SHA-256 against the split file and refuses to run if the data changed.

**Just want a file?** `data/fake_job_postings_cleaned.csv` holds the same rows and columns as `load_split()`. `python -m ml.split` rewrites it; don't edit it by hand.

Rebuild everything with:
- `python -m ml.split`
- `python -m ml.audit`
- `python -m unittest discover -s ml/tests -t .` (16 tests)

## Split specification (v1, fixed)

| Split | Rows | Share | Fraud | Prevalence | Groups |
|---|---|---|---|---|---|
| train | 12,571 | 71.4% | 612 | 4.87% | 3,271 |
| val | 2,514 | 14.3% | 122 | 4.85% | 656 |
| test | 2,514 | 14.3% | 122 | 4.85% | 655 |

- **Group-aware and stratified:** `StratifiedGroupKFold(7, shuffle=True, random_state=42)`. Fold 0 is test, fold 1 is validation, folds 2–6 are train.
- **CV folds:** train rows also have `cv_fold` 0–4, from `StratifiedGroupKFold(5)` within train, and every fold's prevalence is 4.85–4.89%. Rows outside train have `cv_fold = -1`.
- **No leakage across splits:** no group appears in more than one split or more than one CV fold, and a test checks this.
- **Files:** `ml/splits/split_v1.csv` (job_id → group_id, split, cv_fold) and `split_v1.json` (summary + data hash). Both are committed. Don't change them without telling the team; a new split means `v2`.

### Why group-aware, not plain stratified

- **Company identity predicts the label perfectly.** `company_profile` is the only company identifier. Its 1,707 distinct profiles cover 14,572 rows, and **no profile has both real and fraudulent postings**. One profile has 726 postings; 1,173 profiles have 2 or more.
- **Reposts are everywhere:** 4,550 rows share their description with another row (1,263 groups), and 3,219 share title + description.
- **A random split leaks heavily.** Under a random stratified 85/15 split, 80% of test rows (and 53% of test fraud rows) have their company or posting group in training. In a probe, a model trained on `company_profile` text alone got PR-AUC **0.46 with a random split vs. 0.21 with this split**. Most of a random split's "skill" is memorizing companies.

### Groups

- **Linking rule:** rows are linked if they share a normalized `company_profile` (≥ 30 characters) **or** a normalized `description` (≥ 50 characters), and linked rows are merged into groups with union-find. Hashes inside `#URL_…#` placeholders are kept for grouping, since the same hash means the same link.
- **Why description too:** fraud often has no profile but reuses text. That links fraudulent reposts into one group; the largest has 90 fraud rows.
- **Result:** 4,582 groups (3,297 singletons). The largest group is 723 rows (4.1%), and just 1 group (27 rows) mixes labels.
- **Rejected:** adding `requirements` as a third key merged unrelated companies through boilerplate (5 mixed-label groups).

## Cleaning (`ml/cleaning.py`)

Cleaning is row-wise and deterministic, with nothing fitted, so it runs before the split without leaking information. Imputation, encoding and TF-IDF must be fitted inside the training folds (Persons 2 and 3).

| Issue found | Count | Handling |
|---|---|---|
| Exact duplicates (every field and the label identical) | 281 rows (10 fraud), 0 label conflicts | Dropped, keeping the lowest job_id. Listed in the split file as `dropped_duplicate` |
| HTML entities (`&amp;`, sometimes double-escaped) | 10,303 text values | Unescaped twice |
| Run-together words from lost line breaks (`skillsAbility`) | 30,134 text values | A space is inserted at a lowercase→Uppercase boundary after 2+ lowercase letters ("iPhone" and "McDonald" stay intact; "YouTube" becomes "You Tube") |
| Anonymized `#URL_<hash>#`, `#EMAIL_…#`, `#PHONE_…#` | 6,900 / 1,368 / 608 values | Replaced with `URL_TOKEN` / `EMAIL_TOKEN` / `PHONE_TOKEN`. The hash would identify specific companies; the token keeps the signal (e.g. a phone number in `benefits` means fraud 39.6% of the time) |
| Encoding damage (`�`, `â€™`) | 30 values | Repaired to `'` and similar |
| Empty or whitespace-only strings | 17 values | Treated as missing |
| `salary_range` mangled by Excel into dates (`10-Oct`, `Jun-18`) or `0-0` | 168 of 2,868 | `salary_min`/`salary_max` = NaN, `salary_invalid` = 1. The raw string is kept |
| Salary units not stated | 192 have a maximum under 1,000 (hourly or monthly?) | Kept as given. Don't treat salaries as comparable annual pay |
| `location` "country, state, city" | 17,320 standard, 214 irregular | Parsed into `loc_country`, `loc_state`, `loc_city`, with extra parts kept in the city |
| `department` case/spacing variants | 113 | Lowercased |
| `location` case variants | 288 | Kept as is; lowercase in the encoder if needed |

No row is dropped except exact duplicates. `FEATURE_COLS` lists every raw column except `job_id` and `fraudulent`, plus the parsed columns: 22 in total.

`FEATURE_GROUPS` puts each of the 22 into exactly one group:

| Group | Columns |
|---|---|
| text | the 5 text fields |
| categorical | 6 fields + `loc_country`, `loc_state`, `loc_city` |
| binary | 3 flags + `salary_invalid` |
| numeric | `salary_min`, `salary_max` |
| raw_parsed | `location`, `salary_range`: raw strings whose parsed parts are in the groups above; most pipelines can skip them |

## Schema and missingness

- **Types:** 3 binary columns (`telecommuting`, `has_company_logo`, `has_questions`), all 0/1 with no missing values. The label is 0/1 with no missing values: 866 fraud (4.84%). `job_id` runs 1–17,880, unique and contiguous.
- **Identifier leakage:** `job_id` order tracks the label. Fraud is 18.7% in the highest tenth of job_ids, and 0.4–8.5% in the other tenths (Spearman 0.08, p < 1e-25). The file seems to have been put together with many fraud cases at the end. So `job_id` must never be a feature, and nothing may depend on row order. Our split shuffles groups, so it doesn't.

**Missingness is predictive, so impute with explicit "missing" indicators rather than dropping columns.**

| Column | Missing | Fraud rate if missing vs. present |
|---|---|---|
| salary_range | 84.0% | 4.3% vs 7.8% |
| department | 64.6% | 4.6% vs 5.3% |
| required_education | 45.3% | 5.6% vs 4.2% |
| benefits | 40.4% | 5.0% vs 4.7% |
| required_experience | 39.4% | 6.2% vs 4.0% |
| function | 36.1% | 5.2% vs 4.6% |
| industry | 27.4% | 5.6% vs 4.5% |
| employment_type | 19.4% | 6.9% vs 4.3% |
| **company_profile** | 18.5% | **17.7% vs 1.9%** |
| requirements | 15.1% | 5.7% vs 4.7% |
| location | 1.9% | 5.5% vs 4.8% |

Other strong signals:

- **`has_company_logo`:** fraud is 15.9% without a logo vs 2.0% with one.
- **Text length:** fraud postings are shorter. The median requirements length is 249 vs 477 characters.
- **Categorical cardinality:** department has 1,337 distinct values (high-cardinality), industry 131, function 37. `Unspecified` and `Not Applicable` are real categories, distinct from missing.

## Leakage risks and limits

1. **Row order and `job_id` carry label information** (see Schema). Keep `job_id` out of every model, and never use "the first N rows" or a time-ordered split.
2. **Company memorization:** handled by the group split. Persons 2–4 should still keep TF-IDF vocabularies fitted on training folds only, and should report how much of the model's lift comes from `company_profile`.
3. **Missingness and logo are dataset artifacts.** They reflect how EMSCAD was collected (2012–2014, one job board). They predict fraud well here, but may not carry over to postings in the wild.
4. **No dates in the data,** so a time-based split isn't possible. Performance on future postings is untested.
5. **Small positive class:** 122 fraud rows each in validation and test, so PR-AUC on test has wide uncertainty. Report bootstrap intervals.
6. **Mostly English, mostly US/GB.** About 1% of descriptions have significant non-ASCII content. Countries: US 61%, GB 14%, GR 5%.
7. **This label is fraud, not ghost jobs.** It must not be used as RealRole's ghost-job ground truth (`data/README.md`).
