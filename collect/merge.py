"""Merge the four scrapers' outputs into one dataset (build plan 1.5, "The merge", steps 1, 2 and 4).

    python -m collect.merge                    # latest snapshot in every shard
    python -m collect.merge --snapshot 2026-10-17

Writes data/collect/merged/:
  features_<snapshot>.csv     one row per company, all shards (from scraper1..4_features_<date>.csv)
  postings_<snapshot>.csv     all postings (posting fields + extras), deduplicated by posting_id
  candidates.csv              all candidate evidence rows, deduplicated by evidence_id (verify these next)
  coverage_<snapshot>.csv     per shard and sector: companies, and how many have each feature
  merge_report.json           manifest checks: shards present, same code, every company in exactly one shard
Verification (verify/) still runs once, centrally, over candidates before anything is loaded into the store.
"""
import argparse
import json

import pandas as pd

from .common import config
from .common.companies import load_companies
from .common.output import read_jsonl
from .common.supersede import current_candidates
from .features import FEATURES


def _latest(d, pattern):
    files = sorted(p for p in d.glob(pattern) if ".rejected" not in p.name)
    return files[-1] if files else None


def _features_file(n: int, snapshot: str | None):
    """scraper<n>_features_<date>.csv: in shard_<n>/, or anywhere under data/collect/ (e.g. a teammate's file
    dropped in as-is). The latest date wins unless --snapshot is given."""
    pattern = f"scraper{n}_features_{snapshot or '*'}.csv"
    files = [p for p in config.COLLECT_DIR.rglob(pattern) if "merged" not in p.parts]
    files += [p for p in config.shard_dir(n).glob(f"features_{snapshot or '*'}.csv")]   # older name
    return max(files, key=lambda p: (p.stem.rsplit("_", 1)[-1], p.stat().st_mtime)) if files else None


def main():
    ap = argparse.ArgumentParser(description="Merge scraper1..scraper4 outputs.")
    ap.add_argument("--snapshot", help="postings/features snapshot date (default: latest in each shard)")
    ap.add_argument("--companies", default=str(config.COMPANY_LIST))
    a = ap.parse_args()
    out = config.COLLECT_DIR / "merged"
    out.mkdir(parents=True, exist_ok=True)

    report = {"shards": {}, "problems": []}
    feats, posts, cands = [], [], []
    for n in range(1, config.N_SHARDS + 1):
        d = config.shard_dir(n)
        man = d / "manifest.json"
        if man.exists():
            m = json.loads(man.read_text(encoding="utf-8"))
            report["shards"][n] = {k: m.get(k) for k in ("run_id", "git_commit", "prompt_version", "snapshot_date",
                                                         "started_at", "ended_at", "row_counts", "failed")}
        else:
            report["problems"].append(f"shard {n}: no manifest.json (only the features CSV can be merged)")
        f = _features_file(n, a.snapshot)
        if f:
            feats.append(pd.read_csv(f))
            report.setdefault("features_files", {})[n] = str(f.relative_to(config.ROOT))
        else:
            report["problems"].append(f"shard {n}: no scraper{n}_features_*.csv found under {config.COLLECT_DIR}")
        p = d / f"postings_{a.snapshot}.jsonl" if a.snapshot else _latest(d, "postings_2*.jsonl")
        if p and p.exists():
            df = pd.DataFrame(read_jsonl(p))
            ex = pd.DataFrame(read_jsonl(p.with_name(p.name.replace("postings_", "postings_extra_"))))
            if not df.empty and not ex.empty:
                df = df.merge(ex.drop(columns=["ticker"], errors="ignore"), on="posting_id", how="left")
            posts.append(df)
        cands += current_candidates(d)

    commits = {s["git_commit"] for s in report["shards"].values()}
    if len(commits) > 1:
        report["problems"].append(f"shards ran different code: {sorted(map(str, commits))}")

    F = pd.concat(feats, ignore_index=True) if feats else pd.DataFrame(columns=["ticker"] + FEATURES)
    dup = F[F.duplicated("ticker", keep=False)]["ticker"].unique().tolist()
    if dup:
        report["problems"].append(f"companies in more than one shard (kept the latest snapshot): {dup}")
        F = F.sort_values("snapshot_date").drop_duplicates("ticker", keep="last")
    universe = {c["ticker"] for c in load_companies(a.companies)}
    missing = sorted(universe - set(F["ticker"]))
    report["companies"] = {"in_list": len(universe), "merged": len(F), "missing": missing}

    snap = a.snapshot or (F["snapshot_date"].max() if len(F) else "none")
    F.to_csv(out / f"features_{snap}.csv", index=False)
    P = pd.concat(posts, ignore_index=True).drop_duplicates("posting_id", keep="last") if posts else pd.DataFrame()
    P.to_csv(out / f"postings_{snap}.csv", index=False)
    C = pd.DataFrame(cands)
    if not C.empty:
        C = C.drop_duplicates("evidence_id", keep="last")
        C["value"] = C["value"].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
    C.to_csv(out / "candidates.csv", index=False)

    if len(F):
        cov = F.groupby(["shard", "sector"]).agg(companies=("ticker", "count"),
                                                 **{k: (k, "count") for k in FEATURES}).reset_index()
        cov.to_csv(out / f"coverage_{snap}.csv", index=False)
    (out / "merge_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"merged {len(report['shards'])}/4 shards: {len(F)} companies, {len(P)} postings, {len(C)} evidence rows")
    print(f"missing companies: {len(missing)}" + (f" (e.g. {missing[:8]})" if missing else ""))
    for p in report["problems"]:
        print("PROBLEM:", p)
    print(f"output: {out}")


if __name__ == "__main__":
    main()
