# RealRole: Build Plan

What each workstream builds, in what order, and the details that matter. This file is a **plan, not code**: per the official rules, all code is written during the event (October 17–18).

- **Workstream A: AI/ML** (ML lead + agent A)
- **Workstream B: Data and confidential zone** (data lead + agent B)
- **Workstream C: Platform** (Michael + agent C; Michael owns the LinuxONE server)
- **Workstream D: Product** (product/pitch lead + agent D)

> **New to the project, or an AI agent reading this?** Read [START-HERE.md](START-HERE.md) and [realrole-brief.md](realrole-brief.md) first for what we're building and why. Then read "How to use this plan," Part 1 and Part 2 below, and your own workstream's tasks in Part 4. Items marked *verify* couldn't be confirmed before the event; check them rather than guess.

Tasks are tagged **[AGENT]** (built with your agent), **[HUMAN]** (a person does it: labs, logins, labeling, review, screenshots, video, submission) or **[HUMAN + AGENT]** (the agent drafts, a person checks and decides).

---

## How to use this plan: tasks, not prompts

This plan deliberately contains **no prompts**. Each task below gives the goal, the inputs and outputs, details and starting points, and open questions. The person who owns the task turns it into a prompt during the event:

1. **Read the task brief**, plus `CONTRACTS.md` for anything that touches another workstream.
2. **Explore with your agent first.** Have it look at the actual data and code: column names, row counts, edge cases, what's already in `main`. Discuss approaches, push back, and settle the task's open questions. The details in each brief are starting points, not orders: if the data says otherwise, change the approach.
3. **Have your agent draft a master prompt** for the task, covering the goal, decisions made, inputs and outputs, constraints from `AGENTS.md` and `CONTRACTS.md`, and how to check it worked. **Edit it yourself** until it says exactly what you want.
4. **Send the master prompt** and let the agent build.
5. **Review the result**: run it, read the output, check the "Done when." Iterate in the same conversation as needed.
6. **Save the final master prompt** to `docs/prompts/<workstream>-<task>.md`. It helps teammates see what was decided and documents how the team used AI.

If a decision changes a contract (a table column, an API field), tell the whole team before your agent changes anything.

---

## Part 1: Working in parallel

### 1.1 Ownership

| Workstream | Owns these folders (only this agent edits them) |
|---|---|
| A | `ml/`, `artifacts/models/`, `docs/model-card.md` |
| B | `synth/`, `nyc/`, `enclave/`, `analysis/`, `dashboard/`, `data/labels/gold_sample*.csv` |
| C | `api/`, `deploy/`, `scripts/`, `common/` (after Block 0), `tests/integration/` |
| D | `extension/`, `webapp/`, `employer/` |
| Humans only | `CONTRACTS.md`, `AGENTS.md`, `README.md` (final), `docs/evidence/` (screenshots), `docs/prompts/`, `data/labels/gold_*.csv` |

If an agent needs a change in someone else's folder, it stops and tells its person, who asks the owner.

### 1.2 Git

1. One branch per workstream: `ws-a`, `ws-b`, `ws-c`, `ws-d`. Small commits; push at least hourly.
2. Merge to `main` through a pull request reviewed by the person, not the agent. At the end of each block, all four merge and Michael runs that block's integration check on the server.
3. Never commit `data/raw/`, `data/processed/`, `artifacts/` (except `artifacts/metrics/*.json` and `artifacts/charts/*.png`), keys or `.env` files.
4. Pull `main` into your branch before starting each block.

### 1.3 Nobody waits

- C ships a **placeholder API** in Block 1 that returns the contract's example response, so D builds UI before the model exists.
- B ships **100-row samples** of every table in Block 1, so A and C build against them.
- A ships `ml/features.py` and a **baseline model** in Block 1, so C can load a real model early.

### 1.4 `AGENTS.md` (shared rules, pasted into the repo root at kickoff)

These are standing rules every agent follows, not a task prompt:

```
# Rules for AI agents working on RealRole
- You are one of four agents. Read CONTRACTS.md before writing code; never change it.
- Only edit files in your workstream's folders (CONTRACTS.md "Ownership"). If you need something
  elsewhere, stop and say what you need.
- Python 3, run from the repo root as modules (python -m ml.train_scorer). Paths and constants
  come from common/config.py; never hard-code them.
- The server is IBM LinuxONE (s390x). Prefer packages known to work on s390x; if one fails to
  install, say so instead of silently working around it.
- Never write real personal data anywhere. NYC payroll name columns must never be loaded.
- Scripts print a short summary at the end (rows in/out, key numbers) and support --sample to run
  on the 100-row sample files.
- Write a short test for every function other workstreams use.
- Record every open-source package you add in docs/open-source.md with its link (competition rule).
- Never fabricate results. If something fails or a number looks wrong, report it.
```

---

## Part 2: Shared contracts (copied into `CONTRACTS.md` at kickoff)

These are the interfaces between workstreams. Change them only with the whole team's agreement.

### 2.1 Repo layout

```
realrole/
├── AGENTS.md  CONTRACTS.md  README.md  requirements.txt  .gitignore
├── data/ raw/ processed/ (not in git)   labels/ (gold set, in git)
├── artifacts/ models/ metrics/ charts/
├── common/    config.py  ids.py
├── ml/        cleaning, occupations, weak labels, features, embeddings, survival, scorer,
│              explanations, generation, extraction, scam, evaluation, fairness, export
├── synth/     employers, postings, new hires, NYS-45, samples
├── nyc/       title hiring
├── enclave/   zone setup notes, matching, follow-through, access demo
├── analysis/  ghost gap, NY openings estimate, federal, gold sample, survey
├── dashboard/ app.py
├── api/       main, schemas, model, db, seed_reports, employer
├── deploy/    Containerfiles, compose.yaml
├── scripts/   hwcheck, benchmark, loadtest
├── webapp/    app.py
├── employer/  app.py
├── extension/ manifest.json, content.js, sites/, background.js, badge.css, popup.*, applications.*
├── tests/     unit/ integration/
└── docs/      model-card.md  open-source.md  architecture.png  evidence/  prompts/
```

### 2.2 Constants (`common/config.py`)

| Name | Value | Meaning |
|---|---|---|
| `API_URL` | `http://localhost:8000` | Through the SSH tunnel in the demo |
| `GHOST_LOCK_DAYS` | 30 | Days after "I applied" before ghost options unlock |
| `DEMO_LOCK_SECONDS` | 30 | Lock length in demo mode |
| `COMMUNITY_MIN_RESPONSES` | 10 | Responses needed before the community line shows |
| `COMMUNITY_MIN_GHOST_SHARE` | 0.60 | Share of ghost responses needed |
| `REPORT_EXPIRY_DAYS` | 180 | Older reports stop counting |
| `REPORT_RATE_LIMIT_PER_DAY` | 20 | Per anonymous ID |
| `DP_EPSILON` | 1.0 | Differential-privacy setting |
| `DP_MIN_HIRES` | 10 | Below this, no public follow-through score |
| `VERDICT_BANDS` | `<0.35` Likely real · `0.35–0.65` Uncertain · `>0.65` Likely ghost | |
| `SEED` | 42 | All randomness |

### 2.3 IDs (`common/ids.py`)

- `normalize_company(name)`: lowercase; strip punctuation; remove `inc, llc, ltd, corp, corporation, co, company, the, group, holdings`; collapse spaces.
- `posting_id(source, source_job_id=None, url=None)`: `f"{source}:{source_job_id}"` when the site has a job ID; otherwise `source + ":" + sha256(canonical_url)[:16]` (lowercase host, no query string or fragment).

### 2.4 Tables (Parquet in `data/processed/`; 100-row samples in `data/processed/samples/`)

- **`postings.parquet`**: `posting_id` · `source` (`linkedin` · `nyc` · `open_jobs` · `usajobs` · `synthetic`) · `company_name` · `company_norm` · `title` · `description` · `location` · `state` · `salary_min` · `salary_max` (annual USD) · `salary_listed` · `original_listed_at` · `listed_at` · `expires_at` · `closed_at` · `views` · `applies` · `experience_level` · `remote` · `company_size` · `soc_code` · `job_zone`
- **`employers.parquet`** (synthetic): `fein` · `company_name` · `company_norm` · `industry` · `size` · `turnover_rate` · `ghost_propensity` (**hidden: never a model feature; only used to prove the method works**) · `ui_reg_number`
- **`new_hires.parquet`** (synthetic, NY new-hire report layout): `employee_first_name` · `employee_middle_initial` · `employee_last_name` · `employee_address` · `employee_ssn` (fake) · `date_of_hire` · `employer_name` · `employer_address` · `employer_fein` · `dependent_health_insurance_available` · `health_insurance_qualify_date`
- **`nys45_employer.parquet`**: `employer_fein` · `ui_reg_number` · `quarter_ending_date` · `employees_month1` · `employees_month2` · `employees_month3` · `total_ui_remuneration` · `total_withheld`
- **`nys45_employee.parquet`**: `employer_fein` · `quarter_ending_date` · `ssn` · `last_name` · `first_name` · `middle_initial` · `total_ui_remuneration` · `gross_federal_wages` · `total_nys_nyc_yonkers_withheld`
- **`follow_through.parquet`** (the only hiring-derived table allowed outside the confidential zone): `company_norm` · `period` · `postings` · `hires_noisy` · `follow_through` · `published` · `epsilon`
- **`nyc_title_hiring.parquet`**: `posting_id` · `agency` · `civil_service_title` · `posted_positions` · `starts_4y` · `starts_per_year`

### 2.5 API (FastAPI)

`POST /score` request:

```json
{
  "source": "greenhouse",
  "posting_id": "greenhouse:4567",
  "url": "https://...",
  "title": "Data Analyst",
  "company_name": "Acme Inc",
  "description": "...",
  "location": "New York, NY",
  "salary_min": 70000, "salary_max": 90000,
  "date_posted": "2026-08-01",
  "valid_through": "2026-12-31",
  "raw_text": null
}
```

`source` is one of `greenhouse · lever · workday · linkedin · paste · url`. For `paste`, only `raw_text` is required.

Response:

```json
{
  "posting_id": "greenhouse:4567",
  "ghost_probability": 0.68,
  "verdict": "Likely ghost",
  "reasons": [
    {"text": "Reposted 4 times in 90 days", "impact": 0.18},
    {"text": "Open 94 days (typical for this role: 35)", "impact": 0.12},
    {"text": "No salary listed", "impact": 0.07}
  ],
  "summary": "One-sentence explanation written by Granite",
  "what_to_do": "Ask the recruiter when the role opened and when they expect to hire.",
  "scam_warning": null,
  "employer": {"known": true, "follow_through": 0.21, "warn_notices_12m": 1, "response": null},
  "community": {"show": true, "ghost": 14, "total": 18},
  "page_only": false,
  "model_version": "2026-10-17a",
  "latency_ms": 3.1
}
```

| Endpoint | Request | Response |
|---|---|---|
| `POST /email` | posting fields | `{"subject", "body"}` (Granite follow-up email draft) |
| `POST /applied` | `{"anon_id", "posting_id"}` | `{"ok": true, "applied_at"}` |
| `POST /report` | `{"anon_id", "posting_id", "outcome"}` | `{"ok": true}` or `400 {"error": "locked", "unlocks_at"}` |
| `GET /community/{posting_id}` | | `{"show", "ghost", "total"}` |
| `GET /employer/{company_norm}` | | `{"company_name", "follow_through", "postings_scored", "avg_ghost_probability", "reports", "response"}` |
| `POST /employer/{company_norm}/response` | `{"text", "employer_token"}` | `{"ok": true}` |
| `GET /health` | | `{"ok": true, "model_version"}` |

Report outcomes: `never_heard_back`, `told_filled` (locked 30 days) · `reposted`, `interview_then_vanished` (ghost, any time) · `got_interview`, `got_hired` (real, any time).

### 2.6 Reports database (SQLite on the encrypted volume)

Tables: `applied (anon_id, posting_id, applied_at)` · `reports (anon_id, posting_id, outcome, reported_at, seeded)` · `employer_responses (company_norm, text, updated_at)`. One row per `(anon_id, posting_id)` in `applied` and `reports`.

### 2.7 Ports

API 8000 · web app 8501 · employer page 8502 · policy dashboard 8503.

---

## Part 3: People tasks during the event

### 3.1 Gold set [HUMAN]

A hand-labeled test set: the honest measure of whether the model works.

- **Sample:** agent B produces 300 postings (150 LinkedIn, 75 NYC, 75 open-jobs-data), mixed by industry, seniority and age, split into two batches of 150 (task 1B-6).
- **Labeling:** two pairs; each person labels their pair's batch independently: `ghost`, `real`, `unsure` or `scam`, with confidence 1–3 and an optional note. About an hour each, done while agents build.
- **Guide:** ghost signs are vague duties, no team or manager, "talent community"/"future opportunities" wording, open far longer than normal, repeated reposts, missing or extremely wide salary, seniority mismatch, recent layoffs. Real signs are a specific team, tools or projects, a start date, a named manager, a recent posting with a narrow salary range. Scams (asking for money or bank details, off-platform chat) are excluded.
- **Agreement:** agent A computes Cohen's kappa per pair; each pair spends 15 minutes resolving disagreements → `data/labels/gold_final.csv`.
- **Use:** test set only, never training data.

### 3.2 Survey [HUMAN]

- At kickoff, send a 3-question form to classmates, clubs and friends: jobs applied to in the past 12 months; how many never responded; whether some were never real openings (yes / no / not sure).
- Close it at the start of Block 4; export without names or emails to `data/labels/survey.csv`; agent B summarizes it (task 4B-2).

---

## Part 4: Task briefs

Each task has: the **goal**, **inputs → outputs**, **details and starting points** (suggestions to explore with your agent; change them if the data says otherwise), **open questions** to settle before writing the master prompt, and **done when**.

### Block 0: Kickoff

**Done when:** both IBM labs are complete; everyone can run Python on LinuxONE; the repo has `AGENTS.md` and `CONTRACTS.md`.

**0-1 [HUMAN] Mandatory IBM labs (everyone).** Complete "Predictive AI Hybrid AI scenarios (multi-model)" and "Predictive AI + Generative AI" before building. Confirm whether each member or the team must complete them; save completion screenshots to `docs/evidence/labs/`. Note anything from the labs worth reusing as a pattern (not code) in our design.

**0-2 [HUMAN] Repo and shared files.** Create the GitHub repo; add `AGENTS.md` (1.4), `CONTRACTS.md` (Part 2), `.gitignore`, and an empty `docs/prompts/`. Send the survey.

**0-3 [HUMAN: Michael] Server.** Accounts and SSH keys for everyone; a shared group and folder. Share what the setup session revealed (Secure Execution? Telum accelerator? Granite? inbound ports? disk space?) in `README.md` so every agent can read it.

**0-4 [HUMAN + AGENT] Python and containers on s390x (C).**
- Goal: a working environment on the server, plus confirmation that the container tool works.
- Details: install the key packages one at a time (pandas, pyarrow, scikit-learn, xgboost, lightgbm, shap, fastapi, uvicorn, streamlit, diffprivlib, lifelines or scikit-survival, transformers/sentence-transformers, onnx, matplotlib/plotly); try IBM's AI Toolkit builds for anything that fails; `pip freeze`. Check `podman` (or Docker). A small hardware-check script (CPU features including the AI accelerator, crypto hardware, memory, disk) gives the first evidence screenshot.
- Open questions: which packages fail on s390x, and what replaces them?
- Done when: every teammate can import the key packages on the server.

**0-5 [HUMAN] Data onto the server (B).** Copy `data/raw/` (including the Kaggle LinkedIn folder) to the server once accounts exist; confirm sizes match.

**0-6 [AGENT] Config and IDs (A).** `common/config.py` (2.2 and all paths) and `common/ids.py` (2.3), with tests. Done when the tests pass.

**0-7 [HUMAN + AGENT] Granite check (A).** Get one Granite embedding and one short Granite generation running (on the server or via watsonx, per the setup session). If neither works, choose fallbacks (e.g. a small open embedding model; templates for generation) and write the decision in `README.md`.

**0-8 [AGENT] Scaffolds (D).** Empty extension (manifest only), web app and employer page; load the extension unpacked in Chrome.

---

### Block 1: Foundations

**Done when:** a placeholder badge shows on a real job page; a baseline model with metrics exists; synthetic tables and samples exist; the NYC title-hiring table exists; gold labeling has started.

#### A: AI/ML

**1A-1 [AGENT] Clean LinkedIn postings**
- Goal: the LinkedIn data in the `postings.parquet` schema.
- Inputs → outputs: `data/raw/linkedin/` → `data/processed/postings_linkedin.parquet` + sample.
- Details: posting/original-listing/expiry/closed times are probably epoch milliseconds; salary needs annualizing by pay period; company size comes from the company files; remove empty and duplicate postings.
- Open questions: exact file and column names; how many NY postings there are; how to treat postings without dates.
- Done when: row count, % with salary, % in NY and date range look sane.

**1A-2 [AGENT] Job titles → occupations**
- Goal: an occupation code (SOC) and Job Zone for every posting, from O*NET.
- Details: exact match first, then fuzzy matching (e.g. TF-IDF on character n-grams) with a similarity cutoff; one reusable function for all sources.
- Open questions: what match rate is good enough (≥ 70% is a reasonable target)? How should seasonal programs (summer analyst, internships) be handled?
- Done when: match rate is acceptable and a person has eyeballed 20 random matches.

**1A-3 [HUMAN + AGENT] Weak labels**
- Goal: approximate ghost / real / unknown labels for training.
- Starting rules: **ghost** if 2+ of: relisted or the same company + title posted 3+ times in 90 days; open more than twice the normal time for its Job Zone (60+ days); WARN layoff notice from the company in the prior 180 days; salary max ÷ min > 1.8; 2+ vague phrases. **Real** if closed within 21 days, or specific (team, manager or start date) with a narrow salary range.
- Open questions: do the thresholds fit this data? The ML lead reviews 20 examples per label and adjusts.
- Done when: label counts are reasonable (roughly 10–25% ghost, 15–30% real) and the review is done.

**1A-4 [AGENT] Baseline scorer**
- Goal: a first model the platform can load early.
- Details: gradient-boosted trees on a handful of simple features; split train/test **by company** so no company appears in both; never use the label rules themselves as features (otherwise the model just memorizes the rules).
- Done when: the model file and metrics exist. Its weak-label score is partly circular; the gold set (Block 4) is the honest test.

#### B: Data and confidential zone

**1B-1 [AGENT] Synthetic employers**
- Goal: about 2,000 fake NY employers, each with size, industry, turnover rate and a hidden ghost propensity.
- Details: use NY company names from the LinkedIn postings first (so postings can be matched), real company sizes where known; propensity mostly near 0 with a long tail (e.g. a Beta distribution plus a minority of clear ghost-posters); fake but valid-looking FEINs.
- Open questions: how many ghost-posting employers make the demo interesting without being unrealistic?

**1B-2 [AGENT] Synthetic postings, new hires and NYS-45 wage records**
- Goal: hiring records in the real government layouts (`CONTRACTS.md`), generated so the model has to *find* the pattern rather than have it handed over.
- Details: replacement hires from turnover; each posting leads to a hire with a probability that falls as ghost propensity rises, plus noise; hire delays longer for higher Job Zones; monthly headcount from hires and separations; fake names, NY addresses and fake SSNs (never real-format-valid prefixes like 000, 666 or 9xx).
- Open questions: how much noise? (Too little and results look too perfect.)
- Done when: propensity is clearly but not perfectly negatively related to hires per posting; headcounts never go negative; totals add up.

**1B-3 [AGENT] 100-row samples** of every table, for the other workstreams.

**1B-4 [AGENT] NYC postings vs. actual hires (real data)**
- Goal: for each NYC job title posted in 2026, how many people actually started in that title at that agency in FY2022–25.
- Details: never load payroll name columns; drop placeholder start dates; agency names differ between datasets, so a small mapping table may be needed; dedupe employees across fiscal years before counting starts.
- Open questions: match rate (≥ 60% is a good target); what to do with titles that never match.
- Done when: a person has reviewed the titles with the most posted positions and fewest starts, and vice versa.

**1B-5 [AGENT] Gold-set sample** (see 3.1).

#### C: Platform

**1C-1 [HUMAN + AGENT] Confidential zone**
- Goal: hiring data that only the zone can read, with visible proof.
- Details: if Secure Execution is available, use it and record the attestation. Otherwise: an encrypted volume (e.g. LUKS or gocryptfs) for the synthetic hiring data and reports database, which uses LinuxONE's built-in crypto hardware for AES; the zone job runs in its own container with no network, a read-only filesystem and a dedicated user; it writes only `follow_through.parquet` out.
- Open questions: what does the Community Cloud allow (root? loop devices? which crypto tools show hardware use)?
- Done when: a normal user can't read the hiring files and the zone container can; both screenshotted.

**1C-2 [AGENT] Placeholder API and reports database**
- Goal: every endpoint in 2.5 answering with the example responses, and the database enforcing the rules (30-day lock, one report per user per posting, rate limit, expiry, threshold).
- Details: CORS for the extension and Streamlit pages; a containerized version using a Python base image that exists for s390x.
- Done when: requests to each endpoint return the contract shape; a locked report is rejected and accepted once the lock passes.

#### D: Product

**1D-1 [AGENT] Extension skeleton**
- Goal: a badge on real job pages, using the placeholder API.
- Details: Manifest V3 with storage, alarms and notifications permissions; read the posting from the page's structured `JobPosting` data (Greenhouse, Lever, Workday), including when it's nested; LinkedIn needs its own reader based on visible text and ARIA labels, re-running when the URL changes; the background service worker makes the API calls; badge styles prefixed to avoid clashing with the page.
- Open questions: badge position and look; which sites to prioritize.
- Done when: the placeholder badge appears on three real pages.

**1D-2 [HUMAN] Video outline** (pitch lead): segments and visuals from the brief's video plan.

---

### Block 2: Real model, end to end

**Done when:** a real job page and a pasted listing both get a real score with readable reasons, running in containers on LinuxONE; follow-through shows for known employers.

#### A: AI/ML

**2A-1 [AGENT] Features**: one function used by both training and the API. Starting list (about 45): time (days open, reposts, expiry, same-day bulk posting); engagement (views, applications, ratios); pay (listed?, range width, vs. occupation norm); text (length, requirements count, years required, seniority mismatch, vague phrases, team/manager/start date mentioned, similarity to the company's other postings, reading level); employer (posting volume, postings per employee, repost share, layoffs, same title in many locations); occupation (Job Zone, occupation group, seasonal program, government); survival outputs; text-embedding components. **Open question:** which features matter after a first look at importance?

**2A-2 [AGENT] Text embeddings**: Granite embeddings of title + description, cached, reduced (e.g. PCA to ~32 dimensions) for the scorer.

**2A-3 [AGENT] Time-to-hire survival model**: how long each kind of job normally stays open, treating still-open postings as "not yet known" (censored). Gives `expected_days_to_close` and `open_vs_expected`. Note that closing isn't the same as hiring: this sets the *normal timeline*, while the confidential zone gives hiring evidence. **Done when:** concordance is useful (> 0.6) and long-cycle jobs (Job Zone 5, summer analyst programs) come out longest.

**2A-4 [AGENT] Full scorer**: gradient-boosted trees with all features; positive-unlabeled learning (since only some ghosts are labeled and nothing is confirmed real); calibration so "70%" means about 70%; company-grouped cross-validation. **Open question:** how ambitious to be vs. what to keep simple. **Done when:** it beats the baseline (on the gold set once available).

**2A-5 [AGENT] Explanations**: SHAP top contributions turned into plain sentences with real values ("Reposted 4 times in 90 days", "Open 94 days (typical for this role: 35)"). A person reads 10.

**2A-6 [AGENT] Generative features (Granite)**: a one-sentence summary of each score, a "what to do" tip, and a polite follow-up email to the recruiter. Use only the facts given, never accuse the employer. A person reads 5 of each.

**2A-7 [AGENT] Export** the model in formats the API and Telum path can load (XGBoost JSON, ONNX).

#### B: Data and confidential zone

**2B-1 [AGENT] Matching and follow-through (inside the zone)**
- Goal: per employer, the share of postings followed by real hires.
- Details: link postings to employers by normalized name; subtract expected replacement hiring (from turnover and NYS-45 headcount); allow a lag between posting and hire; add Laplace noise to hire counts with IBM's diffprivlib; suppress small employers. Record how well follow-through tracks the hidden propensity at several privacy levels (ε) for the privacy chart.
- Done when: the relationship is clearly visible and degrades sensibly as ε shrinks.

**2B-2 [AGENT] Ghost-gap chart**: Indeed postings index vs. JOLTS hires and openings, indexed to Feb 2020, 2020–2026. The opening data visual for the video.

#### C: Platform

**2C-1 [AGENT] Real API**: loads models once; scoring = extraction (if pasted) → employer context → features → prediction and calibration → explanations → Granite summary → community counts → the contract response with latency. Unknown companies are scored from the page alone (`page_only`).

**2C-2 [AGENT] Access-denied demo**: a normal user trying to read hiring data or query the zone, failing clearly on camera.

**2C-3 [AGENT] All services in containers** (API, web app, employer page, dashboard, zone job); the zone has no network. Screenshot `podman ps`.

**Done when:** a known NY company returns follow-through; p50/p95 latency measured.

#### D: Product

**2D-1 [AGENT] Real badge**: verdict, percentage and color, top reasons, Granite summary; "Why?" panel with all reasons, employer follow-through, community line and the page-only note. Wording: "ghost-likely," never "fake."

**2D-2 [AGENT] Web app v1**: paste text → verdict, reasons, summary, tip.

---

### Block 3: Tracker, reports, generative features, dashboard

**Done when:** apply → report → community count works; the web app drafts follow-up emails; the dashboard shows the ghost gap and NY evidence; the Telum path works (or the fallback is documented).

#### A: AI/ML
- **3A-1 [AGENT] Extraction from pasted text (Granite):** company, title, location, salary, dates, as validated JSON with a regex fallback. Target: most fields that are present get extracted correctly (a person checks 20).
- **3A-2 [AGENT] Scam warning:** rules for payment/bank/SSN requests, off-platform chat, free-email recruiters, too-good pay, "no interview." Scams get a warning instead of a ghost score.
- **3A-3 [AGENT] Report labels into training:** postings past the community threshold become labels; seeded demo reports are excluded from reported metrics.

#### B: Data and confidential zone
- **3B-1 [AGENT] NY ghost-adjusted openings estimate:** official openings vs. an estimate adjusted by the model's ghost rates by industry. Clearly labeled as an estimate.
- **3B-2 [AGENT] Policy dashboard** (port 8503): ghost gap, NY estimate, NYC evidence (posted positions vs. actual starts), and a privacy slider (follow-through accuracy vs. ε). Plain-language captions and sources on every chart.
- **3B-3 [AGENT] Seeded reports** for the demo postings (agree with C): some clearly ghost, some clearly real, one below the threshold so nothing shows.

#### C: Platform
- **3C-1 [AGENT] Reports, timestamps, threshold** wired into the API; demo mode only when the server allows it.
- **3C-2 [HUMAN + AGENT] Telum path:** run the model through IBM's AI Toolkit (Snap ML or the Deep Learning Compiler) if the accelerator is available; plain XGBoost as the fallback; both must give the same predictions.
- **3C-3 [AGENT] Benchmark and load test:** postings per second and latency on each path; concurrent load on the API with error rate and CPU/memory. Screenshots during the run.

#### D: Product
- **3D-1 [AGENT] "I applied" and "My applications":** saved in the browser only; a server timestamp; a page listing applications with status, countdown and report options (locked ones greyed).
- **3D-2 [AGENT] Report menu and job-board link** on the badge; community line when shown.
- **3D-3 [AGENT] Reminders:** alarm after the lock, notification plus icon count, opening "My applications"; *Still waiting* re-arms it.
- **3D-4 [AGENT] Web app follow-up email** button with copy to clipboard.
- **Done when:** a person runs apply → locked → (demo mode) → reminder → report → count changes, and LinkedIn works on 3 postings.

---

### Block 4: Results and polish

**Done when:** all result numbers exist; the full demo runs twice with nobody touching code; all evidence screenshots are taken.

#### A: AI/ML
- **4A-1 [AGENT] Evaluation:** gold set (baseline vs. full model), weak labels vs. gold, labeler agreement, synthetic recovery of the hidden propensity, and **NYC real-data validation** (do titles we flag have fewer actual hires?). Headline numbers to `artifacts/metrics/summary.json`.
- **4A-2 [AGENT] Fairness check** by company size and industry.
- **4A-3 [HUMAN + AGENT] Model card:** purpose, data, models, results, fairness, limitations, how employers contest.

#### B: Data and confidential zone
- **4B-1 [AGENT] Federal postings vs. hires:** parse agency and dates from USAJOBS text; monthly postings vs. OPM accessions, Jan 2025–Mar 2026; dashboard tab. Describe only what the data shows.
- **4B-2 [AGENT] Survey summary** (3.2).
- **4B-3 [AGENT] Dashboard polish:** consistent style, captions, "data as of" dates, sources.

#### C: Platform
- **4C-1 [AGENT]** All services under compose with restart policies; an integration test that walks the demo.
- **4C-2 [HUMAN: Michael]** SSH tunnel from the demo laptop for all four ports; test from another network.
- **4C-3 [HUMAN]** Evidence screenshots: labs, hardware check, containers, encrypted volume, access denied, Telum/benchmark, load test, dashboard, extension on a real page.

#### D: Product
- **4D-1 [AGENT] Employer page** (port 8502): search a company; follow-through, postings scored, average ghost probability, report counts, public response form.
- **4D-2 [AGENT] Web app polish:** URL input (parse the page's structured data like the extension), scam warning, report button.
- **4D-3 [AGENT] Demo mode toggle** (hidden in the popup).
- **4D-4 [HUMAN]** Choose the final 5 demo postings, seed them, and run the full demo twice.

---

### Block 5: Improvements, if time
From the brief's "Improvements, if time" list, in order. Each on its own branch; merge only if the Block 4 demo still runs.

### Block 6: Freeze and submit [HUMAN]
1. Code freeze: demo-breaking fixes only; tag `v1.0`.
2. `README.md` (human + agent): summary, architecture flowchart, how to run, results, **links to every open-source library and dataset**, a note that the team used AI coding agents (the saved master prompts in `docs/prompts/` show how), team members.
3. Make the repo public; check it logged out.
4. Record the video per the brief's plan: **3:00 maximum**, with the LinuxONE instance and model on screen; record a backup take.
5. Submit on Hack2Skill with the title `[Team Name_IBM Z Datathon 2026 Project]`, video, repo, open-source links and flowchart; click every link; submit early.
