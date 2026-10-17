# Open-source libraries and data sources

This list is required by the competition rules. Add every package and source when you start using it.

## Libraries

| Library | Used for | Link |
|---|---|---|
| requests | HTTP client for collection and verification (`collect/`, `verify/`) | https://github.com/psf/requests |
| pandas | Tables, CSV and Excel reading (`collect/`, `verify/`, `dataset/`) | https://github.com/pandas-dev/pandas |
| openpyxl | Reading state WARN spreadsheets (through pandas) | https://foss.heptapod.net/openpyxl/openpyxl |
| NumPy | Bootstrap intervals (`dataset/`) | https://github.com/numpy/numpy |
| Matplotlib | Findings charts (`dataset/findings.py`) | https://github.com/matplotlib/matplotlib |

## Data sources

| Source | Used for | Link |
|---|---|---|
| SEC EDGAR (submissions, XBRL company facts, filings) | Revenue, headcount, HQ, layoffs, hiring statements | https://www.sec.gov/search-filings/edgar-application-programming-interfaces |
| Greenhouse Job Board API | Current postings | https://developers.greenhouse.io/job-board.html |
| Lever Postings API | Current postings | https://github.com/lever/postings-api |
| Workday public job search (per company) | Current postings | Each company's `*.myworkdayjobs.com` site |
| Internet Archive Wayback Machine (CDX API) | Posting history | https://archive.org/developers/wayback-cdx-server.html |
| Indeed Hiring Lab job postings tracker | Sector posting trend | https://github.com/hiring-lab/job_postings_tracker |
| BLS JOLTS via FRED | Industry separation rates (ground truth) | https://fred.stlouisfed.org/categories/32241 |
| NY DOL WARN dashboard | Layoff notices | https://dol.ny.gov/warn-dashboard |
| California EDD WARN report | Layoff notices | https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN |
| Texas Workforce Commission WARN notices | Layoff notices | https://www.twc.texas.gov/data-reports/warn-notice |
