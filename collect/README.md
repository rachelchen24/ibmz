# RealRole collection: scraper1–scraper4

The 300 selected companies in `data/datathon_companies.csv` are split into four shards of 75. Each shard has the same sector and size mix, and the split is fixed. Each person runs one scraper on their own shard. The scrapers can run at the same time on one machine or on four machines.

| Scraper | Shard | Person |
|---|---|---|
| `scraper1` | 1 | A: ML lead |
| `scraper2` | 2 | B: Data lead |
| `scraper3` | 3 | C: Michael |
| `scraper4` | 4 | D: Product lead |

The split is written to `data/collect/shard_assignment.csv` on the first run.

## Run

From the repo root (`python` or `py -3` on Windows; requires Python 3.10+):

```
pip install -r collect/requirements.txt
python -m collect.scraper2 --sample        # 5 pilot companies first (~3 min)
python -m collect.scraper2                 # your whole shard
python -m collect.scraper2 --resume s2-20261017T120433   # continue after a crash or Ctrl-C
python -m collect.scraper2 --tickers JPM AXP             # rerun specific companies
python -m collect.run_all                  # all four at once on one machine
python -m collect.merge                    # after all four finish: one combined dataset
```

Day 2 (October 18): run the same command again. That makes a second postings snapshot, which is used for reposts and `last_seen`.

## What each scraper collects

There is no Claude at run time, so every value comes from a structured public source. Each value is stored with a source URL and a quote taken from that page, so the verifier can check it.

| Step | Source | Fields |
|---|---|---|
| edgar | SEC submissions, XBRL company facts, 10-K text | revenue (2 FYs), employee count (2 FYs, US where reported), HQ country |
| filings | 10-K, 10-Qs, 8-Ks + EX-99 press releases | layoff events, hiring-freeze statements, management hiring statements |
| warn | NY, CA and TX state WARN files | layoff events |
| ats | Greenhouse, Lever and Workday public boards (detected automatically) | open postings → `postings` |
| wayback | archive.org copies of the board | monthly open-posting counts, past job IDs |

If a step fails or finds nothing for a company, it is recorded as `skipped` with the reason, and the run continues.

## Output: `data/collect/shard_<N>/` (not in git)

- `scraper<N>_features_<date>.csv`: one row per company. It has the 30 brief features plus raw inputs. `python -m collect.merge` combines the four shards' files into `data/collect/merged/`.
- `candidates_<run_id>.jsonl`: evidence rows. Send these to the verifier.
- `postings_<date>.jsonl` and `postings_extra_<date>.jsonl`: postings in the contract's columns, plus extra fields (closing date, states, requirement bullets).
- `ats_summary_<date>.csv`: the board found for each company. **Check the `detection` column for any guessed boards.**
- `status_<run_id>.jsonl`, `manifest.json` and `logs/`.

## Features left for `ml/`

These features need models: `open_vs_expected` (survival model), `deleted_and_reposted_share`, `template_similarity` and `text_pc_1..5` (Granite embeddings), and `salary_vs_occupation`, `requirements_vs_job_zone`, `description_length_z`, `mean_job_zone` and `top_soc_group_share` (O*NET norms). They are NaN in the features file. The features are computed before verification. The final model must use `ml/indicators.py` on verified (`used`) evidence.

## Limits

- **Rate limits:** SEC is capped at 2 requests/s per scraper (8/s across all four, under SEC's 10/s limit). Wayback is capped at 1 request/s.
- **Cache:** every raw response is cached in `data/collect/cache/`, so reruns are fast.
