# RealRole lookup website

Paste a job link, or the listing's text, and get its scam-risk check. It's the same report as the extension's side panel.

## Run

From the repo root, with the API running (`py api/main.py`):

```
py lookup/app.py        # or python3; standard library only
```

Open http://localhost:8501. Links also work as `?url=<job link>`.

## How it works

1. `POST /resolve {url}` (this server) reads the listing behind the link:
   - **Greenhouse and Lever:** their public job APIs.
   - **Anything else** (Workday, company careers sites): the page's own JobPosting data.
   - **LinkedIn, Indeed and Glassdoor** are never fetched, and private addresses are refused. In those cases the page asks for the listing's text instead.
2. The page sends the listing to the API's `POST /score`, exactly like the extension. It renders the result with `extension/report.js` + `report.css`, served here under `/shared/`.
3. It then calls `POST /summary`, and swaps in the IBM Granite summary when it arrives.
4. **Pasted text** is scored with `{"posting": {"title", "description"}, "pasted": true}`. Fields that weren't pasted separately (company description, requirements, benefits) are left out of the score, not counted as missing.

The server never logs the pasted link or text.

## For deployment (Workstream C)

Step 1 needs outbound internet. Without it, only pasted text works.
