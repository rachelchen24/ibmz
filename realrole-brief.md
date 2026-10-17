# RealRole: Team Brief

IBM Z Datathon 2026 · October 17–18, 2026 · Last updated 2026-10-16

> **New to the project?** Read [START-HERE.md](START-HERE.md) first: the one-paragraph summary, which files to read, the before-the-event checklist, a glossary, and notes for AI agents.

## What we're building

**RealRole is a browser extension that flags likely ghost jobs on the posting you're viewing, plus a web app where you can paste any job listing and get a verdict. Behind both, an AI system on LinuxONE scores the posting and checks whether the employer actually hires, using confidential hiring records that never leave an encrypted, isolated zone on the mainframe.** Track: **Theme 2, AI Secured: Innovation Without Exposure** (with real-time scoring as a Theme 1 feature).

Built by four people, each working with their own AI coding agent, in four parallel workstreams (see [Team and agents](#team-and-agents)).

### Product components

| # | Component | Workstream |
|---|---|---|
| 1 | **Browser extension** (headline for job seekers): badge on any job posting, e.g. **"68% ghost-likely: reposted 4×, open 94 days, no salary,"** with a "why?" panel. Greenhouse, Lever, Workday and LinkedIn | D |
| 2 | **Web app**: paste a listing's text or URL and get a verdict (*Likely real* / *Uncertain* / *Likely ghost*), reasons, and a "what to do" tip; includes a Granite-written follow-up email to the recruiter | D |
| 3 | **Application tracker and community reports**: "I applied," a private "My applications" page, 30-day reminders, reports shown only when many users agree, and a link to report on the job board | D (UI) · C (server) |
| 4 | **Scoring API**: multi-model AI (gradient-boosted scorer + time-to-hire survival model + Granite text embeddings + Granite generative explanations), running on LinuxONE with Telum acceleration where available | A (models) · C (service) |
| 5 | **Confidential hiring-verification zone**: synthetic new-hire and wage records analyzed in an isolated, encrypted container on LinuxONE; only a privacy-protected "follow-through score" per employer comes out | B · C |
| 6 | **Policy dashboard**: the "ghost gap" (job postings vs. actual hires, 2020–2026), a ghost-adjusted NY job-openings estimate, real NYC government evidence (postings vs. actual hires by job title), and the federal 2025 postings-vs-hires comparison | B |
| 7 | **Employer page**: employers see their own follow-through score and can post a public response to reports | D |
| 8 | **Model card and fairness audit**: what the model does, its data, limits, and results by company size and industry | A |

Scope: postings from New York State employers. Leftover ideas and the post-event roadmap are in [Improvements, if time](#improvements-if-time).

## Official requirements (from the [official rules](https://www.starhacks.org/ibmzdatathon-official-rule))

### What we must submit (on Hack2Skill)

- [ ] **Demo video, 3 minutes maximum**, covering: the problem statement · supporting data that validates the problem · solution overview · how RealRole uses IBM Z, **including our tech stack and a demo of our LinuxONE instance and model**
- [ ] **Public GitHub repo** with the complete code, plus **links to every open-source library and framework used**
- [ ] **Project title** in this exact format: `[Team Name_IBM Z Datathon 2026 Project]`
- [ ] Optional but recommended: **architecture flowchart** and **working prototype** (we'll include both)
- [ ] All links checked live before submitting. Submit by hand: entries submitted by bots or scripts are disqualified

### Rules that shape how we work

- **All code must be written during the event** (October 17–18). Nothing before: no code, no scripts, no notebooks. Planning documents, research, and downloading public data are fine. Our build plan is a plan, not code.
- **Both IBM AI/ML labs are mandatory before we start building:** "Predictive AI Hybrid AI scenarios (multi-model)" and "Predictive AI + Generative AI." Our design deliberately matches both: several predictive models working together, plus Granite generative AI.
- **Must run on the LinuxONE Community Cloud**, and judges want **screenshots as evidence** of containerization, security, scalability and compute.
- **Open-source libraries are allowed** if we link them in the submission.
- **Originality:** no code, ideas or projects from other teams or outside sources. AI coding agents are allowed; the README says we used them.
- **Content standards:** no political messaging. Frame the problem around job seekers and data accuracy, not around any party, administration or politician.
- Team of 4–6; one project per track. **We're competing in person at the New York hub** (1st $1,000 · 2nd $750 · 3rd $500), and can also win an Americas AI Innovation Excellence Award.

### How we'll be judged (4 criteria × 10 points)

| Criterion | What judges look for | How RealRole scores high |
|---|---|---|
| Value to community and theme fit | Real problem, clear beneficiaries, theme visible in idea and execution | Job seekers and unemployed workers; privacy-by-design is the core of the architecture, not an add-on |
| Novelty and originality | New idea, built from scratch | Nobody else verifies postings against hiring records; community + AI + confidential data together |
| Technical design and LinuxONE use | Strong architecture, AI/ML on LinuxONE, open-source AI packages, containers, security, scalability, compute | Multi-model predictive + generative AI on LinuxONE; containerized services; encrypted confidential zone; Telum/benchmark; screenshots of all of it |
| Execution and pitch | Clear, professional, compelling video with a demo, within 3 minutes | Scripted, rehearsed video; live demo footage; real numbers |

There is also an **AI Innovation Excellence Award** for unusually novel AI with strong technical depth on LinuxONE. Our multi-model design, survival modeling and privacy-protected verification are aimed at it.

## The problem

Ghost jobs, postings with no real intent to hire, waste job seekers' time and make the job market look stronger than it is. The data that could prove which jobs are real exists, but it's confidential.

- **Job seekers:** hours lost applying to postings that were never going to be filled. The worst-hit are unemployed workers, new grads and career changers.
- **Unemployment claimants:** NY claimants must log job applications each week to keep their benefits, and ghost postings waste that effort.
- **Data accuracy:** job-openings statistics (JOLTS) may count ghost postings, so labor demand looks higher than it is. Official job numbers also get large later revisions (about −818,000 jobs in the 2024 benchmark revision).
- **Why now:** Ontario now requires postings to disclose whether a vacancy exists, and several US states have proposed ghost-job bills.
- **Our own evidence (collected during the event):** a quick survey of students, and the "ghost gap" chart from public data.

All statistics are approximate and from memory. Check each one against its source before it goes in the video.

## How it works

Public postings get scored in real time; confidential hiring records stay inside the confidential zone and confirm or correct those scores.

```
Browser extension ─── posting ──▶ Scoring API (container) ──┐
Web app ───────── pasted text ──▶   multi-model AI on Telum  │
                ◀── verdict, reasons, community count ───────┤
                                                             ▼
Public postings ──┐         ┌─ Confidential zone (isolated, encrypted container) ─┐──▶ Job seekers: badge, verdict
WARN notices ─────┼────────▶│ Posting ↔ hire matching                             │──▶ Employers: follow-through + responses
New-hire reports ─┤ (enc.)  │ Follow-through score + differential privacy         │──▶ Policy dashboard: ghost gap, NY index
UI wage records ──┘         └──────────── keys never leave the zone ──────────────┘
```

### The AI (Workstream A)

Several models work together. This is the "multi-model" and "predictive + generative" pattern from the two mandatory labs.

1. **Ghost-job scorer (predictive):** gradient-boosted trees on about 45 features: time (days open, reposts), engagement, pay, text (vagueness, boilerplate, seniority mismatch), employer behavior (posting volume vs. size, layoffs) and occupation.
2. **Time-to-hire survival model (predictive):** learns how long each kind of job normally stays open, so 12-month summer analyst cycles aren't flagged as ghosts.
3. **Text embeddings (Granite):** turn the job description into numbers the scorer can use.
4. **Positive-unlabeled learning and calibration:** trains on approximate labels and makes "70%" really mean about 70%.
5. **Explanations (SHAP + Granite, generative):** turn the score into plain-language reasons, and draft a follow-up email to the recruiter.
6. **Extraction (Granite, generative):** pulls company, title, salary and dates out of pasted text.
7. **Evaluation:** tested on a hand-labeled gold set and validated on real NYC hiring data.

### Confidential hiring verification (Workstream B)

1. **Matching:** inside the confidential zone, compare each employer's postings with its new hires (minus normal replacement hiring).
2. **Follow-through score:** real hires ÷ postings, with differential-privacy noise added (IBM's diffprivlib) and small employers suppressed. That's the only number that leaves the zone.
3. **Feedback loop:** verified outcomes recalibrate the public scorer, so it learns from confidential data without exposing it.

On the LinuxONE Community Cloud, the confidential zone is an **isolated container with an encrypted data volume, using LinuxONE's built-in cryptographic hardware**. In production it would run under **IBM Secure Execution / Hyper Protect**, where even system administrators can't see inside (*verify* at setup whether Secure Execution is available on our instance; if so, use it).

### The browser extension and web app (Workstream D)

- **Extension:** reads the posting from the page's structured `JobPosting` data (Greenhouse, Lever, Workday) or its page layout (LinkedIn), sends it to the API, and shows the badge. If the company isn't in our data, the score uses the page alone and the badge says so.
- **Web app:** paste text or a URL; Granite extracts the fields; same API; verdict, reasons, "what to do," and a Granite-drafted follow-up email.
- **Scam postings** (asking for payment or bank details, off-platform chat) get a separate scam warning instead of a ghost score.
- Ground rules: read only the page the user is viewing, send only the posting, and phrase scores as likelihoods ("ghost-likely"), never accusations ("fake").

### Application tracker and follow-ups (no accounts)

1. **"I applied"** on the badge saves the job in the user's browser only.
2. **"My applications"** page lists each application with its status.
3. **30-day lock:** *Never heard back* and *Told it was filled* stay grayed out for 30 days, with a countdown. Positive outcomes can be reported any time.
4. **Reminders** after 30 days: notification plus a count on the extension icon. *Still waiting* asks again later.
5. **Sealed timestamp:** the server records only an anonymous ID, the posting and the date, and rejects early ghost reports, so the lock can't be bypassed.
6. **Demo mode:** 30 days become 30 seconds for the video.

### Community reports

1. Options: *Never heard back* · *Told it was filled* (locked 30 days) · *Keeps getting reposted* · *Interviewed, then the role disappeared* · *Got an interview* · *Got hired*.
2. **Shown only when many agree:** at least 10 responses and at least 60% ghost. Example: *"14 of 18 RealRole users reported no response or a filled role."*
3. **Private:** counts only, never who; stored encrypted with an anonymous ID; one report per user per posting; reports expire after 6 months.
4. **Training:** postings that pass the threshold become labels; reporters who agree with others count more.
5. **Report on the job board:** opens the board's own report page; the user submits it.
6. **Employer responses** appear on the employer page (component 7).

For the demo, community reports are **simulated** (seeded test data), and the video says so.

## Why IBM Z / LinuxONE

**Pitch line:** *"Whether a job is real can only be proven with hiring records that legally can't leave the state, so we bring the AI to the data, inside an encrypted zone on LinuxONE."*

| LinuxONE capability | How RealRole uses it | Screenshot evidence for judges |
|---|---|---|
| **Containerization** | API, web app, confidential zone and dashboard each run in their own container (Podman) | `podman ps` showing all services; compose file |
| **Security** | Encrypted volume for hiring data using the built-in crypto hardware; isolated container; keys never leave the zone; "access denied" test | Crypto hardware in use; encrypted volume; the denied access attempt |
| **AI on Telum** | Scorer runs through IBM's AI Toolkit (Snap ML / Deep Learning Compiler) where the on-chip accelerator is available (*verify* on our instance) | Benchmark output; accelerator check |
| **Scalability and compute** | Load test: thousands of scores per second; projected to every US posting daily | Load-test results and CPU/memory graphs |
| **Data gravity** | State wage and benefits systems already run on mainframes; the AI moves to the data | Architecture diagram |

## Data plan

Postings are real public data; hiring records are synthetic, and the video says so plainly. All raw data is already downloaded in `data/raw/` (see [data/README.md](data/README.md)).

| Dataset | Real or synthetic | Used for |
| --- | --- | --- |
| LinkedIn job postings (Kaggle, 2023–24) | Real | Main training data |
| NYC job postings (2026) + NYC payroll (FY2022–25) | Real | Real-world validation: posted titles vs. actual hires |
| open-jobs-data (tech companies, Aug–Oct 2026) | Real | Recent postings, repost tracking |
| USAJOBS postings + OPM federal hires (2025–26) | Real | Federal postings-vs-hires analysis (dashboard) |
| FRED (JOLTS, Indeed index), Indeed Hiring Lab | Real | Ghost-gap chart, NY openings estimate |
| O*NET 31.0 | Real | Job titles → occupations, normal hiring timelines |
| NY WARN layoff notices (2026) | Real | Scorer feature |
| New-hire reports, NYS-45 wage records | Synthetic, in the real government layouts | Confidential matching, follow-through |
| Community reports | Simulated | Badge, threshold logic, extra labels |
| Gold set: 300 hand-labeled postings | Real labels by our team, made during the event | Honest model evaluation |
| Student survey | Real responses, collected during the event | Problem evidence in the video |

## Team and agents

### Four workstreams, four people, four agents

| Workstream | Person | Their agent builds (folders) |
|---|---|---|
| **A: AI/ML** | ML lead (grad) | `ml/`: cleaning, features, scorer, survival model, embeddings, explanations, Granite extraction and email drafts, evaluation, model card |
| **B: Data and confidential zone** | Data lead | `synth/`, `nyc/`, `enclave/`, `analysis/`, `dashboard/`: synthetic records, matching, differential privacy, NYC validation, policy dashboard |
| **C: Platform** | **Michael** (owns the LinuxONE server) | `api/`, `deploy/`, `scripts/`: API, reports database, containers, encryption, Telum, load test, screenshots |
| **D: Product** | Product and pitch lead | `extension/`, `webapp/`, `employer/`: extension, tracker, web app, employer page |

Each agent works only in its own folders, on its own git branch, against the shared contracts (data tables and API formats) in the build plan. The person reviews and merges their agent's work. Contracts change only after telling the whole team.

### What humans do vs. what agents do

| By hand (people) | By agents (with human review) |
|---|---|
| Complete the **two mandatory IBM labs** | All code for the build plan tasks |
| Set up LinuxONE logins, keys and the shared folder; anything needing passwords or accounts | Data cleaning, feature engineering, model training scripts |
| Michael: confirm with organizers whether Secure Execution, the Telum accelerator and Granite are available | Synthetic data generators |
| Write `CONTRACTS.md` and `AGENTS.md` in the repo at the start (copied from the build plan) | API, database, containers, benchmark scripts |
| **Label the gold set** (300 postings, two people each) while agents build | Extension, web app, employer page, dashboard |
| Run the **student survey** (send the form at kickoff) | Tests, README draft, open-source link list |
| Pick the 5–10 real postings for the demo | Charts from finished results |
| Turn each task brief into a master prompt with your agent; review every pull request; merge; decide when a block is done | First drafts of the model card and architecture diagram |
| Load and test the extension in Chrome; click through the demo | |
| Take the **screenshots** for judges | |
| Write the video script, record narration and screen capture, edit to under 3:00 | |
| Fact-check every number in the video against its source | |
| **Submit on Hack2Skill** (must be done by a person) | |

### Before the event (no code allowed)

- [ ] **Michael:** attend the LinuxONE setup session; find out what's available (Secure Execution? Telum AI accelerator? watsonx or local Granite? inbound ports?) and share it with the team
- [ ] Confirm the team name for the title format, and the New York hub's schedule and location
- [ ] Prepare the survey questions (a 3-question form, sent at kickoff): How many jobs did you apply to this year? How many never responded? Do you think some were ghost jobs?
- [ ] Download the LinkedIn dataset (Kaggle) into `data/raw/linkedin/`
- [ ] Read the build plan; each person reads their workstream and the shared contracts
- [ ] Agree on the label guide (in the build plan) so labeling starts quickly
- [ ] Pick 5–10 candidate demo postings on Greenhouse/Lever/LinkedIn (mix of likely real and likely ghost)
- [ ] Verify every statistic you plan to use and save the sources

### Build order

Work through the blocks in order; within a block, the four workstreams run in parallel. **Task briefs for every block (goal, inputs and outputs, details, open questions, done-when) are in [realrole-build-plan.md](realrole-build-plan.md).** There are no ready-made prompts: each person explores their task with their agent, settles the open questions, has the agent draft a **master prompt**, edits it, then sends it. Final master prompts are saved in `docs/prompts/`.

| Block | A: AI/ML | B: Data and zone | C: Platform | D: Product | People (by hand) | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| 0 Kickoff | Config, IDs | Data onto server | Accounts, repo, Python on s390x, containers | Repo, extension scaffold | **Both IBM labs**; contracts + AGENTS.md; survey sent | Labs done; everyone can run code on LinuxONE |
| 1 Foundations | Clean data, occupations, weak labels, baseline model | Synthetic records; NYC postings ↔ payroll | Confidential zone, placeholder API, reports DB | Extension shows placeholder badge | Start gold-set labeling | Placeholder badge on a real page; first model |
| 2 Real model | Full features, embeddings, survival, PU learning, SHAP | Matching, follow-through with DP; ghost-gap chart | Real API, containerized; access-denied test | Real badge; web app v1 | Keep labeling; review PRs | Real scores everywhere |
| 3 Tracker, reports, AI extras | Granite extraction, follow-up emails, scam warning | Policy dashboard: NY index, NYC evidence | Reports endpoint, timestamps, threshold; Telum; load test | "I applied", lock, reminders, reports; LinkedIn | Finish gold set; screenshots | Apply → report → count shows |
| 4 Results and polish | Gold-set and NYC evaluation, fairness, model card | Federal postings-vs-hires; dashboard polish | End-to-end test, tunnel, final benchmark | Employer page; web app polish; demo mode | Survey results; video script | Full demo runs twice with no help |
| 5 If time | [Improvements, if time](#improvements-if-time) | | | | | |
| 6 Freeze and submit | Bug fixes only | Bug fixes only | Bug fixes only | Bug fixes only | Record and edit video (≤3:00), README, flowchart, submit by hand | Submitted; all links live |

Sleep in shifts, and never have both people a task depends on asleep at once.

### Video plan (3:00 maximum, required content in order)

| Time | Segment | Shows |
|---|---|---|
| 0:00–0:25 | **Problem** | A real ghost-job story; the cost to job seekers |
| 0:25–0:50 | **Supporting data** | Ghost-gap chart, NYC postings-vs-hires evidence, our survey number |
| 0:50–1:15 | **Solution overview** | RealRole in one sentence; architecture flowchart |
| 1:15–2:15 | **Demo** | Extension badge on a real posting → "why?" with follow-through and community count → "I applied" → reminder → report → web app paste with Granite email → employer page |
| 2:15–2:50 | **IBM Z** | Tech stack; **LinuxONE instance on screen**: containers running, encrypted zone, access denied, model scoring on LinuxONE, benchmark |
| 2:50–3:00 | **Close** | Impact number and who it helps |

Record at least one full backup take. Stay under 3:00: going over costs points.

## Pitch framing

Lead with people harmed, then the confidential-data problem, then the confidential zone. Keep it non-political: talk about job seekers and data accuracy, never about parties or administrations. Don't claim anyone fakes numbers; say the data that would make the numbers accurate exists but can't be used safely or in time.

| Likely judge question | Our answer |
| --- | --- |
| "Couldn't this run on a laptop?" | The scorer could. Proof can't: it needs confidential hiring records that must stay inside protected systems like LinuxONE. |
| "Isn't your ground truth made up?" | The hiring records are synthetic by necessity. The scorer is validated separately on real data: a hand-labeled gold set and real NYC payroll records. |
| "Who would deploy this?" | Job seekers directly (extension); the NY Department of Labor for its job bank; job boards wanting cleaner listings. |
| "Is it fair to employers?" | Scores are probabilities with reasons, not accusations; employers see their score and can respond publicly; we audited results by company size and industry. |
| "Why is this AI for Good?" | It protects job seekers' and unemployed workers' time and makes labor data more accurate. |
| "What if people report wrongly or on purpose?" | One report never shows; 10+ responses and 60%+ agreement are needed; positive outcomes count too; one report per user per posting; reliable reporters count more; employers can respond. |
| "Does the extension spy on users?" | It reads only the posting on the current page. The list of applications stays in the user's browser; the server only gets an anonymous timestamp. |

## Improvements, if time

Only after Blocks 0–4 work end to end. In priority order:

| # | Improvement | Why it helps | Effort |
| --- | --- | --- | --- |
| 1 | Impact estimate: ghost share × applications × time per application = hours wasted per year in NY | One memorable number for the video | Small |
| 2 | "I applied" in the web app (saved in the browser) | Tracker works for postings the extension can't read | Small |
| 3 | NY pay transparency notice: when a NY posting has no salary range, explain the law and how to file a complaint | A real, enforceable report path | Small |
| 4 | Subsidy jobs-promise check (published NY incentive awards vs. synthetic hiring) | Adds the taxpayer angle | Large |
| 5 | Auto-detect clicks on a site's Apply button ("Did you apply?") | Users don't have to remember to click | Medium per site |
| 6 | Survival model upgrade (DeepSurv-style neural network) | More advanced time-to-hire model | Large |
| 7 | Submit the extension to the Chrome Web Store ($5 fee) | "It's in review" is a strong line | Small (plus review time) |

### After the datathon (roadmap, not built)

- **Optional accounts** (Sign in with Google) to sync applications across devices and make spam harder; only a hashed ID, kept apart from reports
- **Public release** on the Chrome Web Store and Firefox Add-ons
- **"Ghost job report card":** a privacy-protected monthly report by employer and industry for lawmakers and the NY Department of Labor
- **Early warning for official job-estimate revisions**, comparing survey-based estimates with incoming hiring records
- **Production deployment under IBM Secure Execution / Hyper Protect**, with state agencies holding their own keys
