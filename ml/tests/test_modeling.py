import unittest

import numpy as np
import pandas as pd

from ml.cleaning import RAW_COLUMNS, TARGET, clean
from ml.modeling import (
    compare_models,
    fit_calibrated_stronger_model,
    make_stronger_model,
    select_f1_threshold,
)
from ml.preprocessing import select_features


def training_frame(rows=24):
    base = {column: pd.NA for column in RAW_COLUMNS}
    base.update({"telecommuting": 0, "has_company_logo": 1, "has_questions": 0, TARGET: 0})
    data = []
    for index in range(rows):
        label = index % 2
        data.append(
            {
                **base,
                "job_id": index + 1,
                "title": "Earn money immediately" if label else "Experienced engineer role",
                "location": "US, NY, New York" if label else "US, CA, San Francisco",
                "department": "Sales" if label else "Engineering",
                "company_profile": f"company group {index // 4} software and services",
                "description": (
                    "Work from home and receive guaranteed weekly payments"
                    if label
                    else "Join our established engineering team to build reliable software"
                ),
                "requirements": "No experience required" if label else "Relevant professional experience required",
                "benefits": "Weekly pay" if label else "Health insurance and paid leave",
                "telecommuting": label,
                "has_company_logo": 1 - label,
                "has_questions": 1 - label,
                "employment_type": "Contract" if label else "Full-time",
                "required_experience": "Entry level" if label else "Mid-Senior level",
                "required_education": "Unspecified" if label else "Bachelor's Degree",
                "industry": "Marketing" if label else "Computer Software",
                "function": "Sales" if label else "Engineering",
                TARGET: label,
                "cv_fold": (index // 4) % 3,
            }
        )
    return clean(pd.DataFrame(data))


class StrongerModel(unittest.TestCase):
    def test_stronger_model_uses_common_preprocessor(self):
        model = make_stronger_model()
        baseline_columns = select_features(training_frame())
        self.assertEqual(model.named_steps["preprocess"].transformers[0][0], "text_title")
        self.assertEqual(len(baseline_columns.columns), 22)
        self.assertEqual(model.named_steps["classifier"].class_weight, "balanced")

    def test_cv_comparison_returns_finite_average_precision(self):
        scores = compare_models(training_frame())
        self.assertEqual(set(scores), {"logistic", "linear_svc"})
        self.assertTrue(all(np.isfinite(score) and 0 <= score <= 1 for score in scores.values()))

    def test_calibrated_model_returns_class_one_probabilities(self):
        train = training_frame()
        model = fit_calibrated_stronger_model(train)
        probabilities = model.predict_proba(select_features(train))
        self.assertEqual(probabilities.shape, (len(train), 2))
        self.assertTrue(np.isfinite(probabilities).all())
        self.assertTrue(((probabilities >= 0) & (probabilities <= 1)).all())

    def test_threshold_selection_reports_validation_f1(self):
        result = select_f1_threshold([0, 0, 1, 1], [0.1, 0.4, 0.6, 0.9])
        self.assertEqual(result.threshold, 0.6)
        self.assertEqual(result.precision, 1.0)
        self.assertEqual(result.recall, 1.0)
        self.assertEqual(result.f1, 1.0)

    def test_threshold_selection_rejects_invalid_probabilities(self):
        with self.assertRaisesRegex(ValueError, "finite values"):
            select_f1_threshold([0, 1], [0.2, np.nan])


if __name__ == "__main__":
    unittest.main()
