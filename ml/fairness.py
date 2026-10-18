"""Fairness check: how the scam-risk model behaves across groups of listings (brief component 8).

    python -m ml.fairness            # test split (after the one --final evaluation); --split val for development

For each group: listings, scams, how many scams the model catches (recall), how many genuine listings it wrongly
flags (false-positive rate), precision, and calibration-in-the-large (mean predicted risk vs. actual scam rate).
Groups with few scams have very uncertain numbers; they are reported, marked, and not over-read.
Writes ml/reports/fairness_lgbm_<split>.json. Reads only; never changes the model or threshold.
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from .evaluate import REPORT_DIR
from .run import load_bundle, predict
from .split import load_split

GROUPINGS = {
    "country": lambda d: d["loc_country"].fillna("(none)"),
    "industry": lambda d: d["industry"].fillna("(none)"),
    "employment_type": lambda d: d["employment_type"].fillna("(none)"),
    "remote": lambda d: d["telecommuting"].map({1: "remote", 0: "not remote"}),
    "company_logo": lambda d: d["has_company_logo"].map({1: "logo", 0: "no logo"}),
}
TOP = 8          # largest groups shown per grouping; the rest pooled as "(other)"
MIN_SCAMS = 10   # below this, a group's rates are marked as too uncertain to compare


def group_table(y, p, thr, labels) -> list[dict]:
    labels = pd.Series(labels).reset_index(drop=True)
    top = labels.value_counts().head(TOP).index
    labels = labels.where(labels.isin(top), "(other)")
    rows = []
    for g in list(top) + (["(other)"] if (labels == "(other)").any() else []):
        m = (labels == g).to_numpy()
        yy, pp = y[m], p[m]
        flag = pp >= thr
        scams, genuine = int(yy.sum()), int((1 - yy).sum())
        rows.append({
            "group": str(g), "listings": int(m.sum()), "scams": scams, "scam_rate": round(float(yy.mean()), 4),
            "recall": round(float(flag[yy == 1].mean()), 3) if scams else None,
            "false_positive_rate": round(float(flag[yy == 0].mean()), 4) if genuine else None,
            "precision": round(float(yy[flag].mean()), 3) if flag.any() else None,
            "pr_auc": round(float(average_precision_score(yy, pp)), 3) if 0 < scams < len(yy) else None,
            "mean_predicted": round(float(pp.mean()), 4), "flagged": int(flag.sum()),
            "uncertain": scams < MIN_SCAMS,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", default="test", choices=["val", "test"])
    a = ap.parse_args()
    b = load_bundle("lgbm")
    df = load_split()
    d = df[df["split"] == a.split].reset_index(drop=True)
    y, p, thr = d["fraudulent"].to_numpy(), predict(b, d), float(b["threshold"])
    out = {"model": "lgbm", "split": a.split, "threshold": round(thr, 4), "min_scams_to_compare": MIN_SCAMS,
           "overall": group_table(y, p, thr, ["all"] * len(d))[0],
           "groups": {k: group_table(y, p, thr, f(d)) for k, f in GROUPINGS.items()}}
    path = REPORT_DIR / f"fairness_lgbm_{a.split}.json"
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    o = out["overall"]
    print(f"=== fairness, lgbm on {a.split}: {o['listings']} listings, {o['scams']} scams; overall recall {o['recall']:.0%}, "
          f"false-positive rate {o['false_positive_rate']:.1%} ===")
    for k, rows in out["groups"].items():
        print(f"\n  by {k}:")
        print(f"    {'group':28s} {'listings':>8s} {'scams':>6s} {'recall':>7s} {'FPR':>7s} {'prec':>6s} {'pred':>6s} {'actual':>7s}")
        for r in rows:
            fmt = lambda v, pct=True, w=7: f"{'-':>{w}s}" if v is None else (f"{v:>{w}.0%}" if pct else f"{v:>{w}.1%}")
            print(f"    {r['group'][:28]:28s} {r['listings']:8d} {r['scams']:6d} {fmt(r['recall'])} "
                  f"{fmt(r['false_positive_rate'], False)} {fmt(r['precision'], w=6)} {r['mean_predicted']:6.1%} "
                  f"{r['scam_rate']:7.1%}{'   (few scams: uncertain)' if r['uncertain'] else ''}")
    print(f"\n  wrote {path}")


if __name__ == "__main__":
    main()
