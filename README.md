<p align="center"><img src="extension/icons/logo.png" width="96" alt="RealRole logo" /></p>

# RealRole: is this job listing a ghost job?

**[Team Name_IBM Z Datathon 2026 Project]**: IBM Z Datathon 2026, Theme 2: *AI Secured: Innovation Without Exposure*

RealRole checks a job listing for the signs most often seen in ghost job postings, while you look at it. A browser extension puts a badge on the listing (for example **"74% ghost risk · High ghost risk"**), and **Why?** shows the reasons behind the score. IBM Granite then sums them up in one plain sentence.

Ghost jobs cost applicants time, money and personal data, and many look like normal listings. RealRole gives a second opinion before anyone applies or shares a bank account number or an ID. The score is a probability with reasons, never a verdict: it says "shows signs often seen in ghost postings", not "this is a ghost job".

## How it works

```
Job page (Greenhouse, Lever, Workday, LinkedIn)  or  a pasted link / text on the lookup site
        │  the listing's public content only
        ▼
RealRole API (api/main.py)
  cleaning (ml/cleaning.py) → LightGBM + calibration (ml/lgbm.py) → probability
  → per-field reasons, exact TreeSHAP (ml/explain.py)
  → IBM Granite one-sentence summary, wording-checked (ml/granite.py)
        ▼
Badge + "Why?" panel (extension/)   ·   report page (lookup/)
```

The full diagram, including which IBM lab each part uses, is in [`docs/architecture.md`](docs/architecture.md).

| Part | What it does |
|---|---|
| **Model** (`ml/`) | LightGBM on the text and details of 17,880 labeled listings (EMSCAD, which labels the bad ones "fraudulent"). It's calibrated, so a 70% risk means about 70%. |
| **Explanations** (`ml/explain.py`) | Each score is broken down into the fields that pushed it up or down, quoting words from the listing. |
| **IBM Granite** (`ml/granite.py`) | Writes one sentence from those reasons only. Locally it's `granite-3.1-1b-a400m-instruct`; on LinuxONE it runs through watsonx.ai. A wording check blocks accusations and falls back to a template. |
| **API** (`api/`) | `POST /score` (~100 ms), `POST /summary` (Granite), `GET /health`, `GET /demo`. Standard library only. |
| **Extension** (`extension/`) | Chrome (Manifest V3). Reads the listing on the page and shows the badge and side panel. |
| **Lookup site** (`lookup/`) | Paste a job link (read through the Greenhouse/Lever job APIs or the page's JobPosting data) or the listing's text. |

## Results

From **one evaluation on a held-out test set**: 2,514 listings, 122 ghost listings, from companies the model never saw. The split is by company, because no company in the data has both real and fake listings. A random split would let the model memorize companies; in our check, that doubled a naive model's score.

| | |
|---|---|
| PR-AUC (main metric; chance = 0.049) | **0.739** (95% CI 0.57–0.89) |
| Ghost listings caught at the operating threshold | **68%** |
| Flags that are real ghost listings | **66%**, i.e. 2 in 3 |
| Genuine listings wrongly flagged | 1.8% |
| Calibration (Brier; base rate = 0.046) | 0.023 |
| Real listings from public companies scored live | 200 checked: median risk 0.6%, none flagged |

Everything is in the [model card](docs/model-card.md): how we chose the model (logistic baseline vs LightGBM), calibration, operating points, the fairness check by country, industry, job type, remote work and logo, and the limitations.

## IBM Z and the IBM labs

- **Predictive AI, hybrid multi-model:** a logistic baseline and LightGBM, compared on the same group-aware cross-validation. The calibrated LightGBM serves, with TreeSHAP explanations.
- **Predictive AI + Generative AI:** LightGBM's score and reasons are the only facts IBM Granite sees. Granite writes the summary and never changes the score.
- **LinuxONE:** the API runs in its own container as the only published port, with Granite through watsonx.ai. Screenshots are in `docs/evidence/`. *(Deployment in progress; see [`final_steps.md`](final_steps.md).)*
- **Privacy by design (Theme 2):**
  - The extension sends only the listing's public content, never anything about the person browsing.
  - The API stores nothing and never logs request bodies.
  - The lookup server never logs pasted links or text.

## Run it locally

Requires Python 3.10+ and Chrome.

```
pip install -r ml/requirements.txt
python -m ml.run train --model lgbm      # ~40 min; saves ml/models/lgbm_v1.joblib (already in git; retrain only to change it)
python api/main.py                       # API on http://localhost:8000  (add --no-granite to skip Granite)
python lookup/app.py                     # lookup site on http://localhost:8501
```

- **Extension:** open `chrome://extensions`, turn on Developer mode, click **Load unpacked** and choose `extension/`. Then open http://localhost:8000/demo or any Greenhouse, Lever, Workday or LinkedIn job page.
- **Tests:** `python -m unittest discover -s ml/tests -t .` and `python -m unittest discover -s api/tests -t .`

The first Granite summary downloads the model (~2.6 GB) and then takes ~20 s per summary on a laptop CPU. The badge doesn't wait for it.

## Repository

| Path | Contents |
|---|---|
| `ml/` | Cleaning, split, models, evaluation, fairness, explanations, Granite. See [`ml/README.md`](ml/README.md) and [`ml/AUDIT.md`](ml/AUDIT.md) |
| `api/` | The scoring API. See [`api/README.md`](api/README.md) |
| `extension/` | The Chrome extension. Dev setup: [`extension/dev/README.md`](extension/dev/README.md) |
| `lookup/` | The lookup website |
| `data/` | The EMSCAD dataset and its cleaned copy |
| `docs/` | [Model card](docs/model-card.md), [architecture](docs/architecture.md), [open-source list](docs/open-source.md), saved AI prompts (`docs/prompts/`) |

## Limitations

- **Old training data:** listings from 2012–2014, mostly US/UK and in English, so newer ghost job styles may not be recognized.
- **Polished ghost jobs slip through:** ghost listings with a company logo and detailed text are mostly missed.
- **Some genuine listings are flagged more often:** remote, part-time and no-logo listings (8–11% wrongly flagged vs 1.8% overall).
- **Live pages show less than the training data did.** Fields a page doesn't provide (company description, logo, screening questions) are left out of the score rather than guessed.
- **The small local Granite model** passes the wording check about 6 times in 10; otherwise a template sentence is shown.

## Team

| Name | Role |
|---|---|
| Rachel Chen | Data audit, cleaning and split; API, extension and lookup site |
| Michael Wang | Feature preprocessing and logistic baseline; LinuxONE platform |
| Olivia Moody | LightGBM model, tuning, calibration and threshold |
| Alan He | Evaluation, metrics reporting and integration |

**AI coding agents:** we built RealRole with AI coding agents (Claude Code and GitHub Copilot). People explored each task, reviewed and merged every change, and decided on the data, model and threshold. Saved prompts are in `docs/prompts/`. All open-source libraries, models and data are listed in [`docs/open-source.md`](docs/open-source.md).
