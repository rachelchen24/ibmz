"""Load the company list and split it into the four shards (build plan 1.5)."""
import logging
import os
import random
import re

import pandas as pd

from . import config

log = logging.getLogger(__name__)

_TRUE = {"1", "true", "yes", "y"}


def _clean(v):
    v = (v or "").strip()
    return v or None


def load_companies(path=config.COMPANY_LIST) -> list[dict]:
    """Selected, not-dropped companies with a fixed `shard` (1-4) assigned to each."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "selected" in df:
        df = df[df["selected"].str.strip().str.lower().isin(_TRUE)]
    if "dropped" in df:
        df = df[~df["dropped"].str.strip().str.lower().isin(_TRUE)]

    rows = []
    for i, r in enumerate(df.to_dict("records")):
        ticker = (r.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        cik = re.sub(r"\D", "", r.get("cik") or "")
        aliases = [a.strip() for a in re.split(r"[;|]", r.get("aliases") or "") if a.strip()]
        name = (r.get("name") or "").strip()
        try:
            size = float(r.get("public_float_usd") or r.get("market_cap") or "nan")
        except ValueError:
            size = float("nan")
        tier = r.get("priority_tier") or r.get("tier") or "1"
        rows.append({
            "ticker": ticker,
            "cik": cik.zfill(10) if cik else None,
            "name": name,
            "aliases": [name] + [a for a in aliases if a != name],
            "sector": _clean(r.get("sector")) or _clean(r.get("group")),
            "sic": _clean(r.get("sic")),
            "hq_state": _clean(r.get("hq_state")),
            "size": size,
            "priority_tier": int(tier) if str(tier).strip().isdigit() else 1,
            "ats": _clean(r.get("ats")),
            "careers_url": _clean(r.get("careers_url")),
            "pilot": (r.get("pilot") or "").strip().lower() in _TRUE,
            "shard": int(r["shard"]) if str(r.get("shard") or "").strip().isdigit() else None,
            "order": i,
        })
    if any(c["shard"] is None for c in rows):
        assign_shards(rows)
    return rows


def assign_shards(rows: list[dict]) -> None:
    """Sort by tier, sector, size (largest first) and deal round-robin, so every shard gets the same mix."""
    ordered = sorted(rows, key=lambda c: (c["priority_tier"], c["sector"] or "",
                                          -(c["size"] if c["size"] == c["size"] else 0), c["ticker"]))
    for i, c in enumerate(ordered):
        c["shard"] = i % config.N_SHARDS + 1


def select(rows: list[dict], shard: int, sample: bool = False, tickers=None, limit=None) -> list[dict]:
    """The shard's companies, tier 1 first. --sample gives the shard's pilot companies."""
    picked = [c for c in rows if c["shard"] == shard]
    if tickers:
        want = {t.upper() for t in tickers}
        picked = [c for c in rows if c["ticker"] in want]   # explicit tickers may cross shards (takeovers)
    elif sample:
        pilots = [c for c in picked if c["pilot"]]
        if not pilots:
            pilots = random.Random(config.SEED + shard).sample(picked, min(config.PILOT_PER_SHARD, len(picked)))
        picked = pilots
    picked.sort(key=lambda c: (c["priority_tier"], c["order"]))
    return picked[:limit] if limit else picked


def write_assignment(rows: list[dict]) -> None:
    """data/collect/shard_assignment.csv, the same in every run (deterministic)."""
    out = config.COLLECT_DIR / "shard_assignment.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(f".{os.getpid()}.tmp")
    pd.DataFrame([{k: c[k] for k in ("ticker", "name", "sector", "priority_tier", "shard")} for c in rows]) \
        .sort_values(["shard", "priority_tier", "sector", "ticker"]).to_csv(tmp, index=False)
    os.replace(tmp, out)
