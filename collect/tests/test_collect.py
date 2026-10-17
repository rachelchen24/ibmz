"""Unit tests for the shared collection functions:  python -m unittest discover -s collect/tests -t ."""
import unittest
from datetime import date

from collect.common import ids
from collect.common import textparse as tp
from collect.common.companies import assign_shards
from collect.common.output import make_evidence, validate_evidence
from collect.sources.warn import Warn
from collect.sources.wayback import parse_snapshot


class Ids(unittest.TestCase):
    def test_normalize_company(self):
        self.assertEqual(ids.normalize_company("Leidos Holdings, Inc."), "leidos")
        self.assertEqual(ids.normalize_company("The Goldman Sachs Group, Inc."), "goldman sachs")

    def test_posting_id(self):
        self.assertEqual(ids.posting_id("greenhouse", 123), "greenhouse:123")
        a = ids.posting_id("workday", url="https://X.wd5.myworkdayjobs.com/a/job/1?src=li#top")
        self.assertEqual(a, ids.posting_id("workday", url="https://x.wd5.myworkdayjobs.com/a/job/1"))

    def test_evidence_id_stable(self):
        self.assertEqual(ids.evidence_id("A", "revenue", "FY2025", "u", "q"),
                         ids.evidence_id("A", "revenue", "FY2025", "u", "q"))


class Salary(unittest.TestCase):
    def test_annual_range(self):
        self.assertEqual(tp.parse_salary("The base salary range is $120,000 - $150,000 per year."), (120000, 150000))

    def test_k_and_hourly(self):
        self.assertEqual(tp.parse_salary("Pay: $120K-$160K"), (120000, 160000))
        self.assertEqual(tp.parse_salary("Hourly pay rate: $25.00 - $30.00 per hour"), (52000, 62400))

    def test_ignores_company_figures(self):
        self.assertIsNone(tp.parse_salary("We manage $500 - $600 billion in assets."))
        self.assertIsNone(tp.parse_salary("No pay info here."))


class Locations(unittest.TestCase):
    def test_states(self):
        self.assertEqual(tp.parse_states("New York, NY; San Francisco, CA"), ["NY", "CA"])
        self.assertEqual(tp.parse_states("Washington, D.C."), ["DC"])
        self.assertEqual(tp.parse_states("Seattle, Washington"), ["WA"])
        self.assertEqual(tp.parse_states("London, United Kingdom"), [])


class PostingText(unittest.TestCase):
    def test_deadline(self):
        d, rolling = tp.parse_deadline("Application deadline: November 30, 2026. Open until filled.")
        self.assertEqual(d, date(2026, 11, 30))
        self.assertTrue(rolling)

    def test_specificity(self):
        text = ("You will report to the Director of Data. Our interview process has three rounds. "
                "Expected start date: January 2027. Tools: Python, SQL, Airflow and Snowflake.")
        self.assertEqual(tp.specificity_score(text), 4)
        self.assertEqual(tp.specificity_score("Great opportunity."), 0)

    def test_named_team(self):
        self.assertTrue(tp.named_team("You will join the Payments Risk team in New York."))
        self.assertFalse(tp.named_team("Join our team of great people."))

    def test_seniority_mismatch(self):
        self.assertTrue(tp.seniority_mismatch("Junior Analyst", "Requires 6+ years of experience in finance."))
        self.assertTrue(tp.seniority_mismatch("Senior Engineer", "1 year of experience required."))
        self.assertFalse(tp.seniority_mismatch("Senior Engineer", "7+ years of experience."))

    def test_vague_and_long_cycle(self):
        self.assertEqual(tp.vague_phrase_count("Join our talent community for future opportunities."), 2)
        self.assertTrue(tp.long_cycle("2027 Summer Analyst Program", ""))
        self.assertFalse(tp.long_cycle("Software Engineer", "Our campus in Austin"))

    def test_requirement_bullets(self):
        h = "<h3>Requirements</h3><ul><li>a</li><li>b</li><li>c</li></ul><h3>Benefits</h3><ul><li>x</li></ul>"
        self.assertEqual(tp.requirement_bullets(h), 3)


class Filings(unittest.TestCase):
    def test_layoff(self):
        m = tp.layoff_mention("In January 2026, the Company approved a reduction in force of approximately "
                              "1,200 employees, or 8% of its global workforce.")
        self.assertEqual(m["workers"], 1200)
        self.assertAlmostEqual(m["pct"], 0.08)
        self.assertEqual(m["stated_date"], "2026-01-01")
        self.assertIsNone(tp.layoff_mention("We may need to implement layoffs if demand declines."))

    def test_tone_and_freeze(self):
        self.assertEqual(tp.hiring_tone("We continued to maintain disciplined headcount management this quarter."), -1)
        self.assertEqual(tp.hiring_tone("We are investing in talent and plan to hire additional engineers."), 1)
        self.assertIsNone(tp.hiring_tone("We must attract and retain talented employees."))
        self.assertTrue(tp.is_hiring_freeze("In the third quarter we implemented a hiring freeze across corporate functions."))

    def test_employee_count(self):
        text = ("Item 1. Business. Human Capital. As of December 31, 2025, we had approximately 12,300 full-time "
                "employees. Approximately 9,800 of our employees were located in the United States.")
        e = tp.extract_employee_counts(text)
        self.assertEqual(e["total"], 12300)
        self.assertEqual(e["us"], 9800)


class Output(unittest.TestCase):
    def test_evidence_valid(self):
        row = make_evidence("ACME", "revenue", 5.0, "USD", "FY2025", "https://x", '"val":5', "2026-01-01", "edgar", "r1")
        self.assertEqual(validate_evidence(row), [])
        row["field"] = "ghost_score"
        self.assertTrue(validate_evidence(row))


class Shards(unittest.TestCase):
    def test_balanced(self):
        rows = [{"ticker": f"T{i}", "priority_tier": 1, "sector": ["a", "b", "c"][i % 3], "size": i, "shard": None}
                for i in range(300)]
        assign_shards(rows)
        for n in range(1, 5):
            mine = [r for r in rows if r["shard"] == n]
            self.assertEqual(len(mine), 75)
            self.assertEqual(sum(r["sector"] == "a" for r in mine), 25)


class Matching(unittest.TestCase):
    def test_warn_match(self):
        self.assertTrue(Warn.matches(["Accenture plc"], "accenture llp"[:-4]))
        self.assertTrue(Warn.matches(["Oracle Corporation"], "oracle america"))
        self.assertFalse(Warn.matches(["Bancorp, Inc."], "bancorp south bank"))


class Wayback(unittest.TestCase):
    def test_greenhouse_json(self):
        jobs, quote = parse_snapshot("gh_api", '{"jobs":[{"id":1,"title":"A","location":{"name":"NY"}}],"meta":{"total":1}}')
        self.assertEqual(len(jobs), 1)
        self.assertEqual(quote, '"total":1')

    def test_unreadable_html_is_not_zero(self):
        self.assertIsNone(parse_snapshot("gh_html", "<html>new layout</html>"))


if __name__ == "__main__":
    unittest.main()
