import unittest

import numpy as np
import pandas as pd

from ml.cleaning import BINARY_COLS, FEATURE_COLS, RAW_COLUMNS, TEXT_COLS, clean
from ml.preprocessing import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    select_features,
    make_logistic_baseline,
)


def cleaned_rows():
    base = {column: pd.NA for column in RAW_COLUMNS}
    base.update({"telecommuting": 0, "has_company_logo": 1, "has_questions": 0, "fraudulent": 0})
    rows = []
    for index in range(8):
        row = {
            "job_id": index + 1,
            "title": f"Engineer opportunity team {index % 2}",
            "location": "US, CA, San Francisco" if index % 2 else pd.NA,
            "department": "Engineering" if index % 2 else pd.NA,
            "salary_range": "40000-60000" if index % 2 else pd.NA,
            "company_profile": "Acme builds useful software for customers" if index % 2 else pd.NA,
            "description": f"Join our engineering team and build service {index % 2}",
            "requirements": "Experience with software delivery and communication",
            "benefits": pd.NA if index % 2 else "Health coverage and paid leave",
            "telecommuting": index % 2,
            "has_company_logo": int(index % 2 == 0),
            "has_questions": int(index % 2 == 1),
            "employment_type": "Full-time" if index % 2 else pd.NA,
            "required_experience": "Entry level" if index % 2 else pd.NA,
            "required_education": "Bachelor's Degree" if index % 2 else pd.NA,
            "industry": "Technology" if index % 2 else pd.NA,
            "function": "Engineering" if index % 2 else pd.NA,
            "fraudulent": index % 2,
        }
        rows.append({**base, **row})
    return clean(pd.DataFrame(rows))


class FeatureSelection(unittest.TestCase):
    def test_selects_all_predictors_and_drops_identifier_and_target(self):
        frame = cleaned_rows().assign(unused_column="ignore")
        features = select_features(frame)
        self.assertEqual(features.columns.tolist(), FEATURE_COLS)
        self.assertNotIn("job_id", features.columns)
        self.assertNotIn("fraudulent", features.columns)
        self.assertEqual(len(features), len(frame))

    def test_rejects_missing_feature(self):
        frame = cleaned_rows().drop(columns=["title"])
        with self.assertRaisesRegex(ValueError, "title"):
            select_features(frame)

    def test_rejects_non_dataframe(self):
        with self.assertRaises(TypeError):
            select_features(np.zeros((2, 2)))


class PreprocessingPipeline(unittest.TestCase):
    def test_declared_transform_groups_cover_every_feature_once(self):
        groups = (
            TEXT_COLS
            + CATEGORICAL_FEATURES
            + NUMERIC_FEATURES
            + BINARY_COLS
            + ["salary_invalid"]
        )
        self.assertCountEqual(groups, FEATURE_COLS)
        self.assertEqual(len(groups), len(set(groups)))

    def test_mixed_missing_inputs_fit_and_predict_probabilities(self):
        frame = cleaned_rows()
        X = select_features(frame)
        y = frame["fraudulent"]
        model = make_logistic_baseline().fit(X, y)

        probabilities = model.predict_proba(X)
        self.assertEqual(probabilities.shape, (len(frame), 2))
        self.assertTrue(np.isfinite(probabilities).all())
        self.assertTrue(((probabilities >= 0) & (probabilities <= 1)).all())
        self.assertTrue(np.allclose(probabilities.sum(axis=1), 1))

    def test_unknown_categories_are_supported(self):
        frame = cleaned_rows()
        X = select_features(frame)
        y = frame["fraudulent"]
        model = make_logistic_baseline().fit(X, y)

        unseen = X.iloc[[0]].copy()
        unseen["industry"] = "Previously unseen industry"
        probabilities = model.predict_proba(unseen)
        self.assertEqual(probabilities.shape, (1, 2))
        self.assertTrue(np.isfinite(probabilities).all())


if __name__ == "__main__":
    unittest.main()
