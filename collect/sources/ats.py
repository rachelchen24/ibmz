"""ATS boards: find each company's public Greenhouse / Lever / Workday board, then pull its open postings.

Detection (when the company list has no `ats`): the careers page linked from the company's website is searched
for board links; then Greenhouse and Lever slugs are guessed from the name. Greenhouse guesses are accepted only
when the board's own name matches the company. Every detection is written to ats_detected.csv for a person to check.
"""
import html
import logging
import random
import re
from datetime import date
from difflib import SequenceMatcher

from ..common import config
from ..common import textparse as tp
from ..common.http import Client, FetchError
from ..common.ids import normalize_company, posting_id

log = logging.getLogger(__name__)

GH_BOARD = "https://boards-api.greenhouse.io/v1/boards/{t}"
GH_JOBS = "https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true"
LEVER_JOBS = "https://api.lever.co/v0/postings/{s}?mode=json"
WD_LIST = "https://{host}/wday/cxs/{tenant}/{site}/jobs"
WD_DETAIL = "https://{host}/wday/cxs/{tenant}/{site}{path}"

_GH_LINK = re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([A-Za-z0-9_-]+)"
                      r"|boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)|greenhouse\.io/embed/job_board/js\?for=([\w-]+)")
_LEVER_LINK = re.compile(r"jobs\.lever\.co/([A-Za-z0-9_.-]+)")
_WD_LINK = re.compile(r"https?://([a-z0-9-]+\.wd\d+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)")
_BAD_SLUGS = {"embed", "v1", "jobs", "job_board", "js", "api", "wday", "en-us", "login"}


def _names_match(a: str, b: str) -> bool:
    na, nb = normalize_company(a), normalize_company(b)
    if not na or not nb:
        return False
    return na == nb or na.startswith(nb + " ") or nb.startswith(na + " ") or SequenceMatcher(None, na, nb).ratio() >= 0.85


class Ats:
    def __init__(self, client: Client, snapshot: date, workday_max_details: int = config.WORKDAY_MAX_DETAILS):
        self.client = client
        self.snapshot = snapshot
        self.tag = snapshot.isoformat()
        self.workday_max_details = workday_max_details

    # ------------------------------------------------------------ detection

    def detect(self, company: dict, website: str | None) -> dict:
        """{"ats", "careers_url", "method"}; ats is None when no public board is found."""
        if company.get("ats") == "none":
            return {"ats": None, "careers_url": company.get("careers_url"), "method": "marked none (ats_overrides.csv)"}
        if company.get("ats"):
            return {"ats": company["ats"], "careers_url": company.get("careers_url"), "method": "company list / overrides"}
        pages = []
        if company.get("careers_url"):
            pages.append(company["careers_url"])
        if website:
            root = re.sub(r"^www\.", "", website.lower())
            pages += [f"https://www.{root}/careers", f"https://careers.{root}", f"https://jobs.{root}",
                      f"https://www.{root}/jobs", f"https://www.{root}/en/careers", f"https://www.{root}/about/careers",
                      f"https://www.{root}"]
        for url in pages:
            found = self._scan_page(url, company)
            if found:
                return found
        found = self._guess_slugs(company)
        return found or {"ats": None, "careers_url": company.get("careers_url"), "method": "not_found"}

    def _scan_page(self, url: str, company: dict) -> dict | None:
        try:
            r = self.client.fetch(url, cache_tag=self.tag)
        except FetchError:
            return None
        if not r.ok:
            return None
        body = r.url + " " + r.text
        m = _WD_LINK.search(body)
        if m and m.group(2).lower() not in _BAD_SLUGS and m.group(1) not in config.WORKDAY_SKIP_HOSTS:
            return {"ats": f"workday:{m.group(1)}/{m.group(2)}", "careers_url": r.url, "method": f"link on {url}"}
        for m in _GH_LINK.finditer(body):
            token = next(g for g in m.groups() if g)
            if token.lower() not in _BAD_SLUGS and self._greenhouse_ok(token, company, strict=False):
                return {"ats": f"greenhouse:{token}", "careers_url": r.url, "method": f"link on {url}"}
        for m in _LEVER_LINK.finditer(body):
            slug = m.group(1).rstrip(".")
            if slug.lower() not in _BAD_SLUGS and self._lever_ok(slug):
                return {"ats": f"lever:{slug}", "careers_url": r.url, "method": f"link on {url}"}
        return None

    def _guess_slugs(self, company: dict) -> dict | None:
        n = normalize_company(company["name"])
        words = n.split()
        cands = [n.replace(" ", ""), n.replace(" ", "-")]
        if words and len(words[0]) >= 5:
            cands.append(words[0])
        gh_cands = cands + [company["ticker"].lower().replace(".", "")]
        for slug in dict.fromkeys(c for c in gh_cands if c):
            if self._greenhouse_ok(slug, company, strict=True):
                return {"ats": f"greenhouse:{slug}", "careers_url": f"https://job-boards.greenhouse.io/{slug}",
                        "method": "greenhouse slug guess (board name matched)"}
        # Lever has no board-name endpoint, so only the full-name slug is tried (review in ats_detected.csv).
        slug = n.replace(" ", "")
        if len(slug) >= 5 and self._lever_ok(slug):
            return {"ats": f"lever:{slug}", "careers_url": f"https://jobs.lever.co/{slug}",
                    "method": "lever slug guess (review)"}
        return None

    def _greenhouse_ok(self, token: str, company: dict, strict: bool) -> bool:
        try:
            r = self.client.fetch(GH_BOARD.format(t=token), cache_tag=self.tag)
        except FetchError:
            return False
        if not r.ok:
            return False
        try:
            board_name = r.json().get("name") or ""
        except ValueError:
            return False
        return (not strict) or any(_names_match(board_name, a) for a in company["aliases"])

    def _lever_ok(self, slug: str) -> bool:
        try:
            r = self.client.fetch(LEVER_JOBS.format(s=slug) + "&limit=1", cache_tag=self.tag)
        except FetchError:
            return False
        return r.ok and r.text.strip().startswith("[")

    # ------------------------------------------------------------ postings

    def fetch_postings(self, company: dict, ats: str) -> tuple[list[dict], int]:
        """(posting rows with extras, total open count on the board)."""
        kind, _, ref = ats.partition(":")
        if kind == "greenhouse":
            return self._greenhouse(company, ref)
        if kind == "lever":
            return self._lever(company, ref)
        if kind == "workday":
            return self._workday(company, ref)
        raise ValueError(f"unsupported ats {ats}")

    def _row(self, company, ats_kind, job_id, url, title, location, posted, desc_html, desc_text, salary=None,
             deadline=None, extra=None) -> dict:
        text = desc_text if desc_text is not None else tp.html_to_text(desc_html or "")
        states = tp.parse_states(location)
        sal = salary or tp.parse_salary(text)
        stated_deadline, rolling = tp.parse_deadline(text)
        p = posted if isinstance(posted, date) else tp.parse_date(posted)
        row = {
            "posting_id": posting_id(ats_kind, job_id, url), "ticker": company["ticker"], "ats": ats_kind,
            "ats_job_id": str(job_id) if job_id not in (None, "") else None, "title": (title or "").strip(),
            "location": location, "state": states[0] if states else None, "country": tp.parse_country(location, states),
            "posted_date": p.isoformat() if p else None,
            "salary_min": round(sal[0]) if sal else None, "salary_max": round(sal[1]) if sal else None,
            "salary_listed": bool(sal) if text else None, "description": text or None,
            "first_seen": self.tag, "last_seen": self.tag, "snapshots": [self.tag], "repost_of": None,
            "soc_code": None, "job_zone": None,
        }
        dl = tp.parse_date(deadline) or stated_deadline
        row["_extra"] = {
            "posting_id": row["posting_id"], "ticker": company["ticker"], "snapshot": self.tag, "url": url,
            "states": states, "closing_date": dl.isoformat() if dl else None, "rolling_wording": rolling,
            "requirement_bullets": tp.requirement_bullets(desc_html), "word_count": tp.word_count(text),
            **(extra or {}),
        }
        return row

    def _greenhouse(self, company, token):
        r = self.client.fetch(GH_JOBS.format(t=token), cache_tag=self.tag)
        if not r.ok:
            raise LookupError(f"greenhouse board {token} returned {r.status}")
        jobs = r.json().get("jobs", [])
        rows = []
        for j in jobs:
            desc_html = html.unescape(j.get("content") or "")
            posted = j.get("first_published") or j.get("updated_at")
            rows.append(self._row(
                company, "greenhouse", j.get("id"), j.get("absolute_url"), j.get("title"),
                (j.get("location") or {}).get("name"), posted, desc_html, None,
                deadline=j.get("application_deadline"),
                extra={"posted_date_source": "first_published" if j.get("first_published") else "updated_at",
                       "departments": [d.get("name") for d in j.get("departments") or []]}))
        return rows, len(jobs)

    def _lever(self, company, slug):
        r = self.client.fetch(LEVER_JOBS.format(s=slug), cache_tag=self.tag)
        if not r.ok:
            raise LookupError(f"lever board {slug} returned {r.status}")
        jobs = r.json()
        rows = []
        for j in jobs:
            cats = j.get("categories") or {}
            locs = cats.get("allLocations") or ([cats["location"]] if cats.get("location") else [])
            lists_html = "".join(f"<h3>{l.get('text', '')}</h3><ul>{l.get('content', '')}</ul>" for l in j.get("lists") or [])
            desc_html = (j.get("description") or "") + lists_html + (j.get("additional") or "")
            sr = j.get("salaryRange") or {}
            salary = None
            if sr.get("min") and sr.get("currency", "USD") == "USD":
                mult = {"per-hour-wage": 2080, "per-month-salary": 12, "per-week-salary": 52}.get(sr.get("interval"), 1)
                salary = (sr["min"] * mult, (sr.get("max") or sr["min"]) * mult)
            rows.append(self._row(
                company, "lever", j.get("id"), j.get("hostedUrl"), j.get("text"), "; ".join(locs), j.get("createdAt"),
                desc_html, None, salary=salary,
                extra={"posted_date_source": "createdAt", "team": cats.get("team"),
                       "commitment": cats.get("commitment")}))
        return rows, len(jobs)

    def _workday(self, company, ref):
        host, _, site = ref.partition("/")
        if host in config.WORKDAY_SKIP_HOSTS:
            raise LookupError(f"workday host {host} is on the skip list")
        tenant = host.split(".")[0]
        list_url = WD_LIST.format(host=host, tenant=tenant, site=site)
        listing, total, offset = [], None, 0
        while True:
            r = self.client.fetch(list_url, method="POST", cache_tag=self.tag,
                                  json_body={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""})
            if not r.ok:
                raise LookupError(f"workday {ref} returned {r.status}")
            d = r.json()
            if total is None:
                total = d.get("total") or 0
            page = d.get("jobPostings") or []
            listing += page
            offset += 20
            if not page or offset >= total or offset >= 10000:
                break

        detail_idx = set(range(len(listing)))
        if self.workday_max_details and len(listing) > self.workday_max_details:
            detail_idx = set(random.Random(config.SEED).sample(range(len(listing)), self.workday_max_details))
        rows = []
        for i, j in enumerate(listing):
            path = j.get("externalPath") or ""
            url = f"https://{host}/en-US/{site}{path}" if path else None
            info = {}
            if i in detail_idx and path:
                try:
                    dr = self.client.fetch(WD_DETAIL.format(host=host, tenant=tenant, site=site, path=path),
                                           cache_tag=self.tag)
                    info = dr.json().get("jobPostingInfo", {}) if dr.ok else {}
                except (FetchError, ValueError) as e:
                    log.debug("workday detail failed %s: %s", path, e)
            locs = [info.get("location")] + list(info.get("additionalLocations") or []) if info else [j.get("locationsText")]
            job_id = info.get("jobReqId") or (j.get("bulletFields") or [None])[0] or None
            posted = info.get("startDate") or tp.workday_posted_on(j.get("postedOn"), self.snapshot)
            rows.append(self._row(
                company, "workday", job_id, url, info.get("title") or j.get("title"),
                "; ".join(x for x in locs if x), posted, info.get("jobDescription"), None if info else "",
                deadline=info.get("endDate"),
                extra={"posted_date_source": "startDate" if info.get("startDate") else "postedOn",
                       "detail_fetched": bool(info), "time_type": info.get("timeType")}))
        return rows, total or len(listing)


def split_extra(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    extras = [r.pop("_extra") for r in rows]
    return rows, extras
