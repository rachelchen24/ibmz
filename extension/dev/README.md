# Extension dev setup

## 1. Run the API

From the repo root:

```
py api/main.py              # Windows; python3 elsewhere. Add --no-granite to skip the Granite summaries
```

This serves the scam-risk API on http://localhost:8000 (see `api/README.md`). It needs the trained model at `ml/models/lgbm_v1.joblib`; if it's missing, run `py -3 -m ml.run train --model lgbm`.

## 2. Load the extension

1. Open `chrome://extensions` and turn on **Developer mode** (top right).
2. **Load unpacked** → choose the `extension/` folder.
3. After editing files, click the reload icon on the RealRole card, then reload the job page.

Chrome refuses to load an extension folder that contains `__pycache__`, so keep Python files out of `extension/`.

## 3. Try it

- **Sample listings:** open http://localhost:8000/demo. It has a scam-style listing and a typical listing, both carrying JobPosting data like a real job site. The badge appears under the title.
- **Real listings:** any job page on Greenhouse, Lever, Workday or LinkedIn.
- **Why?** opens the side panel with the reasons. The IBM Granite summary replaces the template sentence after about 20 seconds on a laptop CPU.

## What the extension sends

Only the listing's public content: the page's JobPosting data, or the visible title, description, company name and whether a logo is shown. It never sends anything about the person browsing. Scores are kept for the browser session only.
