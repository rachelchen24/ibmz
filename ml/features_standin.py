"""Stand-in preprocessor for the stronger model (Person 3) until Person 2's ml/preprocessing.py is merged (ws-a).

Same contract as the shared one (ml/PLAN.md, "agree on shared interfaces"):

    build_preprocessor() -> unfitted scikit-learn transformer
        input:  DataFrame with ml.cleaning.FEATURE_COLS (cleaned rows from ml.split.load_split())
        output: sparse matrix, one row per posting

ml/lgbm.py imports ml.preprocessing.make_preprocessor when that module exists and falls back to this one, so switching
over is just Person 2 adding their file. Everything here is fitted inside the pipeline, so on training folds only.

What it does: TF-IDF (words and bigrams) per text column, character length per text column (fraud postings are
shorter, ml/AUDIT.md), one-hot categories with an explicit MISSING level (missingness is predictive), and the
salary/binary columns as numbers with NaN left for LightGBM to route. Raw `location` and `salary_range` are covered
by their parsed columns (loc_*, salary_*).
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

from .cleaning import BINARY_COLS, CATEGORICAL_COLS, TEXT_COLS

CAT_COLS = CATEGORICAL_COLS + ["loc_country", "loc_state", "loc_city"]
NUM_COLS = ["salary_min", "salary_max", "salary_invalid"] + BINARY_COLS
MISSING = "MISSING"


# Module-level functions, not lambdas, so fitted pipelines pickle.
def fill_text(s: pd.Series) -> pd.Series:
    return s.astype(object).where(s.notna(), "").astype(str)


def text_lengths(X: pd.DataFrame) -> np.ndarray:
    return np.column_stack([X[c].str.len().fillna(0).to_numpy(dtype=np.float32) for c in X.columns])


def length_names(transformer, names_in) -> list[str]:
    return [f"{c}_len" for c in names_in]


def fill_categories(X: pd.DataFrame) -> pd.DataFrame:
    return X.astype(object).where(X.notna(), MISSING)


def to_float(X: pd.DataFrame) -> np.ndarray:
    return X.to_numpy(dtype=np.float32, na_value=np.nan)


def text_vectorizer() -> Pipeline:
    return Pipeline([
        ("fill", FunctionTransformer(fill_text, feature_names_out="one-to-one")),
        # 1,500 per column: ~8k columns in all, as accurate as 5,000 (~24k) on CV fold 0 and ~2x faster to fit
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_features=1500, sublinear_tf=True,
                                  dtype=np.float32)),
    ])


def build_preprocessor() -> ColumnTransformer:
    text = [(f"tfidf_{c}", text_vectorizer(), c) for c in TEXT_COLS]   # a bare column name passes a 1-D Series
    return ColumnTransformer(
        text + [
            ("lengths", FunctionTransformer(text_lengths, feature_names_out=length_names), TEXT_COLS),
            ("cat", Pipeline([
                ("fill", FunctionTransformer(fill_categories, feature_names_out="one-to-one")),
                ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=5, dtype=np.float32)),
            ]), CAT_COLS),
            ("num", FunctionTransformer(to_float, feature_names_out="one-to-one"), NUM_COLS),
        ],
        remainder="drop",
        sparse_threshold=1.0,   # always sparse: the TF-IDF blocks dominate
    )
