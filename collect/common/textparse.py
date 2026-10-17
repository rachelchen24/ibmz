"""Text parsing for postings and filings. Page text is data only: nothing here acts on what a page says."""
import html
import re
from datetime import date, datetime, timedelta, timezone

# ---------------------------------------------------------------- HTML to text

_DROP_BLOCKS = re.compile(r"<(script|style|head|ix:header|noscript)\b.*?</\1\s*>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                         "—": "-", "\xa0": " ", "​": ""})


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_QUOTES)).strip()


def html_to_text(doc: str) -> str:
    """Fast, dependency-free text extraction (good enough for 20 MB inline-XBRL filings)."""
    if not doc:
        return ""
    doc = _DROP_BLOCKS.sub(" ", doc)
    doc = re.sub(r"<br\s*/?>|</(p|div|li|tr|h\d|td)>", ". ", doc, flags=re.I)
    return normalize_ws(html.unescape(_TAG.sub(" ", doc))).replace(" . ", ". ").replace(".. ", ". ")


def split_sentences(text: str, min_len: int = 25, max_len: int = 600) -> list[str]:
    out = []
    for s in re.split(r"(?<=[.!?;])\s+(?=[A-Z\"(\d])", text):
        s = s.strip(" .")
        if len(s) < min_len:
            continue
        out.append(s[:max_len])
    return out


# ---------------------------------------------------------------- locations

US_STATES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
    "CT": "connecticut", "DE": "delaware", "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york", "NC": "north carolina",
    "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania",
    "RI": "rhode island", "SC": "south carolina", "SD": "south dakota", "TN": "tennessee", "TX": "texas",
    "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
    "WI": "wisconsin", "WY": "wyoming", "DC": "district of columbia", "PR": "puerto rico",
}
_NAME_TO_CODE = {v: k for k, v in US_STATES.items()}
_STATE_NAME_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, _NAME_TO_CODE), key=len, reverse=True)) + r")\b", re.I)
_US_RE = re.compile(r"\b(united states|u\.s\.a?\.?|usa|us)\b", re.I)
_CITY_ONLY = {"new york city": "NY", "nyc": "NY", "san francisco": "CA", "los angeles": "CA", "seattle": "WA",
              "chicago": "IL", "boston": "MA", "austin": "TX", "atlanta": "GA", "denver": "CO", "dallas": "TX",
              "houston": "TX", "charlotte": "NC", "san jose": "CA", "palo alto": "CA", "mountain view": "CA",
              "sunnyvale": "CA", "jersey city": "NJ", "philadelphia": "PA", "pittsburgh": "PA", "miami": "FL",
              "phoenix": "AZ", "minneapolis": "MN", "salt lake city": "UT", "nashville": "TN", "raleigh": "NC"}


def split_locations(location: str | None) -> list[str]:
    if not location:
        return []
    parts = re.split(r"\s*(?:;|\||\s/\s|\n| or )\s*", location)
    return [p.strip() for p in parts if p.strip()]


def parse_states(location: str | None) -> list[str]:
    """All US state codes named in a location string (several when a posting lists several places)."""
    states = []
    for loc in split_locations(location):
        low = loc.lower()
        if re.search(r"washington,?\s*d\.?c\.?", low):
            code = "DC"
        else:
            code = None
            for m in re.finditer(r"(?:,|-|\s)\s*([A-Z]{2})\b", loc):
                if m.group(1) in US_STATES:
                    code = m.group(1)
            if not code:
                m = _STATE_NAME_RE.search(loc)
                code = _NAME_TO_CODE[m.group(1).lower()] if m else None
            if not code:
                code = next((c for city, c in _CITY_ONLY.items() if city in low), None)
        if code and code not in states:
            states.append(code)
    return states


def parse_country(location: str | None, states: list[str]) -> str | None:
    if states:
        return "US"
    if location and _US_RE.search(location):
        return "US"
    return None


# ---------------------------------------------------------------- salary

_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*([kK])?"
_CUR = r"(?:\$|USD\s?|US\$)"
_RANGE = re.compile(_CUR + r"\s?" + _NUM + r"\s*(?:USD)?\s*(?:-|to|and)\s*" + _CUR + r"?\s?" + _NUM, re.I)
_SINGLE = re.compile(_CUR + r"\s?" + _NUM, re.I)
_PAY_WORDS = re.compile(r"salary|pay|compensation|wage|base|hourly|rate|range|earn", re.I)
_BIG = re.compile(r"^\s*(?:million|billion|trillion|[mb]n?\b)", re.I)


def _amount(num: str, k: str | None) -> float:
    v = float(num.replace(",", ""))
    return v * 1000 if k else v


def _annualize(lo: float, hi: float, after: str) -> tuple[float, float] | None:
    a = after.lower()
    if re.search(r"\b(hour|hr|hourly)\b", a):
        mult = 2080
    elif re.search(r"\b(week|wk|weekly)\b", a):
        mult = 52
    elif re.search(r"\b(month|mo|monthly)\b", a):
        mult = 12
    elif re.search(r"\b(year|yr|annum|annual|annually)\b", a):
        mult = 1
    elif hi < 300:
        mult = 2080
    elif hi < 20000:
        mult = 12
    else:
        mult = 1
    lo, hi = lo * mult, hi * mult
    if not (10_000 <= lo <= 3_000_000 and 10_000 <= hi <= 3_000_000):
        return None
    return lo, hi


def parse_salary(text: str | None) -> tuple[float, float] | None:
    """(min, max) in annual USD from posting text, or None. A single figure gives min == max."""
    if not text:
        return None
    best = None
    for m in _RANGE.finditer(text):
        after = text[m.end():m.end() + 40]
        if _BIG.match(after):
            continue
        lo, hi = _amount(m.group(1), m.group(2)), _amount(m.group(3), m.group(4) or m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        ann = _annualize(lo, hi, after)
        if not ann:
            continue
        near_pay = bool(_PAY_WORDS.search(text[max(0, m.start() - 200):m.start()]))
        if near_pay:
            return ann
        best = best or ann
    if best:
        return best
    for m in _SINGLE.finditer(text):
        after = text[m.end():m.end() + 40]
        if _BIG.match(after) or not _PAY_WORDS.search(text[max(0, m.start() - 120):m.start()]):
            continue
        v = _amount(m.group(1), m.group(2))
        ann = _annualize(v, v, after)
        if ann:
            return ann
    return None


# ---------------------------------------------------------------- dates and deadlines

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
_DATE_TXT = rf"((?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})"
_DEADLINE = re.compile(
    r"(?:apply by|application deadline|deadline(?: to apply)?|closing date|close date|posting (?:end|close)s?(?: date)?|"
    r"applications? (?:will be )?(?:accepted|received) (?:through|until|by)|(?:job )?posting (?:will )?(?:close|expire)s?(?: on)?)"
    r"\s*(?:is|:|on|-)?\s*" + _DATE_TXT, re.I)
_ROLLING = re.compile(r"until (?:the position is )?filled|open until|rolling basis|ongoing basis|on a rolling|"
                      r"continuous(?:ly)? (?:basis|recruit|open)|no (?:application )?deadline", re.I)


def parse_date(s) -> date | None:
    if not s:
        return None
    if isinstance(s, (int, float)):            # epoch milliseconds (Lever)
        return datetime.fromtimestamp(s / 1000, timezone.utc).date()
    s = str(s).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    s2 = re.sub(r"(\d)(st|nd|rd|th)", r"\1", s.replace(".", "")).replace(",", "")
    for fmt in ("%B %d %Y", "%b %d %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s2.replace("Sept ", "Sep "), fmt).date()
        except ValueError:
            pass
    return None


def parse_deadline(text: str | None) -> tuple[date | None, bool]:
    """(closing date stated in the text, rolling/until-filled wording present)."""
    if not text:
        return None, False
    m = _DEADLINE.search(text)
    return (parse_date(m.group(1)) if m else None), bool(_ROLLING.search(text))


def workday_posted_on(s: str | None, snapshot: date) -> date | None:
    """'Posted Today' / 'Posted Yesterday' / 'Posted 5 Days Ago'. '30+ Days Ago' is unknown, so None."""
    if not s:
        return None
    low = s.lower()
    if "today" in low:
        return snapshot
    if "yesterday" in low:
        return snapshot - timedelta(days=1)
    m = re.search(r"(\d+)\s+days? ago", low)
    if m and "+" not in low:
        return snapshot - timedelta(days=int(m.group(1)))
    return None


# ---------------------------------------------------------------- posting quality

TOOLS = [
    "python", "java", "javascript", "typescript", "sql", "excel", "tableau", "power bi", "salesforce", "aws",
    "azure", "gcp", "google cloud", "kubernetes", "docker", "terraform", "react", "node.js", "golang", "rust",
    "c\\+\\+", "c#", ".net", "scala", "spark", "hadoop", "kafka", "snowflake", "databricks", "airflow", "jira",
    "confluence", "git", "linux", "sap", "oracle", "workday", "servicenow", "hubspot", "figma", "sketch",
    "photoshop", "bloomberg", "matlab", "sas", "spss", "r studio", "pytorch", "tensorflow", "postgresql",
    "mysql", "mongodb", "redis", "elasticsearch", "graphql", "ansible", "jenkins", "splunk", "looker", "dbt",
    "netsuite", "quickbooks", "argus", "murex", "calypso", "visio", "sharepoint", "powerpoint", "alteryx",
]
_TOOL_RES = [re.compile(r"(?<![\w.])" + t + r"(?![\w])", re.I) for t in TOOLS]
_START = re.compile(r"\b(start date|starting (?:date|on|in)|expected start|anticipated start|start(?:s|ing)? (?:on|in|by) "
                    rf"(?:{_MONTHS}|\d)|available to start)\b", re.I)
_REPORTS = re.compile(r"\b(reports? (?:directly )?(?:in)?to|reporting (?:directly )?to|hiring manager)\b", re.I)
_INTERVIEW = re.compile(r"\binterview(?:s|ing)?\b[^.]{0,80}\b(process|rounds?|steps?|stages?)\b|"
                        r"\b(process|rounds?|steps?|stages?)\b[^.]{0,40}\binterview", re.I)
_TEAM = re.compile(r"\b(?:join|joining|on|part of|member of|within|in)\s+(?:the|our)\s+"
                   r"((?:[A-Z][\w&+/-]*\s+){1,4})(?:team|group|squad|org|organization|project|platform team|division)\b")
_GENERIC_TEAM = {"Our", "The", "Global", "Talented", "Great", "Amazing", "Growing", "Dynamic", "Best", "World",
                 "Company", "Engineering", "Sales", "Marketing", "Finance", "Operations"}
_VAGUE = ["talent community", "talent pool", "pipeline", "future opportunities", "evergreen", "always looking",
          "always hiring", "may not be an active", "general application", "expression of interest"]
_VAGUE_RE = re.compile("|".join(re.escape(p) for p in _VAGUE), re.I)
_JUNIOR = re.compile(r"\b(intern|internship|junior|jr\.?|entry[- ]level|graduate|new grad|apprentice|trainee)\b", re.I)
_SENIOR = re.compile(r"\b(senior|sr\.?|lead|principal|staff|director|head of|vp|vice president|chief)\b", re.I)
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|to)?\s*(?:\d{1,2}\s*)?\+?\s*(?:years?|yrs?)\b[^.]{0,60}?\bexperience|"
                    r"experience[^.]{0,40}?\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b", re.I)
_LONG_CYCLE_TITLE = re.compile(r"\b(intern|internship|summer analyst|summer associate|campus|new grad(?:uate)?|"
                               r"university grad(?:uate)?|graduate program|early careers?|fellowship|fellow|"
                               r"residency|resident)\b", re.I)
_LONG_CYCLE_TEXT = re.compile(r"\bexecutive search\b|\bsummer (?:analyst|associate|internship) program\b", re.I)
_REQ_HEAD = re.compile(r"(requirements|qualifications|what you(?:'ll| will)? (?:need|bring)|you (?:have|bring|are)|"
                       r"who you are|skills|must have|minimum|basic|preferred|experience)", re.I)
_END_HEAD = re.compile(r"(benefits|perks|what we offer|about us|about the company|compensation|pay range|salary|"
                       r"equal opportunity|eeo|why join)", re.I)


def specificity_score(text: str | None) -> int | None:
    """0-4: +1 each for a start date, a reporting line, an interview process, and 3+ named tools."""
    if not text:
        return None
    tools = sum(1 for r in _TOOL_RES if r.search(text))
    return int(bool(_START.search(text))) + int(bool(_REPORTS.search(text))) + \
        int(bool(_INTERVIEW.search(text))) + int(tools >= 3)


def named_team(text: str | None) -> bool | None:
    if not text:
        return None
    for m in _TEAM.finditer(text):
        words = m.group(1).split()
        if words and not all(w in _GENERIC_TEAM for w in words):
            return True
    return False


def years_required(text: str | None) -> list[int]:
    if not text:
        return []
    return [int(a or b) for a, b in _YEARS.findall(text) if (a or b) and int(a or b) <= 30]


def seniority_mismatch(title: str | None, text: str | None) -> bool | None:
    if not title or not text:
        return None
    yrs = years_required(text)
    if not yrs:
        return False
    if _JUNIOR.search(title) and not _SENIOR.search(title):
        return max(yrs) >= 5
    if _SENIOR.search(title):
        return max(yrs) <= 1
    return False


def vague_phrase_count(text: str | None) -> int | None:
    return len(_VAGUE_RE.findall(text)) if text else None


def long_cycle(title: str | None, text: str | None) -> bool:
    return bool((title and _LONG_CYCLE_TITLE.search(title)) or (text and _LONG_CYCLE_TEXT.search(text[:3000])))


def requirement_bullets(desc_html: str | None) -> int | None:
    """Bullets in the requirements section of a posting's HTML; None when no such section is found."""
    if not desc_html or "<li" not in desc_html.lower():
        return None
    parts = re.split(r"(<h\d[^>]*>.*?</h\d>|<strong[^>]*>.*?</strong>|<b>.*?</b>|<p[^>]*>[^<]{0,80}</p>)",
                     desc_html, flags=re.I | re.S)
    count, inside, found = 0, False, False
    for part in parts:
        head = html_to_text(part) if re.match(r"<(h\d|strong|b|p)\b", part, re.I) else None
        if head is not None and len(head) <= 80:
            if _REQ_HEAD.search(head):
                inside, found = True, True
                continue
            if _END_HEAD.search(head):
                inside = False
                continue
        if inside:
            count += len(re.findall(r"<li\b", part, re.I))
    return count if found else None


def word_count(text: str | None) -> int | None:
    return len(text.split()) if text else None


def norm_title(title: str | None) -> str:
    t = re.sub(r"\(.*?\)|\[.*?\]|\b(req|job)\s*#?\s*\w*\d\w*", " ", (title or "").lower())
    t = re.sub(r"[^a-z0-9+#]+", " ", t)
    return " ".join(t.split())


def norm_location(loc: str | None) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (loc or "").lower()).split())


# ---------------------------------------------------------------- filings: hiring statements and layoffs

_HYPOTHETICAL = re.compile(r"\b(may|might|could|would|if we|if the company|failure to|inability to|unable to|"
                           r"there can be no assurance|risk|risks)\b", re.I)
_BOILERPLATE = re.compile(r"attract(?:,|ing)? (?:and|,)? ?retain|attract, develop|attract and retain", re.I)

HIRING_FREEZE = re.compile(
    r"\b(hiring freeze|freez(?:e|ing|es) (?:on )?(?:new |external )?hiring|hiring pause|"
    r"paus(?:e|ed|ing) (?:on )?(?:new |external |most )?hiring|suspend(?:ed|ing)? (?:new |external )?hiring|"
    r"halt(?:ed|ing)? (?:new |external )?hiring|not (?:to )?backfill(?:ing)?|no(?:t)? backfills?)\b", re.I)

TONE_NEG = ["disciplined headcount", "headcount discipline", "disciplined hiring", "slowing hiring",
            "slowed hiring", "slow hiring", "slowing the pace of hiring", "slowed the pace of hiring", "reduced hiring",
            "reducing hiring", "limit hiring", "limited hiring", "limiting hiring", "hiring freeze", "pause hiring",
            "paused hiring", "reduce headcount", "reduced headcount", "reducing headcount", "headcount reduction",
            "headcount reductions", "workforce reduction", "reduction in force", "lower headcount", "flat headcount",
            "headcount flat", "hold headcount", "holding headcount", "rightsizing", "right-sizing",
            "streamline our workforce", "optimize our workforce", "fewer employees", "lower hiring",
            "moderated hiring", "moderate hiring", "tightly manage headcount", "manage headcount"]
TONE_POS = ["investing in talent", "invest in talent", "invest in our people", "investing in our people",
            "expand our workforce", "expanding our workforce", "grow our workforce", "growing our workforce",
            "grow headcount", "grow our headcount", "increase headcount", "increased headcount", "increasing headcount",
            "headcount growth", "add headcount", "adding headcount", "added headcount", "continue to hire",
            "continued to hire", "continue hiring", "accelerate hiring", "accelerating hiring", "accelerated hiring",
            "increased hiring", "increase hiring", "increasing hiring", "hire additional", "plan to hire",
            "expect to hire", "hiring additional", "recruit additional", "expanded our team", "expanding our team",
            "growing our team", "investments in headcount", "investment in headcount"]
_NEG_RE = re.compile("|".join(re.escape(p) for p in sorted(TONE_NEG, key=len, reverse=True)), re.I)
_POS_RE = re.compile("|".join(re.escape(p) for p in sorted(TONE_POS, key=len, reverse=True)), re.I)


def hiring_tone(sentence: str) -> int | None:
    """+1 / -1 / 0 for a concrete management statement about hiring; None when it isn't one."""
    if _HYPOTHETICAL.search(sentence) or _BOILERPLATE.search(sentence):
        return None
    neg = len(_NEG_RE.findall(sentence))
    pos = len(_POS_RE.findall(_NEG_RE.sub(" ", sentence)))
    if not neg and not pos:
        return None
    return (pos > neg) - (neg > pos)


def is_hiring_freeze(sentence: str) -> bool:
    return bool(HIRING_FREEZE.search(sentence)) and not _HYPOTHETICAL.search(sentence)


_LAYOFF = re.compile(r"\b(reductions? in force|workforce reductions?|reduc(?:e|ed|ing|tion (?:of|in)) (?:our|its|the "
                     r"company's|the) (?:global |overall |total )?(?:workforce|headcount)|layoffs?|laid off|"
                     r"headcount reductions?|job cuts|position eliminations|eliminat(?:e|ed|ing|ion of) "
                     r"(?:approximately |about |roughly )?[\d,]+ (?:positions|roles|jobs))\b", re.I)
_COMMIT = re.compile(r"\b(announced|approved|committed|implemented|initiated|undertook|undertaken|completed|"
                     r"commenced|began|decided|notified|eliminated|reduced|is reducing|will reduce|plans? to reduce|"
                     r"expects? to reduce|took action|actions? taken|executed|carried out|conducted)\b", re.I)
_WORKERS = re.compile(r"(?:approximately|about|roughly|nearly|over|more than|up to|some)?\s*(\d{1,3}(?:,\d{3})+|\d{2,6})"
                      r"\s+(?:full[- ]time\s+)?(?:employees|positions|roles|jobs|team members|people|associates|workers|"
                      r"colleagues|staff)", re.I)
_PCT = re.compile(r"(\d{1,2}(?:\.\d+)?)\s?%\s+(?:of\s+)?(?:(?:our|its|the company's|the)\s+)?(?:global |total |overall )?"
                  r"(?:workforce|employees|headcount|staff)|(?:workforce|headcount|staff)\s+by\s+(?:approximately\s+|about\s+)?"
                  r"(\d{1,2}(?:\.\d+)?)\s?%", re.I)
_MONTH_YEAR = re.compile(rf"\b(?:in|on|during)\s+({_MONTHS})\.?\s+(?:\d{{1,2}},?\s+)?(20\d\d)\b", re.I)
_MONTH_NUM = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def layoff_mention(sentence: str, item_205: bool = False) -> dict | None:
    """A concrete (not hypothetical) layoff statement: {workers, pct, stated_date}; None otherwise."""
    if not _LAYOFF.search(sentence) or _HYPOTHETICAL.search(sentence):
        return None
    if not item_205 and not _COMMIT.search(sentence):
        return None
    workers = None
    m = _WORKERS.search(sentence)
    if m:
        workers = int(m.group(1).replace(",", ""))
        if workers > 500_000:
            workers = None
    pct = None
    m = _PCT.search(sentence)
    if m:
        pct = float(m.group(1) or m.group(2)) / 100
    stated = None
    m = _MONTH_YEAR.search(sentence)
    if m:
        stated = date(int(m.group(2)), _MONTH_NUM[m.group(1).lower()[:3]], 1).isoformat()
    return {"workers": workers, "pct": pct, "stated_date": stated}


# ---------------------------------------------------------------- filings: employee counts

_EMP_NOUN = r"(?:full[- ]time(?: equivalent)?\s+|total\s+|global\s+|permanent\s+|active\s+)?(?:employees|team members|associates|colleagues|people|staff|FTEs?|personnel|workers)"
_EMP_NUM = r"(\d{1,3}(?:,\d{3})+|\d{3,7}|\d+(?:\.\d+)?\s*(?:thousand|million))"
_EMP_PATTERNS = [
    re.compile(r"\b(?:we|the company|the corporation|the bank|[A-Z][\w.&-]+)\s+(?:had|employed|employ|have|has|"
               r"had a total of|employs)\s+(?:a total of\s+)?(?:approximately|about|around|roughly|over|more than|"
               r"nearly|some)?\s*" + _EMP_NUM + r"\s+" + _EMP_NOUN, re.I),
    re.compile(r"\b(?:total|number of)\s+(?:full[- ]time\s+)?(?:employees|headcount|workforce|team members|associates)"
               r"\s+(?:was|of|were|totaled|totalled|is|consisted of)\s+(?:approximately|about|over)?\s*" + _EMP_NUM, re.I),
    re.compile(r"\b(?:workforce|headcount)\s+of\s+(?:approximately|about|over|more than)?\s*" + _EMP_NUM, re.I),
    re.compile(r"\b(?:approximately|about|over|more than|nearly)\s+" + _EMP_NUM + r"\s+" + _EMP_NOUN, re.I),
]
_US_EMP = [
    re.compile(_EMP_NUM + r"\s+(?:\w+\s+){0,5}?(?:were|are|was|is)?\s*(?:located|based|employed)?\s*(?:in|within)\s+the\s+"
                          r"(?:United States|U\.S\.)", re.I),
    re.compile(r"(?:United States|U\.S\.|domestic)\s+(?:employees|workforce|headcount)\s+(?:was|of|were|totaled|"
               r"is)?\s*(?:approximately|about)?\s*" + _EMP_NUM, re.I),
]
_US_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s?%\s+(?:\w+\s+){0,6}?(?:in|within)\s+the\s+(?:United States|U\.S\.)", re.I)


def _emp_value(s: str) -> int | None:
    s = s.lower().replace(",", "").strip()
    m = re.match(r"([\d.]+)\s*(thousand|million)?", s)
    if not m:
        return None
    v = float(m.group(1)) * {"thousand": 1e3, "million": 1e6}.get(m.group(2) or "", 1)
    return int(v) if 10 <= v <= 3_000_000 else None


def extract_employee_counts(text: str) -> dict | None:
    """From 10-K text: {"total", "total_quote", "us", "us_quote"}; searches the Human Capital / Employees section first."""
    if not text:
        return None
    starts = [m.start() for m in re.finditer(r"human capital|our employees|employees\b", text, re.I)]
    hc = re.search(r"human capital", text, re.I)
    windows = [text[hc.start():hc.start() + 15000]] if hc else []
    windows += [text[s:s + 3000] for s in starts[:40]]
    for win in windows:
        for sent in split_sentences(win, min_len=20, max_len=500):
            if _HYPOTHETICAL.search(sent) and "approximately" not in sent.lower():
                continue
            for pat in _EMP_PATTERNS:
                m = pat.search(sent)
                if not m:
                    continue
                total = _emp_value(m.group(1))
                if not total or (1900 <= total <= 2100 and "," not in m.group(1)):
                    continue
                out = {"total": total, "total_quote": sent, "us": None, "us_quote": None}
                idx = text.find(sent)
                nearby = split_sentences(text[idx:idx + 1500], min_len=20, max_len=500)[:4] if idx >= 0 else [sent]
                for s2 in nearby:
                    for up in _US_EMP:
                        mu = up.search(s2)
                        if mu:
                            v = _emp_value(mu.group(1))
                            if v and v <= total:
                                out["us"], out["us_quote"] = v, s2
                                break
                    if out["us"] is None:
                        mp = _US_PCT.search(s2)
                        if mp and 0 < float(mp.group(1)) <= 100:
                            out["us"], out["us_quote"] = int(round(total * float(mp.group(1)) / 100)), s2
                    if out["us"] is not None:
                        break
                return out
    return None


def company_website(text: str, exclude=("sec.gov", "xbrl", "fasb", "w3.org", "edgar", "gaap")) -> str | None:
    """Most frequently mentioned www. domain in a filing (SEC submissions often leave `website` blank)."""
    counts: dict[str, int] = {}
    for m in re.finditer(r"\bwww\.([a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|net|org|io|co|us|ai|bank|financial|tech))\b",
                         text or "", re.I):
        d = m.group(1).lower()
        if not any(x in d for x in exclude):
            counts[d] = counts.get(d, 0) + 1
    return max(counts, key=counts.get) if counts else None
