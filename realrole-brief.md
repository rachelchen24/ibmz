# RealRole: Team Brief

IBM Z Datathon 2026 · October 17–18, 2026 · Last updated 2026-10-17 · @liv

> **New to the project?** Read [START-HERE.md](START-HERE.md) first: the one-paragraph summary, which files to read, a glossary, and notes for AI agents.

## What we're building

**RealRole answers one question: how likely is a company to post real jobs?** For each company it gives a probability, e.g. *"64% of this company's postings are likely to lead to a hire,"* with the reasons behind it. The data comes from **our own dataset**, which we build during the event by having Claude collect company indicators from the web. The indicators we need don't exist in any public dataset, and the datasets that come close aren't reliable enough.

Two audiences use the same score:

- **Investors** check whether a company's job postings reflect real hiring or inflated numbers, and screen their watchlist privately.
- **Job seekers** see, on any posting, how often that company actually hires from its postings.

Track: **Theme 2, AI Secured: Innovation Without Exposure** (see [Why Track 2](#why-track-2)). Four people, each with their own AI coding agent, in four workstreams (see [Team, build order and pitch](#team-build-order-and-pitch)).

### Product components

| # | Component | What it does | Workstream |
|---|---|---|---|
| 1 | **RealRole dataset** | Our own company-level dataset: one row per company, each indicator with its source URL, supporting quote and date collected. Published in the repo as a datathon deliverable. | B |
| 2 | **Collection pipeline** | Claude agents that research each company and return structured indicators; our code verifies every source before a value is accepted. | B · C |
| 3 | **Scoring model** | Turns a company's indicators into a calibrated probability and plain-language reasons, on LinuxONE. | A |
| 4 | **Investor dashboard** | Private watchlist screening: scores, sector comparison, change over time, alerts when a company's posting volume pulls away from its real growth. Watchlists are processed in a confidential zone. | D (UI) · C (zone) |
| 5 | **Browser extension** | Company badge on any job posting (Greenhouse, Lever, Workday, LinkedIn), e.g. **"Acme Corp · 41% likely to hire from postings,"** with a "why?" panel and sources. | D |
| 6 | **Company lookup** | Search any company in our dataset; same score, reasons and sources. | D |
| 7 | **Employer page** | A company sees its score and reasons and can respond or correct a wrong fact. | D |
| 8 | **Model card and fairness audit** | What the score means, how the data was collected, its error rate, limits, and results by sector and company size. | A |

**Company universe:** 300 publicly traded US companies, weighted toward the sectors with the most ghost jobs (about 180, or 60% of the list), with a smaller set from every other sector for comparison. Listed companies are what investors need, and they publish headcount, which gives us ground truth (see [Ground truth](#ground-truth-and-the-probability-score)). The list is fixed at the start of Block 1.

## Why it matters

Job postings are read as a sign that a company is growing, but nothing checks whether they turn into hires. RealRole measures the gap, so the people relying on postings stop being misled by them.

- **Investors.** Hiring activity is watched as a growth signal, and posting counts are an easy number to look at. A company has little reason not to keep extra roles open, since open roles make it look like it's expanding. Our hypothesis is that some companies post far more than they hire. RealRole lets investors tell companies that are really hiring from companies whose postings run well ahead of their actual growth.
- **Job seekers.** Applicants can't see which companies hire from their postings. A company-level probability tells them where an application is likely to be read, before they spend hours on it.
- **The incentive loop.** Once scores are visible to investors, posting bloat starts to cost a company. Companies that trim unfilled postings see their scores improve, so the scores keep changing. That is why RealRole refreshes on a schedule rather than running once: it stays useful as companies respond to it.

**Evidence for the video.** The main evidence comes from our own dataset: the gap between what companies post and how much they actually grow, by sector. We add a short student survey (sent at kickoff): *How many jobs did you apply to this year? How many never responded? Is there a company you applied to more than once and never heard back from?*

**Framing:** we test a hypothesis and show the numbers. We never claim that a named company is deceiving anyone. Scores are probabilities with sources, not accusations, and nothing in the pitch is political. Every outside statistic used in the video gets checked against its source first.

## Why Track 2

Our dataset is built from public sources, so the data we collect is not what needs protecting. Two other things do, and protecting them is the core of the design, not an add-on.

**1. Investors' watchlists are confidential.** The list of companies a fund screens reveals what it holds or plans to trade. Sent to an ordinary cloud service, that list is visible to whoever runs the service. In RealRole, watchlists, alerts and scores for them are handled inside an isolated, encrypted container on LinuxONE. We, the operators, never see which companies a fund looks up; only the fund's own session can read its results. In production this zone would run under **IBM Secure Execution / Hyper Protect**, where even system administrators can't look inside (Michael checks whether it is available on our instance).

**2. The AI must be protected from the companies it scores.** Our collection agents read web pages written by the very companies being scored, and those companies have a reason to game the result. A careers page could carry hidden text aimed at the AI, or a company could publish misleading figures. So:

- The collection agents run in their own **sandboxed container** with no access to the model, the database or any secrets other than the API key they need.
- Every value must come with a **source URL and a quote**; our code fetches the page and rejects the value if the quote isn't there.
- A value that **two sources disagree on is flagged**, not used.
- Each score is **versioned and stored with the sources behind it**, so any change can be traced.

**3. Job seekers' activity stays private.** The extension reads only the current page and sends only the company name. Nothing about what a person views or applies to is stored on our server.

**Pitch line:** *"Investors get an honest hiring signal without revealing what they're watching, and the companies being scored can't tamper with the AI."*

**One question to ask the organizers at kickoff:** does Theme 2 accept protection of users' queries and of the AI pipeline, rather than of a confidential dataset? If they say no, the investor zone is the part to strengthen.

## Official requirements (from the [official rules](https://www.starhacks.org/ibmzdatathon-official-rule))

The requirements are unchanged; the right-hand column says what each rule means for a project built on our own dataset.

### What we must submit (on Hack2Skill)

- [ ] **Demo video, 3:00 maximum**: problem · supporting data · solution overview · how RealRole uses IBM Z (**tech stack, our LinuxONE instance and model**)
- [ ] **Public GitHub repo** with all code, plus **links to every open-source library and framework used**
- [ ] **Title** in this exact format: `[Team Name_IBM Z Datathon 2026 Project]`
- [ ] **Architecture flowchart** and **working prototype** (optional; we include both)
- [ ] All links checked live; **submitted by hand** (bot or script submissions are disqualified)

### Rules and what they mean for us

| Rule | What it means for RealRole |
|---|---|
| All code written October 17–18 | The collection pipeline, prompts-as-code and the dataset itself are all produced during the event. A company list or indicator list written earlier is planning, not code. |
| Both IBM labs mandatory before building | Our scoring stack still matches both: several predictive models together, plus Granite for generated explanations. |
| Must run on LinuxONE Community Cloud, with screenshots | Collection, dataset store, scoring, investor zone and API all run in containers there (see [How we use Linux](#how-we-use-linux-linuxone)). |
| Open-source libraries allowed if linked | Every library is listed in the README. |
| Originality: nothing from other teams or outside sources | No code or ideas from existing fake-job projects. Our dataset is new, which helps here. |
| AI coding agents allowed | The README says we used them. Claude is also a data-collection tool, which is a different use: **ask the organizers at kickoff** whether a non-IBM model may collect data. If not, Claude writes the scrapers and the scrapers collect. |
| No political messaging | Talk about investors, job seekers and data accuracy, never about parties or administrations. |
| Team of 4–6, one project per track | In person at the New York hub (1st $1,000 · 2nd $750 · 3rd $500), plus the Americas AI Innovation Excellence Award. |

Two more of our own rules: **collect only from sources whose terms allow it** (no LinkedIn, Glassdoor or Indeed scraping), and **collect nothing about individual people**.

## How we'll be judged (4 criteria × 10 points)

Our strongest card is the dataset: nobody else will have it.

| Criterion | What judges look for | How RealRole scores high |
|---|---|---|
| Value to community and theme fit | Real problem, clear beneficiaries, theme visible | Two audiences (investors, job seekers) and an incentive loop that pushes companies toward honest postings; confidential watchlists and a tamper-resistant AI pipeline are the design's core |
| Novelty and originality | New idea, built from scratch | A new dataset of company hiring indicators that doesn't exist anywhere, collected by AI with every value sourced and verified |
| Technical design and LinuxONE use | Architecture, AI/ML on LinuxONE, open-source AI, containers, security, scalability, compute | Sandboxed collection container, encrypted dataset store, confidential investor zone, multi-model scoring on LinuxONE, scheduled refresh as Linux services |
| Execution and pitch | Clear, compelling video with a demo, under 3:00 | One finding from our data, then the investor and job-seeker views of the same company |

**AI Innovation Excellence Award angle:** an AI collection pipeline that verifies its own sources and resists manipulation, feeding a calibrated multi-model score.

## Our dataset

We build the RealRole dataset ourselves because the indicators we need aren't in any existing dataset, and the existing job-posting datasets aren't reliable enough to trust. Claude agents collect it from public sources during the event; our code checks every value before it is kept.

### Three tables

| Table | One row per | Holds |
|---|---|---|
| `companies` | Company | Ticker, name, sector, size, and the 30 features below |
| `postings` | Posting seen on a company's careers site | Title, location, posted date, salary range, description, date we saw it |
| `evidence` | Collected value | The value, source URL, supporting quote, page date, date collected, and whether our check passed |

### The indicators (model features, 30)

RealRole scores companies, so each feature is **one number per company**. Features that start from single postings are rolled up over the company's open postings: a share, a median or a mean. Most come from our own `postings` table; the rest come from `evidence` rows collected from filings and other sources. Occupation norms (typical salary, description length, requirements and time to close for each occupation) are learned across all postings in our table plus the Kaggle LinkedIn set (2023–24), which is used only for norms.

**Posting volume and growth (6)**

| # | Feature | Definition (per company) | Why it signals real or inflated hiring | Source |
|---|---|---|---|---|
| 1 | `postings_per_100_employees` | Open postings ÷ latest employee count × 100 | Many more postings than a company could plausibly fill | ATS board; employee count from filings |
| 2 | `open_postings_log` | log(1 + open postings) | Size of the posting footprint, apart from company size | ATS board |
| 3 | `posting_trend_vs_revenue` | 12-month % change in open postings minus % change in revenue | Postings climbing faster than the business is growing | Wayback Machine archives; revenue from filings |
| 4 | `revenue_growth` | Latest fiscal year's revenue growth | Context: a growing company has more reason to hire | 10-K / XBRL |
| 5 | `sector_postings_trend` | 90-day % change in Indeed's US postings index for the company's sector | Context: is the whole sector posting more? | Indeed Hiring Lab (`job_postings_by_sector_US.csv`) |
| 6 | `bulk_posting_share` | Share of open postings posted on the company's busiest 3 days | Batches of roles listed at once, often from a template | ATS posted dates |

**Posting lifetime (3)**

| # | Feature | Definition (per company) | Why | Source |
|---|---|---|---|---|
| 7 | `share_open_90_plus` | Share of open postings with posted date 90+ days ago | Roles that stay open long past normal hiring time | ATS posted dates |
| 8 | `open_vs_expected` | Median of days open ÷ `expected_days_to_close` (from the survival model, by occupation, Job Zone, sector, location and seniority) | Same idea, but fair to roles that normally take long | Survival model on `postings` |
| 9 | `no_real_deadline_share` | Share with no closing date, a closing date 180+ days out, or "until filled" / "rolling" / "open until" wording | Postings not tied to a hiring timeline | Posting text and dates |

**Reposting and duplication (6)**

| # | Feature | Definition (per company) | Why | Source |
|---|---|---|---|---|
| 10 | `repost_rate` | Share of postings whose normalized title + location reappeared with a new ID within 90 days | The same role recycled instead of filled | `postings`, across snapshots and archives |
| 11 | `median_days_between_reposts` | Median gap between those reposts; NaN if fewer than 2 | Regular, scheduled reposting | Same |
| 12 | `deleted_and_reposted_share` | Share of postings that disappeared and reappeared within 60 days with text of cosine similarity > 0.9 | Hiding a posting's age | Same, plus Granite embeddings |
| 13 | `same_role_many_locations` | Median number of locations per normalized title currently open | One job listed in dozens of cities | `postings` |
| 14 | `template_similarity` | Median, over the company's postings, of each posting's highest cosine similarity to its other current postings | Boilerplate rather than specific vacancies | Granite embeddings |
| 15 | `text_pc_1..5` | Company's mean Granite embedding of title + description, reduced to 5 components with PCA (fit on training folds only) | What kinds of roles and wording the company posts | Granite embeddings |

**Posting quality (10)**

| # | Feature | Definition (per company) | Why | Source |
|---|---|---|---|---|
| 16 | `salary_listed_share` | Share of postings with a salary minimum, maximum or midpoint | Openness about a real role | Posting text / ATS fields |
| 17 | `salary_missing_where_required` | Share of postings in NY, CA, CO or WA with no salary range | Low care about the posting being filled | Posting text and location |
| 18 | `salary_range_ratio` | Median of max ÷ min, after converting to yearly pay | Very wide ranges suggest no specific role | Posting text |
| 19 | `salary_vs_occupation` | Median of (salary midpoint − the occupation's median) ÷ the occupation's interquartile range | Pay far off the market for the role | Posting text; occupation norms |
| 20 | `specificity_score` | Mean of a 0–4 score per posting: +1 each for a start date, a reporting line ("reports to," "hiring manager"), an interview process ("interview process," "rounds," "steps"), and 3+ named tools | Real vacancies tend to be specific | Posting text |
| 21 | `named_team_share` | Share mentioning a named team, group or project ("join the Payments team") | Same | Posting text |
| 22 | `seniority_mismatch_share` | Share where an intern/junior/entry title asks for 5+ years, or a senior/lead/principal title asks for 1 year or less | Postings written without a real role in mind | Title and text |
| 23 | `vague_phrase_rate` | Mean count per posting of "talent community," "talent pool," "pipeline," "future opportunities," "evergreen," "always looking," "always hiring," "may not be an active," "general application," "expression of interest" | Postings not tied to a vacancy | Posting text |
| 24 | `requirements_vs_job_zone` | Median of requirement bullets ÷ the median for the same Job Zone | Wish lists far beyond the role's level | Posting text; O*NET Job Zones |
| 25 | `description_length_z` | Median absolute z-score of word count within the occupation group (very short and very long are both unusual) | Placeholder or copy-paste descriptions | Posting text |

**Company signals (3)**

| # | Feature | Definition (per company) | Why | Source |
|---|---|---|---|---|
| 26 | `days_since_layoff` + `layoff_workers` | Days since the latest layoff event (NaN if none in 24 months) and the workers affected | Cutting staff while still posting | State WARN notices, 8-K filings, earnings calls, press releases |
| 27 | `hiring_freeze_stated` | A hiring freeze or pause stated in the last 12 months | Freezing hiring while still posting | Earnings calls, press releases, 8-Ks |
| 28 | `management_hiring_tone` | Score from short quotes on hiring: "disciplined headcount," "slowing hiring" vs. "investing in talent" | What management says vs. what the careers site shows | 10-K, earnings calls, shareholder letters |

**Occupation mix (2)**

| # | Feature | Definition (per company) | Why | Source |
|---|---|---|---|---|
| 29 | `mean_job_zone` + `top_soc_group_share` | Mean O*NET Job Zone of the company's postings, and the share in its most common SOC major group (titles matched by exact match, then character n-gram TF-IDF ≥ 0.6) | Context: some occupations take longer to fill | O*NET titles and Job Zones |
| 30 | `long_cycle_share` | Share of postings for intern, summer analyst, campus, new grad, fellowship, residency or executive-search roles | Context: these open long on purpose and shouldn't count against the company | Title and text |

**Left out on purpose:**

- **Headcount change** and anything built from it, including a postings-to-hires ratio: that is the ground truth ([Ground truth](#ground-truth-and-the-probability-score)), so the model would just read off the answer.
- **LinkedIn-only fields** (sponsored postings, relisted flag, LinkedIn skill tags): we don't scrape LinkedIn, so live postings don't have them.
- **NYC payroll hires by title:** this version scores public companies, not city agencies.
- **Anything per day open** (like applications per day): not available from ATS boards, and it mixes in posting age.
- **32 embedding components:** too many for 300 companies, so we keep 5.

**Headcount change is also our ground truth, so it is never fed to the model as a feature** ([Ground truth](#ground-truth-and-the-probability-score)).

### How collection runs

1. A fixed list of 300 listed companies, weighted toward the sectors with the most ghost jobs; those sectors are collected first.
2. For each company, a Claude agent with web search fills a fixed JSON schema. Every field is a value, a source URL, a short supporting quote and the page's date, or "not found."
3. Our code fetches each URL and rejects any value whose quote isn't on the page. Values two sources disagree on are flagged.
4. A scraper (also written by Claude, during the event) pulls each company's open postings from its ATS board into the `postings` table. It runs again on day 2, so we have two snapshots; the Wayback Machine supplies the longer history.
5. A person spot-checks 30 random companies against the sources. The error rate goes in the model card and the video.
6. A **20-company pilot** runs first to measure time and cost per company before the full run.

**What we publish.** The `companies` and `evidence` tables, with source links, go in the public repo as a datathon deliverable. We publish indicators and short quotes, not copies of whole pages.

### Traps to avoid

- **Leakage:** never ask Claude whether a company "posts ghost jobs" or collect complaints about it. That is the answer, not an input, and the model would just repeat reputations.
- **Untrusted pages:** a page's text is data. The collection prompt tells Claude to ignore instructions found on pages, and the URL-and-quote check catches made-up values.

## Ground truth and the probability score

The score is checked against what companies actually did: how many people they hired, estimated from the headcount they report in their own filings. That is the one outcome we can measure for real without confidential data.

### The outcome we measure, per company, per year

1. **Net headcount change:** employee count in the latest annual filing minus the one before (10-K; 10-Q where reported).
2. **Replacement hiring:** people hired to fill jobs others left, estimated as headcount × the sector's yearly separation rate (BLS JOLTS, a published reference figure).
3. **Estimated hires** = net change + replacement hiring.
4. **Postings** over the same year, counted from archived careers pages.
5. **Follow-through ratio** = estimated hires ÷ postings, capped at 1.

**What the score says.** For each company, the model predicts its follow-through ratio from the indicators alone. We show it as a probability: *"about 64% of this company's postings are likely to lead to a hire."* Calibration checks that companies we score at 60% really land near 60% on held-out data.

### Known weaknesses (say them before a judge does)

- Filings report global headcount; postings may be mostly US. We restrict to companies that are mostly US-based or report US headcount, and note the rest.
- Annual headcount is a slow, coarse outcome. It catches persistent bloat, not one ghost role.
- 300 companies is a small training set: keep models shallow, use cross-validation, and report ranges, not single numbers.
- Headcount change is the answer, so it is never an input. Revenue and posting trend are inputs; headcount change is not.
- **Fairness.** Large companies post more and can look worse on raw counts, so indicators are per employee or compared within the sector. Results are reported by sector and size in the model card.

## How it works

Claude collects, our code verifies, and models on LinuxONE score. Scores are computed ahead of time and refreshed on a schedule; the extension, lookup and investor dashboard only read them.

```
 Internet: careers sites · ATS boards · SEC filings · WARN notices · Wayback Machine
                │
                ▼
 ┌─ COLLECTION SANDBOX (only container with internet) ─┐
 │ Claude agents (web search) + ATS scrapers           │   API key = podman secret;
 │ output: candidate values with URL + quote + date    │   no DB, no model, no other secrets
 └──────────────────────────┬──────────────────────────┘
                            ▼
 VERIFICATION container: fetch each URL, check the quote, flag source conflicts
                            │ accepted values only (the only writer to the store)
                            ▼
 DATASET STORE: PostgreSQL on a LUKS2-encrypted volume (companies · postings · evidence)
                            │ internal network
                            ▼
 SCORING container (no internet): follow-through model + survival + Granite embeddings
   + surge detection + calibration + SHAP/Granite reasons → versioned scores with evidence links
                            │ published scores only
            ┌───────────────┴──────────────────────────┐
            ▼                                          ▼
 PUBLIC API (only published port)          INVESTOR ZONE (own container, encrypted volume,
   extension · lookup · employer page        own internal network): watchlists, alerts and
   ← company name only                       scores for them; operators can't read it
```

Only the collection sandbox reaches the internet, nothing enters the dataset without passing verification, and investors' watchlists never leave their zone.

### The models (Workstream A)

Several models work together, matching both mandatory IBM labs (multi-model predictive, plus predictive + generative):

1. **Follow-through model (predictive):** gradient-boosted trees, with a regularized linear model as the baseline, predicting each company's follow-through ratio from its indicators.
2. **Posting-lifetime survival model (predictive):** on the `postings` table, how long postings stay open compared with similar roles elsewhere. Postings still open are handled properly as unfinished (censored) rather than dropped. Each company's result becomes one indicator.
3. **Granite embeddings:** each posting is embedded to find near-duplicates, template text and roles listed in many locations.
4. **Surge detection (predictive):** flags a company whose posting count jumps away from its own history; this drives investor alerts.
5. **Calibration and ranges:** turns predictions into honest probabilities and shows a range for each score.
6. **Explanations (SHAP + Granite, generative):** the top drivers become plain sentences, each linked to its evidence row.
7. **Extraction (Granite, generative):** reads the company name from the posting page or pasted text and matches it to our `companies` table.

Claude is used only to collect and to write code; scoring, explanations and extraction run on LinuxONE with open-source models and IBM Granite.

### Extension and lookup (Workstream D)

The extension reads the employer from the page's structured `JobPosting` data (Greenhouse, Lever, Workday) or its layout (LinkedIn) and shows the company's badge. A company outside our dataset shows **"Not in our dataset yet."** Ground rules: read only the current page, send only the company name, phrase everything as likelihood, never "fake."

### Investor dashboard (Workstream D with C)

A fund logs in, uploads or types a watchlist, and sees scores, sector comparisons, trends and alerts. The watchlist and everything computed from it stay inside the confidential zone.

## How we use Linux (LinuxONE)

RealRole is a pipeline that keeps running, and Linux on LinuxONE gives each stage its own container with only the access it needs. The collection stage is the only one on the internet, the dataset sits on an encrypted volume, and investors' watchlists live in a separate zone.

| Stage | Linux mechanism | Screenshot for judges |
|---|---|---|
| Collection sandbox (Claude agents + scrapers) | Its own container, the only one with internet access; the Claude API key held as a `podman secret`, never in the image or repo; read-only root filesystem, capabilities dropped, CPU and memory capped | `podman ps`; `podman secret ls`; the run's log in `journalctl` |
| Verification | Separate container that fetches each source and checks the quote; it can write to the dataset, the collection sandbox cannot | Log of accepted and rejected values |
| Dataset store | PostgreSQL in a container on a LUKS2-encrypted volume | `cryptsetup status`; `podman volume inspect` |
| Scheduled refresh | Podman Quadlet units run by a systemd timer: new postings snapshot every day, full company refresh every week (cron as fallback) | `systemctl list-timers` |
| Scoring | Model container on an internal Podman network (`podman network create --internal`), no internet | `podman network inspect`; batch-scoring time |
| Investor zone | Separate container and encrypted volume on its own internal network; reads published scores, never the collection side; request bodies not logged | The "access denied" test: the API and scoring containers cannot read the zone's volume |
| Public API | The only published port; serves scores to the extension and lookup | A `curl` returning a company's score |
| Hardware crypto | LUKS2 with AES runs on LinuxONE's on-chip crypto unit (CPACF); protected keys if a Crypto Express adapter is present | `lszcrypt`, crypto flags in `/proc/cpuinfo`, `icastats` before and after |
| AI on Telum | Models run through IBM's AI Toolkit for IBM Z (Snap ML) where the accelerator is exposed | `uname -m` (s390x), `lscpu`, the `nnpa` flag in `/proc/cpuinfo`, benchmark |
| Scale | Load test on the API; time to rescore all companies | Requests per second, `podman stats` |

**An honest limit for the pitch:** on the Community Cloud we have root, so we could look inside the investor zone ourselves. IBM Secure Execution closes that gap in production, which is why the design names it.

**Michael checks at setup and posts the answers:**

- [ ] Can our instance reach the internet, and the Claude API? If not, collection runs on a laptop and only the verified dataset is copied to LinuxONE (stated in the README).
- [ ] Does `pip install anthropic` work on s390x? If not, the collection code calls the API with plain HTTP requests.
- [ ] Do we have sudo for `cryptsetup` and SELinux labels?
- [ ] Is Podman 4.4+ installed (needed for Quadlet)?
- [ ] Are Secure Execution, the Telum accelerator, a Crypto Express adapter and Granite available?

Claude Code, the agents writing our code, runs on our laptops; the code runs on LinuxONE.

## Team, build order and pitch

Same four people; the dataset becomes the biggest workstream, so B owns it and A starts modeling as soon as the pilot rows exist.

| Workstream | Person | Agent builds (folders) |
|---|---|---|
| **A: AI/ML** | ML lead (grad) | `ml/`: indicators from postings, follow-through model, survival model, embeddings, surge detection, calibration, explanations, model card |
| **B: Dataset** | Data lead | `collect/`, `verify/`, `dataset/`: company list, Claude collection agents, ATS scrapers, source verification, ground-truth headcounts, spot check, published dataset |
| **C: Platform** | **Michael** (LinuxONE) | `deploy/`, `api/`, `zone/`, `scripts/`: containers, networks, encrypted volumes, timers, API, investor zone, Telum, load test, screenshots |
| **D: Product** | Product and pitch lead | `extension/`, `lookup/`, `investor/`, `employer/`: badge, lookup, investor dashboard, employer page |

Each agent works only in its own folders, on its own git branch, against the shared contracts in the [build plan](realrole-build-plan.md). The person reviews and merges their agent's work. **Shared contracts for `CONTRACTS.md` at kickoff:** the three dataset tables (`companies`, `postings`, `evidence`) and the score response (probability, range, reasons with evidence links, date refreshed, "not in dataset").

### What humans do vs. what agents do

| By hand (people) | By agents (with human review) |
|---|---|
| Complete the **two mandatory IBM labs** | All code for the build plan tasks |
| LinuxONE logins and keys; store the Claude API key as a `podman secret`; anything needing passwords or accounts | Collection agents, ATS scrapers, the verifier |
| Michael: run the setup checklist; **ask the organizers about Claude for data collection and about Theme 2** | Ground-truth headcount extraction, indicators, models |
| Sign off the **company list** at the start of Block 1 | API, store, containers, timers, investor zone, benchmark scripts |
| **Spot-check 30 random companies** against their sources | Extension, lookup, investor dashboard, employer page |
| Run the **student survey** (send the form at kickoff) | Tests, README draft, open-source link list, dataset docs |
| Pick the demo company and a demo watchlist | Charts from finished results |
| Turn each task brief into a master prompt with your agent; review every pull request; merge; decide when a block is done | First drafts of the model card and architecture diagram |
| Take the **screenshots** for judges; write, record and edit the video to under 3:00; fact-check every number | |
| **Submit on Hack2Skill** (must be done by a person) | |

### Build order

Work through the blocks in order; within a block, the four workstreams run in parallel. **Task briefs for every block are in [realrole-build-plan.md](realrole-build-plan.md).** There are no ready-made prompts: each person explores their task with their agent, settles the open questions, has the agent draft a **master prompt**, edits it, then sends it. Final master prompts are saved in `docs/prompts/`.

| Block | A: AI/ML | B: Dataset | C: Platform | D: Product | Done when |
| --- | --- | --- | --- | --- | --- |
| 0 Kickoff | Config | Company list; collection schema | Python on s390x, Podman, internet check | Repo, extension scaffold | Both labs done; organizers asked about Claude and Theme 2; contracts written |
| 1 Pilot | Indicator code on pilot rows | 20-company pilot; verifier; ATS scraper | Collection and verification containers; encrypted store | Placeholder badge | 20 verified companies in the store |
| 2 Full data, first model | Follow-through + survival models; first scores | Full run; ground-truth headcounts; day-2 snapshot | Scoring container; API; timers | Real badge; lookup v1 | Real scores in the badge |
| 3 Investor side | Surge detection; Granite explanations | 30-company spot check; first findings | Investor zone; access-denied test; Telum; load test | Investor dashboard; employer page | Watchlist scored inside the zone |
| 4 Results | Calibration, fairness, model card | Publish dataset; findings chart | End-to-end test; final benchmark | Polish; demo mode | Full demo runs twice unaided |
| 5 Freeze | Bug fixes only | Bug fixes only | Bug fixes only | Bug fixes only | Submitted by hand; links live |

[Improvements](#improvements-if-time) happen only between Blocks 4 and 5, once Blocks 0–4 work end to end. Sleep in shifts, and never have both people a task depends on asleep at once.

### Video plan (3:00 maximum, required content in order)

| Time | Segment | Shows |
|---|---|---|
| 0:00–0:25 | **Problem** | Postings are read as growth, but nobody checks whether they become hires |
| 0:25–0:50 | **Supporting data** | Our dataset's headline finding: postings vs. actual hiring by sector; survey number |
| 0:50–1:15 | **Solution** | "RealRole tells you how likely a company is to post real jobs"; architecture |
| 1:15–2:15 | **Demo** | Same company twice: investor watchlist with an alert, then the job-seeker badge and "why?" with sources; employer response |
| 2:15–2:50 | **IBM Z** | Collection sandbox, verification rejecting a bad value, encrypted store, investor zone access denied, timers, scoring on LinuxONE, benchmark |
| 2:50–3:00 | **Close** | Who it helps and the incentive loop |

Record at least one full backup take. Stay under 3:00: going over costs points.

### Likely judge questions

| Question | Our answer |
| --- | --- |
| "Can you trust data an AI collected?" | Every value has a source URL and a quote our code checks on the live page; we hand-checked 30 companies and report the error rate. |
| "What is your ground truth?" | Hiring estimated from the headcount companies report in their own filings, plus normal replacement hiring for their sector. |
| "Where's the confidential part?" | Investors' watchlists, which reveal their positions, are processed in an isolated encrypted zone; in production, Secure Execution keeps even us out. |
| "Can companies game it?" | Collection is sandboxed, every value needs a verified source, conflicting sources are flagged, and every score keeps its evidence trail. |
| "Is it fair to companies?" | Probabilities with sources, compared within the sector; companies can respond and correct facts; audited by size and sector. |
| "Couldn't this run on a laptop?" | The scoring could. Keeping investors' watchlists private from the operator can't; that needs LinuxONE's isolation. |

## Improvements, if time

Only after Blocks 0–4 work end to end, in this order: grow the company list · score history chart per company · "I applied" tracker in the extension · sector leaderboard.

**Roadmap (not built):** daily refresh at scale · an investor data feed · a monthly posting-bloat report by sector · production under Secure Execution.
