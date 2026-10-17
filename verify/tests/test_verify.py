"""python -m unittest discover -s verify/tests -t ."""
import unittest

from verify.conflicts import flag_conflicts
from verify.quote_check import PageIndex, value_check


def row(field, value, quote, **kw):
    return {"field": field, "value": value, "quote": quote, "collector": kw.get("collector", "edgar"),
            "ticker": "ACME", "period": "FY2025", "source_url": kw.get("url", "u1"), "check": "passed"}


class QuoteCheck(unittest.TestCase):
    page = PageIndex("<p>As of December 31, 2025, we had approximately&nbsp;12,300 employees.</p>".replace("&nbsp;", "\xa0"))

    def test_found_and_value(self):
        r = row("employee_count", 12300, "As of December 31, 2025, we had approximately 12,300 employees")
        self.assertEqual(self.page.find(r["quote"]), "exact")
        self.assertEqual(value_check(r, self.page)[0], "match")

    def test_edited_quote_missing(self):
        self.assertIsNone(self.page.find("we had approximately 45,300 employees"))

    def test_wrong_value(self):
        r = row("employee_count", 18450, "As of December 31, 2025, we had approximately 12,300 employees")
        self.assertEqual(value_check(r, self.page)[0], "mismatch")

    def test_derived_us(self):
        r = row("employee_count_us", 2709, "we had a total of 5,636 employees, including 2,927 employees located outside the United States")
        self.assertEqual(value_check(r, PageIndex(r["quote"]))[0], "match")

    def test_warn_row(self):
        p = PageIndex("", rows=["2026-01-05 | Acme Software Inc | Santa Clara | 120", "2026-02-01 | Other | X | 5"])
        r = row("layoff_events", {"workers": 120}, "Acme Software Inc", collector="warn")
        self.assertEqual(value_check(r, p)[0], "match")
        r["value"] = {"workers": 999}
        self.assertEqual(value_check(r, p)[0], "mismatch")


class Conflicts(unittest.TestCase):
    def test_numeric(self):
        rows = [row("revenue", 100.0, "q", url="a"), row("revenue", 125.0, "q", url="b")]
        self.assertEqual(flag_conflicts(rows), 2)
        rows = [row("revenue", 100.0, "q", url="a"), row("revenue", 105.0, "q", url="b")]
        self.assertEqual(flag_conflicts(rows), 0)


if __name__ == "__main__":
    unittest.main()
