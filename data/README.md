# Data

Raw downloads for RealRole, pulled 2026-10-16. Don't edit files in `raw/`; write cleaned outputs to `data/processed/`. `raw/` is ~3 GB, so keep it out of git and copy it to LinuxONE with `scp`/`rsync`.

**Where the data is:** downloaded on Rachel's laptop in this folder; it will be copied to the LinuxONE server once Michael creates accounts. It is ~3 GB, so it is not in git. The Kaggle LinkedIn dataset must be downloaded separately into `raw/linkedin/` ([link](https://www.kaggle.com/datasets/arshkon/linkedin-job-postings), needs a Kaggle account).

| Folder | Source | Coverage | Size | Notes |
|---|---|---|---|---|
| `raw/nyc_jobs/` | [Jobs NYC Postings](https://data.cityofnewyork.us/City-Government/Jobs-NYC-Postings/kpav-sd4t) | 2,594 currently open city postings, posted 2026-03-17 to 2026-10-12 | 17 MB | Snapshot of open jobs only. Join key to payroll: `Agency` + `Civil Service Title` / `Title Code No` |
| `raw/nyc_payroll/` | [Citywide Payroll Data](https://data.cityofnewyork.us/City-Government/Citywide-Payroll-Data-Fiscal-Year-/k397-673e) | FY2022–FY2025 (July 2021–June 2025), one file per year, ~550–615k rows each | ~0.5 GB | **Real hiring ground truth:** `agency_start_date` + `title_description` + `agency_name`. Contains names; use only aggregated counts. Some `agency_start_date` values are placeholders (`9999-12-31`); drop them |
| `raw/fred/` | [FRED](https://fred.stlouisfed.org/) | Monthly to Aug 2026 (Indeed daily to 2026-10-09) | Tiny | `JTSJOL` openings, `JTSHIL` hires, `JTSQUL` quits, `JTSLDL` layoffs (JOLTS); `IHLIDXUS` Indeed postings index; `PAYEMS` payroll employment. No NY state JOLTS series found (BLS moved state JOLTS to annual releases in 2026) |
| `raw/indeed/job_postings_tracker/` | [Indeed Hiring Lab](https://github.com/hiring-lab/job_postings_tracker) | 2020–2026, daily, by country and sector | 165 MB | Use `US/` files. Methodology changed Nov 2024 |
| `raw/onet/` | [O*NET 31.0](https://www.onetcenter.org/database.html) | Current | 13 MB zip + text files | `Sample of Reported Titles.txt` and `Job Titles.txt` map titles → SOC codes; `Job Zones.txt` = preparation level (proxy for long hiring cycles) |
| `raw/opm/` | [OPM Federal Workforce Data](https://data.opm.gov/explore-data/data/data-downloads), accessions | Monthly, Jan 2025–Aug 2026 (20 files) | 10 MB | Real federal hires. Check the [data dictionary](https://data.opm.gov/) for agency and occupation fields |
| `raw/usajobs/` | [USAJOBS archive (Hugging Face)](https://huggingface.co/datasets/loyoladatamining/usajobs) | Monthly, Jan 2025–Mar 2026 (18 files) | 2.4 GB | Only 3 columns: `usajobsControlNumber`, `title`, `text`. Agency, series and dates must be parsed from `text` |
| `raw/open_jobs_data/open-jobs-data/` | [open-jobs-data](https://github.com/lookin4jobs/open-jobs-data) | 94 daily snapshots, 2026-08-03 to 2026-10-16, ~380 tech companies | 115 MB | Git history = daily snapshots; walk commits to get each posting's first-seen / last-seen dates. **Don't run its scripts**; we only read the data |
| `raw/ny_warn/` | [NY DOL WARN dashboard](https://dol.ny.gov/warn-dashboard) (Tableau CSV export) | 208 notices, 2026-01-06 to 2026-10-02 | 34 KB | 2026 only. Columns: business name, layoff start date, notice date, posted date, site address/county, layoff vs closure, permanent vs temporary, reason, # affected workers |
| `fake_job_postings.csv` | [Real / Fake Job Posting Prediction](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction), acknowledging the University of the Aegean EMSCAD project | 17,880 job postings; `fraudulent` label | 48 MB | Kaggle lists CC0: Public Domain. The label concerns fraudulent/scam postings, not ghost jobs or whether a real employer filled a role; do not use it as ground truth for RealRole's ghost-risk score |

## Still needed

- **LinkedIn Job Postings (Kaggle, arshkon):** download yourself into `raw/linkedin/` (needs a Kaggle account). Main training set for the private-sector scorer.

## Known gaps

- No free bulk private-sector postings for 2025–2026; 2025–26 trends come from FRED/Indeed (macro), NYC (city government), OPM + USAJOBS (federal), and open-jobs-data (tech, Aug–Oct 2026).
- NYC payroll ends June 2025, so it gives each title's baseline hiring rate, not outcomes for 2026 postings.
- NY WARN notices before 2026 are not in this export.
