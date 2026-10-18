"""End-to-end tests for ml/run.py: clean -> features -> model -> ml.evaluate report, and scoring raw postings.

The saved-model tests use ml/models/*_v1.joblib when present (train them with `python -m ml.run train`) and are
skipped otherwise. Nothing here evaluates on the test split.
"""
import unittest

import numpy as np
import pandas as pd

from ml import run
from ml.cleaning import DATA_PATH, FEATURE_COLS, TARGET
from ml.split import SPLIT_CSV

HAVE_DATA = DATA_PATH.exists() and SPLIT_CSV.exists()
SCAM = {"title": "Data Entry Clerk - Work From Home", "description": "Earn weekly pay from home! Send your bank details.",
        "telecommuting": 1, "has_company_logo": 0, "has_questions": 0}


class ConstantModel:
    """Stands in for a fitted pipeline: checks it receives exactly the feature columns."""

    def predict_proba(self, X):
        assert list(X.columns) == list(FEATURE_COLS), "model must receive FEATURE_COLS in order"
        return np.column_stack([np.full(len(X), 0.7), np.full(len(X), 0.3)])


def fake_bundle(threshold=0.25):
    return {"model": ConstantModel(), "threshold": threshold, "threshold_source": "test",
            "feature_cols": list(FEATURE_COLS), "split_version": "v1"}


class ScoreRaw(unittest.TestCase):
    def test_partial_raw_posting_is_cleaned_and_scored(self):
        out = run.score_raw(fake_bundle(), [SCAM, {**SCAM, "title": "Clerk", "salary_range": "10-Oct"}])
        self.assertEqual(list(out.columns), ["job_id", "fraud_probability", "flagged"])
        self.assertEqual(len(out), 2)
        self.assertTrue(out["flagged"].all())                     # 0.3 >= 0.25

    def test_threshold_is_inclusive_and_respected(self):
        self.assertFalse(run.score_raw(fake_bundle(0.31), [SCAM])["flagged"].iloc[0])
        self.assertTrue(run.score_raw(fake_bundle(0.30), [SCAM])["flagged"].iloc[0])

    def test_missing_flags_are_rejected_not_guessed(self):
        bad = {k: v for k, v in SCAM.items() if k != "has_company_logo"}
        with self.assertRaises(ValueError):
            run.score_raw(fake_bundle(), [bad])

    def test_label_in_input_is_never_used(self):
        a = run.score_raw(fake_bundle(), [{**SCAM, "fraudulent": 1}])
        b = run.score_raw(fake_bundle(), [{**SCAM, "fraudulent": 0}])
        self.assertEqual(a["fraud_probability"].iloc[0], b["fraud_probability"].iloc[0])


class Guards(unittest.TestCase):
    def test_test_split_needs_final(self):
        with self.assertRaises(PermissionError):
            run.evaluate_model("lgbm", "test")
        with self.assertRaises(SystemExit):
            run.main(["evaluate", "--model", "lgbm", "--split", "test"])

    def test_unknown_model(self):
        with self.assertRaises(ValueError):
            run.bundle_path("xgboost")

    def test_predict_rejects_uncleaned_rows(self):
        with self.assertRaises(ValueError):
            run.predict(fake_bundle(), pd.DataFrame({"title": ["x"]}))


@unittest.skipUnless(HAVE_DATA, "needs data/fake_job_postings.csv and the split")
class EndToEndSmallFit(unittest.TestCase):
    """Real pipeline on a small slice: Person 2's baseline -> Person 4's evaluate(). About 15 seconds."""

    def test_fit_predict_evaluate(self):
        from ml.evaluate import evaluate
        from ml.preprocessing import make_logistic_baseline
        df = run.load_split()
        tr = df[df["split"] == "train"]
        tr = pd.concat([tr[tr[TARGET] == 1], tr[tr[TARGET] == 0].sample(2500, random_state=0)])
        val = df[df["split"] == "val"]
        bundle = {**fake_bundle(0.5), "model": make_logistic_baseline().fit(tr[FEATURE_COLS], tr[TARGET])}
        p = run.predict(bundle, val)
        self.assertEqual(p.shape, (len(val),))
        r = evaluate(val[TARGET].to_numpy(), p, val["group_id"].to_numpy(), threshold=0.5, n_boot=50)
        for key in ("ranking", "at_threshold", "operating_points", "calibration"):
            self.assertIn(key, r)
        self.assertGreater(r["ranking"]["pr_auc_lift_over_prevalence"], 3)   # far above guessing


@unittest.skipUnless(HAVE_DATA, "needs data/fake_job_postings.csv and the split")
class SavedModels(unittest.TestCase):
    def check(self, name):
        if not run.bundle_path(name).exists():
            self.skipTest(f"{name} not trained (python -m ml.run train --model {name})")
        b = run.load_bundle(name)
        self.assertEqual(b["feature_cols"], list(FEATURE_COLS))
        self.assertTrue(0 < b["threshold"] < 1)
        r = run.evaluate_model(name, "val", n_boot=50)
        self.assertEqual(r["split"], "val")
        self.assertGreater(r["ranking"]["pr_auc_lift_over_prevalence"], 5)
        scores = run.score_raw(b, [SCAM])
        self.assertTrue(0 <= scores["fraud_probability"].iloc[0] <= 1)

    def test_logreg(self):
        self.check("logreg")

    def test_lgbm(self):
        self.check("lgbm")


if __name__ == "__main__":
    unittest.main()
