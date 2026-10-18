# Open-source libraries and data sources

This list is required by the competition rules. Add every package and source when you start using it.

## Libraries

| Library | Used for | Link |
|---|---|---|
| requests | HTTP client for collection and verification (`collect/`, `verify/`) | https://github.com/psf/requests |
| pandas | Tables, CSV and Excel reading (`collect/`, `verify/`, `dataset/`, `ml/`) | https://github.com/pandas-dev/pandas |
| openpyxl | Reading state WARN spreadsheets (through pandas) | https://foss.heptapod.net/openpyxl/openpyxl |
| NumPy | Bootstrap intervals (`dataset/`), arrays (`ml/`) | https://github.com/numpy/numpy |
| Matplotlib | Findings charts (`dataset/findings.py`) | https://github.com/matplotlib/matplotlib |
| scikit-learn | Split, preprocessing, logistic baseline, calibration (`ml/`) | https://github.com/scikit-learn/scikit-learn |
| LightGBM | Fraud classifier, stronger model (`ml/lgbm.py`) | https://github.com/microsoft/LightGBM |
| joblib | Saving and loading trained models (`ml/lgbm.py`, `ml/run.py`) | https://github.com/joblib/joblib |

## Data sources

| Source | Used for | Link |
|---|---|---|
| SEC EDGAR (submissions, XBRL company facts, filings) | Revenue, headcount, HQ, layoffs, hiring statements | https://www.sec.gov/search-filings/edgar-application-programming-interfaces |
| Greenhouse Job Board API | Current postings | https://developers.greenhouse.io/job-board.html |
| Lever Postings API | Current postings | https://github.com/lever/postings-api |
| Workday public job search (per company) | Current postings | Each company's `*.myworkdayjobs.com` site |
| Internet Archive Wayback Machine (CDX API) | Posting history | https://archive.org/developers/wayback-cdx-server.html |
| Indeed Hiring Lab job postings tracker | Sector posting trend | https://github.com/hiring-lab/job_postings_tracker |
| NY DOL WARN dashboard | Layoff notices | https://dol.ny.gov/warn-dashboard |
| California EDD WARN report | Layoff notices | https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN |
| Texas Workforce Commission WARN notices | Layoff notices | https://www.twc.texas.gov/data-reports/warn-notice |
| Real / Fake Job Posting Prediction (EMSCAD, Kaggle, CC0) | Fraud classifier training data (`ml/`) | https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction |
