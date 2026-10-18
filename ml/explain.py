"""Why a posting got its fraud score: per-field contributions from the LightGBM model, as plain reasons.

    from ml.explain import Explainer
    ex = Explainer.from_bundle(load_bundle("lgbm"))
    ex.explain(cleaned_rows)   # one list of reasons per row

LightGBM's own feature contributions (booster.predict(pred_contrib=True), exact TreeSHAP values in log-odds, before
calibration) are summed per input field, so "description wording" is one reason rather than 300 TF-IDF terms; the
strongest terms are kept as evidence. Reasons describe what pushed the score up or down; they are not proof of fraud.

Explainer.score() also handles fields a live page does not provide (e.g. job sites rarely put a company
description in their JobPosting data, and in the training data a missing company description is a strong scam
signal). Those fields' contributions are removed, i.e. set to the training average (the TreeSHAP baseline),
before the model's own sigmoid calibration is applied, so "not shown on the page" neither raises nor lowers risk.
"""
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from .cleaning import TEXT_COLS

FIELD_LABEL = {
    "title": "job title", "company_profile": "company description", "description": "job description",
    "requirements": "requirements", "benefits": "benefits", "department": "department",
    "employment_type": "employment type", "required_experience": "required experience",
    "required_education": "required education", "industry": "industry", "function": "job function",
    "loc_country": "country", "loc_state": "state/region", "loc_city": "city", "salary_min": "salary",
    "salary_max": "salary", "salary_invalid": "salary", "telecommuting": "remote work",
    "has_company_logo": "company logo", "has_questions": "screening questions",
}
PLACEHOLDER_TERMS = {"url_token": "a link", "email_token": "an email address", "phone_token": "a phone number"}


def _pipeline_parts(bundle: dict):
    """(preprocessor, LGBMClassifier) inside ml.lgbm's CalibratedClassifierCV(FrozenEstimator(Pipeline))."""
    est = bundle["model"]
    if hasattr(est, "calibrated_classifiers_"):
        est = est.calibrated_classifiers_[0].estimator
    est = getattr(est, "estimator", est)          # FrozenEstimator -> Pipeline
    steps = dict(est.steps)
    clf = steps.get("clf") or est.steps[-1][1]
    if not hasattr(clf, "booster_"):
        raise TypeError("explanations need the LightGBM model (bundle 'lgbm')")
    return est.steps[0][1], clf


def feature_sources(pre) -> tuple[list[str], list[str]]:
    """(source field, detail) for every column the fitted preprocessor outputs, in order."""
    field, detail = [], []
    for name, trans, cols in pre.transformers_:
        if name == "remainder" or trans == "drop":
            continue
        cols = list(cols)
        if name.startswith("text_") and name != "text_missing":
            terms = trans.steps[-1][1].get_feature_names_out()
            field += [cols[0]] * len(terms)
            detail += [f"term:{t}" for t in terms]
        elif name == "text_missing":
            field += cols
            detail += ["missing"] * len(cols)
        elif name == "categorical":
            by_len = sorted(cols, key=len, reverse=True)   # longest prefix first (loc_state vs loc_...)
            for n in trans.steps[-1][1].get_feature_names_out(cols):
                c = next(c for c in by_len if n.startswith(c + "_"))
                field.append(c)
                detail.append(f"is:{n[len(c) + 1:]}")
        elif name == "numeric":
            names = trans.steps[0][1].get_feature_names_out(cols)
            field += [n.replace("missingindicator_", "") for n in names]
            detail += ["missing" if n.startswith("missingindicator_") else "value" for n in names]
        else:   # binary passthrough
            field += cols
            detail += ["flag"] * len(cols)
    return field, detail


def _sentence(field: str, row: pd.Series, terms: list[str], up: bool) -> str:
    lab = FIELD_LABEL.get(field, field.replace("_", " "))
    val = row.get(field)
    missing = val is None or (not isinstance(val, str) and pd.isna(val))
    if field in TEXT_COLS:
        if missing:
            return f"No {lab} given"
        if terms:
            shown = ", ".join(f"'{PLACEHOLDER_TERMS.get(t, t)}'" for t in terms[:3])
            return f"Wording in the {lab} (e.g. {shown})"
        return f"The {lab} as written"
    if field == "has_company_logo":
        return "No company logo" if int(val) == 0 else "Has a company logo"
    if field == "has_questions":
        return "No screening questions" if int(val) == 0 else "Has screening questions"
    if field == "telecommuting":
        return "Listed as remote / telecommute" if int(val) == 1 else "Not a remote role"
    if field.startswith("salary"):
        if row.get("salary_invalid") == 1:
            return "Salary field is malformed"
        if pd.isna(row.get("salary_max")):
            return "No salary given"
        return f"Salary range {int(row['salary_min']):,}-{int(row['salary_max']):,}"
    if missing:
        return f"No {lab} given"
    return f"{lab.capitalize()}: {val}"


class Explainer:
    def __init__(self, pre, clf, calibrator=None):
        self.pre, self.clf, self.calibrator = pre, clf, calibrator
        self.field, self.detail = feature_sources(pre)
        if len(self.field) != clf.booster_.num_feature():
            raise RuntimeError(f"feature map has {len(self.field)} columns, model has {clf.booster_.num_feature()}")
        self.fields = sorted(set(self.field))
        idx = {f: i for i, f in enumerate(self.fields)}
        self.field_idx = np.array([idx[f] for f in self.field])
        self.terms = np.array([d[5:] if d.startswith("term:") else "" for d in self.detail], dtype=object)

    @classmethod
    def from_bundle(cls, bundle: dict) -> "Explainer":
        m = bundle["model"]
        cal = m.calibrated_classifiers_[0].calibrators[0] if hasattr(m, "calibrated_classifiers_") else None
        return cls(*_pipeline_parts(bundle), calibrator=cal)

    def probability(self, raw_score: np.ndarray) -> np.ndarray:
        """Calibrated probability from the model's raw log-odds (the same mapping the saved model applies)."""
        if self.calibrator is not None:
            return np.clip(self.calibrator.predict(raw_score), 0, 1)
        return 1 / (1 + np.exp(-raw_score))

    def score(self, rows: pd.DataFrame, feature_cols: list[str], neutral=(), top: int = 3,
              threshold: float | None = None) -> tuple[np.ndarray, list[list[dict]]]:
        """(probabilities, reasons). Fields in `neutral` are left out: their contributions are removed from the
        score and they are never given as reasons."""
        per_field, raw = self.contributions(rows, feature_cols)
        bias = self._bias(rows, feature_cols)
        keep = np.array([f not in set(neutral) for f in self.fields])
        p = self.probability(bias + (per_field * keep).sum(1))
        flagged = p >= threshold if threshold is not None else None
        return p, self._reasons(rows, per_field * keep, raw * keep[self.field_idx], top, flagged)

    def _bias(self, rows, feature_cols) -> np.ndarray:
        c = self.clf.booster_.predict(self.pre.transform(rows[feature_cols].head(1)), pred_contrib=True)
        c = c.toarray() if hasattr(c, "toarray") else np.asarray(c)
        return np.full(len(rows), c[0, -1])   # expected value: the same for every row

    def contributions(self, rows: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """(per-field contributions [rows x fields], raw per-feature contributions) in log-odds. Also keeps which
        features are present in each row (self._present), so text evidence only quotes words in the listing."""
        Xt = self.pre.transform(rows[feature_cols])
        c = self.clf.booster_.predict(Xt, pred_contrib=True)   # sparse input -> sparse output
        c = (c.toarray() if hasattr(c, "toarray") else np.asarray(c))[:, :-1]
        self._present = (Xt != 0).toarray() if hasattr(Xt, "toarray") else np.asarray(Xt) != 0
        per_field = np.zeros((c.shape[0], len(self.fields)))
        np.add.at(per_field.T, self.field_idx, c.T)
        return per_field, c

    def explain(self, rows: pd.DataFrame, feature_cols: list[str], top: int = 3, flagged=None) -> list[list[dict]]:
        """Up to `top` reasons that raised the score and `top` that lowered it, strongest first. With `flagged`
        (one bool per row), the reasons agreeing with the verdict come first."""
        per_field, raw = self.contributions(rows, feature_cols)
        return self._reasons(rows, per_field, raw, top, flagged)

    def _reasons(self, rows, per_field, raw, top, flagged) -> list[list[dict]]:
        out = []
        for i, (_, row) in enumerate(rows.reset_index(drop=True).iterrows()):
            reasons = []
            order = np.argsort(-np.abs(per_field[i]))
            ups = [j for j in order if per_field[i, j] > 0.05][:top]
            downs = [j for j in order if per_field[i, j] < -0.05][:top]
            lead_down = flagged is not None and not bool(flagged[i])
            for j in (downs + ups if lead_down else ups + downs):
                f = self.fields[j]
                if f in ("telecommuting", "has_company_logo", "has_questions") and pd.isna(row.get(f)):
                    continue   # the page didn't show it; the model treated it as missing
                up = per_field[i, j] > 0
                terms = []
                if f in TEXT_COLS:
                    cols = np.where(self.field_idx == j)[0]
                    cc = raw[i, cols]
                    ranked = cols[np.argsort(-cc if up else cc)]
                    terms = [self.terms[k] for k in ranked[:40] if self._present[i, k]
                             and (raw[i, k] > 0) == up and abs(raw[i, k]) > 1e-3
                             and not set(self.terms[k].split()) <= ENGLISH_STOP_WORDS and len(self.terms[k]) > 2][:5]
                reasons.append({"field": f, "direction": "raises" if up else "lowers",
                                "weight": round(float(per_field[i, j]), 3), "terms": terms,
                                "text": _sentence(f, row, terms, up)})
            out.append(reasons)
        return out
