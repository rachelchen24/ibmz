"""RealRole lookup website: paste a job link, get the company's analysis.

Serves the page on port 8501 and one endpoint, POST /resolve {url} -> {company_name, source, method},
that works out which company a job link belongs to. The page then asks the public API's /score for
that company, exactly like the extension does.

How a link is resolved, cheapest and most private first:
  1. From the URL alone: Greenhouse / Lever / Workday board IDs matched against the boards our
     collectors recorded (data/collect/shard_*/ats_summary_*.csv), a company careers-site host, or
     the "<title>-at-<company>-<id>" part of a LinkedIn job URL.
  2. Only if that fails: fetch the page and read its JobPosting JSON-LD (hiringOrganization.name),
     or ask the Greenhouse board API for the board's name. LinkedIn, Indeed and Glassdoor pages are
     never fetched (project rule). Private and local addresses are never fetched.
URLs are never logged.

Run from the repo root (standard library only):  py lookup/app.py   (or python3)
"""

import argparse
import csv
import ipaddress
import json
import re
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
EXTENSION = REPO / "extension"
SHARED = {"config.js", "format.js", "report.js", "report.css"}  # served from extension/ at /shared/

NEVER_FETCH = ("linkedin.com", "indeed.com", "glassdoor.com")
ATS_HOSTS = ("greenhouse.io", "lever.co", "myworkdayjobs.com")
FETCH_TIMEOUT = 8
FETCH_MAX_BYTES = 3_000_000
USER_AGENT = "RealRole-lookup/0.1 (IBM Z Datathon 2026 project)"
LOCALE = re.compile(r"^[a-z]{2}(-[A-Za-z]{2})?$")


# --- board index -------------------------------------------------------------------------------

def load_board_index():
    """{"greenhouse:<token>" | "lever:<slug>" | "workday:<host>/<site>" | "workday:<host>" | "host:<h>": name}"""
    index = {}
    for path in sorted(REPO.glob("data/collect/shard_*/ats_summary_*.csv")):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row.get("name", "").strip()
                ats = (row.get("ats") or "").strip().lower()
                if not name:
                    continue
                if ats:
                    index[ats] = name
                    if ats.startswith("workday:"):
                        index[ats.split("/")[0]] = name  # host only, for links to another site name
                host = urlparse(row.get("careers_url") or "").hostname
                if host and not host.endswith(ATS_HOSTS):
                    index["host:" + host.lower().removeprefix("www.")] = name
    return index


# --- resolving a link --------------------------------------------------------------------------

def from_url(url, index):
    """Company name from the URL alone, or None. Returns (name, source, method)."""
    host = (url.hostname or "").lower().removeprefix("www.")
    parts = [p for p in url.path.split("/") if p]
    query = parse_qs(url.query)

    if host.endswith("greenhouse.io"):
        token = (query.get("for") or [None])[0] if parts[:1] == ["embed"] else (parts[0] if parts else None)
        if token and (name := index.get(f"greenhouse:{token.lower()}")):
            return name, "greenhouse", "greenhouse board"
    if host.endswith("lever.co") and parts:
        if name := index.get(f"lever:{parts[0].lower()}"):
            return name, "lever", "lever board"
    if host.endswith("myworkdayjobs.com"):
        rest = [p for p in parts if not LOCALE.match(p)]
        site = rest[0].lower() if rest else ""
        name = index.get(f"workday:{host}/{site}") or index.get(f"workday:{host}")
        if name:
            return name, "workday", "workday site"
    if host.endswith("linkedin.com"):
        slug = next((p for p in reversed(parts) if "-at-" in p), None)
        m = re.search(r"-at-(.+?)(?:-\d+)?$", unquote(slug or ""))
        if m:
            return m.group(1).replace("-", " ").strip(), "linkedin", "linkedin link"
        return None
    if name := index.get("host:" + host):
        return name, "careers_site", "careers site"
    return None


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


def org_from_jsonld(html):
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        if name := _find_org(data, 0):
            return name
    return None


def _find_org(node, depth):
    if depth > 6:
        return None
    if isinstance(node, list):
        return next((n for n in (_find_org(x, depth + 1) for x in node) if n), None)
    if not isinstance(node, dict):
        return None
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    if "JobPosting" in types and node.get("hiringOrganization"):
        org = node["hiringOrganization"]
        org = org[0] if isinstance(org, list) and org else org
        name = org if isinstance(org, str) else (org.get("name") if isinstance(org, dict) else None)
        if name and name.strip():
            return name.strip()
    for key in ("@graph", "mainEntity", "itemListElement"):
        if key in node and (n := _find_org(node[key], depth + 1)):
            return n
    return None


def by_fetching(url):
    """Company name by fetching the page (or the Greenhouse board API). Returns (name, source, method)."""
    host = (url.hostname or "").lower()
    if host.endswith(NEVER_FETCH) or not is_public_host(host):
        return None
    parts = [p for p in url.path.split("/") if p]
    source = next((s for s, h in (("greenhouse", "greenhouse.io"), ("lever", "lever.co"),
                                   ("workday", "myworkdayjobs.com")) if host.endswith(h)), "other")
    try:
        if source == "greenhouse" and parts and parts[0] != "embed":
            board = json.loads(fetch(f"https://boards-api.greenhouse.io/v1/boards/{parts[0]}"))
            if board.get("name"):
                return board["name"], source, "greenhouse board api"
        if name := org_from_jsonld(fetch(url.geturl())):
            return name, source, "job page"
    except (URLError, OSError, ValueError):
        return None
    return None


def resolve(raw, index):
    raw = (raw or "").strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    url = urlparse(raw)
    if url.scheme not in ("http", "https") or not url.hostname:
        return {"company_name": None, "message": "That doesn't look like a web link."}
    found = from_url(url, index) or by_fetching(url)
    if not found:
        host = url.hostname.lower()
        why = ("LinkedIn links only work when they include the company in the address."
               if host.endswith("linkedin.com") else "We couldn't read the company from that link.")
        return {"company_name": None, "message": why}
    name, source, method = found
    return {"company_name": name, "source": source, "method": method}


# --- server ------------------------------------------------------------------------------------

TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}


class Handler(BaseHTTPRequestHandler):
    index = {}

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
        self._send(200, resolve(str(body.get("url", "")), self.index))


def main():
    ap = argparse.ArgumentParser(description="RealRole lookup website")
    ap.add_argument("--port", type=int, default=8501)
    args = ap.parse_args()
    Handler.index = load_board_index()
    boards = sum(1 for k in Handler.index if not k.startswith("host:"))
    print(f"RealRole lookup: {boards} job-board IDs indexed")
    print(f"Open http://localhost:{args.port}  (scores come from the API in extension/config.js)")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
