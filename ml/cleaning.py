"""Load and clean data/fake_job_postings.csv (EMSCAD, Kaggle). Shared by every model in ml/.

    from ml.cleaning import load_clean
    df = load_clean()                       # cleaned rows, exact duplicates removed

Cleaning is row-wise and deterministic: nothing here is fitted to the data, so applying it before the split
cannot leak information between train and test. Fitted preprocessing (imputation, encoding, TF-IDF) belongs in the
model pipelines, inside the training folds. Decisions and the evidence behind them: ml/AUDIT.md.
"""
import hashlib
import html
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "fake_job_postings.csv"

TARGET = "fraudulent"
ID = "job_id"
TEXT_COLS = ["title", "company_profile", "description", "requirements", "benefits"]
CATEGORICAL_COLS = ["department", "employment_type", "required_experience", "required_education", "industry",
                    "function"]
BINARY_COLS = ["telecommuting", "has_company_logo", "has_questions"]
RAW_COLUMNS = [ID, "title", "location", "department", "salary_range", "company_profile", "description",
               "requirements", "benefits", "telecommuting", "has_company_logo", "has_questions", "employment_type",
               "required_experience", "required_education", "industry", "function", TARGET]
# Columns added by cleaning (parsed from location and salary_range; the raw columns are kept too).
DERIVED_COLS = ["loc_country", "loc_state", "loc_city", "salary_min", "salary_max", "salary_invalid"]
# Every predictive column: all raw columns except the identifier and the target (ml/PLAN.md).
FEATURE_COLS = [c for c in RAW_COLUMNS if c not in (ID, TARGET)] + DERIVED_COLS
# Feature groups for the preprocessing pipeline: every FEATURE_COLS entry is in exactly one group.
# location and salary_range are kept as raw strings, but their parsed parts are what most encoders should use.
FEATURE_GROUPS = {
    "text": TEXT_COLS,
    "categorical": CATEGORICAL_COLS + ["loc_country", "loc_state", "loc_city"],
    "binary": BINARY_COLS + ["salary_invalid"],
    "numeric": ["salary_min", "salary_max"],
    "raw_parsed": ["location", "salary_range"],
}

_PLACEHOLDER = re.compile(r"#(URL|EMAIL|PHONE)_[0-9a-fA-F]+#")
_GLUED = re.compile(r"(?<=[a-z]{2})(?=[A-Z][a-z])")   # "skillsAbility" -> "skills Ability" (lost line breaks)
_MOJIBAKE = str.maketrans({"�": "'", " ": " ", "​": ""})
_MOJIBAKE_SEQ = {"â€™": "'", "â€œ": '"', "â€\x9d": '"', "â€“": "-", "â€”": "-", "Ã©": "é", "Â": ""}


class SchemaError(ValueError):
    pass


def load_raw(path=DATA_PATH) -> pd.DataFrame:
    """The CSV as published, with its schema checked. Raises SchemaError on any surprise."""
    df = pd.read_csv(path, dtype={c: "string" for c in RAW_COLUMNS if c not in (ID, TARGET, *BINARY_COLS)})
    validate_raw(df)
    return df


def validate_raw(df: pd.DataFrame) -> None:
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in RAW_COLUMNS]
    if missing or extra:
        raise SchemaError(f"columns differ from the expected schema: missing {missing}, unexpected {extra}")
    if not df[ID].is_unique:
        raise SchemaError(f"{ID} is not unique")
    for c in BINARY_COLS + [TARGET]:
        bad = set(pd.unique(df[c].dropna())) - {0, 1}
        if bad or df[c].isna().any():
            raise SchemaError(f"{c} must be 0/1 with no missing values; found {sorted(bad)[:5]}")


def clean_text(s, keep_placeholder_ids: bool = False):
    """Unescape HTML entities, repair common encoding damage, split run-together words, normalize whitespace.

    Anonymized #URL_<hash>#, #EMAIL_<hash>#, #PHONE_<hash># become URL_TOKEN, EMAIL_TOKEN, PHONE_TOKEN: the token says
    a link/email/phone was there, while the hash (which identifies one specific URL, i.e. often one company) is
    dropped so text models can't memorize companies through it. keep_placeholder_ids=True keeps the hash (grouping).
    """
    if s is None or (isinstance(s, float) and np.isnan(s)) or s is pd.NA:
        return pd.NA
    s = html.unescape(html.unescape(str(s)))         # some values are double-escaped (&amp;amp;)
    for bad, good in _MOJIBAKE_SEQ.items():
        s = s.replace(bad, good)
    s = s.translate(_MOJIBAKE)
    if not keep_placeholder_ids:
        s = _PLACEHOLDER.sub(lambda m: f" {m.group(1)}_TOKEN ", s)
    s = _GLUED.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s if s else pd.NA


def clean_category(s):
    if s is None or s is pd.NA or (isinstance(s, float) and np.isnan(s)):
        return pd.NA
    s = re.sub(r"\s+", " ", html.unescape(str(s))).strip()
    return s if s else pd.NA


def parse_location(loc) -> tuple:
    """'US, CA, San Francisco' -> ('US', 'CA', 'San Francisco'); empty parts -> NA. Extra parts stay in the city."""
    if loc is pd.NA or loc is None or not str(loc).strip():
        return pd.NA, pd.NA, pd.NA
    parts = [p.strip() for p in str(loc).split(",")]
    country = parts[0] or pd.NA
    state = parts[1] if len(parts) > 1 and parts[1] else pd.NA
    city = ", ".join(p for p in parts[2:] if p) or pd.NA
    return country, state, city


def parse_salary(s) -> tuple:
    """'40000-60000' -> (40000.0, 60000.0, False). A single number gives min == max.

    Excel-mangled values ('10-Oct', 'Jun-18') and '0-0' are not salaries: (NA, NA, True). Units and currency are
    not stated in the data, so values are kept as given (a max under 1,000 is probably hourly or monthly).
    """
    if s is pd.NA or s is None or not str(s).strip():
        return np.nan, np.nan, False
    s = str(s).strip()
    m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", s) or re.fullmatch(r"(\d+)", s)
    if not m:
        return np.nan, np.nan, True
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.lastindex == 2 else lo
    if hi == 0 or lo > hi:
        return np.nan, np.nan, True
    return lo, hi, False


def row_hash(df: pd.DataFrame) -> pd.Series:
    """Stable hash of all raw predictive fields (used to find exact duplicates)."""
    cols = [c for c in RAW_COLUMNS if c not in (ID, TARGET)]
    joined = df[cols].astype("string").fillna("\x00").agg("\x1f".join, axis=1)
    return joined.map(lambda x: hashlib.sha1(x.encode("utf-8")).hexdigest())


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Cleaned copy of the raw frame (same rows, same job_id). Raw text columns are replaced by cleaned text."""
    out = df.copy()
    for c in TEXT_COLS:
        out[c] = out[c].map(clean_text).astype("string")
    for c in CATEGORICAL_COLS:
        out[c] = out[c].map(clean_category).astype("string")
    out["department"] = out["department"].str.lower().astype("string")   # 113 case/spacing variants
    out["location"] = out["location"].map(clean_category).astype("string")
    loc = out["location"].map(parse_location)
    out["loc_country"] = loc.str[0].astype("string")
    out["loc_state"] = loc.str[1].astype("string")
    out["loc_city"] = loc.str[2].astype("string")
    sal = out["salary_range"].map(parse_salary)
    out["salary_min"] = sal.str[0].astype("float64")
    out["salary_max"] = sal.str[1].astype("float64")
    out["salary_invalid"] = sal.str[2].astype("int8")
    for c in BINARY_COLS + [TARGET]:
        out[c] = out[c].astype("int8")
    return out


def drop_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the lowest job_id of each set of rows identical in every raw field and label.
    Returns (kept, dropped) where dropped has a `duplicate_of` column."""
    h = row_hash(df) + "|" + df[TARGET].astype(str)
    first = df.assign(_h=h).sort_values(ID).groupby("_h")[ID].transform("first").reindex(df.index)
    is_dup = df[ID] != first
    dropped = df[is_dup].assign(duplicate_of=first[is_dup].values)
    return df[~is_dup].copy(), dropped


def load_clean(path=DATA_PATH, drop_duplicates: bool = True) -> pd.DataFrame:
    df = load_raw(path)
    if drop_duplicates:
        df, _ = drop_exact_duplicates(df)
    return clean(df).reset_index(drop=True)
