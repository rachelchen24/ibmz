"""python -m unittest discover -s dataset/tests -t ."""
import unittest
from datetime import date

from dataset.build_outcomes import fiscal_year_end, headcounts
from dataset.spot_check import wilson


class Outcomes(unittest.TestCase):
    def test_fiscal_year_end_from_xbrl_quote(self):
        ev = {"revenue": [{"period": "FY2026", "quote": '{"start":"2025-02-01","end":"2026-01-31","val":5}'}]}
        self.assertEqual(fiscal_year_end(ev, 2026), date(2026, 1, 31))
        self.assertEqual(fiscal_year_end(ev, 2025), date(2025, 12, 31))

    def test_headcount_basis(self):
        ev = {"employee_count": [{"period": "FY2025", "value": 1000, "evidence_id": "a"},
                                 {"period": "FY2024", "value": 900, "evidence_id": "b"}],
              "employee_count_us": [{"period": "FY2025", "value": 700, "evidence_id": "c"}]}
        hc, basis, _ = headcounts(ev)
        self.assertEqual(basis, "total")          # US only for one year: don't mix bases
        self.assertEqual(hc[2025] - hc[2024], 100)


class SpotCheck(unittest.TestCase):
    def test_wilson(self):
        lo, hi = wilson(3, 100)
        self.assertTrue(0.009 < lo < 0.011 and 0.084 < hi < 0.086)


if __name__ == "__main__":
    unittest.main()
