"""Which candidate rows are current: for each company and collection step, only the latest run where that step
succeeded counts. A rerun (e.g. --steps filings after a parser fix) replaces that step's older rows instead of
adding to them. Used by collect.features, collect.merge and verify.accept."""
import json
from pathlib import Path

STEP_FIELDS = {
    "edgar": {"hq_country", "revenue", "revenue_component", "employee_count", "employee_count_us", "reports_us_headcount"},
    "filings": {"hiring_freeze_statements", "management_hiring_statements"},
    "wayback": {"archived_open_postings"},
    "wayback_jobs": {"archived_job_ids"},
}


def step_of(row: dict) -> str | None:
    if row["field"] == "layoff_events":
        return "warn" if row.get("collector") == "warn" else "filings"
    return next((s for s, fields in STEP_FIELDS.items() if row["field"] in fields), None)


def _jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    pass


def current_candidates(shard_dir: Path) -> list[dict]:
    """Candidate rows of one shard folder, keeping for each (ticker, step) only the latest run with that step ok."""
    latest: dict[tuple[str, str], str] = {}
    for p in sorted(shard_dir.glob("status_*.jsonl")):
        for r in _jsonl(p):
            for step, v in r["steps"].items():
                if v == "ok" and r["run_id"] > latest.get((r["ticker"], step), ""):
                    latest[(r["ticker"], step)] = r["run_id"]
    rows = {}
    for p in sorted(shard_dir.glob("candidates_*.jsonl")):
        if ".rejected" in p.name:
            continue
        for r in _jsonl(p):
            step = step_of(r)
            keep = latest.get((r["ticker"], step))
            if step is None or keep is None or r["run_id"] == keep:
                rows[r["evidence_id"]] = r
    return list(rows.values())
