# RealRole verifier

This is the only path from candidate evidence into the dataset (build plan 1B-2). For each row from `scraper1`–`scraper4`, it:

1. Checks the row's format.
2. Fetches the source URL itself. It never uses the scrapers' cached copies.
3. Checks the quote is on the page: exact match after normalizing whitespace, quotes and dashes, with a fallback that compares letters and digits only.
4. Checks the value agrees with the quote. The number must be in the quote. For WARN notices, the company and worker count must be in the same spreadsheet row.
5. Flags conflicts: the same company, field and period from two sources more than 10% apart.

A row is `used` only if its check passed and it isn't in conflict.

```
python -m verify.accept --plant          # all shards' candidates + the planted-wrong-value test
python -m verify.accept --input data/collect/merged/candidates.csv
python -m unittest discover -s verify/tests -t .
```

Output goes to `data/verify/` (not in git):

- `evidence.jsonl` and `evidence.csv`: the contract's `evidence` columns, including `check`, `conflict`, `used` and `spot_check`.
- `verify_log_<time>.txt` and `.csv`: one ACCEPT/REJECT line per row. This is the log screenshot for the judges.

## Differences from CONTRACTS.md (needs team agreement)

- **`check` has an extra value, `value_mismatch`:** the quote is on the page, but the value doesn't agree with it.
- **NY WARN rows are checked against the person-exported CSV in `data/raw/ny_warn/`.** The NY WARN dashboard needs JavaScript, so it can't be fetched. The log says so on each of these rows.
- **PDF sources are marked `fetch_failed`.** None of the current sources are PDFs.

**Still to do (Michael, C):** load `evidence.jsonl` into PostgreSQL once the store exists, with the verifier as the only writer. Then run the verifier in `rr-verify` on the merged candidates.
