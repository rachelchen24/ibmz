"""Mock RealRole public API for building the extension before the real API exists.

Serves the build plan 2.6 contract on port 8000 with placeholder scores: every company in our
300-company list gets the contract's example numbers with its own name, ticker and sector, and
model_version "mock". Unknown names get the "not in dataset" response. Also serves sample job
postings at /demo for trying the badge without a real job site.

Run from the repo root (standard library only; run as a script so no __pycache__ lands in
extension/, which Chrome refuses to load):

    py extension/dev/mock_api.py              # or: python3 extension/dev/mock_api.py
    py extension/dev/mock_api.py --force-p 0.8  # every company gets probability 0.8
"""

import argparse
import csv
import difflib
import html
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[2]
COMPANY_LIST = REPO / "data" / "collect" / "shard_assignment.csv"
FUZZY_CUTOFF = 0.90

# Build plan 2.3 normalize_company.
_DROP = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "the", "group", "holdings", "plc"}


def normalize_company(name):
    words = re.sub(r"[^\w\s]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _DROP)


def load_companies():
    with open(COMPANY_LIST, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {normalize_company(r["name"]): r for r in rows}


def resolve(name, companies):
    """Exact normalized match, then fuzzy >= FUZZY_CUTOFF. Returns (row, confidence) or (None, 0)."""
    norm = normalize_company(name)
    if not norm:
        return None, 0.0
    if norm in companies:
        return companies[norm], 1.0
    squashed = norm.replace(" ", "")
    best, best_ratio = None, 0.0
    for key, row in companies.items():
        ratio = max(
            difflib.SequenceMatcher(None, norm, key).ratio(),
            difflib.SequenceMatcher(None, squashed, key.replace(" ", "")).ratio(),
        )
        if ratio > best_ratio:
            best, best_ratio = row, ratio
    if best_ratio >= FUZZY_CUTOFF:
        return best, round(best_ratio, 2)
    return None, 0.0


def not_in_dataset():
    return {
        "company": None, "in_dataset": False, "probability": None, "range": None,
        "label": "Not in our dataset yet", "reasons": None, "summary": None, "sector": None,
        "employer_response": None, "refreshed_at": None, "score_version": None,
        "model_version": None, "latency_ms": None,
    }


def mock_evidence():
    return [{
        "evidence_id": "ev_mock",
        "source_url": None,
        "quote": "Placeholder: real sources appear once the scoring API is live.",
        "page_date": None,
    }]


def score_response(row, matched_from, confidence, force_p, started):
    # Contract example numbers (build plan 2.6), unless --force-p or ?p= overrides them.
    p = 0.41 if force_p is None else force_p
    lo, hi = max(0.0, p - 0.11), min(1.0, p + 0.12)
    sector = row["sector"]
    return {
        "company": {
            "ticker": row["ticker"], "name": row["name"], "matched_from": matched_from,
            "match_confidence": confidence, "sector": sector,
        },
        "in_dataset": True,
        "probability": round(p, 2),
        "range": [round(lo, 2), round(hi, 2)],
        "label": f"{round(p * 100)}% likely to hire from postings",
        # Sample reasons: same kinds as the contract example, without numbers, since these are
        # placeholders and must not read as real findings about a real company.
        "reasons": [
            {"text": "Sample reason: open postings per employee compared with the sector median",
             "direction": "lower", "evidence": mock_evidence()},
            {"text": "Sample reason: posting growth over the year compared with revenue growth",
             "direction": "lower", "evidence": mock_evidence()},
            {"text": "Sample reason: salary ranges listed in states that require them",
             "direction": "higher", "evidence": mock_evidence()},
        ],
        "summary": "Sample data: a plain-language summary will appear here once the scoring model is live.",
        "sector": {"name": sector, "median": 0.58, "percentile": 22},
        "employer_response": None,
        "refreshed_at": "2026-10-18T02:14:00Z",
        "score_version": f"{row['ticker']}-mock",
        "model_version": "mock",
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }


class Handler(BaseHTTPRequestHandler):
    companies = {}
    by_ticker = {}
    force_p = None

    # --- plumbing ---
    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else (
            json.dumps(body).encode() if content_type == "application/json" else body.encode())
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        # Method, path and status only: never request bodies.
        sys.stderr.write(f"{self.command} {urlparse(self.path).path} {args[1] if len(args) > 1 else ''}\n")

    def _force_p(self, query):
        if "p" in query:
            try:
                return min(1.0, max(0.0, float(query["p"][0])))
            except ValueError:
                pass
        return self.force_p

    # --- routes ---
    def do_POST(self):
        started = time.perf_counter()
        url = urlparse(self.path)
        if url.path != "/score":
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            name = str(body.get("company_name", "")).strip()
        except (ValueError, AttributeError):
            return self._send(400, {"error": "expected JSON {company_name, source}"})
        row, conf = resolve(name, self.companies)
        sys.stderr.write(f"  score: {name!r} -> {row['ticker'] if row else 'not in dataset'}\n")
        if not row:
            return self._send(200, not_in_dataset())
        self._send(200, score_response(row, name, conf, self._force_p(parse_qs(url.query)), started))

    def do_GET(self):
        started = time.perf_counter()
        url = urlparse(self.path)
        query = parse_qs(url.query)
        path = url.path.rstrip("/") or "/"

        if path == "/health":
            return self._send(200, {"ok": True, "model_version": "mock", "refreshed_at": "2026-10-18T02:14:00Z"})
        if path.startswith("/company/"):
            row = self.by_ticker.get(path.split("/", 2)[2].upper())
            if not row:
                return self._send(200, not_in_dataset())
            return self._send(200, score_response(row, row["name"], 1.0, self._force_p(query), started))
        if path == "/companies/search":
            q = normalize_company(query.get("q", [""])[0])
            hits = [r for k, r in self.companies.items() if q and (q in k or q.upper() == r["ticker"])][:10]
            p = self._force_p(query)
            return self._send(200, [{"ticker": r["ticker"], "name": r["name"],
                                     "probability": 0.41 if p is None else p} for r in hits])
        if path in ("/", "/demo"):
            return self._send(200, demo_index(self.by_ticker), "text/html")
        if path == "/demo/posting":
            company = query.get("company", ["Initech"])[0]
            title = query.get("title", ["Senior Data Engineer"])[0]
            with_title = query.get("anchor", ["1"])[0] != "0"
            return self._send(200, demo_posting(company, title, with_title), "text/html")
        self._send(404, {"error": "not found"})


# --- sample postings for trying the badge locally ---
DEMO_STYLE = """
body{margin:0;font:16px/1.6 Georgia,serif;color:#222;background:#fafafa}
.top{padding:14px 32px;background:#24405e;color:#fff;font:600 15px system-ui,sans-serif}
main{max-width:760px;margin:32px auto;padding:0 20px}
h1{font:700 30px/1.2 system-ui,sans-serif;margin:0 0 4px}
.loc{color:#666;font-family:system-ui,sans-serif;margin:0 0 20px}
ul{padding-left:20px} a{color:#24405e}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:20px 24px;margin:16px 0}
"""


def demo_index(by_ticker):
    picks = [t for t in ("MDB", "AAPL", "ALLY", "BKU") if t in by_ticker] or list(by_ticker)[:4]
    links = "".join(
        f'<li><a href="/demo/posting?company={quote(by_ticker[t]["name"])}">{html.escape(by_ticker[t]["name"])}</a>'
        f' <small>({t}, in our dataset)</small></li>' for t in picks)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>RealRole demo postings</title>
<style>{DEMO_STYLE}</style></head><body><div class="top">RealRole mock API · demo postings</div><main>
<h1>Sample job postings</h1><p class="loc">Load the extension, then open one of these.</p>
<div class="card"><ul>{links}
<li><a href="/demo/posting?company=Initech%20LLC">Initech LLC</a> <small>(not in our dataset: no badge should appear)</small></li>
<li><a href="/demo/posting?company={quote(by_ticker[picks[0]]["name"])}&amp;anchor=0">{html.escape(by_ticker[picks[0]]["name"])}, page with no job title</a>
 <small>(badge falls back to a floating pill)</small></li>
</ul></div>
<p class="loc">API: <a href="/health">/health</a> · <a href="/company/{picks[0]}">/company/{picks[0]}</a> ·
<a href="/companies/search?q=bank">/companies/search?q=bank</a></p></main></body></html>"""


def demo_posting(company, title, with_title):
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "JobPosting", "title": title,
        "hiringOrganization": {"@type": "Organization", "name": company},
        "jobLocation": {"@type": "Place", "address": {"addressLocality": "New York", "addressRegion": "NY"}},
        "datePosted": "2026-09-30",
    }).replace("</", "<\\/")
    heading = f"<h1>{html.escape(title)}</h1>" if with_title else f'<div class="loc"><b>{html.escape(title)}</b></div>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)} at {html.escape(company)}</title>
<script type="application/ld+json">{ld}</script><style>{DEMO_STYLE}</style></head><body>
<div class="top">{html.escape(company)} · Careers</div><main>
{heading}<p class="loc">New York, NY · Full-time</p>
<div class="card"><p>This is a sample posting served by the RealRole mock API for testing the extension.</p>
<ul><li>Build and maintain data pipelines</li><li>Work with analysts and product teams</li>
<li>3+ years of experience with Python and SQL</li></ul></div>
<p><a href="/demo">← All sample postings</a></p></main></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--force-p", type=float, default=None,
                    help="give every company this probability of a hire (0-1) to preview color bands")
    args = ap.parse_args()

    Handler.companies = load_companies()
    Handler.by_ticker = {r["ticker"]: r for r in Handler.companies.values()}
    Handler.force_p = args.force_p
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"RealRole mock API: {len(Handler.companies)} companies from {COMPANY_LIST.relative_to(REPO)}")
    print(f"Listening on http://localhost:{args.port}  (demo postings: http://localhost:{args.port}/demo)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
