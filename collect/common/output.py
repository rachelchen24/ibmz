"""Shared output format: candidate evidence rows, postings rows, and their validator (build plan 1.5, 2.4)."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .ids import evidence_id

EVIDENCE_COLUMNS = ["evidence_id", "ticker", "field", "value", "unit", "period", "source_url", "quote",
                    "page_date", "collected_at", "collector", "prompt_version", "run_id"]
POSTING_COLUMNS = ["posting_id", "ticker", "ats", "ats_job_id", "title", "location", "state", "country",
                   "posted_date", "salary_min", "salary_max", "salary_listed", "description", "first_seen",
                   "last_seen", "snapshots", "repost_of", "soc_code", "job_zone"]

# "edgar" and "warn" are additions to the contract's collector list (claude, ats_scraper, wayback, reference):
# without Claude at run time, these collectors fill the fields the agent would have.
COLLECTORS = {"claude", "ats_scraper", "wayback", "reference", "edgar", "warn"}
FIELDS = {
    "employee_count", "employee_count_us", "reports_us_headcount", "revenue", "revenue_component",
    "hq_country", "careers_url", "ats_board", "layoff_events", "hiring_freeze_statements",
    "management_hiring_statements", "archived_open_postings",
}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_QUOTE = 500


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_evidence(ticker, field, value, unit, period, source_url, quote, page_date, collector, run_id) -> dict:
    quote = re.sub(r"\s+", " ", quote or "").strip()[:MAX_QUOTE]
    return {
        "evidence_id": evidence_id(ticker, field, period, source_url, quote),
        "ticker": ticker, "field": field, "value": value, "unit": unit, "period": period,
        "source_url": source_url, "quote": quote, "page_date": page_date, "collected_at": now_iso(),
        "collector": collector, "prompt_version": config.PROMPT_VERSION, "run_id": run_id,
    }


def validate_evidence(row: dict) -> list[str]:
    errs = [f"missing {c}" for c in EVIDENCE_COLUMNS if c not in row]
    if row.get("field") not in FIELDS:
        errs.append(f"unknown field {row.get('field')}")
    if row.get("collector") not in COLLECTORS:
        errs.append(f"unknown collector {row.get('collector')}")
    if row.get("value") is None:
        errs.append("value is null")
    if not str(row.get("source_url") or "").startswith("http"):
        errs.append("source_url not http(s)")
    if not row.get("quote"):
        errs.append("empty quote")
    if row.get("page_date") and not _DATE.match(str(row["page_date"])):
        errs.append(f"bad page_date {row['page_date']}")
    return errs


def validate_posting(row: dict) -> list[str]:
    errs = [f"missing {c}" for c in POSTING_COLUMNS if c not in row]
    if not row.get("posting_id") or not row.get("ticker"):
        errs.append("no posting_id/ticker")
    for c in ("posted_date", "first_seen", "last_seen"):
        if row.get(c) and not _DATE.match(str(row[c])):
            errs.append(f"bad {c} {row[c]}")
    lo, hi = row.get("salary_min"), row.get("salary_max")
    if lo is not None and hi is not None and lo > hi:
        errs.append("salary_min > salary_max")
    return errs


class JsonlWriter:
    """Thread-safe JSONL appender that validates each row first; invalid rows go to <name>.rejected.jsonl."""

    def __init__(self, path: Path, validator=None, append: bool = True):
        self.path = path
        self.validator = validator
        self.lock = threading.Lock()
        self.count = 0
        self.rejected = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(path, "a" if append else "w", encoding="utf-8")
        self._rej = None

    def write(self, row: dict) -> bool:
        errs = self.validator(row) if self.validator else []
        line = json.dumps(row, ensure_ascii=False, default=str)
        with self.lock:
            if errs:
                if self._rej is None:
                    self._rej = open(self.path.with_suffix(".rejected.jsonl"), "a", encoding="utf-8")
                self._rej.write(json.dumps({"errors": errs, "row": row}, default=str) + "\n")
                self._rej.flush()
                self.rejected += 1
                return False
            self._f.write(line + "\n")
            self._f.flush()
            self.count += 1
            return True

    def close(self):
        self._f.close()
        if self._rej:
            self._rej.close()


def read_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def validate_dir(directory: Path) -> dict:
    """Check every candidates_*.jsonl and postings_*.jsonl file in a shard folder against the format."""
    report = {}
    for p in sorted(directory.glob("candidates_*.jsonl")) + sorted(directory.glob("postings_2*.jsonl")):
        if p.name.endswith(".rejected.jsonl"):
            continue
        fn = validate_evidence if p.name.startswith("candidates_") else validate_posting
        rows = read_jsonl(p)
        bad = sum(1 for r in rows if fn(r))
        report[p.name] = {"rows": len(rows), "invalid": bad}
    return report


if __name__ == "__main__":
    import sys
    for d in sys.argv[1:] or [str(config.shard_dir(i)) for i in range(1, config.N_SHARDS + 1)]:
        print(d, json.dumps(validate_dir(Path(d)), indent=2))
