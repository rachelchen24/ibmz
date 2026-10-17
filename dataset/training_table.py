"""Training table: merged features + the ground-truth label, in data/collect/merged/training_<date>.csv.

The features file stays label-free (it is what gets scored); this file is what the model trains on. Only the label
and how it was made are added, never its parts (headcount change), so nothing derived from the answer can leak
into the features.

Label columns (all from data/processed/outcomes.csv, built from verified evidence only):
  gt_follow_through        estimated hires / postings over the fiscal year, capped at 1 (empty = no label)
  gt_available             True when the company has a label
  gt_fiscal_year           the fiscal year the label describes
  gt_postings_year_method  how postings over the year were counted
  gt_archived_months       archived board snapshots inside that fiscal year (more = more reliable)
  gt_capped                True when estimated hires exceeded postings (ratio cut to 1)
  gt_missing_reason        why a company has no label

    python -m dataset.build_outcomes --method unique_ids
    python -m dataset.training_table
"""
import pandas as pd

from collect.common import config

from .common import latest_features


def main():
    feat = latest_features()
    if feat.empty:
        raise SystemExit("no features: run python -m collect.merge first")
    out_path = config.PROCESSED_DIR / "outcomes.csv"
    if not out_path.exists():
        raise SystemExit("no outcomes: run python -m dataset.build_outcomes first")
    o = pd.read_csv(out_path)
    ex = pd.read_csv(config.PROCESSED_DIR / "outcomes_excluded.csv")

    label = pd.DataFrame({
        "ticker": o["ticker"], "gt_follow_through": o["follow_through"], "gt_fiscal_year": o["fiscal_year"],
        "gt_postings_year_method": o["postings_year_method"], "gt_archived_months": o["archived_snapshots_in_year"],
        "gt_capped": o["follow_through_capped"]})
    t = feat.merge(label, on="ticker", how="left").merge(
        ex.rename(columns={"reason": "gt_missing_reason"}), on="ticker", how="left")
    t["gt_available"] = t["gt_follow_through"].notna()
    t.loc[t["gt_available"], "gt_missing_reason"] = None
    t.loc[~t["gt_available"] & t["gt_missing_reason"].isna(), "gt_missing_reason"] = "not processed"

    snap = str(t["snapshot_date"].dropna().max()) if "snapshot_date" in t else "latest"
    dest = config.COLLECT_DIR / "merged" / f"training_{snap}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(dest, index=False)

    n = int(t["gt_available"].sum())
    print(f"=== training table: {len(t)} companies, {n} with a ground-truth label -> {dest}")
    if n:
        g = t.loc[t["gt_available"], "gt_follow_through"]
        print(f"  label median {g.median():.2f}, range {g.min():.2f}-{g.max():.2f}, capped at 1: {int(t['gt_capped'].fillna(False).sum())}")
        print("  labeled by sector: " + ", ".join(f"{k} {v}" for k, v in t[t['gt_available']].groupby('sector').size().items()))
    print("  no label, by reason:")
    for r, k in t.loc[~t["gt_available"], "gt_missing_reason"].str.replace(r"\(.*?\)|[-+]?\d+%?", "#", regex=True).value_counts().items():
        print(f"    {k:4d}  {r}")


if __name__ == "__main__":
    main()
