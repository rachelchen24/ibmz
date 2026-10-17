"""Scraper 3: collects every available RealRole feature for shard 3 (a quarter of data/datathon_companies.csv).

    python -m collect.scraper3                 # full shard
    python -m collect.scraper3 --sample        # this shard's 5 pilot companies
    python -m collect.scraper3 --resume RUN_ID # continue an interrupted run
    python -m collect.scraper3 --help

Output: data/collect/shard_3/ (candidates, postings, features, manifest, logs). All four scrapers can run at once.
"""
from collect.pipeline import main

if __name__ == "__main__":
    main(shard=3)
