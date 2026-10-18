"""Holdout evaluation and machine-readable metrics (Person 4; contract in ml/PLAN.md).

    python -m ml.evaluate --predictions preds.csv --split val --name logreg
    python -m ml.evaluate --predictions preds.csv --split test --name logreg --final

`preds.csv` needs a job_id column and a y_prob column. Report goes to ml/reports/metrics_<name>.json.
Evaluating on test needs --final, because test is for one evaluation at the end (ml/PLAN.md).

PR-AUC is primary, and its floor is the prevalence (~4.85%), not 0.5, so `pr_auc_lift_over_prevalence`
is the number that says whether a model beats guessing. ROC-AUC is reported but reads flatteringly on
this data: with ~17k negatives, an FPR small enough to keep ROC-AUC near 0.98 can still mean most flags
are wrong, so quote `precision` at a fixed recall operationally.

Confidence intervals resample whole *groups*, not rows. ml/AUDIT.md found no company with both real and
fraudulent postings, so the label is effectively per-company: test's 122 fraud rows sit in far fewer
independent groups, and a row bootstrap would report intervals that are too narrow.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score

from .cleaning import ID, TARGET
from .split import load_split

SCHEMA_VERSION = "1"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
PROB_COL = "y_prob"
RECALL_TARGETS = (0.50, 0.70, 0.80, 0.90)
DEFAULT_RECALL_TARGET = 0.80
N_BOOT = 1000
SEED = 42
CAL_BINS = 10


def threshold_for_recall(y, p, target: float) -> float:
    """Largest threshold whose `p >= t` rule still catches `target` of the positives."""
    pos = np.sort(np.asarray(p)[np.asarray(y) == 1])[::-1]
    if len(pos) == 0:
        raise ValueError("no positive rows, so no threshold can be chosen")
    k = min(max(int(np.ceil(target * len(pos))), 1), len(pos))
    return float(pos[k - 1])


def at_threshold(y, p, t: float) -> dict:
    """Counts and threshold-dependent metrics for the `p >= t` rule."""
    y = np.asarray(y)
    pred = (np.asarray(p) >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    prec = float(tp / (tp + fp)) if tp + fp else 0.0
    rec = float(tp / (tp + fn)) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"threshold": round(float(t), 6), "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
            "flagged": int(tp + fp), "flag_rate": round(float((tp + fp) / len(y)), 4)}


def _group_rows(groups) -> list:
    """Row indices for each distinct group, so a replicate can take whole groups at a time."""
    _, inv = np.unique(np.asarray(groups), return_inverse=True)
    order = np.argsort(inv, kind="stable")
    sorted_inv = inv[order]
    bounds = np.arange(sorted_inv[-1] + 1) if len(sorted_inv) else np.array([], dtype=int)
    starts = np.searchsorted(sorted_inv, bounds, side="left")
    ends = np.searchsorted(sorted_inv, bounds, side="right")
    return [order[s:e] for s, e in zip(starts, ends)]


def bootstrap_ci(y, p, groups, stat, n_boot: int = N_BOOT, seed: int = SEED, alpha: float = 0.05,
                 unit: str = "group") -> dict:
    """Percentile CI for `stat(y, p)`.

    unit="group" resamples groups and is the correct unit for this data; unit="row" exists only to show
    how much narrower (wrongly) a row bootstrap looks. Replicates that end up one-class are skipped,
    since PR-AUC is undefined there.
    """
    y, p = np.asarray(y), np.asarray(p)
    rng = np.random.default_rng(seed)
    units = _group_rows(groups) if unit == "group" else None
    vals, skipped = [], 0
    for _ in range(n_boot):
        if units is not None:
            pick = rng.integers(0, len(units), len(units))
            idx = np.concatenate([units[g] for g in pick])
        else:
            idx = rng.integers(0, len(y), len(y))
        yy = y[idx]
        if yy.min() == yy.max():
            skipped += 1
            continue
        vals.append(float(stat(yy, p[idx])))
    if not vals:
        return {"value": None, "ci_low": None, "ci_high": None, "replicates": 0, "skipped": skipped}
    return {"value": round(float(stat(y, p)), 4),
            "ci_low": round(float(np.percentile(vals, 100 * alpha / 2)), 4),
            "ci_high": round(float(np.percentile(vals, 100 * (1 - alpha / 2))), 4),
            "replicates": len(vals), "skipped": skipped}


def calibration(y, p, bins: int = CAL_BINS) -> dict:
    """Brier score plus a reliability table. The baseline predicts the prevalence for every row."""
    y, p = np.asarray(y), np.asarray(p)
    rate = float(y.mean())
    edges = pd.qcut(p, bins, duplicates="drop", retbins=True)[1]
    which = np.clip(np.searchsorted(edges, p, side="left") - 1, 0, len(edges) - 2)
    table, ece = [], 0.0
    for b in range(len(edges) - 1):
        m = which == b
        if not m.any():
            continue
        mean_p, frac_pos = float(p[m].mean()), float(y[m].mean())
        ece += m.sum() / len(y) * abs(mean_p - frac_pos)
        table.append({"bin": b, "rows": int(m.sum()), "mean_predicted": round(mean_p, 4),
                      "fraction_positive": round(frac_pos, 4), "positives": int(y[m].sum())})
    return {"brier": round(float(brier_score_loss(y, p)), 6),
            "brier_baseline_predict_prevalence": round(rate * (1 - rate), 6),
            "expected_calibration_error": round(float(ece), 4), "bins": table}


def evaluate(y, p, groups, *, threshold=None, recall_target: float = DEFAULT_RECALL_TARGET,
             threshold_source: str = "unspecified", n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """The metrics report. Pass `threshold` from validation or train OOF; deriving it here is not independent.

    `groups` must be the split's group_id, so the intervals resample companies rather than postings.
    """
    y, p = np.asarray(y), np.asarray(p)
    if y.ndim != 1 or p.shape != y.shape:
        raise ValueError(f"y and p must be 1-D and the same length, got {y.shape} and {p.shape}")
    if not np.isin(y, (0, 1)).all():
        raise ValueError("y must contain only 0 and 1")
    if np.isnan(p).any() or p.min() < 0 or p.max() > 1:
        raise ValueError("p must be probabilities in [0, 1] with no NaN")
    if len(np.unique(y)) < 2:
        raise ValueError("need both classes to evaluate")

    rate = float(y.mean())
    if threshold is None:
        threshold = threshold_for_recall(y, p, recall_target)
        threshold_source = "derived on this split (development only, not independent)"
    return {
        "schema_version": SCHEMA_VERSION,
        "rows": int(len(y)),
        "groups": int(pd.Series(groups).nunique()),
        "prevalence": {"positives": int(y.sum()), "rate": round(rate, 4)},
        "threshold": {"value": round(float(threshold), 6), "chosen_for_recall": recall_target,
                      "chosen_on": threshold_source},
        "ranking": {
            "pr_auc": bootstrap_ci(y, p, groups, average_precision_score, n_boot, seed),
            "roc_auc": bootstrap_ci(y, p, groups, roc_auc_score, n_boot, seed),
            "pr_auc_floor_is_prevalence": round(rate, 4),
            "pr_auc_lift_over_prevalence": round(float(average_precision_score(y, p)) / rate, 2),
        },
        "at_threshold": at_threshold(y, p, threshold),
        "operating_points": [at_threshold(y, p, threshold_for_recall(y, p, t)) | {"recall_target": t}
                             for t in RECALL_TARGETS],
        "calibration": calibration(y, p),
        "bootstrap": {"n": n_boot, "unit": "group", "seed": seed, "alpha": 0.05},
        "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__, "pandas": pd.__version__},
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def load_predictions(path, split: str, prob_col: str = PROB_COL) -> tuple:
    """Join a job_id/y_prob file to the split's labels and group_ids. Predictions must cover the split exactly."""
    preds = pd.read_csv(path)
    for c in (ID, prob_col):
        if c not in preds.columns:
            raise ValueError(f"{path} needs a {c} column, found {list(preds.columns)}")
    if preds[ID].duplicated().any():
        raise ValueError(f"{path} has duplicate {ID} values")
    rows = load_split()
    rows = rows[rows["split"] == split]
    if rows.empty:
        raise ValueError(f"split {split!r} has no rows")
    out = rows[[ID, TARGET, "group_id"]].merge(preds[[ID, prob_col]], on=ID, how="left", validate="one_to_one")
    missing = int(out[prob_col].isna().sum())
    if missing:
        raise ValueError(f"{path} is missing predictions for {missing} of {len(out)} {split} rows")
    return out[TARGET].to_numpy(), out[prob_col].to_numpy(dtype=float), out["group_id"].to_numpy()


def summary_lines(r: dict) -> list:
    pr, roc = r["ranking"]["pr_auc"], r["ranking"]["roc_auc"]
    op = r["at_threshold"]
    return [
        f"  rows {r['rows']}  groups {r['groups']}  fraud {r['prevalence']['positives']} "
        f"({r['prevalence']['rate']:.2%})",
        f"  PR-AUC  {pr['value']:.4f}  [{pr['ci_low']:.4f}, {pr['ci_high']:.4f}]   "
        f"{r['ranking']['pr_auc_lift_over_prevalence']}x the {r['prevalence']['rate']:.2%} floor",
        f"  ROC-AUC {roc['value']:.4f}  [{roc['ci_low']:.4f}, {roc['ci_high']:.4f}]   (flattering here; see docstring)",
        f"  at threshold {op['threshold']:.4f} ({r['threshold']['chosen_on']}):",
        f"    precision {op['precision']:.4f}  recall {op['recall']:.4f}  f1 {op['f1']:.4f}",
        f"    tp {op['tp']}  fp {op['fp']}  fn {op['fn']}  tn {op['tn']}   "
        f"flagged {op['flagged']} ({op['flag_rate']:.2%} of rows)",
        f"  Brier {r['calibration']['brier']:.6f}  (baseline {r['calibration']['brier_baseline_predict_prevalence']:.6f})"
        f"  ECE {r['calibration']['expected_calibration_error']:.4f}",
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Evaluate fraud-classifier predictions against a fixed split.")
    ap.add_argument("--predictions", required=True, help=f"CSV with {ID} and {PROB_COL} columns")
    ap.add_argument("--split", default="val", choices=["train", "val", "test"])
    ap.add_argument("--name", required=True, help="model name; report goes to ml/reports/metrics_<name>.json")
    ap.add_argument("--threshold", type=float, default=None,
                    help="operating threshold from validation or train OOF (Person 3). Omit only in development.")
    ap.add_argument("--recall-target", type=float, default=DEFAULT_RECALL_TARGET)
    ap.add_argument("--threshold-source", default="unspecified", help="where --threshold came from, for the report")
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--prob-col", default=PROB_COL)
    ap.add_argument("--final", action="store_true", help="required to evaluate on test (one evaluation, at the end)")
    ap.add_argument("--out", default=None, help="override the report path")
    a = ap.parse_args(argv)

    if a.split == "test" and not a.final:
        ap.error("evaluating on test needs --final; use --split val while developing (ml/PLAN.md)")

    y, p, groups = load_predictions(a.predictions, a.split, a.prob_col)
    report = evaluate(y, p, groups, threshold=a.threshold, recall_target=a.recall_target,
                      threshold_source=a.threshold_source, n_boot=a.n_boot, seed=a.seed)
    report = {"model": a.name, "split": a.split, "predictions_file": str(a.predictions), **report}

    out = Path(a.out) if a.out else REPORT_DIR / f"metrics_{a.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"=== {a.name} on {a.split} ===")
    print("\n".join(summary_lines(report)))
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
