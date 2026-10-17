"""Start scraper1..scraper4 in parallel on one machine (each in its own process, each on its own shard).

    python -m collect.run_all                      # all four full shards
    python -m collect.run_all --sample             # the 20 pilot companies (5 per shard)
    python -m collect.run_all --shards 1 3 -- --steps ats,wayback

Arguments after `--` are passed to every scraper. Each scraper's console output goes to
data/collect/shard_<N>/logs/console_<time>.log; this script prints one line as each one finishes.
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime

from .common import config


def main():
    argv = sys.argv[1:]
    extra = []
    if "--" in argv:
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description="Run scraper1..scraper4 in parallel.")
    ap.add_argument("--shards", type=int, nargs="*", default=list(range(1, config.N_SHARDS + 1)))
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args(argv)
    if a.sample:
        extra.append("--sample")

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    procs = {}
    for n in a.shards:
        logdir = config.shard_dir(n) / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        log = open(logdir / f"console_{stamp}.log", "w", encoding="utf-8")
        p = subprocess.Popen([sys.executable, "-m", f"collect.scraper{n}", *extra], cwd=config.ROOT,
                             stdout=log, stderr=subprocess.STDOUT)
        procs[n] = (p, log, time.time())
        print(f"scraper{n} started (pid {p.pid}), log: {log.name}")

    remaining = dict(procs)
    while remaining:
        for n, (p, log, t0) in list(remaining.items()):
            if p.poll() is not None:
                log.close()
                print(f"scraper{n} finished with exit code {p.returncode} after {time.time() - t0:.0f}s")
                del remaining[n]
        time.sleep(5)
    bad = [n for n, (p, _, _) in procs.items() if p.returncode]
    print("all scrapers finished" + (f"; failed: {bad} (see their console logs)" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
