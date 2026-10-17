"""Fixed, reproducible, group-aware train / validation / test split (ml/AUDIT.md explains why).

    python -m ml.split            # writes ml/splits/split_v1.csv, split_v1.json and data/fake_job_postings_cleaned.csv

Groups: postings are linked when they share a company profile or a description (after normalization, with the
anonymized URL/email/phone hashes kept, since a shared hash means the same link). Linked postings form one group via
union-find, so the same company, and the same copy-pasted posting under different companies, never straddles
splits. In this data no company has both real and fraudulent postings, so a random split would let a model
memorize companies and overstate its accuracy.

Split: StratifiedGroupKFold(7, shuffle, seed 42) over the deduplicated rows: fold 0 = test (~14%), fold 1 =
validation (~14%), folds 2-6 = train (~71%). Train rows also get `cv_fold` 0-4 (StratifiedGroupKFold(5) within
train) for model selection. Exact duplicates removed by cleaning are listed with split = "dropped_duplicate".

    from ml.split import load_split
    df = load_split()   # cleaned rows with group_id, split, cv_fold
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from .cleaning import DATA_PATH, ID, TARGET, clean, clean_text, drop_exact_duplicates, load_raw

SEED = 42
VERSION = "v1"
SPLIT_DIR = Path(__file__).resolve().parent / "splits"
SPLIT_CSV = SPLIT_DIR / f"split_{VERSION}.csv"
SPLIT_JSON = SPLIT_DIR / f"split_{VERSION}.json"
CLEAN_CSV = DATA_PATH.with_name("fake_job_postings_cleaned.csv")   # convenience copy; load_split() is the source
GROUP_KEYS = [("company_profile", 30), ("description", 50)]   # (column, minimum normalized length)
N_OUTER, N_CV = 7, 5


def group_key(s, min_len: int):
    t = clean_text(s, keep_placeholder_ids=True)
    if t is pd.NA:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9#_ ]", "", t.lower())).strip()
    return t if len(t) >= min_len else None   # very short texts ("Sales") are too generic to mean same company


def build_groups(df: pd.DataFrame) -> pd.Series:
    """group_id per row: connected components of rows sharing any GROUP_KEYS value."""
    parent = np.arange(len(df))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for col, n in GROUP_KEYS:
        first: dict[str, int] = {}
        for i, k in enumerate(df[col].map(lambda s: group_key(s, n))):
            if k is None:
                continue
            if k in first:
                parent[find(i)] = find(first[k])
            else:
                first[k] = i
    roots = pd.Series([find(i) for i in range(len(df))], index=df.index)
    # stable, readable ids: g + smallest job_id in the group
    return roots.map(df.groupby(roots)[ID].min()).map(lambda j: f"g{int(j):05d}")


def make_split(raw: pd.DataFrame) -> pd.DataFrame:
    kept, dropped = drop_exact_duplicates(raw)
    kept = kept.sort_values(ID).reset_index(drop=True)
    groups = build_groups(kept)
    y = kept[TARGET].to_numpy()
    split = np.empty(len(kept), dtype=object)
    outer = StratifiedGroupKFold(n_splits=N_OUTER, shuffle=True, random_state=SEED)
    for k, (_, idx) in enumerate(outer.split(kept, y, groups)):
        split[idx] = "test" if k == 0 else "val" if k == 1 else "train"
    cv = np.full(len(kept), -1)
    tr = np.where(split == "train")[0]
    inner = StratifiedGroupKFold(n_splits=N_CV, shuffle=True, random_state=SEED)
    for k, (_, idx) in enumerate(inner.split(tr, y[tr], groups.iloc[tr])):
        cv[tr[idx]] = k
    out = pd.DataFrame({ID: kept[ID], "group_id": groups, "split": split, "cv_fold": cv, TARGET: y})
    dmap = dict(zip(kept[ID], groups))
    dup = pd.DataFrame({ID: dropped[ID], "group_id": dropped["duplicate_of"].map(dmap), "split": "dropped_duplicate",
                        "cv_fold": -1, TARGET: dropped[TARGET]})
    return pd.concat([out, dup]).sort_values(ID).reset_index(drop=True)


def summarize(s: pd.DataFrame, data_sha256: str) -> dict:
    live = s[s["split"] != "dropped_duplicate"]
    out = {"version": VERSION, "seed": SEED, "data_file": DATA_PATH.name, "data_sha256": data_sha256,
           "group_keys": [k for k, _ in GROUP_KEYS], "rows_raw": int(len(s)),
           "rows_dropped_duplicates": int((s["split"] == "dropped_duplicate").sum()), "splits": {}, "cv_folds": {}}
    for name, g in live.groupby("split"):
        out["splits"][name] = {"rows": int(len(g)), "share": round(len(g) / len(live), 4), "fraud": int(g[TARGET].sum()),
                               "prevalence": round(float(g[TARGET].mean()), 4), "groups": int(g["group_id"].nunique())}
    for k, g in live[live["cv_fold"] >= 0].groupby("cv_fold"):
        out["cv_folds"][int(k)] = {"rows": int(len(g)), "fraud": int(g[TARGET].sum()),
                                   "prevalence": round(float(g[TARGET].mean()), 4)}
    cross = live.groupby("group_id")["split"].nunique()
    out["groups_crossing_splits"] = int((cross > 1).sum())
    cv_cross = live[live["cv_fold"] >= 0].groupby("group_id")["cv_fold"].nunique()
    out["groups_crossing_cv_folds"] = int((cv_cross > 1).sum())
    return out


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_split(path=SPLIT_CSV, data_path=DATA_PATH) -> pd.DataFrame:
    """Cleaned, deduplicated rows joined to their group_id, split and cv_fold. Checks the data file is the one the
    split was made from."""
    meta = json.loads(Path(path).with_suffix(".json").read_text(encoding="utf-8"))
    if sha256(data_path) != meta["data_sha256"]:
        raise RuntimeError(f"{data_path} differs from the file split_{meta['version']} was built from; rebuild the "
                           "split (python -m ml.split) and tell the team")
    s = pd.read_csv(path)
    s = s[s["split"] != "dropped_duplicate"].drop(columns=[TARGET])
    df = clean(load_raw(data_path))
    out = df.merge(s, on=ID, how="inner", validate="one_to_one")
    if len(out) != len(s):
        raise RuntimeError("split file and data disagree on job_ids")
    return out


def main():
    raw = load_raw()
    s = make_split(raw)
    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    s.to_csv(SPLIT_CSV, index=False)
    meta = summarize(s, sha256(DATA_PATH))
    SPLIT_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"=== split {VERSION}: {meta['rows_raw']} rows, {meta['rows_dropped_duplicates']} exact duplicates dropped ===")
    for name in ("train", "val", "test"):
        m = meta["splits"][name]
        print(f"  {name:5s} {m['rows']:6d} rows ({m['share']:.1%})  fraud {m['fraud']:4d}  prevalence {m['prevalence']:.2%}  "
              f"groups {m['groups']}")
    print("  cv folds (train): " + "  ".join(f"{k}: {v['rows']} rows / {v['prevalence']:.2%}" for k, v in meta["cv_folds"].items()))
    print(f"  groups crossing splits: {meta['groups_crossing_splits']}   crossing cv folds: {meta['groups_crossing_cv_folds']}")
    print(f"  wrote {SPLIT_CSV} and {SPLIT_JSON.name}")
    export_clean()


def export_clean(path=CLEAN_CSV) -> None:
    """Write the cleaned, deduplicated rows with group_id, split and cv_fold to one CSV (for notebooks and Excel)."""
    df = load_split()
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"  wrote {path} ({len(df)} rows, {df.shape[1]} columns)")


if __name__ == "__main__":
    main()
