# D: Extension badge and "Tell me why" side panel (DRAFT master prompt)

> Status: draft for Rachel to edit. Covers build plan 1D-1 and the badge parts of 2D-1.
> Not sent yet.

## Goal

Build the RealRole Chrome extension (Manifest V3) in `extension/`. When a person views a job posting
from one of the 300 companies in our dataset, a small badge appears automatically next to the job
title, showing how likely that company is to hire from its postings. A "Tell me why" button opens
Chrome's side panel with the full breakdown. On postings from companies **not** in our dataset, the
extension shows **nothing** on the page.

Until the real API exists, the extension talks to a local mock API (`extension/dev/mock_api.py`)
that follows the public API contract exactly, so switching to Michael's real API later is only a
change of `API_URL`.

## Decisions already made

- **Branch / folders:** work on the `rachel` branch; edit only `extension/` (Workstream D). Do not
  create or edit `api/`, `common/`, `CONTRACTS.md` or anything owned by other workstreams.
- **Sites (v1):** Greenhouse, Workday, LinkedIn. Lever is out of scope for now.
- **Appears only for known companies:** if the API says `in_dataset: false`, or the call fails, or no
  company name is found, render nothing on the page. (The popup, below, still says "Not in our dataset
  yet" if opened.)
- **Placement:** inline, directly next to / under the job title. If the title anchor can't be found,
  fall back to a floating pill fixed at the bottom-right of the viewport.
- **Collapsed badge shows only:** one sentence with the company name, the chance its postings don't
  lead to a hire, and a ± uncertainty; a color bar; and a "Tell me why" button. No reasons, sources or
  sector stats in the collapsed state.
- **Framing is flipped from the API:** the API returns `probability` = chance a posting leads to a
  hire. The extension shows **`no_hire = 1 − probability`**, e.g. "59% ± 12% chance Acme Corp's
  postings don't lead to a hire." The API contract is unchanged; only the extension's display flips.
- **Color:** green / amber / red bands by `no_hire` (thresholds below); higher `no_hire` = redder.
- **Details:** open in Chrome's **side panel** (`chrome.sidePanel`), not inline.
- **Mock data:** the mock matches the company name against our real 300-company list and returns
  the contract's example score (probability 0.41, range [0.30, 0.53], the example reasons) with that
  company's real name, ticker and sector filled in. Unknown names → `in_dataset: false`.

## Inputs

- API contract: `realrole-build-plan.md` §2.6 (`POST /score` request/response, `GET /company/{ticker}`,
  `GET /health`, and the "not in dataset" shape). Follow it field for field.
- Company list for the mock: `data/collect/shard_assignment.csv` (300 rows: `ticker, name, sector,
  priority_tier, shard`). Read by the mock only; never bundled into the extension.
- Name rules (for the mock's simple matcher): `realrole-build-plan.md` §2.3 `normalize_company`:
  lowercase; strip punctuation; drop `inc, llc, ltd, corp, corporation, co, company, the, group,
  holdings, plc`; collapse spaces. Then exact match on normalized name, then fuzzy match ≥ 0.90
  (stdlib `difflib.SequenceMatcher` is fine), else not found.

## What to build

### 1. `extension/` layout

```
extension/
├── manifest.json
├── config.js          # API_URL and color thresholds, the only place they're defined
├── background.js      # service worker: API calls, per-tab state, opens the side panel
├── content.js         # finds the company + title anchor, renders the badge
├── sites/
│   ├── greenhouse.js
│   ├── workday.js
│   └── linkedin.js
├── badge.css          # loaded into the badge's shadow root
├── sidepanel.html / sidepanel.js / sidepanel.css
├── popup.html / popup.js   # minimal: status for the current tab, link to open side panel
├── icons/
└── dev/
    ├── mock_api.py
    └── README.md      # how to run the mock and load the extension unpacked
```

### 2. Company detection (`sites/*.js`)

Each site module exports `match(url)`, `getCompanyName(document)` and `getTitleAnchor(document)`.

- **Greenhouse** (`boards.greenhouse.io`, `job-boards.greenhouse.io`, and embedded `?gh_jid=` boards
  where detectable): read `hiringOrganization.name` from `<script type="application/ld+json">`
  `JobPosting` data, including when nested inside `@graph` or arrays. Title anchor: the posting's `h1`.
- **Workday** (`*.myworkdayjobs.com`): same JSON-LD approach first; fall back to the visible company
  name if needed. Workday is a single-page app, so re-run detection when the URL changes (watch
  `history` navigation / a `MutationObserver`, debounced).
- **LinkedIn** (`linkedin.com/jobs/*`): no JSON-LD; read the employer from the visible job details
  (company link text / ARIA labels in the top card). Also a single-page app: re-run on URL change and
  when the selected job changes in the list view; remove the old badge before rendering a new one.
- Keep selectors in one clearly commented block per site, since they will break when sites change.

### 3. Badge (`content.js`, `badge.css`)

- Rendered inside a **Shadow DOM** host element so page CSS can't affect it and ours can't leak out.
  Prefix the host element's id/class with `realrole-`.
- Collapsed content (one line where space allows):
  `[color bar] 59% ± 12% chance Acme Corp's postings don't lead to a hire   [Tell me why]`
  - `no_hire = 1 − probability`, shown as a whole percent.
  - `± = (range_high − range_low) / 2`, rounded to a whole percent (the API's range can be
    asymmetric; the ± is its half-width, and the side panel shows the exact range).
  - Company name is `company.name` from the API, tidied for display (drop a trailing "Inc.", ", Inc",
    "Corp", etc., and fix ALL-CAPS names to title case).
  - The color bar is a thin horizontal bar filled to `no_hire`, colored by band, with the ± shown as
    a lighter segment on the same bar.
  - Small "RealRole" wordmark or icon so people know where the badge comes from.
- Bands on `no_hire` (in `config.js`): **green < 0.40**, **amber 0.40–0.65**, **red ≥ 0.65**. Colors
  must pass WCAG AA contrast for the text on them.
- "Tell me why" sends a message to the service worker, which calls `chrome.sidePanel.open` for the
  current tab (must happen inside the user gesture path) and passes the score data to the panel.
- Fallback: if `getTitleAnchor` returns nothing, render the same badge as a floating pill fixed at
  bottom-right, with a small close (×) button.
- Dev-only color preview: if `config.js` has `DEV_FORCE_PROBABILITY` set, use it instead of the API's
  value so all three bands can be checked. Off by default.

### 4. Side panel (`sidepanel.*`)

Shows the full `/score` response for the company on the current tab:

- Company name, ticker, sector; the same sentence as the badge (`no_hire` ± uncertainty), the exact
  range ("between 47% and 70%"), and the color bar (bigger).
- `summary` sentence.
- Sector comparison: sector median and this company's percentile.
- Reasons list: each reason's text, a "lowers / raises the likelihood" marker from `direction`, and its
  evidence: source link (opens in a new tab), the quote, and the page date.
- Employer response, if any.
- Footer: `refreshed_at`, `model_version`, and a one-line explainer: "A company-level likelihood based
  on public data, not a verdict on this posting."
- If the active tab changes, the panel updates to that tab's company (or shows "No RealRole data for
  this page").

### 5. Service worker (`background.js`)

- Receives `{company_name, source}` from the content script; calls `POST {API_URL}/score` with
  exactly that body and nothing else.
- Caches responses in memory (or `chrome.storage.session`) by normalized company name for the browser
  session, so revisiting the same company doesn't re-call the API. No persistent storage of what the
  person viewed.
- Keeps per-tab state (the last score for each tab) for the side panel and popup.
- On network error or non-200: treat as "no badge"; log a short warning to the console (no page URLs).

### 6. `manifest.json`

MV3; `permissions`: `sidePanel`, `storage`; `host_permissions` only for the three sites plus
`http://localhost:8000/*`; content scripts only on the three sites' job pages. No `<all_urls>`, no
`tabs`/`history` permission unless strictly required (say why if so).

### 7. Mock API (`extension/dev/mock_api.py`)

- Python standard library only (`http.server`, `json`, `csv`, `difflib`); runs with
  `python -m extension.dev.mock_api` from the repo root on port 8000.
- Endpoints: `POST /score`, `GET /company/{ticker}`, `GET /companies/search?q=`, `GET /health`.
  Shapes exactly as §2.6.
- Known company → the contract's example response with that company's `ticker`, `name`, `sector`,
  `matched_from` (the name sent) and `match_confidence` filled in; `model_version: "mock"`;
  `score_version: "<TICKER>-mock"`. Unknown → the "not in dataset" shape.
- Optional `?p=0.72` query param on `/score` / `/company` to override the probability (and shift
  the range around it) for testing bands.
- CORS headers allowing the extension.
- Never logs request bodies beyond the company name.

## Constraints (from the plan's AGENTS.md rules)

- Send only the company name and source site. Never send the page URL, posting text, or anything
  about the person.
- Wording is likelihood only, friendly and plain: "X% ± Y% chance [Company]'s postings don't lead
  to a hire." Never "fake", "fraud", "ghost", "scam", "warning" or any claim that a named company is
  deceiving anyone; the red band uses the same sentence.
- No third-party JS libraries in the extension (plain JS). If one becomes necessary, ask first and
  add it to `docs/open-source.md`.
- No code from existing fake-job / ghost-job projects.
- Don't fabricate: mock responses are clearly marked `model_version: "mock"` and the side panel shows
  that version.

## Done when

1. The mock runs, and `curl -X POST localhost:8000/score -d '{"company_name":"MongoDB, Inc.","source":"greenhouse"}'`
   returns a contract-shaped response for MDB; an unknown name returns `in_dataset: false`.
2. The extension loads unpacked in Chrome with no errors in `chrome://extensions`.
3. On a real posting from one of our 300 companies on each of Greenhouse, Workday and LinkedIn
   (URLs to be supplied by Rachel), the badge appears next to the title with the right company.
4. On a posting from a company not in our list, nothing appears.
5. "Tell me why" opens the side panel with the full breakdown; switching tabs updates it.
6. With `DEV_FORCE_PROBABILITY` (or `?p=`), green, amber and red all render correctly.
7. Deleting the title anchor in DevTools and reloading detection shows the floating-pill fallback.
8. `extension/dev/README.md` explains how to run the mock and load the extension.
9. A short summary at the end: files created, what was tested on which pages, anything that didn't work.

## Out of scope (later)

Lever; the lookup / investor / employer web apps; the extension popup beyond a minimal status;
"I applied" tracker; connecting to the real API (only `API_URL` changes).
