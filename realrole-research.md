# RealRole: Research Notes

Background research behind the [brief](realrole-brief.md), done 2026-10-16. Use it as reference; the brief and build plan are the decisions. Items marked *verify* weren't confirmed against an official source.

## 1. Datasets

All of these except LinkedIn are already downloaded; see [data/README.md](data/README.md) for exact coverage and file locations. The LinkedIn dataset must be downloaded from Kaggle (needs an account).

### Core datasets

| # | Dataset | What it gives us | Coverage | Size | Access |
|---|---|---|---|---|---|
| 1 | [LinkedIn Job Postings (arshkon, Kaggle)](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings) | Private-sector postings with text, salary, company, listed time, original listed time, expiry, views, applies | 2023–24, ~124k postings | ~0.5 GB | Needs a Kaggle account + API token (you download it, or put your own `kaggle.json` in place) |
| 2 | [Jobs NYC Postings](https://data.cityofnewyork.us/City-Government/Jobs-NYC-Postings/kpav-sd4t) | Currently open NYC government postings: agency, civil service title + code, # positions, salary, posting date, post-until, last updated, full text | 2,594 open postings, posted Mar–Oct 2026 | Small | Free API |
| 3 | [Citywide Payroll Data](https://data.cityofnewyork.us/City-Government/Citywide-Payroll-Data-Fiscal-Year-/k397-673e) | **Real hiring ground truth**: every city employee with agency, civil service title, agency start date | Through FY2025 (June 2025); we'd take FY2022–25 | A few hundred MB | Free API |
| 4 | FRED series: JOLTS openings `JTSJOL`, hires `JTSHIL`, Indeed Job Postings Index `IHLIDXUS` (+ NY state JOLTS if available) | Official government numbers vs real postings, for the 2023–2026 "postings vs hires gap" chart | 2020–2026 monthly | Tiny | Free |
| 5 | [Indeed Hiring Lab job postings tracker](https://github.com/hiring-lab/job_postings_tracker) | Postings index by sector; shows which sectors' postings grew without hires | 2020–2026 daily | Small | Free (check license) |
| 6 | [O*NET](https://www.onetcenter.org/database.html) titles → SOC codes, Job Zones | Normalize job titles to occupations; Job Zone ≈ how long hiring and preparation normally take | Current | Small | Free |

### Extra datasets (2025–26 and the federal comparison)

| # | Dataset | What it gives us | Notes |
|---|---|---|---|
| 7 | [OPM Federal Workforce Data](https://data.opm.gov/explore-data/data/data-downloads): monthly accessions (hires) | Real federal hires by month, 2025–2026 | Replaced FedScope in 2026; check the data dictionary for agency/occupation fields |
| 8 | [USAJOBS postings archive (Hugging Face)](https://huggingface.co/datasets/loyoladatamining/usajobs) | Federal postings text, Jan 2017–Mar 2026 | 32 GB total, only 3 columns (ID, title, text); download only the 2025–2026 monthly splits and parse agency and dates from text. Natural experiment: postings during the 2025 federal hiring freeze vs actual accessions |
| 9 | [open-jobs-data (GitHub)](https://github.com/lookin4jobs/open-jobs-data) | 2026 postings from ~380 tech companies straight from their applicant tracking systems; git history gives first-seen/last-seen | Limited history (~94 snapshots) |
| 10 | [NY DOL WARN dashboard](https://dol.ny.gov/warn-dashboard) | NY layoff notices (employer, date, # affected) | Manual Tableau download; *verify* format. Big Local News' open WARN scraper is an alternative |

### Not available for free

- **Bulk private-sector postings for 2025–2026** (LinkedIn, Indeed): only commercial vendors (Lightcast, Revelio, Coresignal) at enterprise prices. Scraping LinkedIn violates its terms, so don't.
- Our answer: show 2025–26 growth at the **macro level** (datasets 4 and 5: postings index vs JOLTS hires), at the **NYC government level** (datasets 2 and 3), and optionally at the **federal level** (7 and 8).

### Why NYC data matters most

NYC postings (`agency` + `civil_service_title`/`title_code_no`) can be joined to NYC payroll (`agency_name` + `title_description` + `agency_start_date`). That's **real, job-title-level hiring evidence**, which the private sector doesn't publish. For each posted title we can count how many people actually started in that title at that agency in FY2022–25. Titles posted repeatedly with almost no starts are real evidence of ghost-like postings. Caveat: payroll ends June 2025, so it gives baseline hiring rates for each title, not outcomes for 2026 postings.

## 2. Real hiring record layouts (for the synthetic data)

### NY new-hire report (to NYS Dept. of Taxation & Finance, within 20 days of hire)

Source: [NY Tax new hire reporting](https://tax.ny.gov/bus/wt/newhire.htm), [NY child support fact sheet](https://childsupport.ny.gov/pdfs/CSFS_NewHire.pdf), [HHS NDNH guide](https://hhs.gov/guidance/sites/default/files/hhs-guidance-documents//a_guide_to_the_national_directory_of_new_hires.pdf)

| Field | Notes |
|---|---|
| employee_first_name, employee_middle_initial, employee_last_name | |
| employee_address (street, city, state, zip) | |
| employee_ssn | 9 digits, no hyphens |
| date_of_hire | First day of paid services |
| employer_name, employer_address | |
| employer_fein | IRS federal employer ID |
| dependent_health_insurance_available | Y/N |
| health_insurance_qualify_date | If Y |

**No job title or occupation.** Electronic files in many states use a fixed-width "W4" record type ([Illinois layout](https://newhire.hfs.illinois.gov/NewHireWeb/TextFileLayout.jsp)).

### NYS-45 quarterly return (withholding, wage reporting, unemployment insurance)

Source: [NYS-45](https://www.tax.ny.gov/pdf/current_forms/wt/nys45_fill_in.pdf), [NYS-45-ATT](https://WWW.TAX.NY.GOV/pdf/current_forms/wt/nys45att_fill_in.pdf)

Employer level (one row per employer per quarter): employer_fein / withholding ID, ui_employer_registration_number, quarter_ending_date, employees covered in month 1 / 2 / 3 (*verify*: headcount on the 12th of each month), total_ui_remuneration, total_withheld.

Employee level (Part C / ATT, one row per employee per quarter): ssn, last_name, first_name, middle_initial, total_ui_remuneration_this_quarter, gross_federal_wages, total_nys_nyc_yonkers_withheld. Quarterly amounts (not cumulative) since 2019. **No occupation.**

### Synthetic design (implications)

- Generate employers with FEINs, a hidden ghost propensity, size and turnover rate.
- New-hire table and NYS-45 tables in the exact layouts above. Monthly headcount lets us estimate net growth; new hires minus growth ≈ replacement hiring.
- Matching is **employer-level** (FEIN ↔ posting company). The job-level match is only possible on the NYC government data (real).

## 3. Model design

### Hiring timelines vary, so a fixed 90-day window is too blunt

Instead of a fixed window, model **time-to-hire as a survival problem**: every posting has an expected time-to-fill that depends on occupation, seniority and recruiting cycle. A posting is "ghost-like" when its chance of leading to a hire is far below what's normal for comparable jobs. Postings still open are "censored" (we don't know the outcome yet), which survival models handle natively.

Recruiting cycles to treat as their own category (long but legitimate): campus and summer analyst programs (IB, consulting: recruiting 9–18 months ahead), academic faculty searches (6–12 months), civil service exam-based government hiring, medical residencies (the Match), federal jobs, executive search, union apprenticeships.

### Architecture (Python)

1. **Text encoder:** IBM Granite embedding model (*verify* that it runs on s390x) for posting text → dense vectors; also fine-tune a small classifier head.
2. **Tabular model:** gradient-boosted trees (XGBoost/LightGBM) on engineered features.
3. **Survival head:** XGBoost AFT or a DeepSurv-style network for time-to-hire, conditioned on occupation (SOC/Job Zone).
4. **Weak supervision / PU learning:** labels come from noisy rules (positive-unlabeled learning), not hand labels.
5. **Employer-level aggregation:** roll up per-posting scores into an employer score; compare against enclave follow-through.
6. **Explanations:** SHAP for tabular, top phrases for text, Granite LLM writes the plain-language reason.
7. **Deployment:** export to ONNX → IBM Z Deep Learning Compiler, or Snap ML for tree models → Telum inference (AI Toolkit for IBM Z and LinuxONE, [Redpaper REDP-5749](https://redbooks.ibm.com/abstracts/redp5749.html)).

### Feature set (~45 features)

**Time and lifecycle**
- days_open; days_since_original_listing; reposted (listed ≠ original listed); repost_count for same employer + normalized title; days_to_expiry; post_until blank ("until filled")
- posted on weekend / bulk-posted with many others the same day
- age relative to occupation's typical time-to-fill (survival baseline ratio)

**Engagement (LinkedIn)**
- views, applies, applies/views, applies per day open; high applies + still open long

**Compensation**
- salary disclosed?; salary range width (max/min); range width vs occupation norm; salary vs local market (O*NET/OEWS); pay frequency mismatch

**Text**
- description length; specificity (concrete tools, team names, manager title, start date) vs generic boilerplate; reading-level; template similarity to employer's other postings (cosine); near-duplicate of older postings; "talent community", "future opportunities", "pipeline", "evergreen" phrases; number of requirements vs seniority; inconsistent seniority (entry-level title, 7+ years required); presence of named hiring manager or interview process

**Employer behavior**
- postings per employer / employer size; share of employer's postings that are reposts; same title posted in many locations; recent WARN layoff notice (days since, # affected); posting volume growth vs headcount growth; % of postings remote "anywhere"

**Occupation context**
- SOC major group; Job Zone; seasonal recruiting cycle flag; government / civil service flag; # positions (NYC)

**NYC-specific (real labels)**
- historical starts per year for agency × civil service title (payroll); posting open months / expected starts; internal vs external posting

## 4. LinuxONE logistics

- 2025 precedent: teams used the LinuxONE Community Cloud (Ubuntu VM, root access) ([2025 team write-up](https://community.ibm.com/community/user/blogs/akshata-pandit/2025/04/24/our-experience-using-ibm-linuxone-from-datathon-pa)). A third-party listing says 2026 has a "Get Your LinuxONE System Ready" session on Oct 16 and the event on Oct 17–18 (*verify*: [coursejoiner listing](https://coursejoiner.com/datathon/ibm-z-datathon-2026-check-eligibility/)).
- **Sharing one server:** the server owner creates a Linux user per teammate and adds each teammate's SSH public key; code lives in a shared GitHub repo, and everyone pulls on the server; long jobs run in `tmux`.
- **Viewing apps:** use SSH port-forwarding (`ssh -L 8501:localhost:8501 user@server`) to see Streamlit or Jupyter in your local browser. Inbound ports and public IP on Community Cloud are not documented (*verify* during setup).
- **Architecture:** s390x, big-endian. Test pip installs early (xgboost, lightgbm, torch, scikit-survival, diffprivlib, transformers).
- **IBM software to use:** AI Toolkit for IBM Z and LinuxONE (Snap ML, PyTorch, Deep Learning Compiler), IBM Granite models, IBM diffprivlib for differential privacy.

## 5. Chrome extension (replaces the live feed)

- **Feasible and free for the demo:** Manifest V3 extension, loaded unpacked in developer mode. Publishing to the Chrome Web Store needs a one-time $5 developer fee (per a 2020 Chromium blog post; *verify*), not needed for the demo.
- **How:** a content script reads the job page you're viewing (start with one site, e.g. Greenhouse or LinkedIn), sends the text and visible metadata to our API on LinuxONE, and shows a badge ("62% ghost-likely, reposted 4×, no salary").
- **Networking:** if Community Cloud blocks inbound traffic, the demo laptop uses an SSH tunnel so the extension calls `localhost`, which forwards to LinuxONE.
- **Why it helps the pitch:** every page view is a real-time inference request, which is a natural Telum story without a firehose of irrelevant postings.
- **Effort:** about 4–6 hours for one person. Respect site terms: read only the page the user is viewing, no bulk scraping.

## 6. Ghost-job prevalence figures (for slides; verify originals)

- Greenhouse (2025): 18–22% of postings ([via Entrepreneur](https://www.entrepreneur.com/business-news/one-quarter-of-jobs-posted-online-are-fake-ghost-jobs-study/496683))
- ResumeUp.AI: 27.4% of LinkedIn US listings by a 30-day-open definition
- MyPerfectResume: 30% of JOLTS openings in June 2025 never led to a hire ([CPA Practice Advisor](https://www.cpapracticeadvisor.com/2025/11/12/ghost-jobs-up-to-1-in-3-job-listings-dont-result-in-hires/173044/))
- LiveCareer survey: 93% of HR professionals report posting ghost jobs to some degree
- Figures come from commercial sources with different definitions; present as a range (18–30%).
