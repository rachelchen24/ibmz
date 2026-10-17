"""Tests for ml/evaluate.py (Person 4). Synthetic data only, so the expected metrics are known exactly."""
import json
import unittest

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from ml.evaluate import (_group_rows, at_threshold, bootstrap_ci, calibration, evaluate,
                         threshold_for_recall)


def clustered(n_groups=60, per_group=8, rate=0.2, seed=0):
    """Groups of identical rows: the real sample size is n_groups, not n_groups * per_group."""
    rng = np.random.default_rng(seed)
    gy = (rng.random(n_groups) < rate).astype(int)
    gp = np.clip(gy * 0.5 + rng.normal(0.25, 0.12, n_groups), 0, 1)
    y = np.repeat(gy, per_group)
    p = np.repeat(gp, per_group)
    groups = np.repeat([f"g{i:03d}" for i in range(n_groups)], per_group)
    return y, p, groups


class ThresholdForRecall(unittest.TestCase):
    def test_catches_exactly_the_target_share(self):
        y = np.array([1] * 10 + [0] * 90)
        p = np.concatenate([np.linspace(0.9, 0.5, 10), np.full(90, 0.1)])
        t = threshold_for_recall(y, p, 0.8)
        self.assertEqual(int(((p >= t) & (y == 1)).sum()), 8)

    def test_rounds_up_so_recall_is_never_short(self):
        y = np.array([1] * 7 + [0] * 20)
        p = np.concatenate([np.linspace(0.9, 0.3, 7), np.full(20, 0.05)])
        t = threshold_for_recall(y, p, 0.8)   # 0.8 * 7 = 5.6 -> 6 positives
        self.assertEqual(int(((p >= t) & (y == 1)).sum()), 6)
        self.assertGreaterEqual(((p >= t) & (y == 1)).sum() / 7, 0.8)

    def test_full_recall_and_tiny_target_stay_in_range(self):
        y = np.array([1, 1, 1, 0, 0])
        p = np.array([0.9, 0.6, 0.3, 0.2, 0.1])
        self.assertEqual(int(((p >= threshold_for_recall(y, p, 1.0)) & (y == 1)).sum()), 3)
        self.assertEqual(int(((p >= threshold_for_recall(y, p, 0.0)) & (y == 1)).sum()), 1)

    def test_no_positives_raises(self):
        with self.assertRaises(ValueError):
            threshold_for_recall(np.zeros(5, dtype=int), np.linspace(0, 1, 5), 0.8)


class AtThreshold(unittest.TestCase):
    def test_counts_and_metrics(self):
        y = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
        p = np.array([0.9, 0.8, 0.4, 0.1, 0.7, 0.6, 0.2, 0.2, 0.1, 0.0])
        m = at_threshold(y, p, 0.5)   # flags 0.9 0.8 (tp) and 0.7 0.6 (fp)
        self.assertEqual((m["tp"], m["fp"], m["fn"], m["tn"]), (2, 2, 2, 4))
        self.assertEqual(m["tp"] + m["fp"] + m["fn"] + m["tn"], len(y))
        self.assertAlmostEqual(m["precision"], 0.5)
        self.assertAlmostEqual(m["recall"], 0.5)
        self.assertAlmostEqual(m["f1"], 0.5)
        self.assertEqual(m["flagged"], 4)
        self.assertAlmostEqual(m["flag_rate"], 0.4)

    def test_threshold_is_inclusive(self):
        y = np.array([1, 0])
        self.assertEqual(at_threshold(y, np.array([0.5, 0.4]), 0.5)["tp"], 1)

    def test_flagging_nothing_scores_zero_not_nan(self):
        m = at_threshold(np.array([1, 0, 0]), np.array([0.1, 0.2, 0.3]), 0.9)
        self.assertEqual((m["tp"], m["fp"]), (0, 0))
        self.assertEqual((m["precision"], m["recall"], m["f1"]), (0.0, 0.0, 0.0))


class RankingMetrics(unittest.TestCase):
    def test_perfect_separation(self):
        y = np.array([1] * 20 + [0] * 180)
        p = np.concatenate([np.full(20, 0.9), np.full(180, 0.1)])
        r = evaluate(y, p, np.arange(200), n_boot=50)
        self.assertAlmostEqual(r["ranking"]["pr_auc"]["value"], 1.0)
        self.assertAlmostEqual(r["ranking"]["roc_auc"]["value"], 1.0)

    def test_random_scores_give_roc_half_and_pr_auc_near_prevalence(self):
        """The point from ml/AUDIT.md: imbalance does not lift ROC-AUC, but it does set the PR-AUC floor."""
        rng = np.random.default_rng(7)
        n, rate = 8000, 0.05
        y = (rng.random(n) < rate).astype(int)
        p = rng.random(n)
        self.assertAlmostEqual(roc_auc_score(y, p), 0.5, delta=0.03)
        self.assertAlmostEqual(average_precision_score(y, p), y.mean(), delta=0.02)

    def test_lift_over_prevalence_reported(self):
        y = np.array([1] * 10 + [0] * 190)
        p = np.concatenate([np.full(10, 0.9), np.full(190, 0.1)])
        r = evaluate(y, p, np.arange(200), n_boot=50)
        self.assertAlmostEqual(r["ranking"]["pr_auc_floor_is_prevalence"], 0.05)
        self.assertAlmostEqual(r["ranking"]["pr_auc_lift_over_prevalence"], 20.0)


class Bootstrap(unittest.TestCase):
    def test_group_rows_partitions_every_row_once(self):
        groups = np.array(["b", "a", "b", "c", "a", "b"])
        rows = _group_rows(groups)
        self.assertEqual(sorted(len(r) for r in rows), [1, 2, 3])
        self.assertEqual(sorted(np.concatenate(rows).tolist()), list(range(6)))
        for r in rows:   # a group's rows all share one group label
            self.assertEqual(len(set(groups[r])), 1)

    def test_group_bootstrap_is_wider_than_row_bootstrap_on_clustered_data(self):
        """Resampling rows pretends duplicated postings are independent evidence, so its CI is too narrow."""
        y, p, groups = clustered()
        g = bootstrap_ci(y, p, groups, average_precision_score, n_boot=400, unit="group")
        r = bootstrap_ci(y, p, groups, average_precision_score, n_boot=400, unit="row")
        self.assertGreater(g["ci_high"] - g["ci_low"], 1.5 * (r["ci_high"] - r["ci_low"]))

    def test_interval_brackets_the_point_estimate(self):
        y, p, groups = clustered()
        ci = bootstrap_ci(y, p, groups, average_precision_score, n_boot=400)
        self.assertLessEqual(ci["ci_low"], ci["value"])
        self.assertLessEqual(ci["value"], ci["ci_high"])

    def test_reproducible_for_a_seed(self):
        y, p, groups = clustered()
        a = bootstrap_ci(y, p, groups, roc_auc_score, n_boot=100, seed=42)
        b = bootstrap_ci(y, p, groups, roc_auc_score, n_boot=100, seed=42)
        c = bootstrap_ci(y, p, groups, roc_auc_score, n_boot=100, seed=43)
        self.assertEqual(a, b)
        self.assertNotEqual(a["ci_low"], c["ci_low"])

    def test_one_class_replicates_are_skipped_not_counted(self):
        y = np.array([1] + [0] * 60)   # a single positive, so many replicates miss it
        p = np.concatenate([[0.9], np.full(60, 0.1)])
        ci = bootstrap_ci(y, p, np.arange(61), average_precision_score, n_boot=200)
        self.assertGreater(ci["skipped"], 0)
        self.assertEqual(ci["replicates"] + ci["skipped"], 200)


class Calibration(unittest.TestCase):
    def test_brier_and_baseline(self):
        y = np.array([1, 0, 1, 0])
        c = calibration(np.array([1, 0, 1, 0]), np.array([1.0, 0.0, 1.0, 0.0]), bins=2)
        self.assertAlmostEqual(c["brier"], 0.0)
        self.assertAlmostEqual(c["brier_baseline_predict_prevalence"], 0.25)   # 0.5 * 0.5
        self.assertAlmostEqual(y.mean(), 0.5)

    def test_well_calibrated_scores_have_small_error(self):
        rng = np.random.default_rng(3)
        p = rng.random(20000)
        y = (rng.random(20000) < p).astype(int)   # truly calibrated by construction
        self.assertLess(calibration(y, p)["expected_calibration_error"], 0.02)

    def test_overconfident_scores_are_caught(self):
        rng = np.random.default_rng(3)
        y = (rng.random(5000) < 0.1).astype(int)
        p = np.where(y == 1, 0.99, 0.95)   # ranks perfectly, wildly overconfident
        c = calibration(y, p)
        self.assertGreater(c["expected_calibration_error"], 0.5)
        self.assertGreater(c["brier"], c["brier_baseline_predict_prevalence"])

    def test_bins_cover_every_row(self):
        y, p, groups = clustered()
        self.assertEqual(sum(b["rows"] for b in calibration(y, p)["bins"]), len(y))


class Report(unittest.TestCase):
    def setUp(self):
        self.y, self.p, self.groups = clustered()

    def test_shape_and_json_serializable(self):
        r = evaluate(self.y, self.p, self.groups, n_boot=50)
        for key in ("schema_version", "rows", "groups", "prevalence", "threshold", "ranking",
                    "at_threshold", "operating_points", "calibration", "bootstrap", "versions"):
            self.assertIn(key, r)
        self.assertEqual(r["rows"], len(self.y))
        self.assertEqual(r["groups"], 60)
        self.assertEqual(r["prevalence"]["positives"], int(self.y.sum()))
        json.dumps(r)   # numpy scalars would raise here

    def test_derived_threshold_is_flagged_as_not_independent(self):
        r = evaluate(self.y, self.p, self.groups, n_boot=50)
        self.assertIn("not independent", r["threshold"]["chosen_on"])

    def test_supplied_threshold_is_used_verbatim(self):
        r = evaluate(self.y, self.p, self.groups, threshold=0.42, threshold_source="train OOF", n_boot=50)
        self.assertAlmostEqual(r["threshold"]["value"], 0.42)
        self.assertEqual(r["threshold"]["chosen_on"], "train OOF")
        self.assertEqual(r["at_threshold"], at_threshold(self.y, self.p, 0.42))

    def test_operating_points_trade_precision_for_recall(self):
        r = evaluate(self.y, self.p, self.groups, n_boot=50)
        recalls = [op["recall"] for op in r["operating_points"]]
        self.assertEqual(recalls, sorted(recalls))
        for op, target in zip(r["operating_points"], [0.5, 0.7, 0.8, 0.9]):
            self.assertGreaterEqual(op["recall"], target - 1e-9)
            self.assertEqual(op["recall_target"], target)


class InputValidation(unittest.TestCase):
    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            evaluate(np.array([1, 0, 1]), np.array([0.5, 0.5]), np.arange(3), n_boot=10)

    def test_rejects_non_binary_labels(self):
        with self.assertRaises(ValueError):
            evaluate(np.array([0, 1, 2]), np.array([0.1, 0.2, 0.3]), np.arange(3), n_boot=10)

    def test_rejects_probabilities_out_of_range(self):
        for bad in (np.array([0.1, 1.4]), np.array([-0.1, 0.5]), np.array([0.1, np.nan])):
            with self.assertRaises(ValueError):
                evaluate(np.array([0, 1]), bad, np.arange(2), n_boot=10)

    def test_rejects_single_class(self):
        with self.assertRaises(ValueError):
            evaluate(np.zeros(5, dtype=int), np.linspace(0, 1, 5), np.arange(5), n_boot=10)


if __name__ == "__main__":
    unittest.main()
