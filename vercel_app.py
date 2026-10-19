"""Vercel entry point: the RealRole API (api/main.py) plus the lookup site's /resolve (lookup/app.py) as one function.

vercel.json routes /score, /summary, /health, /resolve and /demo* here (with ?route=<path>) and serves the lookup
page and its files statically. Granite is off: torch doesn't fit in a function, so summaries use the template.
Locally, keep using `py api/main.py` and `py lookup/app.py`; this file is only for Vercel.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

sys.dont_write_bytecode = True
os.environ.setdefault("RR_GRANITE", "off")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from api.main import Handler as ApiHandler, Scorer  # noqa: E402
from lookup.app import resolve  # noqa: E402

ApiHandler.scorer = Scorer(granite=False)   # loaded once per warm instance
ROUTES = ("/score", "/summary", "/health", "/resolve", "/demo", "/demo/posting", "/demo/jobposting")


class handler(ApiHandler):  # Vercel's Python runtime looks for a class named `handler`
    def _route(self):
        """Restore the public path: vercel.json passes it as ?route=..., or the runtime keeps the original path."""
        u = urlparse(self.path)
        q = parse_qs(u.query)
        route = "/" + q.pop("route", [""])[0].strip("/") if "route" in q else u.path
        if route not in ROUTES:
            route = u.path
        rest = urlencode({k: v[0] for k, v in q.items()})
        self.path = route + ("?" + rest if rest else "")

    def do_GET(self):
        self._route()
        super().do_GET()

    def do_POST(self):
        self._route()
        if urlparse(self.path).path != "/resolve":
            return super().do_POST()
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 10_000)
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, {"error": "expected JSON {url}"})
        self._send(200, resolve(str(body.get("url", ""))))
