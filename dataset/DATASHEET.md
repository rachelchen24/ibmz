# RealRole dataset: datasheet

This is a company-level dataset of hiring indicators for 300 publicly traded US companies. It was built during the IBM Z Datathon 2026 (October 17–18, 2026). Every value has a source URL and a supporting quote that our code checked against the live page.

## Numbers

These numbers are filled in by `python -m dataset.publish`:

<!-- AUTO:START -->
- Not yet published.
<!-- AUTO:END -->

## Files

| File | One row per | Contents |
|---|---|---|
| `published/companies.csv` | Company | Ticker, CIK, name, sector, SIC, HQ state, priority tier, shard; the ATS board we found; the indicators (brief, "The indicators") and their raw inputs; `indicators_as_of` |
| `published/evidence.csv` | Verified value | `evidence_id`, ticker, field, value, unit, period, source URL, quote (≤ 300 characters), page date, collected at, collector, check, conflict, used |

Quick reference for the fields and units in `evidence.csv`:

- `employee_count` and `employee_count_us`: employees, by fiscal year.
- `revenue`: USD, fiscal year. Banks have `revenue_component` rows instead (net interest income and noninterest income).
- `hq_country`.
- `reports_us_headcount`.
- `layoff_events`: JSON with date, workers, share of workforce and source.
- `hiring_freeze_statements`.
- `management_hiring_statements`: −1 / 0 / +1 tone.
- `archived_open_postings`: open postings on a dated archive copy of the careers board.

## Company universe

The 300 companies are in `data/datathon_companies.csv`, with `selected = 1`. They are publicly traded US companies across four sectors chosen as having the most ghost postings: tech, banking, finance and professional services. Each company has a filed 10-K. The list was signed off at the start of Block 1 (`data/labels/company_list_signoff.md`).

## How it was collected

Four collection runs (`collect/scraper1` … `scraper4`) each covered one balanced shard of 75 companies. They all ran the same code at the same git commit, recorded in each shard's manifest. No AI model collected values at run time. Every value comes from a structured public source:

| Source | Fields | Access |
|---|---|---|
| SEC EDGAR: submissions and XBRL company facts | revenue, HQ country | Public API; User-Agent with a contact email; ≤ 8 requests/s in total |
| SEC EDGAR: 10-K text | employee count (total, and US where stated) | Public filings |
| SEC EDGAR: 10-K, 10-Q, 8-K and EX-99 exhibits | layoff events, hiring-freeze statements, management hiring statements | Public filings. Earnings-call transcripts not filed with the SEC are not included |
| State WARN notices (NY, CA, TX) | layoff events | State labor department publications |
| Greenhouse, Lever and Workday public job-board APIs | current postings (the `postings` table, not published) | Public board endpoints, rate-limited |
| Internet Archive Wayback Machine | monthly open-posting counts, past job IDs | CDX API, ≤ 1 request/s per run |
| Indeed Hiring Lab job postings index | sector posting trend | Published CSV (`hiring-lab/job_postings_tracker`) |

We did not scrape LinkedIn, Glassdoor or Indeed job listings. We collected nothing about individual people. We never collected reviews, complaints or opinions about whether a company "posts ghost jobs". That is the outcome we are measuring, not an input.

## Verification

`verify/accept.py` re-fetches every source URL independently; it never uses a copy from the collection run. It then checks two things:

1. The quote appears on the page. Matching is exact after normalizing whitespace and punctuation. Quotes of 30 or more letters and digits can also match on the same letters and digits.
2. The value agrees with the quote. For example, the stated number must appear in the quote.

When two sources give the same company, field and period values more than 10% apart, the values are flagged as a conflict and not used. Only rows with `check = passed` and `conflict = false` are published.

Two exceptions to independent fetching:

- **New York WARN:** NY publishes its WARN notices in a Tableau dashboard that needs JavaScript. These rows are checked against a CSV a team member exported from that dashboard.
- **Wayback posting counts:** the verifier confirms the archived page is the company's board, but it does not re-count the jobs listed.

## Ground truth (not published as a feature)

The model is trained against a follow-through ratio built in `dataset/build_outcomes.py`:

- **Net hires per posting** = the change in 10-K headcount between two fiscal years ÷ postings over the same fiscal year. It uses only company-specific data; no industry averages.
- **Follow-through ratio** = net hires per posting, clipped to 0–1. A company that shrank gets 0.
- **Postings over the year** = distinct job IDs observed on archived copies of the company's board during that year (method in `postings_year_method`). This is a lower bound, so the ratio can be overstated for companies whose boards are rarely archived.

Headcount change is never a model feature.

## Known gaps and limits

- **Postings coverage depends on a public ATS board.** Companies whose careers sites use other systems (iCIMS, Taleo, SuccessFactors, Phenom and others) have no postings-based indicators.
- **Headcount scope varies.** 10-K headcount is usually global; we use US headcount where the filing states it.
- **Annual headcount is a slow, coarse outcome.** It catches persistent over-posting, not a single unfilled role.
- **Postings per year is estimated.** Archived boards are captured irregularly. The default method multiplies the average open count by 365 ÷ a typical posting lifetime.
- **Some filing-text fields come from keyword rules, not a model.** These are layoff events, hiring-freeze statements and management hiring tone. They miss statements worded differently, and they are dated by the filing when no date is stated.
- **Greenhouse posted dates are approximate.** When Greenhouse doesn't expose `first_published`, the posted date is the last-updated date, so posting ages are underestimated.
- **Workday detail sampling.** For Workday companies with more than 600 postings, text-based indicators are computed on a random sample of 600.
- **Spot-check error rate.** See the numbers block above and `docs/model-card.md`.

## License and terms

The published files contain facts, short quotes and source links. They contain no copies of pages. SEC filings are public records, and BLS data is public domain. Use of archived pages follows the Internet Archive's terms. The Indeed Hiring Lab data is used under its published terms; check them before reuse. Job-board data was read from the boards' public endpoints, and individual postings are not published.
