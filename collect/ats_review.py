"""List companies with no job board found, as a sheet for people to fill: data/labels/ats_overrides.csv.

    python -m collect.ats_review

Adds every company whose latest ats_summary says "no public board found" or "board fetch failed" (rows already in
the sheet are kept as they are). For each, a person opens the careers site and fills `ats`:
  greenhouse:<token>        from boards.greenhouse.io/<token> or job-boards.greenhouse.io/<token>
  lever:<slug>              from jobs.lever.co/<slug>
  workday:<host>/<site>     from https://<host>/<site> or https://<host>/en-US/<site>, e.g. workday:hpe.wd5.myworkdayjobs.com/ACJobSite
  none                      the site uses another system (iCIMS, Oracle, SuccessFactors, ...): skip detection
Then rerun those companies:  python -m collect.scraperN --tickers T1 T2 --steps ats,wayback
"""
import pandas as pd

from .common import config

COLUMNS = ["ticker", "name", "shard", "ats", "careers_url", "notes"]


def main():
    path = config.ATS_OVERRIDES
    sheet = pd.read_csv(path, dtype=str, keep_default_na=False) if path.exists() else pd.DataFrame(columns=COLUMNS)
    have = set(sheet["ticker"])
    new = []
    for n in range(1, config.N_SHARDS + 1):
        files = sorted(config.shard_dir(n).glob("ats_summary_*.csv"))
        if not files:
            continue
        s = pd.read_csv(files[-1], dtype=str, keep_default_na=False)
        for r in s[s["status"] != "ok"].to_dict("records"):
            if r["ticker"] not in have:
                new.append({"ticker": r["ticker"], "name": r["name"], "shard": n, "ats": "",
                            "careers_url": r.get("careers_url", ""), "notes": r["status"]})
                have.add(r["ticker"])
    out = pd.concat([sheet, pd.DataFrame(new, columns=COLUMNS)], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.sort_values(["shard", "ticker"]).to_csv(path, index=False)
    todo = out[out["ats"].str.strip() == ""]
    print(f"{path}: {len(out)} companies, {len(new)} added, {len(todo)} still to look up")
    print(__doc__.split("\n\n", 2)[2] if len(todo) else "all filled; rerun the scrapers with --tickers to collect them")


if __name__ == "__main__":
    main()
