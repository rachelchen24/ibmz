# RealRole API

The scam-risk score for one job listing. The extension, the lookup site and the demo pages all call it.

```
py api/main.py                    # http://localhost:8000; needs ml/models/lgbm_v1.joblib
py api/main.py --no-granite       # template summaries only (no Granite model download)
python -m unittest discover -s api/tests -t .
```

It uses only the standard library plus `ml/` and its requirements.

## `POST /score`

Request, one of:

```json
{"jobposting": {"@type": "JobPosting", "title": "...", "description": "<p>...</p>", "hiringOrganization": {"name": "...", "logo": "..."}}, "source": "greenhouse"}
{"posting": {"title": "...", "description": "...", "has_company_logo": 1}}
{"posting": {"title": "...", "description": "..."}, "pasted": true}
```

- **`jobposting`:** the schema.org JobPosting a job page embeds (or one built from the visible page).
- **`posting`:** fields in the training data's columns.
- **`pasted: true`:** text a person pasted. It's treated like a page.

Response, in about 150 ms:

```json
{
  "listing": {"title": "Data Entry Clerk - Work From Home", "company": "Global Staffing Partners", "source": "demo"},
  "risk": 0.7389, "risk_pct": 74, "flagged": true, "band": "high", "label": "High scam risk (74%)",
  "reasons": [{"field": "description", "direction": "raises", "weight": 2.9, "terms": ["earn", "home"],
               "text": "Wording in the job description (e.g. 'earn', 'home', 'no experience')"}],
  "summary": "This posting shows signs often seen in scam postings (74% risk): ...", "summary_source": "template",
  "granite_backend": "local",
  "left_out": ["company_profile", "requirements", "benefits", "has_company_logo", "has_questions"],
  "unknown_inputs": ["has_questions", "..."],
  "threshold": 0.1527, "model": {"name": "lgbm", "test": {"pr_auc": 0.739, "precision": 0.659, "recall": 0.68}},
  "disclaimer": "An automated estimate ... not proof of fraud ...", "latency_ms": 142.0
}
```

- **`band`:** `high` when flagged (risk ≥ threshold); `medium` when risk is at or above the 4.85% base rate; `low` otherwise.
- **`reasons`:** the strongest per-field contributions (LightGBM TreeSHAP). The ones that agree with the verdict come first.
- **`left_out`:** fields the page didn't provide (company description, requirements, benefits, logo, screening questions). Their contribution is set to the training average, so "not shown" doesn't read as "missing", which is a scam signal in the training data. See `docs/model-card.md`.

## `POST /summary`

Send `{"risk", "flagged", "reasons"}` from `/score` and get back `{"summary", "summary_source", "latency_ms"}`.

- **IBM Granite** writes one sentence from the reasons only.
- **`summary_source`** is `granite-local:<model>`, `granite-watsonx:<model>`, or `template`. A template is used when Granite is unavailable, or when its draft fails the wording check (no accusations or speculation).
- **Timing:** about 20 s on a laptop CPU, so clients show the template first and swap this in.

Backends (environment variables):
- `RR_GRANITE`: `auto` (default), `local`, `watsonx` or `off`.
- `GRANITE_MODEL`: default `ibm-granite/granite-3.1-1b-a400m-instruct`.
- `WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `WATSONX_MODEL`: for watsonx.

## Other endpoints

- `GET /health`: the model, the threshold, the test metrics and the Granite backend.
- `GET /demo`: sample listing pages with JobPosting JSON-LD, for trying the extension.
- `GET /demo/jobposting?case=scam|real`: the same samples as JSON.

## Privacy

- Requests carry only the listing's public content.
- Nothing is stored, request bodies are never logged, and errors never echo the request.
- CORS is open (`*`), so the extension and lookup site can call it. Tighten this for production.
