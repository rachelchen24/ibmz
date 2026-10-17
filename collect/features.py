"""Company-level features (brief: "The indicators", 30 features) from one shard's collected rows.

Features that need models are left NaN for Workstream A's ml/indicators.py: open_vs_expected (survival model),
deleted_and_reposted_share / template_similarity / text_pc_1..5 (Granite embeddings), salary_vs_occupation /
requirements_vs_job_zone / description_length_z / mean_job_zone / top_soc_group_share (O*NET occupation norms).
Raw inputs for those (requirement bullet counts, word counts) are kept as extra columns.

These are preliminary: they use candidate evidence before verification. The model must use ml/indicators.py on
`used` evidence only.

    python -m collect.features --shard 1 [--snapshot 2026-10-17]
"""
import argparse
import math
import re
import statistics
from datetime import date

import pandas as pd

from .common import config
from .common import textparse as tp
from .common.companies import load_companies
from .common.output import read_jsonl
from .common.supersede import current_candidates
from .sources.indeed import category_trends, sector_trend

FEATURES = [
    "postings_per_100_employees", "open_postings_log", "posting_trend_vs_revenue", "revenue_growth",
    "sector_postings_trend", "bulk_posting_share", "share_open_90_plus", "open_vs_expected", "no_real_deadline_share",
    "repost_rate", "median_days_between_reposts", "deleted_and_reposted_share", "same_role_many_locations",
    "template_similarity", "text_pc_1", "text_pc_2", "text_pc_3", "text_pc_4", "text_pc_5", "salary_listed_share",
    "salary_missing_where_required", "salary_range_ratio", "salary_vs_occupation", "specificity_score",
    "named_team_share", "seniority_mismatch_share", "vague_phrase_rate", "requirements_vs_job_zone",
    "description_length_z", "days_since_layoff", "layoff_workers", "hiring_freeze_stated", "management_hiring_tone",
    "mean_job_zone", "top_soc_group_share", "long_cycle_share",
]
NAN = float("nan")


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else NAN


def _median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else NAN


def _d(s) -> date | None:
    return tp.parse_date(s) if s else None


def _latest_snapshot(d) -> str | None:
    snaps = sorted(p.stem.split("_", 1)[1] for p in d.glob("postings_2*.jsonl") if ".rejected" not in p.name)
    return snaps[-1] if snaps else None


def _fy(period: str) -> int | None:
    m = re.match(r"FY(\d{4})", str(period))
    return int(m.group(1)) if m else None


def _status(d) -> dict[str, dict[str, str]]:
    """ticker -> step -> latest status across runs ('ok' wins if any run collected that step)."""
    out: dict[str, dict[str, str]] = {}
    for p in sorted(d.glob("status_*.jsonl")):
        for r in read_jsonl(p):
            cur = out.setdefault(r["ticker"], {})
            for s, v in r["steps"].items():
                if cur.get(s) != "ok":
                    cur[s] = v
    return out


def _evidence(d) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = {}
    for r in current_candidates(d):
        out.setdefault(r["ticker"], {}).setdefault(r["field"], []).append(r)
    return out


def _employees(ev: dict) -> tuple[float, str | None, str | None]:
    """(count, basis, period): US headcount where reported for the latest FY, else total."""
    totals = sorted(ev.get("employee_count", []), key=lambda r: str(r["period"]), reverse=True)
    if not totals:
        return NAN, None, None
    period = totals[0]["period"]
    us = [r for r in ev.get("employee_count_us", []) if r["period"] == period]
    if us:
        return float(us[0]["value"]), "us", period
    return float(totals[0]["value"]), "total", period


def _revenue(ev: dict) -> dict[int, float]:
    out = {}
    for r in ev.get("revenue", []):
        fy = _fy(r["period"])
        if fy and fy not in out:
            out[fy] = float(r["value"])
    if out:
        return out
    comps: dict[int, dict[str, float]] = {}
    for r in ev.get("revenue_component", []):
        fy = _fy(r["period"])
        if fy:
            comps.setdefault(fy, {})[r["value"]["tag"]] = float(r["value"]["val"])
    return {fy: sum(c.values()) for fy, c in comps.items() if len(c) == 2}


def _reposts(cur: pd.DataFrame, hist: list[dict]) -> tuple[float, float]:
    """(repost_rate, median_days_between_reposts) for one company's current postings."""
    if not hist or cur.empty:
        return NAN, NAN
    current_ids = set(cur["ats_job_id"].dropna().astype(str))
    seen: dict[str, dict[str, list[date]]] = {}
    for h in hist:
        if h["ats_job_id"] is None or str(h["ats_job_id"]) in current_ids or not h["seen"]:
            continue
        key = tp.norm_title(h["title"]) + "|" + tp.norm_location(h["location"])
        seen.setdefault(key, {}).setdefault(str(h["ats_job_id"]), []).append(h["seen"])
    n_rep, gaps = 0, []
    for _, p in cur.iterrows():
        start = _d(p["posted_date"]) or _d(p["first_seen"])
        if not start:
            continue
        olds = seen.get(tp.norm_title(p["title"]) + "|" + tp.norm_location(p["location"]), {})
        best = None
        for dates in olds.values():
            before = [x for x in dates if x <= start and (start - x).days <= config.REPOST_WINDOW_DAYS]
            if before:
                gap = (start - min(dates)).days
                best = gap if best is None else min(best, gap)
        if best is not None:
            n_rep += 1
            gaps.append(best)
    rate = n_rep / len(cur)
    return rate, (statistics.median(gaps) if len(gaps) >= 2 else NAN)


def company_features(c, P: pd.DataFrame, ev: dict, st: dict, summary: dict, hist: list[dict], snap: date,
                     trends: dict) -> dict:
    f = {k: NAN for k in FEATURES}
    row = {"ticker": c["ticker"], "name": c["name"], "sector": c["sector"], "shard": c["shard"],
           "snapshot_date": snap.isoformat()}

    # -- company size, revenue, open postings
    emp, basis, emp_period = _employees(ev)
    rev = _revenue(ev)
    open_count = summary.get("open_count")
    open_count = float(open_count) if open_count not in (None, "") and not pd.isna(open_count) else NAN
    row.update({"open_postings": open_count, "employee_count_used": emp, "employee_basis": basis,
                "employee_period": emp_period, "ats": summary.get("ats")})
    if not math.isnan(open_count):
        f["open_postings_log"] = math.log1p(open_count)
        if emp and not math.isnan(emp):
            f["postings_per_100_employees"] = open_count / emp * 100
    if rev:
        fy = max(rev)
        if fy - 1 in rev and rev[fy - 1]:
            f["revenue_growth"] = (rev[fy] - rev[fy - 1]) / abs(rev[fy - 1])
        row["revenue_latest"], row["revenue_fy"] = rev[fy], fy

    # -- 12-month posting trend from Wayback (+ today's live count) vs revenue growth
    arch = sorted(((_d(r["period"]), float(r["value"])) for r in ev.get("archived_open_postings", [])
                   if _d(r["period"])), key=lambda x: x[0])
    now = open_count
    if math.isnan(now):
        recent = [v for dt, v in arch if (snap - dt).days <= 60]
        now = recent[-1] if recent else NAN
    year_ago = [(abs((snap - dt).days - 365), v) for dt, v in arch if 300 <= (snap - dt).days <= 430]
    if year_ago and not math.isnan(now):
        base = min(year_ago)[1]
        if base > 0:
            pct = (now - base) / base
            row["postings_pct_change_12m"] = pct
            if not math.isnan(f["revenue_growth"]):
                f["posting_trend_vs_revenue"] = pct - f["revenue_growth"]
    row["archived_snapshots"] = len(arch)

    f["sector_postings_trend"] = sector_trend(c["sector"], trends)

    # -- postings
    if not P.empty:
        dated = [d for d in (_d(x) for x in P["posted_date"]) if d]
        if dated:
            counts = pd.Series(dated).value_counts()
            f["bulk_posting_share"] = counts.head(3).sum() / len(dated)
            f["share_open_90_plus"] = sum((snap - d).days >= config.LONG_OPEN_DAYS for d in dated) / len(dated)
        T = P[P["description"].notna()]
        if not T.empty:
            nodl = []
            for _, p in T.iterrows():
                cd = _d(p.get("closing_date"))
                nodl.append(cd is None or (cd - snap).days > config.NO_DEADLINE_DAYS or bool(p.get("rolling_wording")))
            f["no_real_deadline_share"] = _mean(nodl)
            f["specificity_score"] = _mean([tp.specificity_score(x) for x in T["description"]])
            f["named_team_share"] = _mean([tp.named_team(x) for x in T["description"]])
            f["seniority_mismatch_share"] = _mean([tp.seniority_mismatch(t, x) for t, x in zip(T["title"], T["description"])])
            f["vague_phrase_rate"] = _mean([tp.vague_phrase_count(x) for x in T["description"]])
            row["median_requirement_bullets"] = _median([None if pd.isna(x) else x for x in T.get("requirement_bullets", [])])
            row["median_word_count"] = _median([tp.word_count(x) for x in T["description"]])
        S = P[P["salary_listed"].notna()]
        if not S.empty:
            f["salary_listed_share"] = S["salary_listed"].astype(bool).mean()
            req = [not bool(sl) for sl, sts in zip(S["salary_listed"], S.get("states", [[]] * len(S)))
                   if isinstance(sts, list) and set(sts) & config.PAY_RANGE_STATES]
            f["salary_missing_where_required"] = _mean(req)
        ratios = [hi / lo for lo, hi in zip(P["salary_min"], P["salary_max"])
                  if not pd.isna(lo) and not pd.isna(hi) and lo > 0]
        f["salary_range_ratio"] = _median(ratios)
        locs: dict[str, set] = {}
        for t, loc in zip(P["title"], P["location"]):
            locs.setdefault(tp.norm_title(t), set()).update(tp.norm_location(x) for x in tp.split_locations(loc) or [""])
        f["same_role_many_locations"] = _median([len(v) for v in locs.values()])
        f["long_cycle_share"] = _mean([tp.long_cycle(t, x) for t, x in zip(P["title"], P["description"])])
        f["repost_rate"], f["median_days_between_reposts"] = _reposts(P, hist)
        row["n_postings"], row["n_postings_with_text"] = len(P), len(T)

    # -- layoffs (filings + WARN), hiring freeze, management tone
    events = []
    for r in ev.get("layoff_events", []):
        v = r["value"]
        d = _d(v.get("date"))
        if d and 0 <= (snap - d).days <= config.LAYOFF_LOOKBACK_DAYS:
            workers = v.get("workers")
            if workers is None and v.get("pct") and emp and not math.isnan(emp):
                workers = round(v["pct"] * emp)
            events.append((d, workers, r["collector"]))
    searched_layoffs = st.get("filings") == "ok" or st.get("warn") == "ok"
    if events:
        latest = max(e[0] for e in events)
        f["days_since_layoff"] = (snap - latest).days
        window = [e for e in events if (latest - e[0]).days <= 30]
        warn_sum = sum(w for d, w, col in window if col == "warn" and w)
        filed = max([w for d, w, col in window if col != "warn" and w] or [0])
        f["layoff_workers"] = max(warn_sum, filed) or NAN
    elif searched_layoffs:
        f["layoff_workers"] = 0
    stmt_cut = config.STATEMENT_LOOKBACK_DAYS
    if st.get("filings") == "ok":
        freeze = [r for r in ev.get("hiring_freeze_statements", []) if _d(r["period"]) and (snap - _d(r["period"])).days <= stmt_cut]
        f["hiring_freeze_stated"] = 1.0 if freeze else 0.0
        tones = [float(r["value"]) for r in ev.get("management_hiring_statements", [])
                 if _d(r["period"]) and (snap - _d(r["period"])).days <= stmt_cut]
        f["management_hiring_tone"] = _mean(tones)
        row["n_hiring_statements"] = len(tones)

    row.update(f)
    return row


def build(shard: int, snapshot: str | None = None, companies_path=config.COMPANY_LIST):
    d = config.shard_dir(shard)
    snapshot = snapshot or _latest_snapshot(d) or date.today().isoformat()
    snap = date.fromisoformat(snapshot)
    status = _status(d)
    if not status:
        print(f"features: nothing collected yet in {d}")
        return None
    companies = [c for c in load_companies(companies_path) if c["ticker"] in status]

    posts = pd.DataFrame(read_jsonl(d / f"postings_{snapshot}.jsonl"))
    extras = pd.DataFrame(read_jsonl(d / f"postings_extra_{snapshot}.jsonl"))
    if not posts.empty and not extras.empty:
        posts = posts.merge(extras.drop(columns=["ticker"], errors="ignore"), on="posting_id", how="left")
    if not posts.empty:
        posts = posts.astype(object).where(posts.notna(), None)
    summary_path = d / f"ats_summary_{snapshot}.csv"
    summary = {}
    if summary_path.exists():
        summary = {r["ticker"]: r for r in pd.read_csv(summary_path).to_dict("records")}

    hist: dict[str, list[dict]] = {}
    for p in sorted(d.glob("postings_2*.jsonl")):
        s = p.stem.split("_", 1)[1]
        if s < snapshot and ".rejected" not in p.name:
            for r in read_jsonl(p):
                for sd in r.get("snapshots") or [s]:
                    hist.setdefault(r["ticker"], []).append({"ats_job_id": r.get("ats_job_id"), "title": r["title"],
                                                             "location": r["location"], "seen": _d(sd)})
    for p in sorted(d.glob("wayback_postings_*.jsonl")):
        for r in read_jsonl(p):
            hist.setdefault(r["ticker"], []).append({**r, "seen": _d(r["seen"])})

    ev = _evidence(d)
    trends, trend_date = category_trends()
    rows = []
    for c in companies:
        P = posts[posts["ticker"] == c["ticker"]] if not posts.empty else pd.DataFrame()
        rows.append(company_features(c, P, ev.get(c["ticker"], {}), status.get(c["ticker"], {}),
                                     summary.get(c["ticker"], {}), hist.get(c["ticker"], []), snap, trends))
    df = pd.DataFrame(rows)
    lead = ["ticker", "name", "sector", "shard", "snapshot_date"]
    df = df[lead + FEATURES + [c for c in df.columns if c not in lead + FEATURES]]
    out = d / f"scraper{shard}_features_{snapshot}.csv"
    df.to_csv(out, index=False)

    print(f"\n=== features shard {shard}, snapshot {snapshot}: {len(df)} companies -> {out}")
    print(f"  (Indeed sector index as of {trend_date}; features are pre-verification)")
    for k in FEATURES:
        n = int(df[k].notna().sum())
        print(f"  {k:32s} {n:3d}/{len(df)}" + ("   [left for ml/: needs a model]" if n == 0 and k in _MODEL_FEATURES else ""))
    return df


_MODEL_FEATURES = {"open_vs_expected", "deleted_and_reposted_share", "template_similarity", "text_pc_1", "text_pc_2",
                   "text_pc_3", "text_pc_4", "text_pc_5", "salary_vs_occupation", "requirements_vs_job_zone",
                   "description_length_z", "mean_job_zone", "top_soc_group_share"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--snapshot")
    ap.add_argument("--companies", default=str(config.COMPANY_LIST))
    a = ap.parse_args()
    build(a.shard, a.snapshot, a.companies)
