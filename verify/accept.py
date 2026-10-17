"""The verifier: the only path from candidate evidence to used evidence (build plan 1B-2).

For every candidate row: validate the format, fetch the source URL independently, check the quote is on the page,
check the value agrees with the quote, then flag values two sources disagree on. A row is `used` only if its check
passed and it isn't in conflict. Every accept and reject is logged.

    python -m verify.accept                       # all shards' candidates_*.jsonl
    python -m verify.accept --input data/collect/merged/candidates.csv
    python -m verify.accept --plant               # also prove a deliberately wrong value is rejected
    python -m verify.accept --limit 200 --verbose

Output in data/verify/ (not in git): evidence.jsonl and evidence.csv (contract columns + check, conflict, used,
spot_check), verify_log_<time>.csv and .txt (one line per decision). The database loader reads evidence.jsonl.

`check` values are the contract's (passed, quote_missing, fetch_failed, no_url, bad_format) plus value_mismatch:
the quote is on the page but the value doesn't agree with it.
"""
import argparse
import copy
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import pandas as pd

from collect.common import config
from collect.common.output import EVIDENCE_COLUMNS, read_jsonl, validate_evidence
from collect.common.supersede import current_candidates

from .conflicts import flag_conflicts
from .fetch import VERIFY_DIR, Fetcher
from .quote_check import PageIndex, value_check

OUT_COLUMNS = EVIDENCE_COLUMNS + ["check", "conflict", "used", "spot_check"]


def load_candidates(paths: list[str]) -> list[dict]:
    rows = {}
    if not paths:    # every shard, current rows only (a rerun of a step replaces that step's older rows)
        return [r for d in sorted(config.COLLECT_DIR.glob("shard_*")) for r in current_candidates(d)]
    files = [p for spec in paths for p in sorted(config.ROOT.glob(spec))]
    for p in files:
        if ".rejected" in p.name:
            continue
        if p.suffix == ".csv":
            for r in pd.read_csv(p, dtype=str, keep_default_na=False).to_dict("records"):
                v = r.get("value", "")
                try:
                    r["value"] = json.loads(v) if v[:1] in "{[" or v in ("true", "false") else (float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else v)
                except ValueError:
                    pass
                rows[r["evidence_id"]] = r
        else:
            for r in read_jsonl(p):
                rows[r["evidence_id"]] = r
    return list(rows.values())


def plant(rows: list[dict]) -> list[dict]:
    """Two deliberately wrong rows: an edited quote, and a wrong value with a real quote."""
    base = next((r for r in rows if r["field"] in ("employee_count", "revenue") and re.search(r"\d", r["quote"])), None)
    if not base:
        return []
    a = copy.deepcopy(base)
    a["quote"] = re.sub(r"\d", lambda m: str((int(m.group()) + 3) % 10), a["quote"], count=3)
    a["evidence_id"], a["_planted"] = "ev_PLANTED_QUOTE", "edited quote"
    b = copy.deepcopy(base)
    b["value"] = float(b["value"]) * 1.5
    b["evidence_id"], b["_planted"] = "ev_PLANTED_VALUE", "wrong value, real quote"
    return [a, b]


def verify(rows: list[dict], workers: int, today: date, defer_wayback: bool = False) -> list[dict]:
    fetcher = Fetcher(today, defer_wayback)
    by_url = defaultdict(list)
    for r in rows:
        r["check"], r["_detail"], r["_match"] = None, "", ""
        errs = validate_evidence(r)
        if not str(r.get("source_url") or "").startswith("http"):
            r["check"], r["_detail"] = "no_url", "no source URL"
        elif errs:
            r["check"], r["_detail"] = "bad_format", "; ".join(errs)
        else:
            by_url[r["source_url"]].append(r)

    def check_url(url, group):
        page = fetcher.get(url)
        if not page.ok:
            for r in group:
                r["check"], r["_detail"] = "fetch_failed", page.reason
            return
        idx = PageIndex(page.text, page.rows)
        for r in group:
            mode = idx.find(r["quote"])
            if not mode:
                r["check"], r["_detail"] = "quote_missing", "quote not on the page"
                continue
            vc, detail = value_check(r, idx)
            r["_match"] = mode + (f" ({page.reason})" if page.reason else "")
            r["check"], r["_detail"] = ("value_mismatch", detail) if vc == "mismatch" else ("passed", f"{vc}: {detail}".strip(": "))

    done = 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = [pool.submit(check_url, u, g) for u, g in by_url.items()]
        for f in as_completed(futs):
            f.result()
            done += 1
            if done % 100 == 0:
                print(f"  ... {done}/{len(by_url)} sources checked")
    flag_conflicts(rows)
    for r in rows:
        r["used"] = r["check"] == "passed" and not r["conflict"]
        r.setdefault("spot_check", None)
    return rows


def main():
    ap = argparse.ArgumentParser(description="Verify candidate evidence; write used evidence.")
    ap.add_argument("--input", nargs="*", help="candidate files (glob, relative to repo root); default all shards")
    ap.add_argument("--plant", action="store_true", help="add two deliberately wrong rows and check they're rejected")
    ap.add_argument("--limit", type=int, help="only the first N candidates (for a quick check)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--verbose", action="store_true", help="print every decision, not just a sample")
    ap.add_argument("--defer-wayback", action="store_true",
                    help="archive.org unreachable: check Wayback rows only against pages already fetched today")
    a = ap.parse_args()

    t0 = time.time()
    rows = load_candidates(a.input or [])
    if a.limit:
        rows = rows[:a.limit]
    planted = plant(rows) if a.plant else []
    print(f"verifying {len(rows)} candidate rows" + (f" + {len(planted)} planted wrong rows" if planted else ""))
    verify(rows + planted, a.workers, date.today(), a.defer_wayback)

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    VERIFY_DIR.mkdir(parents=True, exist_ok=True)
    log_rows, lines = [], []
    for r in rows + planted:
        decision = "ACCEPT" if r["used"] else "REJECT"
        why = r["check"] if r["check"] != "passed" else ("conflict between sources" if r["conflict"] else r["_match"])
        value = json.dumps(r["value"]) if isinstance(r["value"], (dict, list)) else r["value"]
        line = f"{decision} {r['ticker']:6s} {r['field']:28s} {str(r['period']):10s} {str(value)[:40]:40s} {why}" + \
               (f" - {r['_detail']}" if r["_detail"] and not r["used"] else "") + (f"  [PLANTED: {r['_planted']}]" if r.get("_planted") else "")
        lines.append(line)
        log_rows.append({"decision": decision, "evidence_id": r["evidence_id"], "ticker": r["ticker"], "field": r["field"],
                         "period": r["period"], "value": value, "check": r["check"], "conflict": r["conflict"],
                         "match": r["_match"], "detail": r["_detail"], "source_url": r["source_url"],
                         "planted": r.get("_planted")})
    pd.DataFrame(log_rows).to_csv(VERIFY_DIR / f"verify_log_{stamp}.csv", index=False)
    (VERIFY_DIR / f"verify_log_{stamp}.txt").write_text("\n".join(lines), encoding="utf-8")

    out = [{k: r.get(k) for k in OUT_COLUMNS} for r in rows]   # planted rows are never written
    with open(VERIFY_DIR / "evidence.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    df = pd.DataFrame(out, columns=OUT_COLUMNS)
    df["value"] = df["value"].map(lambda v: json.dumps(v) if isinstance(v, (dict, list)) else v)
    df.to_csv(VERIFY_DIR / "evidence.csv", index=False)

    # ---- summary
    shown = lines if a.verbose else [l for l in lines if l.startswith("ACCEPT")][:8] + [l for l in lines if l.startswith("REJECT")][:12]
    print("\n".join(shown))
    checks = Counter(r["check"] for r in rows)
    print(f"\n=== verifier: {len(rows)} rows in {time.time() - t0:.0f}s ===")
    print(f"  used {sum(r['used'] for r in rows)}   " + "   ".join(f"{k} {v}" for k, v in checks.most_common()) +
          f"   conflicts {sum(r['conflict'] for r in rows)}")
    print("  pass rate by field:")
    for field in sorted({r["field"] for r in rows}):
        g = [r for r in rows if r["field"] == field]
        print(f"    {field:30s} {sum(r['used'] for r in g):5d}/{len(g):<5d} used")
    if planted:
        ok = all(not r["used"] for r in planted)
        for r in planted:
            print(f"  planted ({r['_planted']}): {'REJECTED' if not r['used'] else 'ACCEPTED'} as {r['check']}")
        print("  PLANTED TEST " + ("PASSED: both wrong rows rejected" if ok else "FAILED: a wrong row was accepted"))
    print(f"  output: {VERIFY_DIR / 'evidence.jsonl'}  log: {VERIFY_DIR / f'verify_log_{stamp}.txt'}")


if __name__ == "__main__":
    main()
