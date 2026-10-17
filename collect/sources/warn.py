"""State WARN notices (NY, CA, TX): layoff events matched to our companies by name.

Reference files are downloaded once into data/collect/reference/; a state whose file can't be fetched is skipped.
"""
import logging
import re
from datetime import date, timedelta
from difflib import SequenceMatcher

import pandas as pd

from ..common import config
from ..common.http import Client
from ..common.ids import normalize_company
from ..common.output import make_evidence

log = logging.getLogger(__name__)

# Names too generic to match on a prefix alone (common in bank names).
_GENERIC = {"bank", "bancorp", "bancshares", "financial", "first", "national", "trust", "capital", "american",
            "united", "community", "federal", "savings", "global", "international", "services", "systems",
            "technologies", "technology", "solutions", "partners", "enterprises", "industries", "corp"}


def _find_col(cols, *patterns, exclude=None):
    for p in patterns:
        for c in cols:
            s = re.sub(r"[\s_]+", " ", str(c)).strip().lower()
            if re.search(p, s) and not (exclude and re.search(exclude, s)):
                return c
    return None


def _from_frame(df: pd.DataFrame, state: str, url: str) -> list[dict]:
    """Normalize one WARN table to rows {state, company, date, workers, url}."""
    name = _find_col(df.columns, r"company|business|employer|job site name")
    when = _find_col(df.columns, r"effective|layoff.*start|layoff date|separation", r"notice|received|date")
    notice = _find_col(df.columns, r"notice")
    workers = _find_col(df.columns, r"no\.? of emp|employees|affected|workers|layoff number|number", exclude=r"date")
    if not name or not when:
        return []
    out = []
    for r in df.to_dict("records"):
        d = pd.to_datetime(r.get(when), errors="coerce")
        if notice and not pd.isna(d) and d > pd.Timestamp.today():   # announced layoff not yet effective
            d = pd.to_datetime(r.get(notice), errors="coerce")
        n = pd.to_numeric(str(r.get(workers, "")).replace(",", ""), errors="coerce") if workers else float("nan")
        company = str(r.get(name) or "").strip()
        if company and not pd.isna(d):
            out.append({"state": state, "company": company, "date": d.date().isoformat(),
                        "workers": None if pd.isna(n) else int(n), "url": url})
    return out


def _read_excel_tables(path, state, url) -> list[dict]:
    rows = []
    for sheet, raw in pd.read_excel(path, sheet_name=None, header=None).items():
        for i in range(min(12, len(raw))):
            cells = [str(x).lower() for x in raw.iloc[i].tolist()]
            if any(re.search(r"company|employer|business|job_site_name", c) for c in cells) and any("date" in c for c in cells):
                df = raw.iloc[i + 1:].copy()
                df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in raw.iloc[i].tolist()]
                rows += _from_frame(df, state, url)
                break
    return rows


class Warn:
    def __init__(self, client: Client, today: date):
        self.rows = []
        cutoff = (today - timedelta(days=config.LAYOFF_LOOKBACK_DAYS)).isoformat()
        if config.NY_WARN_FILE.exists():
            try:
                df = pd.read_csv(config.NY_WARN_FILE)
                df.columns = [re.sub(r"\s+", " ", c).strip() for c in df.columns]
                df = df.loc[:, ~df.columns.duplicated()]
                self.rows += _from_frame(df, "NY", config.NY_WARN_URL)
            except Exception as e:   # one bad file must not stop the run
                log.warning("NY WARN file unreadable: %s", e)
        for state, url in config.WARN_SOURCES:
            dest = config.REFERENCE_DIR / "warn" / f"{state}_{url.rsplit('/', 1)[-1]}"
            if not client.download(url, dest):
                continue
            try:
                self.rows += _read_excel_tables(dest, state, url)
            except Exception as e:
                log.warning("WARN file %s unreadable: %s", dest.name, e)
        self.rows = [r for r in self.rows if r["date"] >= cutoff]
        for r in self.rows:
            r["norm"] = normalize_company(r["company"])
        log.info("WARN: %d notices since %s from %s", len(self.rows), cutoff,
                 sorted({r["state"] for r in self.rows}))

    @staticmethod
    def matches(company_names: list[str], warn_norm: str) -> bool:
        for name in company_names:
            n = normalize_company(name)
            if not n:
                continue
            if warn_norm == n:
                return True
            tokens = n.split()
            specific = not (len(tokens) == 1 and tokens[0] in _GENERIC) and len(n) >= 5
            if specific and (warn_norm.startswith(n + " ")):
                return True
            if specific and len(n) >= 8 and SequenceMatcher(None, n, warn_norm).ratio() >= 0.92:
                return True
        return False

    def collect(self, company: dict, run_id: str, emit) -> int:
        n = 0
        names = company["aliases"] or [company["name"]]
        for r in self.rows:
            if not self.matches(names, r["norm"]):
                continue
            value = {"date": r["date"], "workers": r["workers"], "pct": None, "source": f"WARN {r['state']}",
                     "date_is_filing_date": False}
            quote = r["company"]
            emit(make_evidence(company["ticker"], "layoff_events", value, "workers", r["date"], r["url"], quote,
                               r["date"], "warn", run_id))
            n += 1
        return n
