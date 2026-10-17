"""Headline findings for the video and README (build plan 3B-2, 4B-2). Phrased as testing a hypothesis.

1. Postings vs. estimated hiring by sector: median follow-through ratio per sector with a 95% bootstrap interval
   (needs data/processed/outcomes.csv).
2. How far posting growth outruns revenue growth: the distribution of posting_trend_vs_revenue across companies
   (needs features only). Shown as a distribution, never a list of company names.

    python -m dataset.findings
Writes artifacts/charts/findings_*.png and artifacts/metrics/findings.json (both committed, per plan 1.2).
"""
import numpy as np
import pandas as pd

from collect.common import config

from .common import companies, dump_json, latest_features

# Reference palette (dataviz skill), light mode: one series, so one hue and no legend.
SURFACE, INK, INK_2, GRID, SERIES, NEUTRAL = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6", "#8a8984"
SECTOR_NAMES = {"tech": "Tech", "banking": "Banking", "finance": "Finance", "professional_services": "Professional services"}


def bootstrap_median(x: np.ndarray, n: int = 2000) -> tuple[float, float]:
    rng = np.random.default_rng(config.SEED)
    meds = np.median(rng.choice(x, size=(n, len(x)), replace=True), axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def _style(ax, plt):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK_2, length=0, labelsize=10)
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def chart_sectors(out_df: pd.DataFrame, plt) -> dict:
    stats = {}
    for sector, g in out_df.groupby("sector"):
        x = g["follow_through"].dropna().to_numpy()
        if len(x) < 3:
            continue
        lo, hi = bootstrap_median(x)
        stats[sector] = {"n": int(len(x)), "median": float(np.median(x)), "ci95": [lo, hi],
                         "iqr": [float(np.percentile(x, 25)), float(np.percentile(x, 75))]}
    if not stats:
        return stats
    order = sorted(stats, key=lambda s: stats[s]["median"])
    fig, ax = plt.subplots(figsize=(8, 0.9 * len(order) + 1.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    _style(ax, plt)
    for i, s in enumerate(order):
        st = stats[s]
        ax.plot(st["ci95"], [i, i], color=SERIES, linewidth=2, solid_capstyle="round", alpha=0.45)
        ax.scatter([st["median"]], [i], s=90, color=SERIES, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(f"{st['median']:.0%}", (st["median"], i), xytext=(0, 9), textcoords="offset points",
                    ha="center", fontsize=10, color=INK)
    ax.set_yticks(range(len(order)), [f"{SECTOR_NAMES.get(s, s)}  (n={stats[s]['n']})" for s in order], color=INK)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(-0.7, len(order) - 0.3)
    fig.suptitle("Estimated hires per posting, by sector", x=0.02, ha="left", fontsize=13, color=INK, weight="bold")
    ax.set_title("Median follow-through ratio (estimated hires ÷ postings, capped at 100%), 95% interval",
                 loc="left", fontsize=9.5, color=INK_2)
    fig.text(0.02, 0.01, "Source: RealRole dataset. Hires estimated from 10-K headcount + BLS JOLTS separations; "
             "postings from archived careers boards.", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(config.CHARTS_DIR / "findings_follow_through_by_sector.png", facecolor=SURFACE)
    plt.close(fig)
    return stats


def chart_trend(feat: pd.DataFrame, plt) -> dict:
    x = feat["posting_trend_vs_revenue"].dropna().to_numpy() * 100
    if len(x) < 5:
        return {"n": int(len(x))}
    clipped = np.clip(x, -200, 300)
    stats = {"n": int(len(x)), "median_pts": float(np.median(x)),
             "quartiles_pts": [float(np.percentile(x, 25)), float(np.percentile(x, 75))],
             "share_outrunning_by_20pts": float((x > 20).mean()), "share_outrunning_by_50pts": float((x > 50).mean())}
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    _style(ax, plt)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID, linewidth=1)
    bins = np.arange(-200, 325, 25)
    ax.hist(clipped, bins=bins, color=SERIES, edgecolor=SURFACE, linewidth=2)
    ax.axvline(0, color=NEUTRAL, linewidth=1.5, linestyle=(0, (4, 3)))
    ymax = ax.get_ylim()[1]
    ax.annotate("postings grew faster\nthan revenue →", (12, ymax * 0.92), fontsize=9, color=INK_2, va="top")
    ax.annotate("← postings grew slower", (-12, ymax * 0.92), fontsize=9, color=INK_2, va="top", ha="right")
    ax.set_xlabel("12-month change in open postings minus revenue growth (percentage points; ends clipped)",
                  fontsize=9.5, color=INK_2)
    ax.set_ylabel("Companies", fontsize=9.5, color=INK_2)
    fig.suptitle(f"For {stats['share_outrunning_by_20pts']:.0%} of companies, postings outran revenue by 20+ points",
                 x=0.02, ha="left", fontsize=13, color=INK, weight="bold")
    ax.set_title(f"Distribution across {stats['n']} companies (median {stats['median_pts']:+.0f} points)",
                 loc="left", fontsize=9.5, color=INK_2)
    fig.text(0.02, 0.01, "Source: RealRole dataset. Postings from careers boards and Wayback Machine archives; "
             "revenue from SEC XBRL filings.", fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(config.CHARTS_DIR / "findings_postings_vs_revenue.png", facecolor=SURFACE)
    plt.close(fig)
    return stats


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    config.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    comp = companies()
    result = {"framing": "Hypothesis test: do some companies post far more than they hire? Not a claim about any named company."}

    outcomes_path = config.PROCESSED_DIR / "outcomes.csv"
    if outcomes_path.exists():
        out_df = pd.read_csv(outcomes_path)
        out_df["sector"] = out_df["ticker"].map(lambda t: (comp.get(t) or {}).get("sector"))
        result["follow_through_by_sector"] = chart_sectors(out_df, plt)
    else:
        print("no outcomes yet (run python -m dataset.build_outcomes); skipping the sector chart")

    feat = latest_features()
    if not feat.empty:
        result["posting_trend_vs_revenue"] = chart_trend(feat, plt)
        result["postings_per_100_employees_by_sector"] = {
            SECTOR_NAMES.get(s, s): {"n": int(g.notna().sum()), "median": float(g.median()) if g.notna().any() else None}
            for s, g in feat.groupby("sector")["postings_per_100_employees"]}
    dump_json(result, config.METRICS_DIR / "findings.json")

    print("=== findings ===")
    for s, st in (result.get("follow_through_by_sector") or {}).items():
        print(f"  {SECTOR_NAMES.get(s, s):24s} median follow-through {st['median']:.0%} "
              f"(95% CI {st['ci95'][0]:.0%}-{st['ci95'][1]:.0%}, n={st['n']})")
    tr = result.get("posting_trend_vs_revenue") or {}
    if tr.get("n", 0) >= 5:
        print(f"  posting growth minus revenue growth: median {tr['median_pts']:+.0f} pts over {tr['n']} companies; "
              f"{tr['share_outrunning_by_20pts']:.0%} outran revenue by 20+ pts")
    else:
        print(f"  posting trend vs revenue: only {tr.get('n', 0)} companies with both numbers so far")
    print(f"  charts: {config.CHARTS_DIR}   numbers: {config.METRICS_DIR / 'findings.json'}")


if __name__ == "__main__":
    main()
