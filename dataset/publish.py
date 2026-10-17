"""Publish the dataset (build plan 4B-1): dataset/published/companies.csv and evidence.csv, committed to the repo.

companies.csv: one row per company, its company-list columns, the board we found, and the indicator columns.
evidence.csv: every `used` evidence row (value, source URL, short quote, dates, check result). Quotes are cut to
QUOTE_MAX characters; we publish indicators and short quotes, never copies of pages. Nothing about individual people.
The numbers block in DATASHEET.md (between the AUTO markers) is refreshed from the published files.

    python -m dataset.publish
"""
import json
import re
from datetime import date

import pandas as pd

from collect.common import config
from collect.common.output import EVIDENCE_COLUMNS

from .common import companies, latest_features, used_evidence

QUOTE_MAX = 300
DATASHEET = config.ROOT / "dataset" / "DATASHEET.md"
COMPANY_COLUMNS = ["ticker", "cik", "name", "sector", "sic", "hq_state", "priority_tier", "shard"]
PUBLISHED_EVIDENCE = [c for c in EVIDENCE_COLUMNS if c not in ("run_id",)] + ["check", "conflict", "used"]


def main():
    comp = companies()
    feat = latest_features()
    base = pd.DataFrame([{k: c.get(k) for k in COMPANY_COLUMNS} for c in comp.values()])
    if not feat.empty:
        keep = [c for c in feat.columns if c not in ("name", "sector", "shard")]
        base = base.merge(feat[keep], on="ticker", how="left")
        base = base.rename(columns={"snapshot_date": "indicators_as_of"})

    ev = used_evidence()
    E = pd.DataFrame(ev)
    if not E.empty:
        E["quote"] = E["quote"].map(lambda q: q if len(q) <= QUOTE_MAX else q[:QUOTE_MAX - 1].rstrip() + "…")
        E["value"] = E["value"].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
        E = E[[c for c in PUBLISHED_EVIDENCE if c in E.columns]].sort_values(["ticker", "field", "period"])

    config.PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    base.sort_values("ticker").to_csv(config.PUBLISHED_DIR / "companies.csv", index=False)
    E.to_csv(config.PUBLISHED_DIR / "evidence.csv", index=False)

    n_feat = int(base["open_postings_log"].notna().sum()) if "open_postings_log" in base else 0
    stats = [
        f"- Published {date.today().isoformat()}: **{len(base)} companies**, **{len(E)} verified evidence rows**.",
        f"- Companies with current postings from a public ATS board: {n_feat}.",
    ]
    if not E.empty:
        stats.append("- Evidence rows by field: " + ", ".join(f"`{k}` {v}" for k, v in E["field"].value_counts().items()) + ".")
        stats.append("- Evidence rows by collector: " + ", ".join(f"`{k}` {v}" for k, v in E["collector"].value_counts().items()) + ".")
    spot = config.METRICS_DIR / "spot_check.json"
    if spot.exists():
        s = json.loads(spot.read_text(encoding="utf-8"))["overall"]
        stats.append(f"- Spot check: {s['wrong']}/{s['n']} values wrong = {s['error_rate']:.1%} "
                     f"(95% CI {s['ci95'][0]:.1%}-{s['ci95'][1]:.1%}).")
    if DATASHEET.exists():
        text = DATASHEET.read_text(encoding="utf-8")
        text = re.sub(r"(<!-- AUTO:START -->\n).*?(\n<!-- AUTO:END -->)", lambda m: m.group(1) + "\n".join(stats) + m.group(2),
                      text, flags=re.S)
        DATASHEET.write_text(text, encoding="utf-8")
    print(f"published {len(base)} companies and {len(E)} evidence rows to {config.PUBLISHED_DIR}")
    print("\n".join(stats))


if __name__ == "__main__":
    main()
