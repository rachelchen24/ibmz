"""Scraper 1: collects every available RealRole feature for shard 1 (a quarter of data/datathon_companies.csv).

    python -m collect.scraper1                 # full shard
    python -m collect.scraper1 --sample        # this shard's 5 pilot companies
    python -m collect.scraper1 --resume RUN_ID # continue an interrupted run
    python -m collect.scraper1 --help

Output: data/collect/shard_1/ (candidates, postings, features, manifest, logs). All four scrapers can run at once.
"""
from collect.pipeline import main

if __name__ == "__main__":
    main(shard=1)
