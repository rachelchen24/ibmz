"""Paths and constants for the collection scrapers (scraper1..scraper4).

Mirrors build plan 2.2. Move to common/config.py once Workstream A ships it (task 0-5).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
COMPANY_LIST = DATA_DIR / "datathon_companies.csv"
COLLECT_DIR = DATA_DIR / "collect"          # not in git
CACHE_DIR = COLLECT_DIR / "cache"           # every raw HTTP response, gzipped
REFERENCE_DIR = COLLECT_DIR / "reference"   # shared reference files (state WARN lists)

INDEED_SECTOR_FILE = RAW_DIR / "indeed" / "job_postings_tracker" / "US" / "job_postings_by_sector_US.csv"
NY_WARN_FILE = RAW_DIR / "ny_warn" / "ny_warn_dashboard_2026-10-16.csv"

N_SHARDS = 4
PILOT_PER_SHARD = 5
SEED = 42

# No Claude at run time (team decision 2026-10-17: no API budget). Recorded on every evidence row.
PROMPT_VERSION = "none"

CONTACT_EMAIL = "ryc7070@nyu.edu"
SEC_USER_AGENT = f"RealRole IBM Z Datathon 2026 {CONTACT_EMAIL}"
WEB_USER_AGENT = "Mozilla/5.0 (compatible; RealRole-collector/1.0; IBM Z Datathon 2026 research)"

# Requests per second, per scraper process. Four scrapers in parallel keep SEC at 8/s (< 10/s limit).
RATES = {"sec": 2.0, "wayback": 1.0, "ats": 2.0, "web": 1.0}

LONG_OPEN_DAYS = 90
PAY_RANGE_STATES = {"NY", "CA", "CO", "WA"}   # verify each law's scope and thresholds
NO_DEADLINE_DAYS = 180
REPOST_WINDOW_DAYS = 90
LAYOFF_LOOKBACK_DAYS = 730
STATEMENT_LOOKBACK_DAYS = 365
WAYBACK_LOOKBACK_DAYS = 400
SECTOR_TREND_DAYS = 90
MAX_8K_PER_COMPANY = 16
WORKDAY_MAX_DETAILS = 600     # job detail pages fetched per Workday company (0 = all)
WORKDAY_SKIP_HOSTS: set[str] = set()   # hosts whose terms forbid automated access

# State WARN lists pulled once into REFERENCE_DIR. A source that fails to download is skipped.
WARN_SOURCES = [
    ("CA", "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"),
    ("CA", "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report.xlsx"),
    ("TX", "https://www.twc.texas.gov/sites/default/files/oei/docs/warn-act-listings-2026-twc.xlsx"),
    ("TX", "https://www.twc.texas.gov/sites/default/files/oei/docs/warn-act-listings-2025-twc.xlsx"),
]
NY_WARN_URL = "https://dol.ny.gov/warn-dashboard"


def shard_dir(shard: int) -> Path:
    return COLLECT_DIR / f"shard_{shard}"
