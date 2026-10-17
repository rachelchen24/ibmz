"""Ground-truth outcomes (build plan 2B-2; brief "Ground truth and the probability score").

Per company, for its latest fiscal year with two years of headcount:
  1. net_change        = headcount - headcount_prev            (verified 10-K employee counts; US where reported)
  2. replacement_hires = average headcount x separation_rate     (BLS JOLTS total separations, company's industry,
                                                                  summed over the 12 months of the fiscal year)
  3. est_hires         = max(net_change + replacement_hires, 0)
  4. postings_year     = postings over the same fiscal year, from Wayback archives of the company's board
  5. follow_through    = min(est_hires / postings_year, FOLLOW_THROUGH_CAP)

postings_year methods (the plan's open question; decide with Workstream A, then pass --method):
  turnover    mean archived open-posting count in the year x 365 / typical posting lifetime (days). The lifetime
              is TYPICAL_POSTING_DAYS until the survival model (2A-2) gives one: --lifetimes CSV (ticker or sector,days).
  unique_ids  distinct job IDs seen on the archived board during the year (needs 6+ monthly snapshots).
              A lower bound: postings that open and close between snapshots are missed.
Both are computed and kept; `postings_year` uses --method, and `postings_year_method` records which one.

This table is the answer, never a model input: ml/ must not join it into features.

    python -m dataset.build_outcomes [--method turnover|unique_ids] [--lifetimes path.csv]
"""
import argparse
import json
import re
import statistics
from datetime import date, timedelta

import pandas as pd

from collect.common import config
from collect.common.http import Client
from collect.common.output import read_jsonl

from .common import by_ticker_field, companies, dump_json, fy, used_evidence

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"
JOLTS = {   # JOLTS total separations rate, not seasonally adjusted (% of employment, monthly)
    "finance_insurance": "JTU5200TSR", "durable_manufacturing": "JTU3200TSR", "information": "JTU5100TSR",
    "professional_business": "JTU540099TSR", "total_private": "JTU1000TSR",
}


def jolts_industry(sic: str | None) -> str:
    s = int(sic) if sic and str(sic).isdigit() else 0
    if 6000 <= s < 6800:
        return "finance_insurance"
    if 3400 <= s < 3900:
        return "durable_manufacturing"
    if s == 7372 or 4800 <= s < 4900:
        return "information"
    if 7300 <= s < 7400 or 8100 <= s < 8200 or 8700 <= s < 8800:
        return "professional_business"
    return "total_private"


def load_jolts(client: Client) -> dict[str, pd.Series]:
    """Monthly rates (fractions) by industry, cached to data/collect/reference/jolts/."""
    out = {}
    for key, sid in JOLTS.items():
        dest = config.REFERENCE_DIR / "jolts" / f"{sid}.csv"
        if not dest.exists():
            r = client.fetch(FRED.format(id=sid), cache_tag=date.today().isoformat())
            if not r.ok:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(r.text, encoding="utf-8")
        df = pd.read_csv(dest)
        df.columns = ["date", "rate"]
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce") / 100
        out[key] = df.dropna().set_index(pd.to_datetime(df.dropna()["date"]))["rate"]
    return out


def annual_rate(series: pd.Series, start: date, end: date) -> tuple[float | None, int]:
    """Sum of the monthly rates for the months in (start, end]; scaled up if some months aren't published yet."""
    months = series[(series.index > pd.Timestamp(start)) & (series.index <= pd.Timestamp(end))]
    if len(months) < 6:
        return None, len(months)
    return float(months.mean() * 12), len(months)


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
    ap.add_argument("--method", choices=["turnover", "unique_ids"], default="turnover")
    ap.add_argument("--lifetimes", help="CSV of ticker-or-sector,days from the survival model (2A-2)")
    a = ap.parse_args()

    ev_all = by_ticker_field(used_evidence())
    comp = companies()
    jolts = load_jolts(Client())
    life = lifetimes(a.lifetimes)
    archive_urls = {r["source_url"] for t in ev_all.values() for r in t.get("archived_open_postings", [])}
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
        industry = jolts_industry(c.get("sic"))
        rate, n_months = annual_rate(jolts.get(industry, pd.Series(dtype=float)), start, end)
        row = {"ticker": t, "fiscal_year": pair, "fy_start": start.isoformat(), "fy_end": end.isoformat(),
               "headcount_basis": basis, "headcount": h, "headcount_prev": hp, "net_change": h - hp,
               "jolts_industry": industry, "jolts_months": n_months, "separation_rate": rate}
        if rate is None:
            excluded.append({"ticker": t, "reason": f"JOLTS {industry} has only {n_months} months for {start}..{end}"})
            continue
        row["replacement_hires"] = (h + hp) / 2 * rate
        row["est_hires"] = max(row["net_change"] + row["replacement_hires"], 0.0)
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
        seen = {str(r["ats_job_id"]) for r in ids_by_ticker.get(t, [])
                if r.get("ats_job_id") and start < date.fromisoformat(r["seen"]) <= end}
        row["postings_year_unique_ids"] = float(len(seen)) if row["archived_snapshots_in_year"] >= 6 else None
        py = row[f"postings_year_{a.method}"]
        row["postings_year"] = py
        row["postings_year_method"] = (f"turnover (lifetime {lt:g} days{', placeholder' if lt == config.TYPICAL_POSTING_DAYS else ''})"
                                       if a.method == "turnover" else "unique_ids (lower bound)")
        if not py:
            excluded.append({"ticker": t, "reason": f"too few archived snapshots in FY{pair} ({row['archived_snapshots_in_year']})"})
            continue
        row["follow_through"] = min(row["est_hires"] / py, config.FOLLOW_THROUGH_CAP)
        row["follow_through_capped"] = row["est_hires"] / py > config.FOLLOW_THROUGH_CAP
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
              f"capped at {config.FOLLOW_THROUGH_CAP}: {int(out['follow_through_capped'].sum())}")
        both = out.dropna(subset=["postings_year_turnover", "postings_year_unique_ids"])
        if len(both) >= 5:
            print(f"  methods agree? Spearman r = {both['postings_year_turnover'].corr(both['postings_year_unique_ids'], method='spearman'):.2f} "
                  f"on {len(both)} companies")
    dump_json({"companies": len(out), "excluded": len(ex), "method": a.method,
               "typical_posting_days": config.TYPICAL_POSTING_DAYS}, config.PROCESSED_DIR / "outcomes_summary.json")
    print(f"  output: {config.PROCESSED_DIR / 'outcomes.csv'} (never a model input)")


if __name__ == "__main__":
    main()
