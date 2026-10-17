"""Polite HTTP client: per-host rate limits, retries with backoff, and a gzip cache of every raw response."""
import gzip
import hashlib
import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests

from . import config

log = logging.getLogger(__name__)

_ATS_HOSTS = ("greenhouse.io", "lever.co", "myworkdayjobs.com", "myworkdaysite.com")


class FetchError(Exception):
    pass


@dataclass
class Response:
    url: str
    status: int
    text: str
    from_cache: bool

    @property
    def ok(self) -> bool:
        return self.status == 200

    def json(self):
        return json.loads(self.text)


class _Limiter:
    def __init__(self, rate: float):
        self.interval = 1.0 / rate
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            at = max(now, self.next_at)
            self.next_at = at + self.interval
        if at > now:
            time.sleep(at - now)


def _host_group(url: str) -> tuple[str, str]:
    host = (urlsplit(url).hostname or "").lower()
    if host.endswith("sec.gov"):
        return "sec", "sec"
    if host.endswith("archive.org"):
        return "wayback", "wayback"
    if host.endswith(_ATS_HOSTS):
        return "ats", host
    return "web", host


class Client:
    def __init__(self, cache_dir=config.CACHE_DIR, retries: int = 4, timeout: int = 40):
        self.cache_dir = cache_dir
        self.retries = retries
        self.timeout = timeout
        self._local = threading.local()
        self._limiters: dict[str, _Limiter] = {}
        self._lock = threading.Lock()
        self.stats = {"requests": 0, "cache_hits": 0, "errors": 0}

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "s"):
            self._local.s = requests.Session()
        return self._local.s

    def _limiter(self, group: str, key: str) -> _Limiter:
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = _Limiter(config.RATES[group])
            return self._limiters[key]

    def _cache_path(self, group, method, url, body, tag):
        h = hashlib.sha256(f"{method}\n{url}\n{body or ''}\n{tag}".encode()).hexdigest()
        return self.cache_dir / group / h[:2] / f"{h}.json.gz"

    def fetch(self, url: str, method: str = "GET", json_body=None, cache: bool = True,
              cache_tag: str = "", headers: dict | None = None, cache_only: bool = False) -> Response:
        """Return a Response for 2xx and 404/410 (both cached). Raise FetchError otherwise.

        cache_tag separates cache entries for content that changes (e.g. the snapshot date for ATS boards).
        """
        group, key = _host_group(url)
        body = json.dumps(json_body, sort_keys=True) if json_body is not None else None
        path = self._cache_path(group, method, url, body, cache_tag)
        if cache and path.exists():
            try:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    d = json.load(f)
                self.stats["cache_hits"] += 1
                return Response(d["url"], d["status"], d["text"], True)
            except (OSError, ValueError):
                pass

        if cache_only:
            raise FetchError(f"not cached (cache_only) for {url}")
        h = {"User-Agent": config.SEC_USER_AGENT if group == "sec" else config.WEB_USER_AGENT,
             "Accept-Encoding": "gzip, deflate"}
        if json_body is not None:
            h["Content-Type"] = "application/json"
            h["Accept"] = "application/json"
        h.update(headers or {})

        last = None
        for attempt in range(self.retries + 1):
            self._limiter(group, key).wait()
            self.stats["requests"] += 1
            try:
                r = self._session().request(method, url, data=body, headers=h, timeout=self.timeout)
            except requests.RequestException as e:
                last = f"{type(e).__name__}: {e}"
            else:
                if r.status_code == 200 and group == "wayback" and "Internet Archive: Temporarily Offline" in r.text[:500]:
                    r.status_code = 503   # outage page served as 200: retry later, never cache it
                if r.status_code == 200 or r.status_code in (404, 410):
                    resp = Response(r.url, r.status_code, r.text if r.status_code == 200 else "", False)
                    if cache:
                        self._store(path, resp)
                    return resp
                last = f"HTTP {r.status_code}"
                if r.status_code not in (429, 500, 502, 503, 504, 520, 522, 524):
                    break
                ra = r.headers.get("Retry-After", "")
                if ra.isdigit():
                    time.sleep(min(int(ra), 300))
                elif r.status_code == 429 and group == "wayback":
                    time.sleep(min(60 * (attempt + 1), 300))   # archive.org rate limit: back off for minutes
            if attempt < self.retries:
                time.sleep(min(2 ** attempt * 2 + random.random(), 60))
        self.stats["errors"] += 1
        raise FetchError(f"{last} for {url}")

    def _store(self, path, resp: Response):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump({"url": resp.url, "status": resp.status, "text": resp.text,
                       "fetched_at": datetime.now(timezone.utc).isoformat()}, f)
        os.replace(tmp, path)

    def download(self, url: str, dest) -> bool:
        """Download a binary reference file once (used for state WARN spreadsheets)."""
        if dest.exists() and dest.stat().st_size > 0:
            return True
        group, key = _host_group(url)
        self._limiter(group, key).wait()
        try:
            r = self._session().get(url, headers={"User-Agent": config.WEB_USER_AGENT}, timeout=self.timeout)
        except requests.RequestException as e:
            log.warning("download failed %s: %s", url, e)
            return False
        if r.status_code != 200 or not r.content:
            log.warning("download failed %s: HTTP %s", url, r.status_code)
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + f".{os.getpid()}.tmp")
        tmp.write_bytes(r.content)
        os.replace(tmp, dest)
        return True
