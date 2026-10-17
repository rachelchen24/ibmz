"""Run every collector for one shard of the company list. scraper1..scraper4 call main(shard=N).

Per company: EDGAR (revenue, headcount, HQ) -> filings text (layoffs, hiring freeze, management tone) -> state WARN
notices -> ATS board (open postings) -> Wayback (12-month posting history). A step that fails or has nothing to
collect is recorded as skipped and the run continues. Features are built at the end (collect/features.py).
"""
import argparse
import json
import logging
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import pandas as pd

from .common import config
from .common import textparse as tp
from .common.companies import load_companies, select, write_assignment
from .common.http import Client
from .common.output import JsonlWriter, now_iso, read_jsonl, validate_evidence, validate_posting
from .sources.ats import Ats, split_extra
from .sources.edgar import Edgar
from .sources.filings_text import FilingsText
from .sources.warn import Warn
from .sources.wayback import Wayback

log = logging.getLogger("collect")
STEPS = ["edgar", "filings", "warn", "ats", "wayback"]


def _setup_logging(shard: int, run_id: str):
    logdir = config.shard_dir(shard) / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(f"%(asctime)s scraper{shard} %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(logdir / f"scraper{shard}_{run_id}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [fh, sh]
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def _git_commit() -> str | None:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=config.ROOT,
                             timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "collect"], capture_output=True, text=True,
                               cwd=config.ROOT, timeout=10).stdout.strip()
        return sha + ("+dirty" if dirty else "") if sha else None
    except (OSError, subprocess.SubprocessError):
        return None


def _drop_tickers(path, tickers: set[str]):
    """Remove rows for companies about to be re-collected, so a rerun replaces them instead of duplicating."""
    if not path.exists():
        return
    if path.suffix == ".csv":
        df = pd.read_csv(path, dtype=str)
        df[~df["ticker"].isin(tickers)].to_csv(path, index=False)
        return
    keep = [r for r in read_jsonl(path) if r.get("ticker") not in tickers]
    with open(path, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def _load_history(shard: int, snapshot: str) -> dict[str, dict[str, dict]]:
    """Postings from earlier snapshots of this shard: ticker -> posting_id -> latest row."""
    hist: dict[str, dict[str, dict]] = {}
    for p in sorted(config.shard_dir(shard).glob("postings_2*.jsonl")):
        snap = p.stem.split("_", 1)[1]
        if snap >= snapshot or ".rejected" in p.name:
            continue
        for r in read_jsonl(p):
            hist.setdefault(r["ticker"], {})[r["posting_id"]] = r
    return hist


def _apply_history(rows: list[dict], prior: dict[str, dict], snapshot: str):
    """first_seen / snapshots from earlier snapshots; repost_of when a vanished posting's role reappears."""
    current = {r["posting_id"] for r in rows}
    by_key: dict[str, list[dict]] = {}
    for old in prior.values():
        if old["posting_id"] not in current:
            by_key.setdefault(tp.norm_title(old["title"]) + "|" + tp.norm_location(old["location"]), []).append(old)
    for r in rows:
        old = prior.get(r["posting_id"])
        if old:
            r["first_seen"] = old.get("first_seen") or r["first_seen"]
            r["snapshots"] = sorted(set(old.get("snapshots") or []) | {snapshot})
            r["repost_of"] = old.get("repost_of")
            continue
        start = date.fromisoformat(r["posted_date"] or snapshot)
        for cand in by_key.get(tp.norm_title(r["title"]) + "|" + tp.norm_location(r["location"]), []):
            last = date.fromisoformat(cand.get("last_seen") or snapshot)
            if 0 <= (start - last).days <= config.REPOST_WINDOW_DAYS or last >= start:
                r["repost_of"] = cand["posting_id"]
                break


def main(shard: int, argv=None):
    ap = argparse.ArgumentParser(prog=f"python -m collect.scraper{shard}",
                                 description=f"Collect every available RealRole feature for shard {shard}.")
    ap.add_argument("--companies", default=str(config.COMPANY_LIST), help="company list CSV")
    ap.add_argument("--sample", action="store_true", help=f"only this shard's {config.PILOT_PER_SHARD} pilot companies")
    ap.add_argument("--tickers", nargs="*", help="only these tickers (e.g. a rerun list)")
    ap.add_argument("--limit", type=int, help="only the first N companies")
    ap.add_argument("--steps", default=",".join(STEPS), help=f"comma list from {STEPS}")
    ap.add_argument("--workers", type=int, default=4, help="companies processed at once (rate limits are shared)")
    ap.add_argument("--resume", metavar="RUN_ID", help="continue an interrupted run, skipping finished companies")
    ap.add_argument("--snapshot-date", help="postings snapshot date (default today)")
    ap.add_argument("--workday-max-details", type=int, default=config.WORKDAY_MAX_DETAILS)
    ap.add_argument("--no-features", action="store_true", help="skip building features at the end")
    args = ap.parse_args(argv)

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    unknown = set(steps) - set(STEPS)
    if unknown:
        ap.error(f"unknown steps {sorted(unknown)}")
    run_id = args.resume or f"s{shard}-{datetime.now():%Y%m%dT%H%M%S}"
    snapshot = args.snapshot_date or date.today().isoformat()
    today = date.today()
    out = config.shard_dir(shard)
    out.mkdir(parents=True, exist_ok=True)
    _setup_logging(shard, run_id)
    started = now_iso()
    t0 = time.time()

    all_companies = load_companies(args.companies)
    write_assignment(all_companies)
    companies = select(all_companies, shard, sample=args.sample, tickers=args.tickers, limit=args.limit)
    status_path = out / f"status_{run_id}.jsonl"
    done = {r["ticker"] for r in read_jsonl(status_path)} if args.resume else set()
    todo = [c for c in companies if c["ticker"] not in done]
    log.info("run %s: shard %d, %d companies (%d already done), steps %s, snapshot %s",
             run_id, shard, len(companies), len(done), steps, snapshot)

    postings_path = out / f"postings_{snapshot}.jsonl"
    extra_path = out / f"postings_extra_{snapshot}.jsonl"
    summary_path = out / f"ats_summary_{snapshot}.csv"
    if "ats" in steps:
        redo = {c["ticker"] for c in todo}
        for p in (postings_path, extra_path, summary_path):
            _drop_tickers(p, redo)

    client = Client()
    edgar = Edgar(client, today)
    filings = FilingsText(edgar, today)
    warn = Warn(client, today) if "warn" in steps else None
    ats = Ats(client, date.fromisoformat(snapshot), args.workday_max_details)
    wayback = Wayback(client, today)
    history = _load_history(shard, snapshot) if "ats" in steps else {}

    ev_writer = JsonlWriter(out / f"candidates_{run_id}.jsonl", validate_evidence)
    post_writer = JsonlWriter(postings_path, validate_posting)
    extra_writer = JsonlWriter(extra_path)
    hist_writer = JsonlWriter(out / f"wayback_postings_{run_id}.jsonl")
    status_writer = JsonlWriter(status_path)
    summary_lock = threading.Lock()
    counter = {"n": 0}

    def write_summary(row: dict):
        with summary_lock:
            pd.DataFrame([row]).to_csv(summary_path, mode="a", header=not summary_path.exists(), index=False)

    def run_ats(c, website):
        info = ats.detect(c, website)
        row = {"ticker": c["ticker"], "name": c["name"], "ats": info["ats"], "careers_url": info["careers_url"],
               "detection": info["method"], "open_count": None, "postings_written": 0, "status": "no public board found"}
        if info["ats"]:
            try:
                rows, total = ats.fetch_postings(c, info["ats"])
            except Exception:
                row["status"] = "board fetch failed"
                write_summary(row)
                raise
            rows = list({r["posting_id"]: r for r in rows}.values())
            _apply_history(rows, history.get(c["ticker"], {}), snapshot)
            rows, extras = split_extra(rows)
            for r, e in zip(rows, extras):
                if post_writer.write(r):
                    extra_writer.write(e)
                    row["postings_written"] += 1
            row["open_count"], row["status"] = total, "ok"
        write_summary(row)
        if not info["ats"]:
            raise LookupError("no public Greenhouse/Lever/Workday board found")
        return info

    def process(c):
        st, notes, ts = {}, {}, time.time()

        def step(name, fn):
            try:
                res = fn()
                st[name] = "ok"
                return res
            except Exception as e:   # skip, don't stop: the run must finish for every other company
                st[name] = f"skipped: {type(e).__name__}: {e}"[:300]
                log.debug("%s %s", c["ticker"], name, exc_info=True)
                return None

        ctx = None
        if steps_need_edgar:
            emit = ev_writer.write if "edgar" in steps else (lambda row: None)
            ctx = step("edgar", lambda: edgar.collect(c, run_id, emit))
            if "edgar" not in steps:
                st.pop("edgar", None)
        if "filings" in steps:
            if ctx:
                notes["filings"] = step("filings", lambda: filings.collect(c, ctx, run_id, ev_writer.write))
            else:
                st["filings"] = "skipped: no EDGAR filing list"
        if "warn" in steps:
            notes["warn"] = step("warn", lambda: warn.collect(c, run_id, ev_writer.write))
        info = None
        if "ats" in steps:
            info = step("ats", lambda: run_ats(c, (ctx or {}).get("website")))
        if "wayback" in steps:
            board = (info or {}).get("ats") or c.get("ats") or _known_ats.get(c["ticker"])
            notes["wayback"] = step("wayback", lambda: wayback.collect(c, board, run_id, ev_writer.write,
                                                                       hist_writer.write))
        status_writer.write({"ticker": c["ticker"], "run_id": run_id, "steps": st, "notes": notes,
                             "finished_at": now_iso(), "seconds": round(time.time() - ts, 1)})
        with summary_lock:
            counter["n"] += 1
            k = counter["n"]
        short = " ".join(f"{s}={'ok' if v == 'ok' else 'skip'}" for s, v in st.items())
        log.info("[%d/%d] %s %s (%.0fs)", k, len(todo), c["ticker"], short, time.time() - ts)
        return st

    steps_need_edgar = bool({"edgar", "filings", "ats"} & set(steps))
    _known_ats = {}
    if "wayback" in steps and "ats" not in steps and summary_path.exists():
        prev = pd.read_csv(summary_path, dtype=str).dropna(subset=["ats"])
        _known_ats = dict(zip(prev["ticker"], prev["ats"]))

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = {pool.submit(process, c): c["ticker"] for c in todo}
        for f in as_completed(futs):
            try:
                results[futs[f]] = f.result()
            except Exception as e:
                log.error("%s crashed: %s", futs[f], e)
                results[futs[f]] = {"pipeline": f"skipped: {e}"}
    for w in (ev_writer, post_writer, extra_writer, hist_writer, status_writer):
        w.close()

    # ---- summary and manifest
    all_status = {r["ticker"]: r["steps"] for r in read_jsonl(status_path)}
    ok_counts = Counter(s for st in all_status.values() for s, v in st.items() if v == "ok")
    failed = {s: sorted(t for t, st in all_status.items() if s in st and st[s] != "ok") for s in steps}
    ev_rows = read_jsonl(out / f"candidates_{run_id}.jsonl")
    by_field = Counter(r["field"] for r in ev_rows)
    manifest = {
        "shard": shard, "scraper": f"scraper{shard}", "run_id": run_id, "snapshot_date": snapshot,
        "tickers": [c["ticker"] for c in companies], "git_commit": _git_commit(),
        "prompt_version": config.PROMPT_VERSION, "started_at": started, "ended_at": now_iso(),
        "claude_cost_usd": 0.0, "steps": steps,
        "row_counts": {"evidence": len(ev_rows), "evidence_by_field": dict(by_field),
                       "evidence_rejected_by_validator": ev_writer.rejected,
                       "postings_this_run": post_writer.count, "wayback_history_rows": hist_writer.count},
        "steps_ok": dict(ok_counts), "failed": failed, "http": client.stats,
    }
    (out / f"manifest_{run_id}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n=== scraper{shard} {run_id}: {len(all_status)}/{len(companies)} companies in {time.time() - t0:.0f}s ===")
    for s in steps:
        print(f"  {s:8s} ok {ok_counts.get(s, 0):3d}   skipped {len(failed[s]):3d}")
    print(f"  evidence rows {len(ev_rows)} " + json.dumps(dict(by_field)))
    print(f"  postings rows {post_writer.count}   wayback history rows {hist_writer.count}")
    print(f"  output: {out}")

    if not args.no_features:
        from .features import build
        build(shard, snapshot, companies_path=args.companies)
