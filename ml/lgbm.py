"""Stronger model: LightGBM on the shared features, tuned, calibrated and thresholded (Person 3, ml/PLAN.md).

    python -m ml.lgbm                     # tune (20 configs x 5 folds), calibrate, choose threshold, save
    python -m ml.lgbm --n-iter 40         # wider search
    python -m ml.lgbm --no-ablation       # skip the company_profile ablation (5 extra fits)
    python -m ml.lgbm --reuse-search      # skip tuning: refit from the last search (ml/models/lgbm_v1_search.json)

Data use follows ml/AUDIT.md and never touches the test split (that is Person 4's one final evaluation):
  train  random search over PARAM_SPACE, scored by PR-AUC (average precision) on the predefined group-aware cv_fold
         0-4. In each fold the preprocessor is fitted on the training rows only, and the number of trees is set by
         early stopping on a held-back, group-aware slice of those training rows, never on the fold being scored.
         The best config is refit on all of train with the median of its early-stopped tree counts.
  val    sigmoid (Platt) calibration of the frozen model, then the operating threshold: the one maximizing F1 on the
         calibrated validation probabilities. Sigmoid, not isotonic: val has only 122 fraud rows. Sigmoid is
         monotonic, so calibrating and thresholding on the same rows does not change which postings rank highest.

Outputs:
  ml/models/lgbm_v1.joblib     bundle {model, threshold, ...}; not in git. model.predict_proba(df[FEATURE_COLS])
  ml/reports/lgbm_v1.json      search results, chosen params, validation metrics, threshold trade-offs, ablation

The preprocessor is ml.preprocessing.make_preprocessor (Person 2's, on the ws-a branch until merged) when that
module exists, otherwise ml.features_standin. The report records which one was used. Rerun after switching.
"""
import argparse
import json
import time
import warnings
from pathlib import Path
from typing import NamedTuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, precision_recall_curve,
                             roc_auc_score)
from sklearn.model_selection import ParameterSampler, StratifiedGroupKFold
from sklearn.pipeline import Pipeline

from .cleaning import FEATURE_COLS, TARGET
from .split import VERSION, load_split

try:
    from .preprocessing import make_preprocessor as build_preprocessor   # Person 2's (ws-a branch until merged)
    PREPROCESSOR = "ml.preprocessing"
except ModuleNotFoundError as e:
    if e.name != f"{__package__}.preprocessing":
        raise   # ml/preprocessing.py exists but one of its own imports is missing: surface it, don't hide it
    from .features_standin import build_preprocessor
    PREPROCESSOR = "ml.features_standin"

SEED = 42
ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = ML_DIR / "models" / f"lgbm_{VERSION}.joblib"
REPORT_PATH = ML_DIR / "reports" / f"lgbm_{VERSION}.json"
SEARCH_PATH = ML_DIR / "models" / f"lgbm_{VERSION}_search.json"   # every config's CV result, saved right after tuning
ABLATE_COL = "company_profile"   # ml/AUDIT.md asks how much of the lift comes from it
ABLATED_TEXT = "ablated"         # the same text in every row: carries nothing, but text vectorizers still fit
PRECISION_TARGETS = (0.5, 0.7, 0.8, 0.9)
MAX_TREES = 2000   # a ceiling; early stopping picks the real count (often well under 200 at learning_rate 0.1)
PATIENCE = 50      # stop after this many trees without a better early-stopping PR-AUC
STOP_FOLDS = 7     # 1/7 of each fold's training rows (group-aware, stratified) is held back for early stopping

# Kept small and regularized: ~12.6k training rows and 612 fraud, and leaf-wise trees overfit small data.
# No n_estimators here: early stopping sets it.
PARAM_SPACE = {
    "num_leaves": [15, 31, 63],
    "min_child_samples": [10, 20, 50, 100],
    "learning_rate": [0.03, 0.05, 0.1],
    "colsample_bytree": [0.1, 0.3, 0.5],   # thousands of sparse TF-IDF columns
    "subsample": [0.7, 0.9, 1.0],
    "reg_lambda": [0.0, 1.0, 10.0],
    "class_weight": [None, "balanced"],
}


class Fold(NamedTuple):
    """One CV fold, preprocessed: fit = trees learn from it, stop = early stopping, score = PR-AUC."""
    X_fit: object
    y_fit: np.ndarray
    X_stop: object
    y_stop: np.ndarray
    X_score: object
    y_score: np.ndarray


def make_classifier(**params) -> LGBMClassifier:
    clf = LGBMClassifier(objective="binary", metric="average_precision", n_estimators=MAX_TREES, subsample_freq=1,
                         force_col_wise=True, random_state=SEED, n_jobs=-1, verbose=-1)
    return clf.set_params(**params)


def build_pipeline(**params) -> Pipeline:
    return Pipeline([("prep", build_preprocessor()), ("clf", make_classifier(**params))])


def train_val(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The only rows this model may learn from. Test rows are left out here and nowhere else."""
    train = df[df["split"] == "train"].reset_index(drop=True)
    val = df[df["split"] == "val"].reset_index(drop=True)
    if (train["cv_fold"] < 0).any():
        raise ValueError("train rows without a cv_fold: is this split_v1 from ml.split.load_split()?")
    return train, val


def xy(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    return df[FEATURE_COLS], df[TARGET].to_numpy()


def stopping_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(rows to fit trees on, rows to early-stop on), with no posting group on both sides."""
    sgkf = StratifiedGroupKFold(n_splits=STOP_FOLDS, shuffle=True, random_state=SEED)
    fit_idx, stop_idx = next(sgkf.split(df, df[TARGET], df["group_id"]))
    return df.iloc[fit_idx], df.iloc[stop_idx]


def prepare_folds(train: pd.DataFrame) -> list[Fold]:
    """Preprocess each CV fold once (fitted on that fold's tree-fitting rows only), for reuse by every config."""
    folds = []
    for k in sorted(train["cv_fold"].unique()):
        fit, stop = stopping_split(train[train["cv_fold"] != k])
        score = train[train["cv_fold"] == k]
        prep = build_preprocessor().fit(fit[FEATURE_COLS])
        folds.append(Fold(*[part for df in (fit, stop, score)
                            for part in (prep.transform(df[FEATURE_COLS]), df[TARGET].to_numpy())]))
    return folds


def fit_early_stopped(params: dict, X, y, X_stop, y_stop) -> LGBMClassifier:
    with warnings.catch_warnings():   # lightgbm 4.7 renamed eval_set; keep it so older 4.x still work
        warnings.filterwarnings("ignore", message="The argument 'eval_set' is deprecated")
        return make_classifier(**params).fit(X, y, eval_set=[(X_stop, y_stop)],
                                             callbacks=[early_stopping(PATIENCE, verbose=False)])


def evaluate(params: dict, folds: list[Fold]) -> dict:
    """CV PR-AUC of one config; predictions use each fold's early-stopped tree count."""
    t0 = time.time()
    scores, trees = [], []
    for f in folds:
        clf = fit_early_stopped(params, f.X_fit, f.y_fit, f.X_stop, f.y_stop)
        scores.append(average_precision_score(f.y_score, clf.predict_proba(f.X_score)[:, 1]))
        trees.append(int(clf.best_iteration_))
    return {"cv_pr_auc_mean": round(float(np.mean(scores)), 4), "cv_pr_auc_std": round(float(np.std(scores)), 4),
            "cv_pr_auc_folds": [round(float(s), 4) for s in scores], "trees_per_fold": trees,
            "seconds": round(time.time() - t0), "params": params}


def tune(train: pd.DataFrame, n_iter: int, log=print) -> list[dict]:
    """Every sampled config's CV result, best first."""
    folds = prepare_folds(train)
    configs = list(ParameterSampler(PARAM_SPACE, n_iter, random_state=SEED))
    results = []
    for i, params in enumerate(configs, 1):
        r = evaluate(params, folds)
        results.append(r)
        log(f"  [{i:2d}/{len(configs)}] CV PR-AUC {r['cv_pr_auc_mean']:.4f} ± {r['cv_pr_auc_std']:.4f}  "
            f"trees {r['trees_per_fold']}  {r['seconds']}s  {params}")
    return sorted(results, key=lambda r: -r["cv_pr_auc_mean"])


def final_trees(result: dict) -> int:
    return max(1, int(np.median(result["trees_per_fold"])))


def fit_final(train: pd.DataFrame, result: dict) -> Pipeline:
    """The chosen config refit on all training rows with a fixed tree count (no rows spent on early stopping)."""
    return build_pipeline(**result["params"], n_estimators=final_trees(result)).fit(*xy(train))


def calibrate(model, X_val: pd.DataFrame, y_val: np.ndarray) -> CalibratedClassifierCV:
    """Platt scaling on validation rows; the tuned model itself is frozen, not refit."""
    return CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid").fit(X_val, y_val)


def choose_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """The probability cut-off maximizing F1."""
    precision, recall, thresholds = precision_recall_curve(y, p)
    f1 = 2 * precision[:-1] * recall[:-1] / np.clip(precision[:-1] + recall[:-1], 1e-12, None)
    return float(thresholds[np.argmax(f1)])


def at_threshold(y: np.ndarray, p: np.ndarray, t: float) -> dict:
    pred = (p >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"threshold": round(t, 4), "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "flagged": int(tp + fp), "confusion": {"tn": int(tn), "fp": int(fp),
                                                                       "fn": int(fn), "tp": int(tp)}}


def threshold_tradeoffs(y: np.ndarray, p: np.ndarray) -> list[dict]:
    """For each precision target, the lowest threshold reaching it (so the most recall at that precision)."""
    precision, _, thresholds = precision_recall_curve(y, p)
    rows = []
    for target in PRECISION_TARGETS:
        ok = np.where(precision[:-1] >= target)[0]
        if len(ok):
            rows.append({"precision_target": target, **at_threshold(y, p, float(thresholds[ok[0]]))})
    return rows


def bootstrap_pr_auc(y: np.ndarray, p: np.ndarray, n: int = 1000) -> list[float]:
    """95% row-bootstrap interval. Validation has 122 fraud rows, so the point estimate alone overstates certainty."""
    rng = np.random.default_rng(SEED)
    scores = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].any():
            scores.append(average_precision_score(y[i], p[i]))
    return [round(float(q), 4) for q in np.percentile(scores, [2.5, 97.5])]


def validation_report(y: np.ndarray, p_raw: np.ndarray, p_cal: np.ndarray, t: float) -> dict:
    return {
        "rows": int(len(y)), "fraud": int(y.sum()), "prevalence": round(float(y.mean()), 4),
        "pr_auc": round(float(average_precision_score(y, p_cal)), 4),
        "pr_auc_95ci": bootstrap_pr_auc(y, p_cal),
        "roc_auc": round(float(roc_auc_score(y, p_cal)), 4),
        "brier_uncalibrated": round(float(brier_score_loss(y, p_raw)), 5),
        "brier_calibrated": round(float(brier_score_loss(y, p_cal)), 5),
        "brier_predict_prevalence": round(float(brier_score_loss(y, np.full(len(y), y.mean()))), 5),
        "operating_point": at_threshold(y, p_cal, t),
        "threshold_tradeoffs": threshold_tradeoffs(y, p_cal),
        "note": "Calibration and threshold were fitted on these rows, so these numbers are in-sample for both. "
                "The holdout estimate is Person 4's test evaluation.",
    }


def ablate(train: pd.DataFrame, params: dict) -> dict:
    """CV PR-AUC of the chosen config when the model never sees company_profile (not even whether it is missing).
    The column becomes one constant string rather than all-missing, which would leave a text vectorizer with an
    empty vocabulary."""
    blind = train.assign(**{ABLATE_COL: pd.Series(ABLATED_TEXT, index=train.index, dtype="string")})
    r = evaluate(params, prepare_folds(blind))
    return {"column": ABLATE_COL, **{k: r[k] for k in ("cv_pr_auc_mean", "cv_pr_auc_std", "cv_pr_auc_folds")}}


def top_features(model: Pipeline, n: int = 25) -> list[dict] | None:
    """Largest-gain features, or None if the preprocessor can't name its outputs (optional in the interface)."""
    try:
        names = model.named_steps["prep"].get_feature_names_out()
    except (AttributeError, ValueError):
        return None
    gain = model.named_steps["clf"].booster_.feature_importance(importance_type="gain")
    order = np.argsort(gain)[::-1][:n]
    total = gain.sum() or 1.0
    return [{"feature": str(names[i]), "gain_share": round(float(gain[i] / total), 4)} for i in order]


def load_model(path=MODEL_PATH) -> dict:
    """The saved bundle. bundle["model"].predict_proba(df[bundle["feature_cols"]])[:, 1] is the fraud probability;
    flag a posting when it is >= bundle["threshold"]."""
    return joblib.load(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-iter", type=int, default=20, help="hyperparameter configs to try (each is 5 CV fits)")
    ap.add_argument("--no-ablation", action="store_true", help=f"skip the {ABLATE_COL} ablation")
    ap.add_argument("--reuse-search", action="store_true", help=f"skip tuning and read {SEARCH_PATH.name}")
    args = ap.parse_args()

    t0 = time.time()
    log = lambda msg: print(msg, flush=True)
    log(f"preprocessor: {PREPROCESSOR}")
    train, val = train_val(load_split())
    X_val, y_val = xy(val)
    log(f"train {len(train)} rows ({int(train[TARGET].sum())} fraud), val {len(val)} rows ({int(y_val.sum())} fraud)")

    if args.reuse_search:
        results = json.loads(SEARCH_PATH.read_text(encoding="utf-8"))
        log(f"reusing {len(results)} configs from {SEARCH_PATH}")
    else:
        log(f"searching {args.n_iter} configs x {train['cv_fold'].nunique()} folds")
        results = tune(train, args.n_iter, log=log)
        SEARCH_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEARCH_PATH.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    best = results[0]
    log(f"best CV PR-AUC {best['cv_pr_auc_mean']:.4f} ± {best['cv_pr_auc_std']:.4f}  final trees {final_trees(best)}  "
        f"{best['params']}")

    model = fit_final(train, best)
    p_raw = model.predict_proba(X_val)[:, 1]
    calibrated = calibrate(model, X_val, y_val)
    p_cal = calibrated.predict_proba(X_val)[:, 1]
    threshold = choose_threshold(y_val, p_cal)
    val_metrics = validation_report(y_val, p_raw, p_cal, threshold)

    params = {**best["params"], "n_estimators": final_trees(best)}
    report = {
        "model": "lightgbm", "split_version": VERSION, "preprocessor": PREPROCESSOR, "seed": SEED,
        "selection": {"metric": "average_precision (PR-AUC)", "cv": "split_v1 cv_fold 0-4 (group-aware, train only)",
                      "early_stopping": f"PR-AUC on a 1/{STOP_FOLDS} group-aware slice of each fold's training rows, "
                                        f"patience {PATIENCE}; final model uses the median tree count",
                      "n_iter": len(results), "best": {**best, "final_params": params}, "all": results},
        "calibration": {"method": "sigmoid (Platt) on validation, model frozen"},
        "threshold": {"rule": "max F1 on calibrated validation probabilities", "value": round(threshold, 4)},
        "validation": val_metrics,
        "ablation": "skipped" if args.no_ablation else "pending",
        "top_features_by_gain": top_features(model),
        "runtime_seconds": round(time.time() - t0),
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": calibrated, "threshold": threshold, "feature_cols": FEATURE_COLS,
                 "split_version": VERSION, "preprocessor": PREPROCESSOR, "params": params}, MODEL_PATH)
    write_report(report)

    op = val_metrics["operating_point"]
    log(f"val PR-AUC {val_metrics['pr_auc']:.4f} {val_metrics['pr_auc_95ci']}  ROC-AUC {val_metrics['roc_auc']:.4f}  "
        f"Brier {val_metrics['brier_uncalibrated']:.5f} -> {val_metrics['brier_calibrated']:.5f}")
    log(f"threshold {threshold:.4f}: precision {op['precision']:.3f} recall {op['recall']:.3f} f1 {op['f1']:.3f} "
        f"({op['flagged']} flagged)")
    log(f"wrote {MODEL_PATH} and {REPORT_PATH}  ({report['runtime_seconds']}s)")

    if not args.no_ablation:   # last, so a failure here can't lose the model and report
        report["ablation"] = ablate(train, best["params"])
        write_report(report)
        log(f"without {ABLATE_COL}: CV PR-AUC {report['ablation']['cv_pr_auc_mean']:.4f} "
            f"± {report['ablation']['cv_pr_auc_std']:.4f} (with it: {best['cv_pr_auc_mean']:.4f})")


def write_report(report: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
