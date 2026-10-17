# RealRole lookup website

Paste a job link, get the company's analysis: the same report as the extension's side panel.

## Run

From the repo root, with the API running (for now the mock: `py extension/dev/mock_api.py`):

```
py lookup/app.py        # or python3; standard library only
```

Open http://localhost:8501. Links also work as `?url=<job link>` or `?ticker=MDB`.

## How it works

1. `POST /resolve {url}` (this server) works out the company from the link:
   - from the URL alone, using the Greenhouse / Lever / Workday boards our collectors recorded in
     `data/collect/shard_*/ats_summary_*.csv`, or the company in a LinkedIn job URL;
   - only if that fails, by fetching the page's JobPosting data (or the Greenhouse board API).
     LinkedIn, Indeed and Glassdoor are never fetched; private addresses are refused.
2. The page sends the company name to the public API's `POST /score` (URL in
   `extension/config.js`), exactly like the extension, and renders the result with
   `extension/report.js` + `report.css`, served here under `/shared/`.
3. If the link can't be read, or the company isn't in our dataset, a company search box
   (`GET /companies/search`) takes over.

The server never logs the pasted link.

## For deployment (Workstream C)

- The board index comes from collection output for now. Once the store is up, it should come from
  the `ats` and `careers_url` columns of `companies`.
- Step 1's fallback fetch needs outbound internet. The build plan has `rr-lookup` talking to the API
  only; without internet, links still resolve from the URL alone and the rest fall back to search.
