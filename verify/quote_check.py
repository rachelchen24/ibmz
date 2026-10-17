"""Is the quote on the page, and does the value agree with the quote?

Quote match: exact after normalizing whitespace, quotes, dashes and case of HTML entities; then, for quotes of 30+
letters and digits, the same sequence of letters and digits (tolerates spacing differences at tag boundaries).
Value check, per field: the number must appear in the quote (or in the same spreadsheet row for WARN).
"""
import re

_TRANS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                        "\xa0": " ", "​": "", " ": " "})


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_TRANS)).strip()


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").translate(_TRANS).lower())


class PageIndex:
    """Normalized forms of one page, built once and reused for every quote from that page."""

    def __init__(self, text: str, rows: list[str] | None = None):
        self.norm = norm(text)
        self.alnum = alnum(text)
        self.rows = rows or []

    def find(self, quote: str) -> str | None:
        q = norm(quote)
        if not q:
            return None
        if q in self.norm:
            return "exact"
        aq = alnum(quote)
        if len(aq) >= 30 and aq in self.alnum:
            return "letters_digits"
        return None


def numbers_in(s: str) -> list[float]:
    out = []
    for m in re.finditer(r"(-?\d[\d,]*(?:\.\d+)?)\s*(thousand|million|billion)?", s or "", re.I):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        v *= {"thousand": 1e3, "million": 1e6, "billion": 1e9}.get((m.group(2) or "").lower(), 1)
        out.append(v)
    return out


def _has_number(value, text) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(n - v) <= max(0.5, abs(v) * 1e-9) for n in numbers_in(text))


_FREEZE = re.compile(r"freez|pause|suspend|halt|backfill", re.I)


def value_check(row: dict, page: PageIndex) -> tuple[str, str]:
    """('match' | 'mismatch' | 'not_checkable', detail)."""
    f, v, q = row["field"], row["value"], row["quote"]
    if f in ("revenue", "employee_count"):
        return ("match", "number in quote") if _has_number(v, q) else ("mismatch", f"{v} not in quote")
    if f == "employee_count_us":
        if _has_number(v, q):
            return "match", "number in quote"
        nums = numbers_in(q)   # derived: total minus non-US, or total x US share
        if any(abs(a - b - float(v)) <= 1 for a in nums for b in nums) or "%" in q:
            return "match", "derived from numbers in quote"
        return "mismatch", f"{v} not derivable from quote"
    if f == "revenue_component":
        return ("match", "number in quote") if _has_number((v or {}).get("val"), q) else ("mismatch", "val not in quote")
    if f == "hq_country":
        m = re.search(r'"stateOrCountry":"(\w+)"', q)
        if not m:
            return "not_checkable", "no state code in quote"
        from collect.common.textparse import US_STATES
        return ("match", "") if (v == "US") == (m.group(1) in US_STATES) else ("mismatch", "country vs state code")
    if f == "archived_open_postings":
        m = re.search(r'"total"\s*:\s*(\d+)', q)
        if m:
            return ("match", "total in quote") if int(m.group(1)) == int(v) else ("mismatch", "total differs")
        return "not_checkable", "count of listed jobs (quote shows the page is the board)"
    if f == "layoff_events":
        workers = (v or {}).get("workers")
        if row.get("collector") == "warn":
            same_row = [r for r in page.rows if norm(q) in norm(r)]
            if not same_row:
                return "mismatch", "company not found in any row"
            if workers is None or any(_has_number(workers, r) for r in same_row):
                return "match", "company and workers in the same row"
            return "mismatch", "workers not in the company's rows"
        if workers is not None:
            return ("match", "workers in quote") if _has_number(workers, q) else ("mismatch", "workers not in quote")
        return "not_checkable", "no worker count stated"
    if f == "hiring_freeze_statements":
        return ("match", "") if _FREEZE.search(q) else ("mismatch", "no freeze wording in quote")
    return "not_checkable", ""
