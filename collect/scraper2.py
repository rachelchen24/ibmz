"""Scraper 2: collects every available RealRole feature for shard 2 (a quarter of data/datathon_companies.csv).

    python -m collect.scraper2                 # full shard
    python -m collect.scraper2 --sample        # this shard's 5 pilot companies
    python -m collect.scraper2 --resume RUN_ID # continue an interrupted run
    python -m collect.scraper2 --help

Output: data/collect/shard_2/ (candidates, postings, features, manifest, logs). All four scrapers can run at once.
"""
from collect.pipeline import main

if __name__ == "__main__":
    main(shard=2)
