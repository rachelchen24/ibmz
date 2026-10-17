"""Wayback Machine: monthly archived open-posting counts for a company's ATS board over the past ~13 months.

Each month's count is an `archived_open_postings` evidence row (source = the archived page). The jobs listed on
each archived board are also kept (wayback_postings_<run_id>.jsonl) as history for repost detection.
Workday boards are rendered by JavaScript and aren't archived with their jobs, so they are skipped.
"""
import json
import logging
import re
from datetime import date, timedelta

from ..common import config
from ..common import textparse as tp
from ..common.http import Client, FetchError
from ..common.output import make_evidence

log = logging.getLogger(__name__)

CDX = "https://web.archive.org/cdx/search/cdx?url={url}&output=json&from={frm}&fl=timestamp,original,statuscode" \
      "&filter=statuscode:200&collapse=timestamp:6"
SNAP = "https://web.archive.org/web/{ts}id_/{url}"


def _targets(ats: str) -> list[tuple[str, str]]:
    """(kind, archived URL) in order of preference: JSON APIs give exact lists."""
    kind, _, ref = ats.partition(":")
    if kind == "greenhouse":
        return [("gh_api", f"boards-api.greenhouse.io/v1/boards/{ref}/jobs"),
                ("gh_html", f"job-boards.greenhouse.io/{ref}"), ("gh_html", f"boards.greenhouse.io/{ref}")]
    if kind == "lever":
        return [("lever_api", f"api.lever.co/v0/postings/{ref}"), ("lever_html", f"jobs.lever.co/{ref}")]
    return []


def parse_snapshot(kind: str, body: str) -> tuple[list[dict], str | None] | None:
    """(jobs [{id, title, location}], quote) from an archived board; None when the page can't be counted."""
    if kind == "gh_api":
        try:
            d = json.loads(body)
        except ValueError:
            return None
        jobs = [{"id": str(j.get("id")), "title": j.get("title"), "location": (j.get("location") or {}).get("name")}
                for j in d.get("jobs", [])]
        m = re.search(r'"total"\s*:\s*\d+', body)
        quote = m.group(0) if m else (f'"title":"{jobs[0]["title"]}"' if jobs else None)
        return jobs, quote
    if kind == "lever_api":
        try:
            d = json.loads(body)
        except ValueError:
            return None
        if not isinstance(d, list):
            return None
        jobs = [{"id": j.get("id"), "title": j.get("text"), "location": (j.get("categories") or {}).get("location")}
                for j in d]
        return jobs, (f'"id":"{jobs[0]["id"]}"' if jobs else None)
    if kind == "gh_html":
        if re.search(r"[?&]page=2\b", body):     # paginated board: the page shows only part of the list
            return None
        jobs, seen = [], set()
        for m in re.finditer(r'<a[^>]+href="[^"]*/jobs/(\d+)[^"]*"[^>]*>(.*?)</a>', body, re.S | re.I):
            if m.group(1) in seen:
                continue
            seen.add(m.group(1))
            parts = [p for p in re.split(r"\s*\.\s+|\n", tp.html_to_text(m.group(2))) if p]
            jobs.append({"id": m.group(1), "title": parts[0] if parts else None,
                         "location": parts[1] if len(parts) > 1 else None})
        for j in jobs:      # old boards put the location in a sibling span
            if not j["location"]:
                m = re.search(r'/jobs/' + j["id"] + r'[^>]*>.*?</a>\s*<span class="location">(.*?)</span>', body, re.S)
                if m:
                    j["location"] = tp.html_to_text(m.group(1))
        if not jobs:     # an HTML layout we can't read is not evidence of zero postings
            return None
        return jobs, jobs[0]["title"]
    if kind == "lever_html":
        jobs = []
        for m in re.finditer(r'<div class="posting" data-qa-posting-id="([0-9a-f-]{36})"(.*?)</a>', body, re.S):
            title = re.search(r'<h5[^>]*>(.*?)</h5>', m.group(2), re.S)
            loc = re.search(r'sort-by-location[^>]*>(.*?)</span>', m.group(2), re.S)
            jobs.append({"id": m.group(1), "title": tp.html_to_text(title.group(1)) if title else None,
                         "location": tp.html_to_text(loc.group(1)) if loc else None})
        if not jobs:
            return None
        return jobs, jobs[0]["title"]
    return None


class Wayback:
    def __init__(self, client: Client, today: date):
        self.client = client
        self.today = today

    def collect(self, company: dict, ats: str | None, run_id: str, emit, emit_history) -> int:
        if not ats or not _targets(ats):
            raise LookupError("no archivable board (Workday or no ATS)")
        frm = (self.today - timedelta(days=config.WAYBACK_LOOKBACK_DAYS)).strftime("%Y%m%d")
        by_month: dict[str, tuple[str, str, str]] = {}
        for kind, url in _targets(ats):
            try:
                r = self.client.fetch(CDX.format(url=url, frm=frm), cache_tag=self.today.isoformat())
            except FetchError as e:
                log.debug("CDX failed %s: %s", url, e)
                continue
            if not r.ok or not r.text.strip():
                continue
            try:
                rows = json.loads(r.text)[1:]
            except ValueError:
                continue
            for ts, original, _ in rows:
                by_month.setdefault(ts[:6], (kind, ts, original))   # first target listed wins the month

        n = 0
        for month in sorted(by_month):
            kind, ts, original = by_month[month]
            src = SNAP.format(ts=ts, url=original)
            try:
                r = self.client.fetch(src)
            except FetchError as e:
                log.debug("snapshot failed %s: %s", src, e)
                continue
            parsed = parse_snapshot(kind, r.text) if r.ok else None
            if not parsed:
                continue
            jobs, quote = parsed
            if quote is None and jobs:
                continue
            snap_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            emit(make_evidence(company["ticker"], "archived_open_postings", len(jobs), "postings", snap_date, src,
                               quote or "[]", snap_date, "wayback", run_id))
            for j in jobs:
                emit_history({"ticker": company["ticker"], "ats": ats.split(":")[0], "ats_job_id": j["id"],
                              "title": j["title"], "location": j["location"], "seen": snap_date, "source_url": src})
            n += 1
        if not n:
            raise LookupError("no readable archived snapshots of the board in the past year")
        return n
