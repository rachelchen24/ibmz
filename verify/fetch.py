"""Independent re-fetch of each source URL, and our own text extraction.

The verifier never reads the collection sandbox's cache or page copies: it fetches every source itself (its own
cache in data/verify/cache, one day at most) and extracts text with its own code.
"""
import html
import io
import re
from datetime import date
from pathlib import Path

import pandas as pd

from collect.common import config
from collect.common.http import Client, FetchError

VERIFY_DIR = config.DATA_DIR / "verify"
NY_WARN_LOCAL = config.NY_WARN_FILE   # the NY WARN dashboard is Tableau (JavaScript only); a person exported it


class Page:
    def __init__(self, url: str, ok: bool, text: str = "", rows: list[str] | None = None, reason: str = ""):
        self.url, self.ok, self.text, self.rows, self.reason = url, ok, text, rows or [], reason


_DROP = re.compile(r"<(script|style|head|ix:header|noscript)\b.*?</\1\s*>", re.I | re.S)


def extract_text(body: str) -> str:
    """HTML -> visible text; JSON and plain text are kept as they are."""
    head = body.lstrip()[:1]
    if head in "{[":
        return body
    body = _DROP.sub(" ", body)
    body = re.sub(r"<[^>]+>", " ", body)
    return html.unescape(body)


def _sheet_rows(content: bytes) -> list[str]:
    rows = []
    for _, df in pd.read_excel(io.BytesIO(content), sheet_name=None, header=None).items():
        for r in df.itertuples(index=False):
            rows.append(" | ".join(str(x) for x in r if not pd.isna(x)))
    return rows


class Fetcher:
    def __init__(self, today: date):
        self.client = Client(cache_dir=VERIFY_DIR / "cache")
        self.tag = today.isoformat()

    def get(self, url: str) -> Page:
        if not url or not url.startswith("http"):
            return Page(url, False, reason="no_url")
        if url.rstrip("/") == config.NY_WARN_URL.rstrip("/"):
            if not NY_WARN_LOCAL.exists():
                return Page(url, False, reason="NY WARN dashboard needs JavaScript and no local export exists")
            text = Path(NY_WARN_LOCAL).read_text(encoding="utf-8", errors="replace")
            return Page(url, True, text, text.splitlines(), reason="checked against the person-exported NY WARN CSV")
        if url.lower().endswith((".xlsx", ".xls")):
            dest = VERIFY_DIR / "files" / self.tag / re.sub(r"[^\w.-]", "_", url.split("://", 1)[1])
            if not self.client.download(url, dest):
                return Page(url, False, reason="spreadsheet download failed")
            try:
                rows = _sheet_rows(dest.read_bytes())
            except Exception as e:
                return Page(url, False, reason=f"spreadsheet unreadable: {e}")
            return Page(url, True, "\n".join(rows), rows)
        if url.lower().endswith(".pdf"):
            return Page(url, False, reason="PDF sources are not supported yet")
        try:
            r = self.client.fetch(url, cache_tag=self.tag)
        except FetchError as e:
            return Page(url, False, reason=str(e)[:200])
        if not r.ok:
            return Page(url, False, reason=f"HTTP {r.status}")
        text = extract_text(r.text)
        if len(text.strip()) < 20:
            return Page(url, False, reason="empty page (blocked or needs JavaScript)")
        return Page(url, True, text)
