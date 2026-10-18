"""RealRole lookup website: paste a job link (or the listing's text), get its scam-risk check.

Serves the page on port 8501 and one endpoint, POST /resolve {url} -> {jobposting, source, method}, which reads
the listing behind a job link. The page then sends the listing to the RealRole API's POST /score, exactly like the
extension does, and asks POST /summary for the Granite summary.

How a link is read:
  - Greenhouse and Lever: their public job APIs (boards-api.greenhouse.io, api.lever.co), which return the listing.
  - Anything else (Workday, company careers sites): the page's own JobPosting JSON-LD.
  LinkedIn, Indeed and Glassdoor pages are never fetched (project rule): the page asks for the listing text
  instead. Private and local addresses are never fetched. URLs are never logged.

Run from the repo root (standard library only):  py lookup/app.py   (or python3)
"""

import argparse
import html
import ipaddress
import json
import re
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from api.jobposting import find_jobposting  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
EXTENSION = REPO / "extension"
SHARED = {"config.js", "format.js", "report.js", "report.css"}  # served from extension/ at /shared/

NEVER_FETCH = ("linkedin.com", "indeed.com", "glassdoor.com")
FETCH_TIMEOUT = 8
FETCH_MAX_BYTES = 3_000_000
USER_AGENT = "RealRole-lookup/0.2 (IBM Z Datathon 2026 project)"


# --- reading a listing ---------------------------------------------------------------------------

def is_public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def fetch(url):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    with urlopen(req, timeout=FETCH_TIMEOUT) as res:
        return res.read(FETCH_MAX_BYTES).decode("utf-8", errors="replace")


def jsonld_jobposting(page):
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            jp = find_jobposting(json.loads(block.strip()))
        except ValueError:
            continue
        if jp and (jp.get("title") or jp.get("description")):
            return jp
    return None


def greenhouse(parts):
    """boards.greenhouse.io/<board>/jobs/<id> or job-boards.greenhouse.io/<board>/jobs/<id>."""
    if len(parts) < 3 or parts[1] != "jobs" or not parts[2].isdigit():
        return None
    board, job_id = parts[0], parts[2]
    j = json.loads(fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"))
    try:
        company = json.loads(fetch(f"https://boards-api.greenhouse.io/v1/boards/{board}")).get("name")
    except (URLError, OSError, ValueError):
        company = j.get("company_name")
    return {"@type": "JobPosting", "title": j.get("title"), "description": html.unescape(j.get("content") or ""),
            "hiringOrganization": {"name": company or j.get("company_name") or board},
            "jobLocation": {"address": (j.get("location") or {}).get("name")}}


def lever(parts):
    """jobs.lever.co/<company>/<uuid>."""
    if len(parts) < 2:
        return None
    j = json.loads(fetch(f"https://api.lever.co/v0/postings/{parts[0]}/{parts[1]}?mode=json"))
    cats = j.get("categories") or {}
    lists = "".join(f"<h3>{x.get('text', '')}</h3><ul>{x.get('content', '')}</ul>" for x in j.get("lists") or [])
    sr = j.get("salaryRange") or {}
    jp = {"@type": "JobPosting", "title": j.get("text"),
          "description": (j.get("description") or "") + lists + (j.get("additional") or ""),
          "hiringOrganization": {"name": parts[0]}, "jobLocation": {"address": cats.get("location")},
          "employmentType": (cats.get("commitment") or "").upper().replace("-", "_") or None,
          "jobLocationType": "TELECOMMUTE" if j.get("workplaceType") == "remote" else None}
    if sr.get("min"):
        jp["baseSalary"] = {"value": {"minValue": sr["min"], "maxValue": sr.get("max") or sr["min"]}}
    return {k: v for k, v in jp.items() if v}


def resolve(raw):
    raw = (raw or "").strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    url = urlparse(raw)
    if url.scheme not in ("http", "https") or not url.hostname:
        return {"jobposting": None, "message": "That doesn't look like a web link."}
    host = url.hostname.lower()
    if host.endswith(NEVER_FETCH):
        return {"jobposting": None, "message": "We don't read LinkedIn, Indeed or Glassdoor pages. Paste the "
                                               "listing's text below instead."}
    if not is_public_host(host):
        return {"jobposting": None, "message": "That address isn't a public website."}
    parts = [p for p in url.path.split("/") if p]
    try:
        if host.endswith("greenhouse.io") and (jp := greenhouse(parts)):
            return {"jobposting": jp, "source": "greenhouse", "method": "Greenhouse job API"}
        if host == "jobs.lever.co" and (jp := lever(parts)):
            return {"jobposting": jp, "source": "lever", "method": "Lever job API"}
        if jp := jsonld_jobposting(fetch(url.geturl())):
            source = "workday" if host.endswith("myworkdayjobs.com") else "careers site"
            return {"jobposting": jp, "source": source, "method": "the page's job data"}
    except (URLError, OSError, ValueError):
        return {"jobposting": None, "message": "We couldn't open that link. Paste the listing's text below instead."}
    return {"jobposting": None, "message": "We couldn't find a job listing at that link. Paste its text below instead."}


# --- server ------------------------------------------------------------------------------------

TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        # Path only, never query strings or bodies (they can hold the pasted link).
        sys.stderr.write(f"{self.command} {urlparse(self.path).path} {args[1] if len(args) > 1 else ''}\n")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            file = STATIC / "index.html"
        elif path.startswith("/static/"):
            file = STATIC / path.removeprefix("/static/")
        elif path.startswith("/shared/") and path.removeprefix("/shared/") in SHARED:
            file = EXTENSION / path.removeprefix("/shared/")
        else:
            return self._send(404, {"error": "not found"})
        file = file.resolve()
        if not (file.is_relative_to(STATIC) or file.is_relative_to(EXTENSION)) or not file.is_file():
            return self._send(404, {"error": "not found"})
        self._send(200, file.read_bytes(), TYPES.get(file.suffix, "application/octet-stream"))

    def do_POST(self):
        if urlparse(self.path).path != "/resolve":
            return self._send(404, {"error": "not found"})
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 10_000)
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "expected JSON {url}"})
        self._send(200, resolve(str(body.get("url", ""))))


def main():
    ap = argparse.ArgumentParser(description="RealRole lookup website")
    ap.add_argument("--port", type=int, default=8501)
    args = ap.parse_args()
    print(f"Open http://localhost:{args.port}  (scores come from the API in extension/config.js)")
    class ExclusiveServer(ThreadingHTTPServer):
        allow_reuse_address = sys.platform != "win32"   # Windows would let two servers share the port silently
    try:
        server = ExclusiveServer(("127.0.0.1", args.port), Handler)
    except OSError:
        sys.exit(f"Port {args.port} is already in use: another lookup server is running. Stop it first.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
