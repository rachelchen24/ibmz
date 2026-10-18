# Model card: RealRole scam-risk score

**In one line:** for a single job listing, the probability that it is a scam posting, with the reasons behind it. It's an automated estimate, not proof of fraud.

| | |
|---|---|
| Model | LightGBM (gradient-boosted trees) with sigmoid calibration. File: `ml/models/lgbm_v1.joblib` |
| Built by | Person 2 (features, baseline), Person 3 (LightGBM, calibration, threshold), Person 4 (evaluation), Person 1 (data, split) |
| Training data | EMSCAD (Kaggle "Real / Fake Job Posting Prediction", CC0): 17,880 listings from 2012–2014, 866 labeled fraudulent |
| Output | `risk` 0–1, band low / medium / high, flagged when `risk ≥ 0.153`, plus 3–6 reasons and a one-sentence summary |
| Version | split `v1`; threshold rule: best F1 on validation (team decision 2026-10-17) |

## Intended use

- **For:** helping a job seeker decide whether to look more carefully before applying or sharing personal details.
- **Not for:** proving that a listing or company is fraudulent; automated removal of listings; judging a company's hiring overall. It is also **not** a ghost-job probability: the label marks scams, not roles that never get filled.

## Data and evaluation design

**Cleaning:** HTML entities unescaped, run-together words split, anonymized URL/email/phone hashes replaced with plain tokens, salary and location parsed, and 281 exact duplicates removed. The result is 17,599 listings (`ml/AUDIT.md`).

**Split by company, not by row.** No company in the data has both real and fake listings, so a random split would let the model memorize companies. A random split put 80% of test rows in companies seen in training, and doubled a company-text-only model's PR-AUC (0.46 vs 0.21).

| Split | Listings | Share | Scams |
|---|---|---|---|
| Train | 12,571 | 71% | 612 |
| Validation | 2,514 | 14% | 122 |
| Test | 2,514 | 14% | 122 |

Train also has 5 cross-validation folds. Splits are stratified and no company crosses one.

**Selection used only train and validation.** LightGBM was tuned on the 5 CV folds (20 configurations), then calibrated and thresholded on validation. **The test set was scored once,** at the end.

## Results

### Test set: 2,514 listings, 122 scams, scored once

95% intervals resample whole companies, not rows.

| Metric | Value |
|---|---|
| PR-AUC (main metric; chance = 0.049) | **0.739** (0.57–0.89), 15× chance |
| ROC-AUC | 0.946 (0.90–0.98) |
| At the threshold (0.153): flagged | 126 listings (5.0%) |
| At the threshold: precision | **66%**, i.e. 2 in 3 flags are scams |
| At the threshold: recall | **68%** of scams caught |
| At the threshold: false-positive rate | 1.8% of genuine listings flagged |
| Calibration: Brier score | 0.023 (always guessing the base rate = 0.046) |
| Calibration: ECE | 0.021 |

Other operating points on test:

| Recall target | Precision | Listings flagged |
|---|---|---|
| 50% | 93% | 67 |
| 70% | 53% | 162 |
| 80% | 37% | 291 |
| 90% | 36% | 305 |

### Validation and model comparison

| Model | Validation PR-AUC | CV PR-AUC (train folds) |
|---|---|---|
| Logistic regression (baseline) | 0.573 (0.40–0.83) | 0.656 |
| **LightGBM (chosen)** | **0.620** (0.46–0.82) | **0.680 ± 0.177** |

LightGBM was chosen for its better ranking and much better calibration (validation Brier 0.027 vs 0.049).

### What the model relies on

Share of the average per-listing contribution, on validation:

| Field | Share |
|---|---|
| Company description | 35% |
| Job description | 19% |
| Company logo | 10% |
| Country | 8% |
| Requirements | 7% |
| Benefits | 4% |
| Everything else | 17% |

Without `company_profile`, CV PR-AUC drops from 0.68 to 0.62. So a large share of the model is "what fraudulent companies' descriptions look like".

## Fairness and error analysis

Test set (`ml/fairness.py`, `ml/reports/fairness_lgbm_test.json`). The overall false-positive rate (FPR) is 1.8%, and overall recall is 68%.

| Group | Listings | Scams | Recall | False-positive rate | Note |
|---|---|---|---|---|---|
| US | 1,637 | 107 | 68% | 2.8% | Well calibrated: predicted 6.5% vs actual 6.5% |
| Other countries | 877 | 15 | n/a | 0–0.4% | Too few scams to judge |
| Remote | 90 | 4 | n/a | **10.5%** | Genuine remote jobs are flagged ~7× more often than others (1.5%) |
| Part-time | 81 | 10 | 90% | **8.5%** | |
| Contract | 847 | 6 | **0%** | 0.7% | Contract-type scams are missed |
| No company logo | 459 | 112 | 74% | **10.7%** | |
| Has a logo | 2,055 | 10 | **0%** | 0.3% | Scams with a logo slip through |

**Known blind spot: disguised campaigns.** One training fold scored PR-AUC 0.33 instead of about 0.74 because of a single group of 90 scam listings from one "staffing for Oil & Energy" company. They had a logo and detailed technician job descriptions, and the model gave them about 15% risk on average. Well-presented scams are the hardest case. A single campaign can also move the metrics a lot, which is why the intervals are wide.

## Explanations and the IBM Granite summary

- **Reasons:** LightGBM's exact TreeSHAP contributions, summed per input field. For example, "Wording in the job description (e.g. 'earn', 'home')" or "No company logo". Quoted words are always words that appear in the listing.
- **Fields a live page can't show:** company description, requirements and benefits when they aren't given separately; screening questions; and the logo when it can't be seen. These are **left out of the score**: their contribution is set to the training average. That prevents "not shown on the page" from reading as "missing", which is a strong scam signal in EMSCAD. In a check on 200 real listings from public companies, median risk was 0.6% and none was flagged.
- **Granite:**
  - `ml/granite.py` gives IBM Granite only the score and those reasons. Locally that's `granite-3.1-1b-a400m-instruct` (about 20 s per summary on a laptop CPU); on LinuxONE it's watsonx.ai with `granite-3-8b-instruct`.
  - Granite writes one sentence and never changes the score.
  - A wording check rejects drafts that accuse, speculate, or don't start with "This posting". A fixed template is used instead, and the response says which (`summary_source`).
  - The small local model often fails the check; see the Limitations section.

## Limitations

- **Old, narrow data:** 2012–2014 listings from one job board, mostly English and mostly US/UK. Today's scams (crypto, task scams, impersonating real companies) may look different.
- **Small positive class:** 122 scams each in validation and test, from relatively few companies, so all numbers have wide intervals.
- **Domain shift to live pages.** Training listings came with the board's own fields (logo flag, screening questions, company profile). Live pages often don't expose these. They're left out rather than guessed, but the model then has less to go on.
- **The threshold was chosen on validation,** so validation's own precision and recall are optimistic. The test figures above are the honest ones.
- **The local Granite model is small.** On 10 validation listings, **6 of 10** of `granite-3.1-1b-a400m-instruct`'s drafts passed the wording check (median 22 s each on a laptop CPU). The rest said "red flags" or "is a genuine listing" and fell back to the template. Even passing drafts sometimes add loose wording, such as calling a location "a positive sign". The 8B model via watsonx is expected to do better; this hasn't been measured, because it needs IBM Cloud credentials.

## Ethics and privacy

- **The extension sends only the listing's public content,** never anything about the person browsing. Nothing is stored, and request bodies aren't logged.
- **Wording:** user-facing text says "signs often seen in scam postings" and "verify the employer". It never says a listing or company *is* a scam.
- **Groups we don't serve as well:** the remote, part-time and no-logo groups have higher false-positive rates. A flag on those listings deserves extra caution, and the UI should say so.
