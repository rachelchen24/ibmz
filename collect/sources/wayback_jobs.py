"""Wayback Machine index of archived *job pages*: which job IDs existed on a company's board, and when.

The board front page is rarely archived, but individual job pages often are (people link to them). The CDX index
alone tells us each archived job URL and its first capture, without fetching any page. Each distinct job ID is a
posting observed to exist on that date. Works for Workday too, whose front pages aren't archived usefully.

Counts are a lower bound: a posting nobody archived is missed. One `archived_job_ids` evidence row per board URL
prefix (value = distinct job IDs found, source = the CDX query), plus one history row per job ID.
"""
import json
import logging
import re
from datetime import date, timedelta

from ..common import config
from ..common.http import Client, FetchError
from ..common.output import make_evidence

log = logging.getLogger(__name__)

CDX = ("https://web.archive.org/cdx/search/cdx?url={prefix}&matchType=prefix&from={frm}&output=json"
       "&fl=timestamp,original&filter=statuscode:200&collapse=urlkey&limit=50000")


def prefixes(ats: str) -> list[str]:
    kind, _, ref = ats.partition(":")
    if kind == "greenhouse":
        return [f"job-boards.greenhouse.io/{ref}/jobs/", f"boards.greenhouse.io/{ref}/jobs/"]
    if kind == "lever":
        return [f"jobs.lever.co/{ref}/"]
    if kind == "workday":
        host, _, site = ref.partition("/")
        return [f"{host}/{site}/job/", f"{host}/en-US/{site}/job/"]
    return []


def job_from_url(kind: str, url: str) -> dict | None:
    """{id, title, location} from an archived job URL; None for non-job pages (search, apply, assets)."""
    path = re.sub(r"[?#].*$", "", url)
    if kind == "greenhouse":
        m = re.search(r"/jobs/(\d{5,})", path)
        return {"id": m.group(1), "title": None, "location": None} if m else None
    if kind == "lever":
        m = re.search(r"jobs\.lever\.co/[^/]+/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", path)
        return {"id": m.group(1), "title": None, "location": None} if m else None
    if kind == "workday":
        m = re.search(r"/job/(?:([^/]+)/)?([^/]+)_([A-Za-z0-9][A-Za-z0-9-]*?)(?:-\d{1,2})?(?:/apply.*)?/?$", path)
        if not m:
            return None
        return {"id": m.group(3), "title": m.group(2).replace("-", " "),
                "location": m.group(1).replace("-", " ") if m.group(1) else None}
    return None


class WaybackJobs:
    def __init__(self, client: Client, today: date):
        self.client = client
        self.frm = (today - timedelta(days=config.WAYBACK_LOOKBACK_DAYS)).strftime("%Y%m%d")
        self.tag = today.isoformat()

    def collect(self, company: dict, ats: str | None, run_id: str, emit, emit_history) -> int:
        if not ats or not prefixes(ats):
            raise LookupError("no supported job board")
        kind = ats.split(":")[0]
        seen: dict[str, dict] = {}
        for prefix in prefixes(ats):
            url = CDX.format(prefix=prefix, frm=self.frm)
            try:
                r = self.client.fetch(url, cache_tag=self.tag)
            except FetchError as e:
                raise LookupError(f"Wayback index unavailable: {e}") from e
            if not r.ok or not r.text.strip().startswith("["):
                continue
            rows = json.loads(r.text)[1:]
            found = 0
            for ts, original in rows:
                job = job_from_url(kind, original)
                if not job:
                    continue
                d = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                cur = seen.get(job["id"])
                if cur is None or d < cur["seen"]:
                    seen[job["id"]] = {**job, "seen": d, "source_url": url, "line": f'["{ts}","{original}"]'}
                found += 1
            if found:
                first = min((v for v in seen.values() if v["source_url"] == url), key=lambda v: v["seen"])
                emit(make_evidence(company["ticker"], "archived_job_ids",
                                   len({k for k, v in seen.items() if v["source_url"] == url}), "job IDs",
                                   self.tag, url, first["line"], self.tag, "wayback", run_id))
        for job_id, v in seen.items():
            emit_history({"ticker": company["ticker"], "ats": kind, "ats_job_id": job_id, "title": v["title"],
                          "location": v["location"], "seen": v["seen"], "source_url": v["source_url"],
                          "kind": "job_page"})
        if not seen:
            raise LookupError("no archived job pages")
        return len(seen)
