"""Student survey summary (build plan 3.4, 4B-3). Reads data/labels/survey.csv (exported without names or emails).

Expected questions (column names are matched loosely): jobs applied to in the past 12 months; how many never
responded; applied to the same company more than once and never heard back (yes / no).

    python -m dataset.survey_summary
"""
import re

import numpy as np
import pandas as pd

from collect.common import config

from .common import dump_json

SURVEY = config.LABELS_DIR / "survey.csv"


def _col(df, *patterns):
    for p in patterns:
        for c in df.columns:
            if re.search(p, c, re.I):
                return c
    return None


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.extract(r"(\d+)")[0], errors="coerce")


def main():
    if not SURVEY.exists():
        raise SystemExit(f"{SURVEY} not found: export the form (no names or emails) there first")
    df = pd.read_csv(SURVEY)
    c_app = _col(df, r"how many.*appl|applied", r"appl")
    c_none = _col(df, r"never.*(respond|heard|repl)", r"no response")
    c_same = _col(df, r"more than once|same company")
    out = {"responses": int(len(df))}
    if c_app and c_none:
        a, n = _num(df[c_app]), _num(df[c_none])
        ok = a.notna() & n.notna() & (a > 0) & (n <= a)
        a, n = a[ok], n[ok]
        rng = np.random.default_rng(config.SEED)
        idx = rng.integers(0, len(a), size=(2000, len(a))) if len(a) else None
        boot = (n.to_numpy()[idx].sum(1) / a.to_numpy()[idx].sum(1)) if len(a) else []
        out.update({
            "valid": int(ok.sum()), "median_applied": float(a.median()), "median_never_responded": float(n.median()),
            "share_of_applications_never_answered": float(n.sum() / a.sum()) if a.sum() else None,
            "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))] if len(a) else None})
    if c_same:
        yes = df[c_same].astype(str).str.strip().str.lower().str.startswith("y")
        out["share_reapplied_no_answer"] = float(yes.mean())
    dump_json(out, config.METRICS_DIR / "survey.json")
    print(f"=== survey: {out['responses']} responses ===")
    for k, v in out.items():
        print(f"  {k}: {v}")
    print("Quote these as 'in our survey of N students', not as a population estimate.")


if __name__ == "__main__":
    main()
