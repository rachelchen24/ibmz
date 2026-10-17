"""IDs per build plan 2.3. Replace with common/ids.py once Workstream A ships it (task 0-5)."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

_SUFFIXES = {"inc", "llc", "ltd", "corp", "corporation", "co", "company", "the", "group", "holdings", "plc"}


def normalize_company(name: str | None) -> str:
    s = re.sub(r"[^\w\s]", "", (name or "").lower())
    return " ".join(w for w in s.split() if w not in _SUFFIXES)


def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, "", ""))


def posting_id(ats: str, ats_job_id=None, url: str | None = None) -> str:
    if ats_job_id not in (None, ""):
        return f"{ats}:{ats_job_id}"
    if not url:
        raise ValueError("posting_id needs ats_job_id or url")
    return f"{ats}:" + hashlib.sha256(canonical_url(url).encode()).hexdigest()[:16]


def evidence_id(ticker: str, field: str, period, source_url: str, quote: str) -> str:
    key = "\x1f".join(str(x) for x in (ticker, field, period, source_url, quote))
    return "ev_" + hashlib.sha256(key.encode()).hexdigest()[:16]
