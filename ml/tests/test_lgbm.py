"""python -m unittest discover -s ml/tests -t .   (synthetic data; no CSV needed)"""
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml import cleaning as C
from ml import features_standin as F
from ml import lgbm as L

TINY = {"n_estimators": 20, "num_leaves": 7, "min_child_samples": 5, "colsample_bytree": 1.0}


def synthetic(n=300, seed=0) -> pd.DataFrame:
    """Cleaned-looking rows in every FEATURE_COL; fraud rows say 'wire fee' and have no logo."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.2).astype("int8")
    words = np.array(["team", "growth", "customer", "sales", "engineer", "office", "benefits", "remote"])

    def text(i, extra=""):
        return " ".join(rng.choice(words, 8)) + (" wire fee upfront" if y[i] else "") + extra

    df = pd.DataFrame({c: pd.Series([pd.NA] * n, dtype="string") for c in C.FEATURE_COLS})
    for c in C.TEXT_COLS:
        df[c] = pd.Series([text(i) if rng.random() > 0.2 else pd.NA for i in range(n)], dtype="string")
    for c in F.CAT_COLS:
        df[c] = pd.Series(rng.choice(["a", "b", "c", None], n), dtype="string")
    df["salary_min"] = np.where(rng.random(n) < 0.8, np.nan, 30000.0)
    df["salary_max"] = df["salary_min"] + 10000
    df["salary_invalid"] = np.int8(0)
    df["telecommuting"] = rng.integers(0, 2, n).astype("int8")
    df["has_company_logo"] = (1 - y).astype("int8")
    df["has_questions"] = rng.integers(0, 2, n).astype("int8")
    df[C.TARGET] = y
    df["split"] = np.where(np.arange(n) < n * 0.7, "train", np.where(np.arange(n) < n * 0.85, "val", "test"))
    df["group_id"] = [f"g{i // 3:05d}" for i in range(n)]   # groups of 3, never split across cv folds
    df["cv_fold"] = np.where(df["split"] == "train", (np.arange(n) // 3) % 5, -1)
    return df


class StandInPreprocessor(unittest.TestCase):
    def test_sparse_one_row_per_posting(self):
        df = synthetic()
        Xt = F.build_preprocessor().fit_transform(df[C.FEATURE_COLS])
        self.assertTrue(hasattr(Xt, "tocsr"))
        self.assertEqual(Xt.shape[0], len(df))

    def test_unseen_category_and_all_missing_column(self):
        df = synthetic()
        prep = F.build_preprocessor().fit(df[C.FEATURE_COLS])
        new = df.head(5).copy()
        new["industry"] = pd.Series(["never seen"] * 5, dtype="string")
        new["benefits"] = pd.Series([pd.NA] * 5, dtype="string")
        self.assertEqual(prep.transform(new[C.FEATURE_COLS]).shape[0], 5)

    def test_feature_names_cover_every_column(self):
        df = synthetic()
        prep = F.build_preprocessor().fit(df[C.FEATURE_COLS])
        names = prep.get_feature_names_out()
        self.assertEqual(len(names), prep.transform(df[C.FEATURE_COLS]).shape[1])
        self.assertIn("lengths__description_len", names)

    def test_target_and_id_not_features(self):
        self.assertNotIn(C.TARGET, C.FEATURE_COLS)
        self.assertNotIn(C.ID, C.FEATURE_COLS)


class Model(unittest.TestCase):
    def test_train_val_excludes_test(self):
        train, val = L.train_val(synthetic())
        self.assertEqual(set(train["split"]) | set(val["split"]), {"train", "val"})

    def test_probabilities_shape_and_range(self):
        train, _ = L.train_val(synthetic())
        model = L.build_pipeline(**TINY).fit(*L.xy(train))
        p = model.predict_proba(L.xy(train)[0])
        self.assertEqual(p.shape, (len(train), 2))
        self.assertTrue(((p >= 0) & (p <= 1)).all())

    def test_calibrate_threshold_report_and_round_trip(self):
        train, val = L.train_val(synthetic())
        model = L.build_pipeline(**TINY).fit(*L.xy(train))
        X_val, y_val = L.xy(val)
        cal = L.calibrate(model, X_val, y_val)
        p = cal.predict_proba(X_val)[:, 1]
        t = L.choose_threshold(y_val, p)
        self.assertTrue(0 < t < 1)
        rep = L.validation_report(y_val, model.predict_proba(X_val)[:, 1], p, t)
        self.assertEqual(sum(rep["operating_point"]["confusion"].values()), len(val))
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "m.joblib"
            joblib.dump({"model": cal, "threshold": t}, path)
            np.testing.assert_allclose(L.load_model(path)["model"].predict_proba(X_val)[:, 1], p)

    def test_preprocessor_without_feature_names(self):
        """The interface only requires fit/transform; naming outputs is optional."""
        from sklearn.compose import ColumnTransformer
        from sklearn.preprocessing import FunctionTransformer
        train, _ = L.train_val(synthetic())
        prep = ColumnTransformer([("num", FunctionTransformer(F.to_float), F.NUM_COLS)])
        model = L.build_pipeline(**TINY).set_params(prep=prep).fit(*L.xy(train))
        self.assertIsNone(L.top_features(model))

    def test_stopping_split_keeps_groups_apart(self):
        train, _ = L.train_val(synthetic(600))
        fit, stop = L.stopping_split(train)
        self.assertEqual(len(fit) + len(stop), len(train))
        self.assertFalse(set(fit["group_id"]) & set(stop["group_id"]))

    def test_tune_ranks_configs_and_records_trees(self):
        train, _ = L.train_val(synthetic(600))
        results = L.tune(train, n_iter=2, log=lambda _: None)
        self.assertEqual(len(results), 2)
        self.assertGreaterEqual(results[0]["cv_pr_auc_mean"], results[1]["cv_pr_auc_mean"])
        for r in results:
            self.assertEqual(len(r["trees_per_fold"]), 5)
            self.assertTrue(all(1 <= t <= L.MAX_TREES for t in r["trees_per_fold"]))
        model = L.fit_final(train, results[0])
        self.assertEqual(model.named_steps["clf"].n_estimators, L.final_trees(results[0]))

    def test_ablation_runs_on_text_preprocessor(self):
        train, _ = L.train_val(synthetic(600))
        r = L.ablate(train, {"num_leaves": 7, "min_child_samples": 5, "colsample_bytree": 1.0})
        self.assertEqual(len(r["cv_pr_auc_folds"]), 5)

    def test_choose_threshold_maximizes_f1(self):
        y = np.array([0, 0, 0, 1, 1])
        p = np.array([0.1, 0.2, 0.6, 0.7, 0.9])
        self.assertEqual(L.choose_threshold(y, p), 0.7)


if __name__ == "__main__":
    unittest.main()
