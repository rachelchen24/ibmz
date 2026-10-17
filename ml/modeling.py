"""Training-fold model comparison and probability calibration for the fraud classifier."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from .cleaning import TARGET
from .preprocessing import make_logistic_baseline, make_preprocessor, select_features

SEED = 42


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    precision: float
    recall: float
    f1: float


def make_stronger_model() -> Pipeline:
    """LinearSVC is a sparse-text-capable alternative to logistic regression.

    Keep Person 2's preprocessing identical between models. Raw decision scores are for
    ranking only; use ``fit_calibrated_stronger_model`` for probability estimates.
    """
    return Pipeline(
        [
            ("preprocess", make_preprocessor()),
            (
                "classifier",
                LinearSVC(
                    class_weight="balanced",
                    random_state=SEED,
                    dual="auto",
                    max_iter=5_000,
                ),
            ),
        ]
    )


def _validate_train_frame(train: pd.DataFrame) -> None:
    required = {"cv_fold", TARGET}
    missing = sorted(required - set(train.columns))
    if missing:
        raise ValueError(f"training data is missing required columns: {missing}")
    if train.empty:
        raise ValueError("training data must not be empty")
    if train["cv_fold"].isna().any() or (train["cv_fold"] < 0).any():
        raise ValueError("training data must have a non-negative cv_fold for every row")
    if set(train[TARGET].unique()) != {0, 1}:
        raise ValueError("training data must contain both target classes 0 and 1")
    for fold in sorted(train["cv_fold"].unique()):
        validation_y = train.loc[train["cv_fold"] == fold, TARGET]
        fit_y = train.loc[train["cv_fold"] != fold, TARGET]
        if set(validation_y.unique()) != {0, 1} or set(fit_y.unique()) != {0, 1}:
            raise ValueError(f"cv_fold {fold} and its complement must both contain classes 0 and 1")


def _fold_splits(cv_folds: pd.Series) -> list[tuple[np.ndarray, np.ndarray]]:
    values = cv_folds.to_numpy()
    return [
        (np.flatnonzero(values != fold), np.flatnonzero(values == fold))
        for fold in sorted(np.unique(values))
    ]


def _positive_probability(model, X: pd.DataFrame) -> np.ndarray:
    classes = list(model.classes_)
    if 1 not in classes:
        raise ValueError("fitted classifier has no positive class 1")
    return model.predict_proba(X)[:, classes.index(1)]


def compare_models(train: pd.DataFrame) -> dict[str, float]:
    """Compare logistic regression and LinearSVC by group-aware out-of-fold average precision.

    The supplied frame must be the training partition from ``load_split``. Its precomputed
    ``cv_fold`` values ensure groups do not cross fit/validation folds. The holdout partitions
    are not accepted or inspected here.
    """
    _validate_train_frame(train)
    X = select_features(train)
    y = train[TARGET].to_numpy()
    folds = _fold_splits(train["cv_fold"])
    predictions = {
        "logistic": np.full(len(train), np.nan, dtype=float),
        "linear_svc": np.full(len(train), np.nan, dtype=float),
    }

    for fit_indices, validation_indices in folds:
        X_fit, X_validation = X.iloc[fit_indices], X.iloc[validation_indices]
        y_fit = y[fit_indices]
        logistic = make_logistic_baseline().fit(X_fit, y_fit)
        predictions["logistic"][validation_indices] = _positive_probability(logistic, X_validation)

        linear_svc = make_stronger_model().fit(X_fit, y_fit)
        predictions["linear_svc"][validation_indices] = linear_svc.decision_function(X_validation)

    scores = {}
    for name, values in predictions.items():
        if not np.isfinite(values).all():
            raise RuntimeError(f"out-of-fold predictions are incomplete for {name}")
        scores[name] = float(average_precision_score(y, values))
    return scores


def fit_calibrated_stronger_model(train: pd.DataFrame) -> CalibratedClassifierCV:
    """Fit sigmoid-calibrated LinearSVC using only the training partition and its group CV folds."""
    _validate_train_frame(train)
    X = select_features(train)
    y = train[TARGET].to_numpy()
    return CalibratedClassifierCV(
        estimator=make_stronger_model(),
        method="sigmoid",
        cv=_fold_splits(train["cv_fold"]),
        ensemble=True,
    ).fit(X, y)


def select_f1_threshold(y_true, probabilities) -> ThresholdResult:
    """Choose the validation threshold with the best F1; break ties by precision, then threshold."""
    y = np.asarray(y_true)
    p = np.asarray(probabilities, dtype=float)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or not len(y):
        raise ValueError("y_true and probabilities must be non-empty one-dimensional arrays of equal length")
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("y_true must contain both classes 0 and 1")
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("probabilities must be finite values in [0, 1]")

    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = np.divide(
        2 * precision[:-1] * recall[:-1],
        precision[:-1] + recall[:-1],
        out=np.zeros_like(precision[:-1]),
        where=(precision[:-1] + recall[:-1]) != 0,
    )
    best_f1 = float(f1.max())
    candidates = np.flatnonzero(np.isclose(f1, best_f1))
    best = max(candidates, key=lambda i: (precision[i], thresholds[i]))
    return ThresholdResult(
        threshold=float(thresholds[best]),
        precision=float(precision[best]),
        recall=float(recall[best]),
        f1=float(f1[best]),
    )
