"""Indeed Hiring Lab US postings index by category (reference data, data/raw/indeed) -> 90-day trend per sector.

Indeed's "sectors" are occupational categories, so each company sector is mapped to the categories it mostly
hires in and their trends are averaged. The mapping is our approximation; edit it here.
"""
import pandas as pd

from ..common import config

SECTOR_CATEGORIES = {
    "tech": ["Software Development", "IT Systems & Solutions", "IT Infrastructure", "Data & Analytics"],
    "information technology": ["Software Development", "IT Systems & Solutions", "IT Infrastructure", "Data & Analytics"],
    "communication services": ["Media & Communications", "Marketing", "Software Development"],
    "banking": ["Banking & Finance", "Customer Service"],
    "finance": ["Banking & Finance", "Insurance", "Accounting"],
    "financials": ["Banking & Finance", "Insurance", "Accounting"],
    "professional_services": ["Management", "Accounting", "Project Management", "Human Resources", "Legal"],
    "industrials": ["Production & Manufacturing", "Mechanical Engineering", "Driving", "Logistic Support",
                    "Installation & Maintenance", "Construction"],
    "health care": ["Nursing", "Medical Technician", "Pharmacy", "Physicians & Surgeons",
                    "Scientific Research & Development"],
    "consumer discretionary": ["Retail", "Food Preparation & Service", "Hospitality & Tourism", "Sales"],
    "consumer staples": ["Retail", "Production & Manufacturing", "Loading & Stocking"],
    "energy": ["Mechanical Engineering", "Electrical Engineering", "Installation & Maintenance"],
    "materials": ["Production & Manufacturing", "Industrial Engineering", "Scientific Research & Development"],
    "utilities": ["Electrical Engineering", "Installation & Maintenance", "Civil Engineering"],
    "real estate": ["Construction", "Sales", "Management"],
}


def category_trends(path=config.INDEED_SECTOR_FILE, days=config.SECTOR_TREND_DAYS) -> tuple[dict[str, float], str | None]:
    """({category: % change in total postings index over `days`}, latest date)."""
    if not path.exists():
        return {}, None
    df = pd.read_csv(path, parse_dates=["date"])
    df = df[df["variable"] == "total postings"]
    if df.empty:
        return {}, None
    latest = df["date"].max()
    past = latest - pd.Timedelta(days=days)
    out = {}
    for cat, g in df.groupby("display_name"):
        now = g.loc[g["date"] == latest, "indeed_job_postings_index"]
        before = g.loc[g["date"] <= past].sort_values("date").tail(1)["indeed_job_postings_index"]
        if len(now) and len(before) and before.iloc[0]:
            out[cat] = float(now.iloc[0]) / float(before.iloc[0]) - 1
    return out, latest.date().isoformat()


def sector_trend(sector: str | None, trends: dict[str, float]) -> float:
    cats = SECTOR_CATEGORIES.get((sector or "").strip().lower(), [])
    vals = [trends[c] for c in cats if c in trends]
    return sum(vals) / len(vals) if vals else float("nan")
