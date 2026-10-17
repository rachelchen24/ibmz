"""Scraper 4: collects every available RealRole feature for shard 4 (a quarter of data/datathon_companies.csv).

    python -m collect.scraper4                 # full shard
    python -m collect.scraper4 --sample        # this shard's 5 pilot companies
    python -m collect.scraper4 --resume RUN_ID # continue an interrupted run
    python -m collect.scraper4 --help

Output: data/collect/shard_4/ (candidates, postings, features, manifest, logs). All four scrapers can run at once.
"""
from collect.pipeline import main

if __name__ == "__main__":
    main(shard=4)
