"""python -m unittest discover -s ml/tests -t ."""
import json
import unittest

import numpy as np
import pandas as pd

from ml import cleaning as C
from ml import split as S


def raw_frame(rows):
    base = {c: pd.NA for c in C.RAW_COLUMNS}
    base.update({"telecommuting": 0, "has_company_logo": 1, "has_questions": 0, "fraudulent": 0})
    return pd.DataFrame([{**base, **r} for r in rows])


class CleanText(unittest.TestCase):
    def test_entities_glue_placeholders(self):
        self.assertEqual(C.clean_text("teamWe offer &amp;amp; perks #URL_ab12# industry�s best"),
                         "team We offer & perks URL_TOKEN industry's best")

    def test_keep_placeholder_ids_for_grouping(self):
        self.assertIn("#URL_ab12#", C.clean_text("see #URL_ab12#", keep_placeholder_ids=True))

    def test_names_not_split(self):
        self.assertEqual(C.clean_text("iPhone and McDonald"), "iPhone and McDonald")

    def test_empty_is_missing(self):
        self.assertIs(C.clean_text("   "), pd.NA)
        self.assertIs(C.clean_text(np.nan), pd.NA)


class Parsers(unittest.TestCase):
    def test_salary(self):
        self.assertEqual(C.parse_salary("40000-60000"), (40000.0, 60000.0, False))
        self.assertEqual(C.parse_salary("40000"), (40000.0, 40000.0, False))
        for bad in ("10-Oct", "Jun-18", "0-0"):
            lo, hi, invalid = C.parse_salary(bad)
            self.assertTrue(np.isnan(lo) and np.isnan(hi) and invalid, bad)
        lo, _, invalid = C.parse_salary(pd.NA)
        self.assertTrue(np.isnan(lo) and not invalid)

    def test_location(self):
        self.assertEqual(C.parse_location("US, CA, San Francisco"), ("US", "CA", "San Francisco"))
        self.assertEqual(C.parse_location("US, , "), ("US", pd.NA, pd.NA))
        self.assertEqual(C.parse_location("US, CA, Menlo Park, CA"), ("US", "CA", "Menlo Park, CA"))
        self.assertEqual(C.parse_location("US"), ("US", pd.NA, pd.NA))


class Schema(unittest.TestCase):
    def test_feature_columns_exclude_target_and_id(self):
        self.assertNotIn(C.TARGET, C.FEATURE_COLS)
        self.assertNotIn(C.ID, C.FEATURE_COLS)
        self.assertTrue(set(C.RAW_COLUMNS) - {C.ID, C.TARGET} <= set(C.FEATURE_COLS))

    def test_feature_groups_cover_every_feature_once(self):
        grouped = [c for cols in C.FEATURE_GROUPS.values() for c in cols]
        self.assertEqual(sorted(grouped), sorted(C.FEATURE_COLS))
        self.assertEqual(len(grouped), len(set(grouped)))

    def test_rejects_bad_schema(self):
        df = raw_frame([{"job_id": 1}])
        with self.assertRaises(C.SchemaError):
            C.validate_raw(df.drop(columns=["title"]))
        with self.assertRaises(C.SchemaError):
            C.validate_raw(df.assign(fraudulent=2))
        with self.assertRaises(C.SchemaError):
            C.validate_raw(pd.concat([df, df]))

    def test_clean_keeps_rows_and_ids(self):
        df = raw_frame([{"job_id": 1, "title": "Engineer", "salary_range": "10-Oct", "location": "GB, LND, London"},
                        {"job_id": 2, "title": "Clerk"}])
        out = C.clean(df)
        self.assertEqual(out["job_id"].tolist(), [1, 2])
        self.assertEqual(int(out.loc[0, "salary_invalid"]), 1)
        self.assertEqual(out.loc[0, "loc_city"], "London")


class Duplicates(unittest.TestCase):
    def test_exact_duplicates(self):
        df = raw_frame([{"job_id": 5, "title": "A"}, {"job_id": 2, "title": "A"}, {"job_id": 3, "title": "B"}])
        kept, dropped = C.drop_exact_duplicates(df)
        self.assertEqual(sorted(kept["job_id"]), [2, 3])
        self.assertEqual(dropped["duplicate_of"].tolist(), [2])

    def test_same_text_different_label_not_dropped(self):
        df = raw_frame([{"job_id": 1, "title": "A"}, {"job_id": 2, "title": "A", "fraudulent": 1}])
        kept, _ = C.drop_exact_duplicates(df)
        self.assertEqual(len(kept), 2)


class Groups(unittest.TestCase):
    def test_links_profile_and_description(self):
        prof = "Acme Corp builds rockets for the outer solar system and beyond."
        desc = "We are hiring a data entry clerk to work from home, no experience needed, weekly pay."
        df = raw_frame([{"job_id": 1, "company_profile": prof, "description": "x"},
                        {"job_id": 2, "company_profile": prof, "description": desc},
                        {"job_id": 3, "company_profile": pd.NA, "description": desc},   # same posting, no profile
                        {"job_id": 4, "company_profile": pd.NA, "description": "Sales"}])  # too short to link
        g = S.build_groups(df)
        self.assertEqual(g.iloc[0], g.iloc[1])
        self.assertEqual(g.iloc[1], g.iloc[2])
        self.assertNotEqual(g.iloc[3], g.iloc[0])
        self.assertEqual(g.iloc[0], "g00001")


@unittest.skipUnless(S.SPLIT_CSV.exists() and C.DATA_PATH.exists(), "needs data/fake_job_postings.csv and the split")
class SavedSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = pd.read_csv(S.SPLIT_CSV)
        cls.meta = json.loads(S.SPLIT_JSON.read_text(encoding="utf-8"))

    def test_every_row_assigned_once(self):
        self.assertTrue(self.s["job_id"].is_unique)
        self.assertEqual(len(self.s), self.meta["rows_raw"])
        self.assertTrue(set(self.s["split"]) <= {"train", "val", "test", "dropped_duplicate"})

    def test_no_group_crosses_splits_or_folds(self):
        live = self.s[self.s["split"] != "dropped_duplicate"]
        self.assertEqual(int((live.groupby("group_id")["split"].nunique() > 1).sum()), 0)
        tr = live[live["split"] == "train"]
        self.assertEqual(int((tr.groupby("group_id")["cv_fold"].nunique() > 1).sum()), 0)
        self.assertTrue((tr["cv_fold"] >= 0).all())
        self.assertTrue((live.loc[live["split"] != "train", "cv_fold"] == -1).all())

    def test_prevalence_balanced(self):
        prev = [v["prevalence"] for v in self.meta["splits"].values()]
        self.assertLess(max(prev) - min(prev), 0.01)

    def test_reproducible(self):
        rebuilt = S.make_split(C.load_raw())
        pd.testing.assert_frame_equal(rebuilt.reset_index(drop=True), self.s, check_dtype=False)


if __name__ == "__main__":
    unittest.main()
