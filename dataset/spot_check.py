"""30-company spot check (build plan 3B-1, 3.3).

    python -m dataset.spot_check sample   # draws SPOT_CHECK_N companies -> data/labels/spot_check_sample.csv
    python -m dataset.spot_check score    # reads data/labels/spot_check_results.csv -> error rates with 95% intervals

People: open each source URL, and in a copy of the sample saved as data/labels/spot_check_results.csv fill
`checker_1` and `checker_2` with ok or wrong (and `notes`). A row counts as wrong if either checker marks it wrong.
Pay most attention to employee_count (the ground truth). A field with an error rate above ~10% is dropped as a feature.
"""
import argparse
import math
import random

import pandas as pd

from collect.common import config

from .common import dump_json, used_evidence

SAMPLE = config.LABELS_DIR / "spot_check_sample.csv"
RESULTS = config.LABELS_DIR / "spot_check_results.csv"
ORDER = ["employee_count", "employee_count_us", "revenue", "revenue_component", "layoff_events",
         "hiring_freeze_statements", "management_hiring_statements", "archived_open_postings", "hq_country",
         "reports_us_headcount"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def sample():
    rows = used_evidence()
    tickers = sorted({r["ticker"] for r in rows})
    pick = sorted(random.Random(config.SEED).sample(tickers, min(config.SPOT_CHECK_N, len(tickers))))
    out = [r for r in rows if r["ticker"] in set(pick)]
    df = pd.DataFrame([{
        "evidence_id": r["evidence_id"], "ticker": r["ticker"], "field": r["field"], "period": r["period"],
        "value": r["value"], "source_url": r["source_url"], "quote": r["quote"], "page_date": r["page_date"],
        "checker_1": "", "checker_2": "", "notes": ""} for r in out])
    df["field_order"] = df["field"].map({f: i for i, f in enumerate(ORDER)}).fillna(99)
    df = df.sort_values(["ticker", "field_order", "period"]).drop(columns="field_order")
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAMPLE, index=False)
    print(f"spot check sample: {len(pick)} companies, {len(df)} values -> {SAMPLE}")
    print(df["field"].value_counts().to_string())
    print(f"\nTwo people check each row, then save the filled copy as {RESULTS}")


def score():
    if not RESULTS.exists():
        raise SystemExit(f"{RESULTS} not found: the people doing the spot check save their filled sheet there")
    df = pd.read_csv(RESULTS, dtype=str, keep_default_na=False)
    marks = df[["checker_1", "checker_2"]].apply(lambda s: s.str.strip().str.lower())
    checked = (marks != "").any(axis=1)
    df = df[checked].copy()
    df["wrong"] = (marks.loc[df.index] == "wrong").any(axis=1)
    both = (marks.loc[df.index] != "").all(axis=1)
    agree = (marks.loc[df.index, "checker_1"] == marks.loc[df.index, "checker_2"])[both]

    out = {"rows_checked": int(len(df)), "companies": int(df["ticker"].nunique()),
           "checker_agreement": float(agree.mean()) if len(agree) else None, "fields": {}}
    k, n = int(df["wrong"].sum()), len(df)
    out["overall"] = {"wrong": k, "n": n, "error_rate": k / n if n else None, "ci95": wilson(k, n)}
    agreement = "n/a" if out["checker_agreement"] is None else f"{out['checker_agreement']:.0%}"
    print(f"=== spot check: {n} values from {out['companies']} companies; checkers agree on {agreement} ===")
    print(f"  overall error rate {k}/{n} = {k / n:.1%}  (95% CI {out['overall']['ci95'][0]:.1%}-{out['overall']['ci95'][1]:.1%})")
    for field, g in df.groupby("field"):
        kf, nf = int(g["wrong"].sum()), len(g)
        lo, hi = wilson(kf, nf)
        drop = kf / nf > 0.10
        out["fields"][field] = {"wrong": kf, "n": nf, "error_rate": kf / nf, "ci95": [lo, hi], "drop_as_feature": drop}
        print(f"  {field:30s} {kf:3d}/{nf:<3d} wrong = {kf / nf:5.1%}  (95% CI {lo:.1%}-{hi:.1%})" + ("   -> DROP as a feature" if drop else ""))
    dump_json(out, config.METRICS_DIR / "spot_check.json")
    print(f"  saved {config.METRICS_DIR / 'spot_check.json'} (for the model card and the video)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["sample", "score"])
    {"sample": sample, "score": score}[ap.parse_args().action]()
