"""Data audit for data/fake_job_postings.csv: every number in ml/AUDIT.md comes from this script.

    python -m ml.audit            # prints the audit and writes ml/reports/data_audit.json

Run `python -m ml.split` first for the split section (and the random-vs-group leakage check).
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .cleaning import (BINARY_COLS, CATEGORICAL_COLS, ID, RAW_COLUMNS, TARGET, TEXT_COLS, clean, drop_exact_duplicates,
                       load_raw, parse_salary)

REPORT = Path(__file__).resolve().parent / "reports" / "data_audit.json"
PLACEHOLDERS = {"url": r"#URL_[0-9a-fA-F]+#", "email": r"#EMAIL_[0-9a-fA-F]+#", "phone": r"#PHONE_[0-9a-fA-F]+#"}


def _rate(mask, y):
    return round(float(y[mask].mean()), 4) if mask.any() else None


def audit(raw: pd.DataFrame) -> dict:
    y = raw[TARGET]
    a: dict = {"rows": int(len(raw)), "columns": int(raw.shape[1]),
               "dtypes": {c: str(raw[c].dtype) for c in raw.columns},
               "label": {"values": {int(k): int(v) for k, v in y.value_counts().items()},
                         "prevalence": round(float(y.mean()), 4)},
               "job_id": {"unique": bool(raw[ID].is_unique), "min": int(raw[ID].min()), "max": int(raw[ID].max()),
                          "contiguous": bool(raw[ID].max() - raw[ID].min() + 1 == len(raw))}}

    # missingness, overall and by class: missing-ness itself is predictive here
    miss = {}
    for c in RAW_COLUMNS:
        if c in (ID, TARGET):
            continue
        s = raw[c]
        m = s.isna() | (s.astype("string").str.strip() == "")
        miss[c] = {"missing": int(m.sum()), "share": round(float(m.mean()), 4),
                   "fraud_rate_if_missing": _rate(m, y), "fraud_rate_if_present": _rate(~m, y)}
    a["missingness"] = miss

    a["binary"] = {c: {"values": {int(k): int(v) for k, v in raw[c].value_counts().items()},
                       "fraud_rate_if_1": _rate(raw[c] == 1, y), "fraud_rate_if_0": _rate(raw[c] == 0, y)}
                   for c in BINARY_COLS}
    a["categorical"] = {c: {"distinct": int(raw[c].nunique()),
                            "case_or_space_variants": int(raw[c].nunique() - raw[c].str.lower().str.strip().nunique()),
                            "top": {str(k): int(v) for k, v in raw[c].value_counts().head(8).items()}}
                        for c in CATEGORICAL_COLS + ["location"]}

    # text characteristics
    txt = {}
    for c in TEXT_COLS:
        s = raw[c].fillna("")
        L = s.str.len()
        t = {"chars_median": float(L.median()), "chars_p95": float(L.quantile(.95)), "chars_max": int(L.max()),
             "chars_median_fraud": float(L[y == 1].median()), "chars_median_real": float(L[y == 0].median()),
             "html_entities": int(s.str.contains(r"&[a-z]+;|&#\d+;", regex=True).sum()),
             "run_together_words": int(s.str.contains(r"[a-z]{2}[A-Z][a-z]", regex=True).sum()),
             "replacement_char": int(s.str.contains("�").sum())}
        for k, p in PLACEHOLDERS.items():
            has = s.str.contains(p, regex=True)
            t[f"{k}_placeholder_rows"] = int(has.sum())
            t[f"{k}_placeholder_fraud_rate"] = _rate(has, y)
        txt[c] = t
    a["text"] = txt

    sal = raw["salary_range"].map(parse_salary)
    valid = sal.map(lambda t: not np.isnan(t[0]))
    a["salary_range"] = {"present": int(raw["salary_range"].notna().sum()), "parsed": int(valid.sum()),
                         "invalid_excel_dates_or_zero": int(sal.map(lambda t: t[2]).sum()),
                         "max_under_1000": int(sal.map(lambda t: t[1] < 1000 if not np.isnan(t[1]) else False).sum())}
    parts = raw["location"].dropna().str.split(",").map(len)
    a["location"] = {"present": int(raw["location"].notna().sum()),
                     "country_state_city_format": int((parts == 3).sum()), "other_formats": int((parts != 3).sum())}

    # duplicates
    kept, dropped = drop_exact_duplicates(raw)
    norm = lambda s: s.fillna("").str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    dup = {"exact_duplicate_rows_removed": int(len(dropped)), "exact_duplicates_fraud": int(dropped[TARGET].sum())}
    feats = [c for c in RAW_COLUMNS if c not in (ID, TARGET)]
    allfeat = raw.duplicated(feats, keep=False)
    dup["exact_duplicate_label_conflicts"] = int((raw[allfeat].groupby(feats, dropna=False)[TARGET].nunique() > 1).sum())
    for name, cols in {"title+description": ["title", "description"], "description": ["description"]}.items():
        k = raw[cols].apply(norm).agg("|".join, axis=1)
        d = k.duplicated(keep=False) & (k.str.len() > len(cols))
        conf = raw[d].groupby(k[d])[TARGET].nunique()
        dup[f"rows_sharing_{name}"] = int(d.sum())
        dup[f"groups_sharing_{name}"] = int(k[d].nunique())
        dup[f"label_conflict_groups_{name}"] = int((conf > 1).sum())
    a["duplicates"] = dup

    # company overlap (company_profile is the only company identifier in the data)
    cp = norm(raw["company_profile"])
    has = cp != ""
    grp = raw[has].groupby(cp[has])[TARGET].agg(["size", "sum"])
    a["company_overlap"] = {
        "rows_with_profile": int(has.sum()), "distinct_profiles": int(len(grp)),
        "largest_profile_rows": int(grp["size"].max()), "profiles_with_2plus_postings": int((grp["size"] >= 2).sum()),
        "rows_in_shared_profiles": int(grp.loc[grp["size"] >= 2, "size"].sum()),
        "profiles_with_any_fraud": int((grp["sum"] > 0).sum()),
        "profiles_with_mixed_labels": int(((grp["sum"] > 0) & (grp["sum"] < grp["size"])).sum()),
        "fraud_rate_profile_missing": _rate(~has, raw[TARGET]), "fraud_rate_profile_present": _rate(has, raw[TARGET])}
    return a


def split_section() -> dict | None:
    from .split import SPLIT_CSV, SPLIT_JSON, load_split
    if not SPLIT_CSV.exists():
        return None
    out = json.loads(SPLIT_JSON.read_text(encoding="utf-8"))
    df = load_split()
    s = df.groupby("group_id")[TARGET].agg(["size", "sum"])
    out["group_stats"] = {"groups": int(len(s)), "singletons": int((s["size"] == 1).sum()),
                          "largest_rows": int(s["size"].max()), "largest_share": round(float(s["size"].max() / len(df)), 4),
                          "mixed_label_groups": int(((s["sum"] > 0) & (s["sum"] < s["size"])).sum()),
                          "fraud_groups": int((s["sum"] > 0).sum()), "largest_fraud_group_rows": int(s["sum"].max())}
    # How often would a random stratified split put a test row's group in train?
    from sklearn.model_selection import train_test_split
    idx = np.arange(len(df))
    tr, te = train_test_split(idx, test_size=0.15, stratify=df[TARGET], random_state=42)
    seen = set(df["group_id"].iloc[tr])
    in_train = df["group_id"].iloc[te].isin(seen).to_numpy()
    fraud_te = df[TARGET].iloc[te].to_numpy() == 1
    out["random_split_leakage"] = {"test_rows_with_group_in_train": round(float(in_train.mean()), 4),
                                   "test_fraud_rows_with_group_in_train": round(float(in_train[fraud_te].mean()), 4)}
    return out


def main():
    raw = load_raw()
    a = audit(raw)
    sp = split_section()
    if sp:
        a["split"] = sp
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(a, indent=2, default=str), encoding="utf-8")

    print(f"=== audit: {a['rows']} rows x {a['columns']} columns, fraud {a['label']['values'].get(1)} "
          f"({a['label']['prevalence']:.2%}) ===")
    print("  missing (share; fraud rate if missing vs present):")
    for c, m in sorted(a["missingness"].items(), key=lambda kv: -kv[1]["share"]):
        if m["missing"]:
            print(f"    {c:20s} {m['share']:6.1%}   {m['fraud_rate_if_missing']:.1%} vs {m['fraud_rate_if_present']:.1%}")
    d, co = a["duplicates"], a["company_overlap"]
    print(f"  exact duplicates removed: {d['exact_duplicate_rows_removed']} (label conflicts {d['exact_duplicate_label_conflicts']}); "
          f"rows sharing a description: {d['rows_sharing_description']}")
    print(f"  company profiles: {co['distinct_profiles']} distinct; {co['profiles_with_mixed_labels']} with mixed labels; "
          f"fraud rate {co['fraud_rate_profile_missing']:.1%} when missing vs {co['fraud_rate_profile_present']:.1%}")
    if sp:
        g, rl = sp["group_stats"], sp["random_split_leakage"]
        print(f"  groups: {g['groups']} (largest {g['largest_share']:.1%} of rows, {g['mixed_label_groups']} mixed-label)")
        print(f"  a random split would put {rl['test_rows_with_group_in_train']:.0%} of test rows "
              f"({rl['test_fraud_rows_with_group_in_train']:.0%} of test fraud) in groups seen in training")
    print(f"  wrote {REPORT}")


if __name__ == "__main__":
    main()
