"""SEC EDGAR: CIK, HQ country, revenue (XBRL), employee counts (10-K text), company website.

Fills the collection-schema fields employee_count (latest and prior FY, US where reported), revenue (latest and
prior FY), hq_country and reports_us_headcount, each as a candidate evidence row with a source URL and a quote
that appears verbatim on that URL.
"""
import logging
import re
from datetime import date

from ..common import textparse as tp
from ..common.http import Client
from ..common.output import make_evidence

log = logging.getLogger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{doc}"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{acc_dash}-index.htm"

REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "RevenuesNetOfInterestExpense",
                "SalesRevenueServicesNet", "TotalRevenuesAndOtherIncome"]
BANK_COMPONENTS = ["InterestIncomeExpenseNet", "NoninterestIncome"]


class Edgar:
    def __init__(self, client: Client, today: date):
        self.client = client
        self.today = today
        self._tickers = None

    # -- lookups shared with the filings-text collector

    def cik_for(self, company: dict) -> str | None:
        if company.get("cik"):
            return company["cik"]
        if self._tickers is None:
            r = self.client.fetch(TICKERS_URL, cache_tag=self.today.isoformat())
            self._tickers = {v["ticker"].upper().replace("-", "."): str(v["cik_str"]).zfill(10)
                             for v in r.json().values()}
        return self._tickers.get(company["ticker"].replace("-", "."))

    def submissions(self, cik: str) -> tuple[dict, str]:
        url = SUBMISSIONS_URL.format(cik=cik)
        r = self.client.fetch(url, cache_tag=self.today.isoformat())
        return (r.json() if r.ok else {}), r.text

    def recent_filings(self, subs: dict, forms: set[str]) -> list[dict]:
        rec = subs.get("filings", {}).get("recent", {})
        out = []
        for i, form in enumerate(rec.get("form", [])):
            if form in forms:
                out.append({k: rec[k][i] for k in ("accessionNumber", "filingDate", "reportDate", "form", "items",
                                                   "primaryDocument")})
        return out   # newest first, as SEC lists them

    def doc_url(self, cik: str, f: dict, doc: str | None = None) -> str:
        return DOC_URL.format(cik_int=int(cik), acc=f["accessionNumber"].replace("-", ""),
                              doc=doc or f["primaryDocument"])

    def fetch_text(self, url: str) -> str:
        r = self.client.fetch(url)
        return tp.html_to_text(r.text) if r.ok else ""

    def exhibit_urls(self, cik: str, f: dict, prefix: str = "EX-99") -> list[str]:
        """Exhibit documents of a filing (e.g. EX-99.1 press releases), from the filing index page."""
        acc = f["accessionNumber"]
        url = INDEX_URL.format(cik_int=int(cik), acc=acc.replace("-", ""), acc_dash=acc)
        r = self.client.fetch(url)
        if not r.ok:
            return []
        out = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S | re.I):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
            if len(cells) < 4:
                continue
            doc_type = tp.html_to_text(cells[3]).upper()
            href = re.search(r'href="([^"]+)"', cells[2])
            if href and doc_type.startswith(prefix):
                path = href.group(1).replace("/ix?doc=", "")
                if path.lower().endswith((".htm", ".html", ".txt")):
                    out.append("https://www.sec.gov" + path if path.startswith("/") else path)
        return out

    # -- the collector

    def collect(self, company: dict, run_id: str, emit) -> dict:
        """Emit evidence rows; return context for the other collectors (cik, submissions, website, 10-K text)."""
        t = company["ticker"]
        cik = self.cik_for(company)
        if not cik:
            raise LookupError("no CIK")
        subs, subs_raw = self.submissions(cik)
        ctx = {"cik": cik, "submissions": subs, "website": None, "tenk_text": ""}
        subs_url = SUBMISSIONS_URL.format(cik=cik)

        # hq_country
        biz = (subs.get("addresses") or {}).get("business") or {}
        soc = biz.get("stateOrCountry")
        if soc:
            us = soc in tp.US_STATES and not biz.get("isForeignLocation")
            quote = f'"stateOrCountry":"{soc}"'
            if quote in subs_raw:
                emit(make_evidence(t, "hq_country", "US" if us else (biz.get("stateOrCountryDescription") or soc),
                                   None, self.today.isoformat(), subs_url, quote, self.today.isoformat(), "edgar", run_id))

        self._revenue(company, cik, run_id, emit)

        # employee counts from the two latest 10-Ks
        tenks = [f for f in self.recent_filings(subs, {"10-K", "10-K/A", "10-KT"}) if f["form"] != "10-K/A"][:2]
        for i, f in enumerate(tenks):
            url = self.doc_url(cik, f)
            text = self.fetch_text(url)
            if i == 0:
                ctx["tenk_text"] = text
                ctx["website"] = subs.get("website") or tp.company_website(text)
            period = "FY" + (f.get("reportDate") or f["filingDate"])[:4]
            emp = tp.extract_employee_counts(text)
            if not emp:
                continue
            emit(make_evidence(t, "employee_count", emp["total"], "employees", period, url, emp["total_quote"],
                               f["filingDate"], "edgar", run_id))
            if emp["us"] is not None:
                emit(make_evidence(t, "employee_count_us", emp["us"], "employees", period, url, emp["us_quote"],
                                   f["filingDate"], "edgar", run_id))
            if i == 0:
                emit(make_evidence(t, "reports_us_headcount", emp["us"] is not None, None, period, url,
                                   emp["us_quote"] or emp["total_quote"], f["filingDate"], "edgar", run_id))
        return ctx

    def _revenue(self, company, cik, run_id, emit):
        url = FACTS_URL.format(cik=cik)
        r = self.client.fetch(url, cache_tag=self.today.isoformat())
        if not r.ok:
            return
        facts = r.json().get("facts", {})
        gaap = facts.get("us-gaap", {})

        # dei:EntityNumberOfEmployees, when a company tags it
        units = facts.get("dei", {}).get("EntityNumberOfEmployees", {}).get("units", {})
        for fact in [f for vals in units.values() for f in vals][-1:]:
            quote = self._raw_object(r.text, fact)
            if quote:
                emit(make_evidence(company["ticker"], "employee_count", int(fact["val"]), "employees",
                                   "FY" + str(fact.get("fy") or fact["end"][:4]), url, quote, fact.get("filed"),
                                   "edgar", run_id))

        best = None
        for tag in REVENUE_TAGS:
            annual = self._annual(gaap.get(tag))
            if annual and (best is None or annual[-1]["end"] > best[1][-1]["end"]):
                best = (tag, annual)
        if best:
            for fact in best[1][-2:]:
                quote = self._raw_object(r.text, fact)
                if quote:
                    emit(make_evidence(company["ticker"], "revenue", fact["val"], "USD", "FY" + fact["end"][:4], url,
                                       quote, fact.get("filed"), "edgar", run_id))
            return
        # banks: revenue = net interest income + noninterest income (summed in features)
        for tag in BANK_COMPONENTS:
            for fact in (self._annual(gaap.get(tag)) or [])[-2:]:
                quote = self._raw_object(r.text, fact)
                if quote:
                    emit(make_evidence(company["ticker"], "revenue_component", {"tag": tag, "val": fact["val"]}, "USD",
                                       "FY" + fact["end"][:4], url, quote, fact.get("filed"), "edgar", run_id))

    @staticmethod
    def _annual(concept: dict | None) -> list[dict] | None:
        """Full-year 10-K values by period end (latest filing wins for restatements), oldest first."""
        if not concept:
            return None
        by_end = {}
        for f in concept.get("units", {}).get("USD", []):
            if not f.get("start") or not str(f.get("form", "")).startswith("10-K"):
                continue
            days = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
            if 330 <= days <= 400 and (f["end"] not in by_end or f.get("filed", "") > by_end[f["end"]].get("filed", "")):
                by_end[f["end"]] = f
        return [by_end[k] for k in sorted(by_end)] or None

    @staticmethod
    def _raw_object(raw: str, fact: dict) -> str | None:
        """The fact's JSON object exactly as it appears in the companyfacts response (the verifiable quote)."""
        pat = (r'\{[^{}]*"end":"' + re.escape(fact["end"]) + r'"[^{}]*"val":' + re.escape(str(fact["val"])) +
               r'[^{}]*"accn":"' + re.escape(fact.get("accn", "")) + r'"[^{}]*\}')
        m = re.search(pat, raw)
        return m.group(0) if m else None
