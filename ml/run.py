"""One entry point for the fraud classifier: train, predict, evaluate, score new postings (Person 4 integration).

    python -m ml.run train --model logreg            # Person 2's baseline (~1 min)
    python -m ml.run train --model lgbm              # Person 3's LightGBM (ml.lgbm: tune + calibrate, ~40 min)
    python -m ml.run evaluate --model lgbm --split val
    python -m ml.run evaluate --model lgbm --split test --final   # the one holdout evaluation, at the end
    python -m ml.run predict --model lgbm --split val --out preds.csv
    python -m ml.run score --model lgbm postings.csv  # new raw postings (same columns as the Kaggle CSV)

Every model is saved as the same bundle, ml/models/<name>_v1.joblib (git-ignored):
    {"model": fitted, "threshold": float, "threshold_source": str, "feature_cols": [...], "split_version": "v1"}
    bundle["model"].predict_proba(df[bundle["feature_cols"]])[:, 1] -> fraud probability in [0, 1]

Threshold rule (team decision 2026-10-17): the cut-off maximizing F1 on the validation split, for every model
(Person 3's ml.lgbm.choose_threshold). Validation's own precision/recall at that cut-off are therefore optimistic;
the test split, scored once with --final, gives the honest numbers.

Metrics go through ml.evaluate.evaluate (PR-AUC primary, group bootstrap), so every model's report has the same
schema: ml/reports/metrics_<name>_<split>.json. The test split needs --final.

A fraud probability is not a ghost-job probability: the label marks scam postings in EMSCAD (2012-2014).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .cleaning import BINARY_COLS, FEATURE_COLS, ID, RAW_COLUMNS, TARGET, clean
from .evaluate import REPORT_DIR, evaluate, summary_lines
from .split import VERSION, load_split

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODELS = ("logreg", "lgbm")


def bundle_path(name: str) -> Path:
    if name not in MODELS:
        raise ValueError(f"unknown model {name!r}; choose from {MODELS}")
    return MODEL_DIR / f"{name}_{VERSION}.joblib"


def load_bundle(name: str) -> dict:
    path = bundle_path(name)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run `python -m ml.run train --model {name}` first")
    b = joblib.load(path)
    if b.get("split_version") != VERSION:
        raise RuntimeError(f"{path} was trained on split {b.get('split_version')}, not {VERSION}: retrain it")
    b.setdefault("threshold_source", "max F1 on validation" if name == "lgbm" else "unspecified")
    return b


def predict(bundle: dict, df: pd.DataFrame) -> np.ndarray:
    """Fraud probabilities for cleaned rows (load_split() output or clean(raw))."""
    missing = [c for c in bundle["feature_cols"] if c not in df.columns]
    if missing:
        raise ValueError(f"rows are missing feature columns {missing}; pass cleaned rows (ml.cleaning.clean)")
    p = bundle["model"].predict_proba(df[bundle["feature_cols"]])[:, 1]
    if not np.isfinite(p).all() or p.min() < 0 or p.max() > 1:
        raise RuntimeError("model returned probabilities outside [0, 1]")
    return p


def score_raw(bundle: dict, postings: pd.DataFrame | list[dict], allow_unknown_flags: bool = False) -> pd.DataFrame:
    """Score new postings given in the raw Kaggle columns. job_id and fraudulent are optional. The three 0/1 flags
    (telecommuting, has_company_logo, has_questions) are required unless allow_unknown_flags, which leaves an absent
    flag missing instead of guessing it; only the LightGBM model accepts that (it handles missing values natively)."""
    raw = pd.DataFrame(postings).copy()
    missing_flags = [c for c in BINARY_COLS if c not in raw.columns or raw[c].isna().any()]
    if missing_flags and not allow_unknown_flags:
        raise ValueError(f"postings need 0/1 values for {missing_flags}")
    for c in BINARY_COLS:
        if c not in raw.columns:
            raw[c] = np.nan
    bad = [c for c in BINARY_COLS if not raw[c].dropna().isin([0, 1, True, False]).all()]
    if bad:
        raise ValueError(f"{bad} must be 0 or 1")
    if ID not in raw.columns:
        raw[ID] = np.arange(1, len(raw) + 1)
    raw[TARGET] = 0                      # placeholder so clean() sees the full schema; never used as input
    for c in RAW_COLUMNS:
        if c not in raw.columns:
            raw[c] = pd.NA
    for c in RAW_COLUMNS:
        if c not in (ID, TARGET, *BINARY_COLS):
            raw[c] = raw[c].astype("string")
    p = predict(bundle, clean(raw[RAW_COLUMNS]))
    return pd.DataFrame({ID: raw[ID].to_numpy(), "fraud_probability": p, "flagged": p >= bundle["threshold"]})


def clean_postings(postings: pd.DataFrame | list[dict]) -> pd.DataFrame:
    """Raw postings (Kaggle columns, any subset) -> cleaned rows, with absent flags left missing."""
    raw = pd.DataFrame(postings).copy()
    if ID not in raw.columns:
        raw[ID] = np.arange(1, len(raw) + 1)
    raw[TARGET] = 0
    for c in RAW_COLUMNS:
        if c not in raw.columns:
            raw[c] = np.nan if c in BINARY_COLS else pd.NA
    for c in RAW_COLUMNS:
        if c not in (ID, TARGET, *BINARY_COLS):
            raw[c] = raw[c].astype("string")
    return clean(raw[RAW_COLUMNS])


def train_logreg(log=print) -> dict:
    """Person 2's class-weighted logistic baseline fitted on all of train. Out-of-fold PR-AUC on the train CV folds
    is recorded for model comparison; the threshold uses the same rule as LightGBM (max F1 on validation)."""
    from sklearn.metrics import average_precision_score

    from .lgbm import choose_threshold
    from .preprocessing import make_logistic_baseline, select_features

    df = load_split()
    train = df[df["split"] == "train"].reset_index(drop=True)
    X, y = select_features(train), train[TARGET].to_numpy()
    oof = np.full(len(train), np.nan)
    for k in sorted(train["cv_fold"].unique()):
        hold = (train["cv_fold"] == k).to_numpy()
        oof[hold] = make_logistic_baseline().fit(X[~hold], y[~hold]).predict_proba(X[hold])[:, 1]
        log(f"  fold {k}: PR-AUC {average_precision_score(y[hold], oof[hold]):.4f}")
    model = make_logistic_baseline().fit(X, y)
    val = df[df["split"] == "val"]
    threshold = choose_threshold(val[TARGET].to_numpy(), model.predict_proba(select_features(val))[:, 1])
    bundle = {"model": model, "threshold": threshold, "threshold_source": "max F1 on validation",
              "feature_cols": list(FEATURE_COLS), "split_version": VERSION,
              "cv_oof_pr_auc": float(average_precision_score(y, oof))}
    log(f"  train OOF PR-AUC {bundle['cv_oof_pr_auc']:.4f}; threshold {threshold:.4f} ({bundle['threshold_source']})")
    return bundle


def train(name: str, log=print) -> Path:
    path = bundle_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if name == "logreg":
        joblib.dump(train_logreg(log), path)
    else:   # Person 3's script owns tuning and calibration and saves its own bundle at the same path
        from . import lgbm
        if Path(lgbm.MODEL_PATH) != path:
            raise RuntimeError(f"ml.lgbm saves to {lgbm.MODEL_PATH}, expected {path}")
        saved, sys.argv = sys.argv, [sys.argv[0]]
        try:
            lgbm.main()
        finally:
            sys.argv = saved
    log(f"  saved {path}")
    return path


def evaluate_model(name: str, split: str, final: bool = False, n_boot: int = 1000) -> dict:
    if split == "test" and not final:
        raise PermissionError("the test split is for the one final evaluation: pass final=True / --final")
    bundle = load_bundle(name)
    df = load_split()
    rows = df[df["split"] == split]
    p = predict(bundle, rows)
    report = evaluate(rows[TARGET].to_numpy(), p, rows["group_id"].to_numpy(), threshold=bundle["threshold"],
                      threshold_source=bundle["threshold_source"], n_boot=n_boot)
    return {"model": name, "split": split, **report}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Train, evaluate and use the fraud classifier.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--model", choices=MODELS, required=True)
    for cmd in ("evaluate", "predict"):
        s = sub.add_parser(cmd)
        s.add_argument("--model", choices=MODELS, required=True)
        s.add_argument("--split", choices=["train", "val", "test"], default="val")
        s.add_argument("--final", action="store_true", help="required for --split test")
        if cmd == "predict":
            s.add_argument("--out", required=True)
        else:
            s.add_argument("--n-boot", type=int, default=1000)
    sc = sub.add_parser("score")
    sc.add_argument("--model", choices=MODELS, required=True)
    sc.add_argument("postings", help="CSV of new postings in the raw Kaggle columns")
    sc.add_argument("--out", help="write scores here (default: print)")
    a = ap.parse_args(argv)

    t0 = time.time()
    if a.cmd == "train":
        print(f"=== training {a.model} ===")
        train(a.model)
    elif a.cmd in ("evaluate", "predict"):
        if a.split == "test" and not a.final:
            ap.error("the test split is for the one final evaluation: add --final")
        if a.cmd == "evaluate":
            r = evaluate_model(a.model, a.split, a.final, a.n_boot)
            out = REPORT_DIR / f"metrics_{a.model}_{a.split}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(r, indent=2), encoding="utf-8")
            print(f"=== {a.model} on {a.split} ===")
            print("\n".join(summary_lines(r)))
            print(f"  wrote {out}")
        else:
            df = load_split()
            rows = df[df["split"] == a.split]
            pd.DataFrame({ID: rows[ID], "y_prob": predict(load_bundle(a.model), rows)}).to_csv(a.out, index=False)
            print(f"wrote {len(rows)} predictions to {a.out}")
    else:
        scores = score_raw(load_bundle(a.model), pd.read_csv(a.postings))
        if a.out:
            scores.to_csv(a.out, index=False)
            print(f"wrote {len(scores)} scores to {a.out}")
        else:
            print(scores.to_string(index=False))
    print(f"({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
