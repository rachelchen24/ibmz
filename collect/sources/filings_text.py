"""Filings text: layoff events, hiring-freeze statements and management hiring statements.

Replaces the Claude agent for these schema fields (no Claude at run time). Reads the latest 10-K, recent 10-Qs,
and 8-Ks with their EX-99 exhibits (earnings releases, shareholder letters, call transcripts some companies file).
Earnings-call transcripts that are not filed with the SEC are not collected.
"""
import logging
from datetime import date, timedelta

from ..common import config
from ..common import textparse as tp
from ..common.output import make_evidence
from .edgar import Edgar

log = logging.getLogger(__name__)

_8K_ITEMS = {"2.05": "layoff", "2.02": "earnings", "7.01": "reg_fd", "8.01": "other"}


class FilingsText:
    def __init__(self, edgar: Edgar, today: date):
        self.edgar = edgar
        self.today = today

    def collect(self, company: dict, ctx: dict, run_id: str, emit) -> dict:
        cik, subs = ctx["cik"], ctx["submissions"]
        t = company["ticker"]
        stmt_cut = (self.today - timedelta(days=config.STATEMENT_LOOKBACK_DAYS)).isoformat()
        layoff_cut = (self.today - timedelta(days=config.LAYOFF_LOOKBACK_DAYS)).isoformat()

        docs = []   # (url, text, filing, is_item_205)
        tenk = next(iter(self.edgar.recent_filings(subs, {"10-K", "10-KT"})), None)
        if tenk and tenk["filingDate"] >= layoff_cut:
            url = self.edgar.doc_url(cik, tenk)
            docs.append((url, ctx.get("tenk_text") or self.edgar.fetch_text(url), tenk, False))
        for q in [f for f in self.edgar.recent_filings(subs, {"10-Q"}) if f["filingDate"] >= stmt_cut][:4]:
            url = self.edgar.doc_url(cik, q)
            docs.append((url, self.edgar.fetch_text(url), q, False))

        eightks = []
        for f in self.edgar.recent_filings(subs, {"8-K"}):
            items = set((f.get("items") or "").split(","))
            if "2.05" in items and f["filingDate"] >= layoff_cut:
                eightks.append((f, True))
            elif items & {"2.02", "7.01", "8.01"} and f["filingDate"] >= stmt_cut:
                eightks.append((f, False))
        for f, is_205 in eightks[:config.MAX_8K_PER_COMPANY]:
            if is_205:
                url = self.edgar.doc_url(cik, f)
                docs.append((url, self.edgar.fetch_text(url), f, True))
            for ex in self.edgar.exhibit_urls(cik, f)[:3]:
                docs.append((ex, self.edgar.fetch_text(ex), f, is_205))

        n = {"docs": len(docs), "layoff_events": 0, "hiring_freeze_statements": 0, "management_hiring_statements": 0}
        seen_layoff_filings = set()
        for url, text, f, is_205 in docs:
            fdate = f["filingDate"]
            for sent in tp.split_sentences(text):
                if fdate >= layoff_cut and f["accessionNumber"] not in seen_layoff_filings:
                    lay = tp.layoff_mention(sent, item_205=is_205)
                    if lay:
                        seen_layoff_filings.add(f["accessionNumber"])
                        event_date = lay["stated_date"] if lay["stated_date"] and lay["stated_date"] <= fdate else fdate
                        value = {"date": event_date, "workers": lay["workers"], "pct": lay["pct"],
                                 "source": f"{f['form']}{' item 2.05' if is_205 else ''}", "date_is_filing_date":
                                 event_date == fdate}
                        emit(make_evidence(t, "layoff_events", value, "workers", event_date, url, sent, fdate,
                                           "edgar", run_id))
                        n["layoff_events"] += 1
                if fdate < stmt_cut:
                    continue
                if tp.is_hiring_freeze(sent):
                    emit(make_evidence(t, "hiring_freeze_statements", True, None, fdate, url, sent, fdate,
                                       "edgar", run_id))
                    n["hiring_freeze_statements"] += 1
                tone = tp.hiring_tone(sent)
                if tone is not None:
                    emit(make_evidence(t, "management_hiring_statements", tone, "tone(-1..1)", fdate, url, sent,
                                       fdate, "edgar", run_id))
                    n["management_hiring_statements"] += 1
        return n
