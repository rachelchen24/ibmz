"""Map a schema.org JobPosting (the JSON-LD job sites embed in their pages) to the model's raw Kaggle columns.

Fields a page can't show (has_questions, required_experience, department, function) are left missing and listed
in `unknown`, so the API can say what it did not see instead of guessing.
"""
import html
import re

COUNTRY = {"united states": "US", "united states of america": "US", "usa": "US", "u.s.": "US", "us": "US",
           "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB", "canada": "CA",
           "germany": "DE", "greece": "GR", "new zealand": "NZ", "india": "IN", "australia": "AU", "ireland": "IE",
           "france": "FR", "netherlands": "NL", "spain": "ES", "singapore": "SG", "philippines": "PH"}
EMPLOYMENT = {"FULL_TIME": "Full-time", "PART_TIME": "Part-time", "CONTRACTOR": "Contract", "CONTRACT": "Contract",
              "TEMPORARY": "Temporary", "INTERN": "Other", "PER_DIEM": "Other", "VOLUNTEER": "Other", "OTHER": "Other"}
EDUCATION = [("high school", "High School or equivalent"), ("associate", "Associate Degree"),
             ("bachelor", "Bachelor's Degree"), ("master", "Master's Degree"), ("doctor", "Doctorate"),
             ("phd", "Doctorate"), ("professional certificate", "Certification"), ("certificat", "Certification")]


def html_to_text(s) -> str | None:
    if not s:
        return None
    s = re.sub(r"<(br|/p|/li|/h\d|/div)\s*/?>", "\n", str(s), flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip() or None


def _first(x):
    return x[0] if isinstance(x, list) and x else x


def _text(x) -> str | None:
    """A schema.org value that may be a string, an object with name/description, or a list of either."""
    if x is None:
        return None
    if isinstance(x, list):
        parts = [_text(i) for i in x]
        return "\n".join(p for p in parts if p) or None
    if isinstance(x, dict):
        return _text(x.get("description") or x.get("name") or x.get("credentialCategory"))
    return html_to_text(x)


def find_jobposting(data, depth: int = 0) -> dict | None:
    """The first JobPosting in parsed JSON-LD (handles @graph, arrays, mainEntity)."""
    if depth > 6 or data is None:
        return None
    if isinstance(data, list):
        for item in data:
            jp = find_jobposting(item, depth + 1)
            if jp:
                return jp
        return None
    if isinstance(data, dict):
        if "JobPosting" in ([data.get("@type")] if isinstance(data.get("@type"), str) else data.get("@type") or []):
            return data
        for key in ("@graph", "mainEntity", "itemListElement"):
            jp = find_jobposting(data.get(key), depth + 1)
            if jp:
                return jp
    return None


US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC "
                "ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())


def free_location(s: str) -> str | None:
    """'San Francisco, CA' -> 'US, CA, San Francisco' (the training data's 'country, state, city' form).
    Anything we can't place keeps its text as the city with no country, rather than guessing one."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if not s:
        return None
    parts = [p.strip() for p in re.split(r"[;|/]| or ", s)[0].split(",") if p.strip()]
    if parts and parts[-1].lower() in COUNTRY:
        country = COUNTRY[parts[-1].lower()]
        parts = parts[:-1]
    else:
        country = "US" if parts and parts[-1].upper() in US_STATES else ""
    state = parts[-1].upper() if country == "US" and parts and parts[-1].upper() in US_STATES else ""
    city = ", ".join(parts[:-1] if state else parts)
    return f"{country}, {state}, {city}"


def _location(jp: dict) -> str | None:
    loc = _first(jp.get("jobLocation"))
    addr = loc.get("address") if isinstance(loc, dict) else (loc if isinstance(loc, str) else None)
    if isinstance(addr, str):
        return free_location(addr)
    if not isinstance(addr, dict):
        req = _first(jp.get("applicantLocationRequirements"))
        name = req.get("name") if isinstance(req, dict) else req
        return f"{COUNTRY.get(str(name).lower(), name)}, , " if name else None
    country = addr.get("addressCountry")
    country = country.get("name") if isinstance(country, dict) else country
    country = COUNTRY.get(str(country or "").strip().lower(), country)
    parts = [country or "", addr.get("addressRegion") or "", addr.get("addressLocality") or ""]
    return ", ".join(str(p).strip() for p in parts) if any(parts) else None


def _salary(jp: dict) -> str | None:
    sal = jp.get("baseSalary") or jp.get("estimatedSalary")
    sal = _first(sal)
    if not isinstance(sal, dict):
        return None
    v = sal.get("value", sal)
    if isinstance(v, (int, float)):
        return f"{int(v)}-{int(v)}"
    if isinstance(v, dict):
        lo, hi = v.get("minValue", v.get("value")), v.get("maxValue", v.get("value"))
        try:
            return f"{int(float(lo))}-{int(float(hi))}" if lo is not None and hi is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _education(jp: dict) -> str | None:
    t = (_text(jp.get("educationRequirements")) or "").lower()
    return next((label for key, label in EDUCATION if key in t), None) if t else None


def to_raw(jp: dict) -> tuple[dict, list[str]]:
    """(raw posting in the Kaggle columns, inputs the page did not provide)."""
    org = _first(jp.get("hiringOrganization"))
    org = org if isinstance(org, dict) else ({"name": org} if org else {})
    requirements = "\n".join(t for t in (_text(jp.get("qualifications")), _text(jp.get("experienceRequirements")),
                                         _text(jp.get("skills"))) if t) or None
    etype = _first(jp.get("employmentType"))
    raw = {
        "title": _text(jp.get("title")),
        "company_profile": _text(org.get("description")),
        "description": html_to_text(jp.get("description")),
        "requirements": requirements,
        "benefits": _text(jp.get("jobBenefits")),
        "location": _location(jp),
        "salary_range": _salary(jp),
        "employment_type": EMPLOYMENT.get(str(etype).upper().replace("-", "_"), "Other") if etype else None,
        "required_education": _education(jp),
        "industry": _text(jp.get("industry")),
        "telecommuting": int(str(jp.get("jobLocationType", "")).upper() == "TELECOMMUTE"),
        # A logo we can see counts; no logo in the data usually means the page or API simply doesn't say, so it is
        # left unknown rather than read as "no logo" (a strong scam signal in the training data).
        "has_company_logo": 1 if org.get("logo") else None,
    }
    unknown = ["has_questions", "required_experience", "department", "function"]
    unknown += ["has_company_logo"] if raw["has_company_logo"] is None else []
    unknown += [k for k in ("company_profile", "requirements", "benefits", "salary_range", "employment_type",
                            "required_education", "industry") if raw.get(k) is None]
    return {k: v for k, v in raw.items() if v is not None}, unknown


def company_name(jp: dict) -> str | None:
    org = _first(jp.get("hiringOrganization"))
    return (org.get("name") if isinstance(org, dict) else org) or None
