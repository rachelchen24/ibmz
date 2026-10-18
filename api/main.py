"""RealRole public API: scam-risk score for one job listing (the extension, lookup site and demo all call this).

    py api/main.py                 # http://localhost:8000   (python3 elsewhere; standard library + ml/)
    py api/main.py --port 8000 --no-granite

Endpoints
  POST /score    {"jobposting": <schema.org JobPosting>, "source": "greenhouse"}   from a job page, or
                 {"posting": {<Kaggle columns>}}                                    structured fields
                 {"posting": {"title", "description"}, "pasted": true}             text pasted by a person
                 -> risk, band, label, reasons, template summary, unknown inputs   (~50 ms)
  POST /summary  {"risk", "flagged", "reasons"} (from /score) -> Granite one-sentence summary (~20 s on CPU)
  GET  /health   model, threshold, test metrics, Granite backend
  GET  /demo     sample job pages with JobPosting JSON-LD, to try the extension without a job site
  GET  /demo/jobposting?case=scam|real   the same samples as JSON (the lookup site's "try a sample")

Privacy: the request carries only the listing's public content. Nothing is stored, and request bodies are never
logged (log_message is silenced). A scam-risk score is an automated estimate, not proof of fraud.
"""
import argparse
import html
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.jobposting import company_name, find_jobposting, to_raw  # noqa: E402

MODEL_NAME = "lgbm"
# Fields job pages rarely give separately (they sit inside the description): when absent from a page they are
# left out of the score rather than counted as "missing", which in the training data signals scams.
NEUTRAL_IF_ABSENT_ON_PAGE = ("company_profile", "requirements", "benefits", "department", "function",
                             "required_experience")
# The model never saw a missing 0/1 flag in training and reads one as 0 ("no logo", "no questions"), which raises
# risk, so a flag we can't observe is left out of the score instead (its contribution set to the training average).
UNKNOWN_FLAGS = ("telecommuting", "has_company_logo", "has_questions")
DISCLAIMER = ("An automated estimate from the listing's text and details, trained on known scam postings. "
              "It is not proof of fraud: verify the employer through its official website.")
MAX_BODY = 512 * 1024


class Scorer:
    """The model, its explainer and metadata, loaded once."""

    def __init__(self, granite: bool = True):
        from ml.explain import Explainer
        from ml.run import load_bundle
        self.bundle = load_bundle(MODEL_NAME)
        self.explainer = Explainer.from_bundle(self.bundle)
        self.threshold = float(self.bundle["threshold"])
        self.lock = threading.Lock()
        if not granite:
            os.environ["RR_GRANITE"] = "off"
        metrics = ROOT / "ml" / "reports" / f"metrics_{MODEL_NAME}_test.json"
        self.test = json.loads(metrics.read_text(encoding="utf-8")) if metrics.exists() else None
        self.prevalence = 0.0485

    def band(self, p: float) -> tuple[str, str]:
        if p >= self.threshold:
            return "high", "High scam risk"
        if p >= self.prevalence:
            return "medium", "Some scam signals"
        return "low", "Low scam risk"

    def score(self, body: dict) -> dict:
        from ml.run import clean_postings
        t0 = time.perf_counter()
        if body.get("jobposting"):
            jp = find_jobposting(body["jobposting"]) or body["jobposting"]
            raw, unknown = to_raw(jp)
            neutral = [f for f in NEUTRAL_IF_ABSENT_ON_PAGE if f not in raw]
            neutral += [f for f in UNKNOWN_FLAGS if f not in raw]
            company = company_name(jp)
        elif body.get("posting"):
            raw = {k: v for k, v in body["posting"].items() if v not in (None, "")}
            unknown = [f for f in ("telecommuting", "has_company_logo", "has_questions") if f not in raw]
            company = body.get("company_name")
            # Pasted text is like a page: fields the person didn't paste separately are left out, not "missing".
            neutral = [f for f in NEUTRAL_IF_ABSENT_ON_PAGE if f not in raw] if body.get("pasted") else []
            neutral += [f for f in UNKNOWN_FLAGS if f not in raw]
        else:
            raise ValueError('send {"jobposting": {...}} or {"posting": {...}}')
        if not (raw.get("title") or raw.get("description")):
            raise ValueError("the listing needs at least a title or a description")
        rows = clean_postings([raw])
        with self.lock:
            p, reasons = self.explainer.score(rows, self.bundle["feature_cols"], neutral=neutral,
                                              threshold=self.threshold)
        risk = float(p[0])
        from ml.granite import backend, template_summary
        band, label = self.band(risk)
        flagged = risk >= self.threshold
        return {
            "listing": {"title": raw.get("title"), "company": company, "source": body.get("source")},
            "risk": round(risk, 4), "risk_pct": round(100 * risk), "flagged": flagged, "band": band,
            "label": f"{label} ({round(100 * risk)}%)",
            "reasons": reasons[0],
            "summary": template_summary(risk, flagged, reasons[0]), "summary_source": "template",
            "granite_backend": backend(),
            "left_out": neutral, "unknown_inputs": unknown,
            "threshold": round(self.threshold, 4), "model": self.model_info(), "disclaimer": DISCLAIMER,
            "latency_ms": round(1000 * (time.perf_counter() - t0), 1),
        }

    def model_info(self) -> dict:
        info = {"name": MODEL_NAME, "split_version": self.bundle.get("split_version"),
                "threshold_rule": self.bundle.get("threshold_source")}
        if self.test:
            info["test"] = {"pr_auc": self.test["ranking"]["pr_auc"]["value"],
                            "precision": self.test["at_threshold"]["precision"],
                            "recall": self.test["at_threshold"]["recall"]}
        return info


def summary(body: dict) -> dict:
    from ml.granite import summarize
    t0 = time.perf_counter()
    text, source = summarize(float(body["risk"]), bool(body["flagged"]), list(body.get("reasons") or []))
    return {"summary": text, "summary_source": source, "latency_ms": round(1000 * (time.perf_counter() - t0))}


DEMO = {
    "scam": {"title": "Data Entry Clerk - Work From Home",
             "description": "<p>Earn $500 weekly from home! No experience needed.</p><p>Send your bank details and a "
                            "copy of your ID to get started today. Limited spots!</p>",
             "hiringOrganization": {"@type": "Organization", "name": "Global Staffing Partners"},
             "employmentType": "PART_TIME", "jobLocationType": "TELECOMMUTE", "industry": "Oil & Energy",
             "baseSalary": {"@type": "MonetaryAmount", "value": {"minValue": 50000, "maxValue": 90000}},
             "jobLocation": {"@type": "Place", "address": {"addressCountry": "US", "addressRegion": "TX",
                                                           "addressLocality": "Houston"}}},
    "real": {"title": "Senior Software Engineer, Payments",
             "description": "<p>Join the Payments team to design and run our card processing services. You will "
                            "report to the Engineering Manager and work with product and risk teams.</p>"
                            "<ul><li>5+ years of backend experience</li><li>Python, Go, PostgreSQL, Kubernetes</li>"
                            "</ul><p>Our interview process has three rounds.</p>",
             "hiringOrganization": {"@type": "Organization", "name": "Acme Payments",
                                    "logo": "https://example.com/logo.png",
                                    "description": "Acme builds payment infrastructure for online businesses."},
             "employmentType": "FULL_TIME", "industry": "Internet",
             "educationRequirements": {"credentialCategory": "bachelor degree"},
             "jobBenefits": "Health, dental, 401(k), equity",
             "jobLocation": {"@type": "Place", "address": {"addressCountry": "US", "addressRegion": "CA",
                                                           "addressLocality": "San Francisco"}}},
}


def demo_page(case: str) -> str:
    jp = {"@context": "https://schema.org", "@type": "JobPosting", **DEMO[case]}
    org = jp["hiringOrganization"]["name"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(jp['title'])} at {html.escape(org)}</title>
<script type="application/ld+json">{json.dumps(jp)}</script>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}}</style></head>
<body><p><a href="/demo">&larr; Sample listings</a></p><h1>{html.escape(jp['title'])}</h1><p>{html.escape(org)}</p>
{jp['description']}</body></html>"""


class ExclusiveServer(ThreadingHTTPServer):
    """On Windows, SO_REUSEADDR lets a second server bind the same port and silently share requests with an old
    one. Refuse instead, so a stale server can't answer for the new one."""
    allow_reuse_address = sys.platform != "win32"


class Handler(BaseHTTPRequestHandler):
    scorer: Scorer = None

    def _send(self, status: int, body, content_type: str = "application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):   # never log request lines or bodies
        pass

    def do_OPTIONS(self):
        self._send(204, "")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            from ml.granite import backend
            return self._send(200, {"ok": True, "model": self.scorer.model_info(),
                                    "threshold": round(self.scorer.threshold, 4), "granite_backend": backend()})
        if u.path in ("/", "/demo"):
            links = "".join(f'<li><a href="/demo/posting?case={c}">{html.escape(DEMO[c]["title"])}</a></li>'
                            for c in DEMO)
            return self._send(200, f"<!doctype html><meta charset=utf-8><title>RealRole demo</title>"
                                   f"<h1>Sample listings</h1><ul>{links}</ul>", "text/html")
        if u.path == "/demo/jobposting":
            case = parse_qs(u.query).get("case", ["scam"])[0]
            return self._send(200, {"@context": "https://schema.org", "@type": "JobPosting",
                                    **DEMO[case if case in DEMO else "scam"]})
        if u.path == "/demo/posting":
            case = parse_qs(u.query).get("case", ["scam"])[0]
            return self._send(200, demo_page(case if case in DEMO else "scam"), "text/html")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"error": "listing too large"})
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/score":
                return self._send(200, self.scorer.score(body))
            if self.path == "/summary":
                return self._send(200, summary(body))
            self._send(404, {"error": "not found"})
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, {"error": str(e)})
        except Exception as e:   # report, but never echo the request
            self._send(500, {"error": f"{type(e).__name__}"})


def main():
    ap = argparse.ArgumentParser(description="RealRole scam-risk API")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-granite", action="store_true", help="template summaries only (no model download)")
    a = ap.parse_args()
    Handler.scorer = Scorer(granite=not a.no_granite)
    print(f"RealRole API on http://{a.host}:{a.port}  (demo listings: /demo; model {MODEL_NAME}, "
          f"threshold {Handler.scorer.threshold:.3f})", flush=True)
    try:
        server = ExclusiveServer((a.host, a.port), Handler)
    except OSError:
        sys.exit(f"Port {a.port} is already in use: another API (or the old mock) is running. Stop it first.")
    server.serve_forever()


if __name__ == "__main__":
    main()
