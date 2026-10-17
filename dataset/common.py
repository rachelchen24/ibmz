"""Shared loaders for the dataset stage. Only verified (`used`) evidence is read here."""
import json
import re
from collections import defaultdict

import pandas as pd

from collect.common import config
from collect.common.companies import load_companies
from collect.common.output import read_jsonl


def used_evidence(path=None) -> list[dict]:
    path = path or config.VERIFY_DIR / "evidence.jsonl"
    if not path.exists():
        raise SystemExit(f"{path} not found: run `python -m verify.accept` first")
    return [r for r in read_jsonl(path) if r.get("used") in (True, "True", "true")]


def by_ticker_field(rows: list[dict]) -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        out[r["ticker"]][r["field"]].append(r)
    return out


def companies() -> dict[str, dict]:
    return {c["ticker"]: c for c in load_companies()}


def fy(period) -> int | None:
    m = re.match(r"FY(\d{4})", str(period))
    return int(m.group(1)) if m else None


def latest_features() -> pd.DataFrame:
    """Merged features if `collect.merge` has run, else every shard's latest features file."""
    merged = sorted((config.COLLECT_DIR / "merged").glob("features_*.csv"))
    if merged:
        return pd.read_csv(merged[-1])
    frames = []
    for d in sorted(config.COLLECT_DIR.glob("shard_*")):
        files = sorted(d.glob("features_*.csv"))
        if files:
            frames.append(pd.read_csv(files[-1]))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def dump_json(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
