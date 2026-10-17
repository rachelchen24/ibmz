"""Flag values that two sources disagree on (build plan 2.2: CONFLICT_TOLERANCE = 10%). Flagged values aren't used."""
from collections import defaultdict

CONFLICT_TOLERANCE = 0.10
NUMERIC_FIELDS = {"employee_count", "employee_count_us", "revenue"}
TEXT_FIELDS = {"hq_country", "reports_us_headcount"}


def flag_conflicts(rows: list[dict]) -> int:
    """Set row['conflict'] on passed rows; returns how many rows were flagged."""
    groups = defaultdict(list)
    for r in rows:
        r["conflict"] = False
        if r["check"] == "passed" and r["field"] in NUMERIC_FIELDS | TEXT_FIELDS:
            groups[(r["ticker"], r["field"], r["period"])].append(r)
    flagged = 0
    for (_, field, _), g in groups.items():
        if len({r["source_url"] for r in g}) < 2:
            continue
        if field in NUMERIC_FIELDS:
            vals = [float(r["value"]) for r in g]
            lo, hi = min(vals), max(vals)
            disagree = hi > 0 and (hi - lo) / hi > CONFLICT_TOLERANCE
        else:
            disagree = len({str(r["value"]) for r in g}) > 1
        if disagree:
            for r in g:
                r["conflict"] = True
            flagged += len(g)
    return flagged
