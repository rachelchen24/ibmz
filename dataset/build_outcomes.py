"""Ground-truth outcomes (build plan 2B-2; brief "Ground truth and the probability score").

Per company, for its latest fiscal year with two years of headcount (company-specific data only; no industry
averages such as BLS JOLTS separation rates, team decision 2026-10-17):
  1. net_change            = headcount - headcount_prev       (verified 10-K employee counts; US where reported)
  2. postings_year         = postings over the same fiscal year, from Wayback archives of the company's board
  3. net_hires_per_posting = net_change / postings_year       (raw; negative when the company shrank)
  4. follow_through        = net_hires_per_posting clipped to 0..FOLLOW_THROUGH_CAP

postings_year methods (the plan's open question; decide with Workstream A, then pass --method):
  turnover    mean archived open-posting count in the year x 365 / typical posting lifetime (days). The lifetime
              is TYPICAL_POSTING_DAYS until the survival model (2A-2) gives one: --lifetimes CSV (ticker or sector,days).
  unique_ids  distinct job IDs seen on the archived board during the year (needs 6+ monthly snapshots).
              A lower bound: postings that open and close between snapshots are missed.
Both are computed and kept; `postings_year` uses --method, and `postings_year_method` records which one.

This table is the answer, never a model input: ml/ must not join it into features.

    python -m dataset.build_outcomes [--method unique_ids|turnover] [--lifetimes path.csv]

Default is unique_ids: observed job IDs only, no assumed posting lifetime (team decision 2026-10-17).
"""
import argparse
import json
import re
import statistics
from datetime import date, timedelta

import pandas as pd

from collect.common import config
from collect.common.output import read_jsonl

from .common import by_ticker_field, companies, dump_json, fy, used_evidence

MIN_JOB_PAGE_IDS = 20   # distinct archived job pages in the fiscal year needed for a unique_ids label


def fiscal_year_end(ev: dict, year: int) -> date:
    """The fiscal year's end date, read from the verified XBRL revenue quote ("end":"2026-01-31"); else Dec 31."""
    for f in ("revenue", "revenue_component"):
        for r in ev.get(f, []):
            if fy(r["period"]) == year:
                m = re.search(r'"end":"(\d{4}-\d{2}-\d{2})"', r["quote"])
                if m:
                    return date.fromisoformat(m.group(1))
    return date(year, 12, 31)


def headcounts(ev: dict) -> tuple[dict[int, float], str, list[str]]:
    """FY -> headcount on one basis for every year (US if reported for the years used, else total)."""
    def table(field):
        t: dict[int, list] = {}
        for r in ev.get(field, []):
            y = fy(r["period"])
            if y:
                t.setdefault(y, []).append(r)
        return t
    total, us = table("employee_count"), table("employee_count_us")
    years = sorted(total, reverse=True)
    use_us = len(years) >= 2 and years[0] in us and years[0] - 1 in us
    src = us if use_us else total
    hc = {y: statistics.median(float(r["value"]) for r in rows) for y, rows in src.items()}
    ids = [r["evidence_id"] for rows in src.values() for r in rows]
    return hc, ("us" if use_us else "total"), ids


def lifetimes(path) -> dict[str, float]:
    if not path:
        return {}
    df = pd.read_csv(path)
    return dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1].astype(float)))


def wayback_ids(used_urls: set[str]) -> dict[str, list[dict]]:
    """Archived job IDs per company, only from archive pages whose count passed verification."""
    out: dict[str, list[dict]] = {}
    for p in config.COLLECT_DIR.glob("shard_*/wayback_postings_*.jsonl"):
        for r in read_jsonl(p):
            if r["source_url"] in used_urls:
                out.setdefault(r["ticker"], []).append(r)
    return out


def main():
    ap = argparse.ArgumentParser(description="Build the ground-truth outcomes table.")
    ap.add_argument("--method", choices=["turnover", "unique_ids"], default="unique_ids")
    ap.add_argument("--lifetimes", help="CSV of ticker-or-sector,days from the survival model (2A-2)")
    a = ap.parse_args()

    ev_all = by_ticker_field(used_evidence())
    comp = companies()
    life = lifetimes(a.lifetimes)
    archive_urls = {r["source_url"] for t in ev_all.values()
                    for f in ("archived_open_postings", "archived_job_ids") for r in t.get(f, [])}
    ids_by_ticker = wayback_ids(archive_urls)

    rows, excluded = [], []
    for t, c in sorted(comp.items()):
        ev = ev_all.get(t, {})
        hc, basis, hc_ids = headcounts(ev)
        years = sorted(hc, reverse=True)
        pair = next((y for y in years if y - 1 in hc), None)
        if pair is None:
            excluded.append({"ticker": t, "reason": "no verified headcount for two consecutive fiscal years"})
            continue
        h, hp = hc[pair], hc[pair - 1]
        end = fiscal_year_end(ev, pair)
        start = end - timedelta(days=365)
        row = {"ticker": t, "fiscal_year": pair, "fy_start": start.isoformat(), "fy_end": end.isoformat(),
               "headcount_basis": basis, "headcount": h, "headcount_prev": hp, "net_change": h - hp}
        if hp and abs(h - hp) / hp > config.HEADCOUNT_JUMP:
            excluded.append({"ticker": t, "reason": f"headcount changed {100 * (h - hp) / hp:+.0f}% (acquisition or divestiture?)"})
            continue

        arch = [(date.fromisoformat(r["period"]), float(r["value"]), r["evidence_id"])
                for r in ev.get("archived_open_postings", [])]
        in_year = [x for x in arch if start < x[0] <= end]
        lt = life.get(t) or life.get(str(c.get("sector"))) or config.TYPICAL_POSTING_DAYS
        row["archived_snapshots_in_year"] = len({d.strftime("%Y-%m") for d, _, _ in in_year})
        row["posting_lifetime_days"] = lt
        row["postings_year_turnover"] = (statistics.mean(v for _, v, _ in in_year) * 365 / lt
                                         if len(in_year) >= 3 else None)
        in_fy = [r for r in ids_by_ticker.get(t, [])
                 if r.get("ats_job_id") and start < date.fromisoformat(r["seen"]) <= end]
        seen = {str(r["ats_job_id"]) for r in in_fy}
        from_pages = {str(r["ats_job_id"]) for r in in_fy if r.get("kind") == "job_page"}
        row["archived_job_ids_in_year"] = len(seen)
        row["archived_job_ids_from_job_pages"] = len(from_pages)
        enough = row["archived_snapshots_in_year"] >= 6 or len(from_pages) >= MIN_JOB_PAGE_IDS
        row["postings_year_unique_ids"] = float(len(seen)) if enough else None
        py = row[f"postings_year_{a.method}"]
        row["postings_year"] = py
        row["postings_year_method"] = (f"turnover (lifetime {lt:g} days{', placeholder' if lt == config.TYPICAL_POSTING_DAYS else ''})"
                                       if a.method == "turnover" else "unique_ids (lower bound)")
        if not py:
            excluded.append({"ticker": t, "reason": f"too little archived posting history in FY{pair} "
                                                    f"({row['archived_snapshots_in_year']} board snapshots, {len(seen)} job IDs)"})
            continue
        ratio = row["net_change"] / py
        row["net_hires_per_posting"] = ratio
        row["follow_through"] = min(max(ratio, 0.0), config.FOLLOW_THROUGH_CAP)
        row["follow_through_capped"] = ratio > config.FOLLOW_THROUGH_CAP
        row["follow_through_floored"] = ratio < 0
        row["evidence_ids"] = json.dumps(hc_ids + [i for _, _, i in in_year])
        rows.append(row)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out.to_csv(config.PROCESSED_DIR / "outcomes.csv", index=False)
    ex = pd.DataFrame(excluded, columns=["ticker", "reason"])
    ex.to_csv(config.PROCESSED_DIR / "outcomes_excluded.csv", index=False)

    print(f"=== outcomes: {len(out)} companies with a follow-through ratio, {len(ex)} excluded ===")
    if len(ex):
        print("  excluded by reason:")
        for reason, n in ex["reason"].str.replace(r"\(.*?\)|-?\d+%?|\d{4}-\d{2}-\d{2}", "#", regex=True).value_counts().items():
            print(f"    {n:4d}  {reason}")
    if len(out):
        print(f"  follow_through median {out['follow_through'].median():.2f}  "
              f"IQR {out['follow_through'].quantile(.25):.2f}-{out['follow_through'].quantile(.75):.2f}  "
              f"capped at {config.FOLLOW_THROUGH_CAP}: {int(out['follow_through_capped'].sum())}  "
              f"shrank (floored at 0): {int(out['follow_through_floored'].sum())}")
        both = out.dropna(subset=["postings_year_turnover", "postings_year_unique_ids"])
        if len(both) >= 5:
            print(f"  methods agree? Spearman r = {both['postings_year_turnover'].corr(both['postings_year_unique_ids'], method='spearman'):.2f} "
                  f"on {len(both)} companies")
    dump_json({"companies": len(out), "excluded": len(ex), "method": a.method,
               "typical_posting_days": config.TYPICAL_POSTING_DAYS}, config.PROCESSED_DIR / "outcomes_summary.json")
    print(f"  output: {config.PROCESSED_DIR / 'outcomes.csv'} (never a model input)")


if __name__ == "__main__":
    main()
