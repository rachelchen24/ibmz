# Extension dev setup

## 1. Run the mock API

From the repo root (Python 3, standard library only):

```
py extension/dev/mock_api.py            # Windows; python3 elsewhere
```

It serves the public API contract (build plan 2.6) on http://localhost:8000. Every company in
`data/collect/shard_assignment.csv` gets the contract's example score (41% chance of a hire, so the
badge shows 59% ± 12%) with `model_version: "mock"`; any other name gets "Not in our dataset yet".

Run it as a script, not with `python -m`: Chrome refuses to load an extension folder that contains
`__pycache__`.

Options:
- `--force-p 0.85` gives every company that probability of a hire, to preview other color bands
  (0.85 → 15%, green; 0.20 → 80%, red).
- `?p=0.85` on `/company/{ticker}` does the same for one request.

## 2. Load the extension

1. Open `chrome://extensions` and turn on **Developer mode** (top right).
2. **Load unpacked** → choose the `extension/` folder.
3. After editing files, click the reload icon on the RealRole card, then reload the job page.

## 3. Try it

- Sample postings: http://localhost:8000/demo (a company in our dataset, one that isn't, and a page
  with no job title to show the floating fallback).
- Real pages: any Greenhouse, Workday or LinkedIn job posting from one of our 300 companies.
- Click **Tell me why** to open the side panel.

## Switching to the real API

Change `API_URL` in `extension/config.js`. Nothing else depends on the mock.
