"""Leakage-safe feature preprocessing and logistic-regression baseline for fraud classification.

Inputs are cleaned rows from ``ml.cleaning.clean`` or ``ml.split.load_split``. Fit this pipeline on
training rows only; every imputer, category encoder, and TF-IDF vocabulary is learned during ``fit``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from .cleaning import (
    BINARY_COLS,
    CATEGORICAL_COLS,
    FEATURE_COLS,
    TEXT_COLS,
)

MISSING_CATEGORY = "__MISSING_CATEGORY__"
MISSING_TEXT = "MISSINGTEXTTOKEN"
TEXT_MAX_FEATURES = 30_000

CATEGORICAL_FEATURES = [
    *CATEGORICAL_COLS,
    "location",
    "salary_range",
    "loc_country",
    "loc_state",
    "loc_city",
]
NUMERIC_FEATURES = ["salary_min", "salary_max"]
BINARY_FEATURES = [*BINARY_COLS, "salary_invalid"]


def select_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Select the complete model feature set, rejecting incomplete inputs and excluding ID/label."""
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("features must be provided as a pandas DataFrame")
    missing = [column for column in FEATURE_COLS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing model feature columns: {missing}")
    return frame.loc[:, FEATURE_COLS].copy()


def _object_with_nan(values) -> np.ndarray:
    result = np.asarray(values, dtype=object).copy()
    result[pd.isna(result)] = np.nan
    return result


def _text_values(values) -> np.ndarray:
    result = np.asarray(values, dtype=object).reshape(-1)
    return np.asarray(
        [MISSING_TEXT if pd.isna(value) else str(value) for value in result],
        dtype=object,
    )


def _missing_flags(values) -> np.ndarray:
    return pd.isna(np.asarray(values, dtype=object)).astype(np.float64)


def _text_pipeline() -> Pipeline:
    return make_pipeline(
        FunctionTransformer(_text_values, validate=False),
        TfidfVectorizer(
            max_features=TEXT_MAX_FEATURES,
            min_df=2,
            ngram_range=(1, 2),
            sublinear_tf=True,
        ),
    )


def make_preprocessor() -> ColumnTransformer:
    """Create sparse mixed-feature transforms; all learned state is fitted by the returned pipeline."""
    text_columns = [
        (f"text_{column}", _text_pipeline(), [column])
        for column in TEXT_COLS
    ]
    return ColumnTransformer(
        [
            *text_columns,
            ("text_missing", FunctionTransformer(_missing_flags, validate=False), TEXT_COLS),
            (
                "categorical",
                make_pipeline(
                    FunctionTransformer(_object_with_nan, validate=False),
                    SimpleImputer(strategy="constant", fill_value=MISSING_CATEGORY),
                    OneHotEncoder(handle_unknown="ignore", min_frequency=2),
                ),
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                make_pipeline(
                    SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                    StandardScaler(),
                ),
                NUMERIC_FEATURES,
            ),
            ("binary", "passthrough", BINARY_FEATURES),
        ],
        remainder="drop",
        sparse_threshold=0.3,
        verbose_feature_names_out=False,
    )


def make_logistic_baseline() -> Pipeline:
    """Return a class-weighted sparse logistic baseline with all transforms inside the fit pipeline.

    Its probabilities are the baseline classifier's class-weight-adjusted outputs and are not calibrated;
    probability calibration is handled as a separate model-development step.
    """
    return Pipeline(
        [
            ("preprocess", make_preprocessor()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=2_000,
                    random_state=42,
                    solver="liblinear",
                ),
            ),
        ]
    )
