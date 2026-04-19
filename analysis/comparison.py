"""
Comparison: FY-1C events vs all other LEO conjunction events.
Pc distribution, miss distance, severity profile.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG_DARK = "#0d1117"
BG_CARD = "#161b22"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
GRID_COLOR = "#21262d"
ACCENT_ORANGE = "#f0883e"
ACCENT_BLUE = "#58a6ff"
ACCENT_RED = "#f85149"

OUTPUT = Path("output/analysis")
OUTPUT.mkdir(parents=True, exist_ok=True)


def setup_style():
    plt.rcParams.update({
        "figure.facecolor": BG_DARK, "axes.facecolor": BG_CARD,
        "axes.edgecolor": GRID_COLOR, "axes.labelcolor": TEXT_PRIMARY,
        "axes.grid": True, "grid.color": GRID_COLOR, "grid.alpha": 0.5,
        "text.color": TEXT_PRIMARY, "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY, "font.size": 11,
        "axes.titlesize": 15, "axes.titleweight": "bold",
        "legend.facecolor": BG_CARD, "legend.edgecolor": GRID_COLOR,
        "legend.labelcolor": TEXT_PRIMARY, "savefig.facecolor": BG_DARK,
        "savefig.dpi": 200, "savefig.bbox": "tight",
    })


def main():
    setup_style()

    # Load FY-1C events
    fy = pd.read_csv("data/clean/fengyun_conjunctions.csv")
    fy_ids = set(fy["cdm_id"].astype(str))

    # Load ALL CDMs for same period
    all_cdms = json.load(open("data/raw/cdm_total_count.json"))
    print(f"Total CDMs: {len(all_cdms)}")
    print(f"FY-1C CDMs: {len(fy)}")

    # Build non-FY dataframe
    non_fy_rows = []
    for cdm in all_cdms:
        if str(cdm.get("CDM_ID", "")) not in fy_ids:
            pc = cdm.get("PC")
            mr = cdm.get("MIN_RNG")
            non_fy_rows.append({
                "pc": float(pc) if pc else None,
                "miss_km": float(mr) if mr else None,
                "sat1_type": cdm.get("SAT1_OBJECT_TYPE", ""),
                "sat2_type": cdm.get("SAT2_OBJECT_TYPE", ""),
            })

    nf = pd.DataFrame(non_fy_rows)
    print(f"Non-FY CDMs: {len(nf)}")

    # --- Stats comparison ---
    fy_pc = fy["collision_probability"].dropna()
    nf_pc = nf["pc"].dropna()
    fy_miss = fy["miss_distance_km"].dropna()
    nf_miss = nf["miss_km"].dropna()

    print("\n=== COLLISION PROBABILITY ===")
    print(f"  {'Metric':<25s} {'FY-1C':>12s} {'Non-FY-1C':>12s} {'Ratio':>8s}")
    print(f"  {'-'*60}")

    comparisons = {}
    for label, fy_val, nf_val in [
        ("Median Pc", fy_pc.median(), nf_pc.median()),
        ("Mean Pc", fy_pc.mean(), nf_pc.mean()),
        ("Max Pc", fy_pc.max(), nf_pc.max()),
        ("75th pctile Pc", fy_pc.quantile(0.75), nf_pc.quantile(0.75)),
    ]:
        ratio = fy_val / nf_val if nf_val > 0 else float("inf")
        print(f"  {label:<25s} {fy_val:>12.2e} {nf_val:>12.2e} {ratio:>7.1f}x")
        comparisons[label] = {"fy1c": float(fy_val), "non_fy": float(nf_val), "ratio": round(float(ratio), 2)}

    print(f"\n=== MISS DISTANCE ===")
    for label, fy_val, nf_val in [
        ("Median miss (km)", fy_miss.median(), nf_miss.median()),
        ("Mean miss (km)", fy_miss.mean(), nf_miss.mean()),
        ("Min miss (km)", fy_miss.min(), nf_miss.min()),
    ]:
        ratio = fy_val / nf_val if nf_val > 0 else 0
        print(f"  {label:<25s} {fy_val:>12.1f} {nf_val:>12.1f} {ratio:>7.2f}x")
        comparisons[label] = {"fy1c": float(fy_val), "non_fy": float(nf_val), "ratio": round(float(ratio), 2)}

    # Fraction above key thresholds
    print(f"\n=== THRESHOLD EXCEEDANCE ===")
    for thresh in [1e-4, 1e-3]:
        fy_above = (fy_pc > thresh).mean() * 100
        nf_above = (nf_pc > thresh).mean() * 100
        print(f"  Events > {thresh:.0e}: FY-1C={fy_above:.1f}%  Non-FY={nf_above:.1f}%")
        comparisons[f"pct_above_{thresh:.0e}"] = {"fy1c": round(fy_above, 1), "non_fy": round(nf_above, 1)}

    # --- CHART: Side-by-side Pc distribution ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Pc histogram comparison
    bins = np.logspace(-5, -1, 35)
    ax1.hist(fy_pc, bins=bins, color=ACCENT_ORANGE, alpha=0.75, label=f"FY-1C (n={len(fy_pc)})", density=True)
    ax1.hist(nf_pc, bins=bins, color=ACCENT_BLUE, alpha=0.55, label=f"Non-FY-1C (n={len(nf_pc)})", density=True)
    ax1.set_xscale("log")
    ax1.set_title("Collision Probability: FY-1C vs Rest of LEO")
    ax1.set_xlabel("Probability of Collision (Pc)")
    ax1.set_ylabel("Density")
    ax1.legend(loc="upper right", framealpha=0.8)
    ax1.axvline(x=fy_pc.median(), color=ACCENT_ORANGE, linestyle="--", linewidth=1.5, alpha=0.8)
    ax1.axvline(x=nf_pc.median(), color=ACCENT_BLUE, linestyle="--", linewidth=1.5, alpha=0.8)

    # Miss distance comparison
    bins2 = np.linspace(0, 1000, 40)
    ax2.hist(fy_miss, bins=bins2, color=ACCENT_ORANGE, alpha=0.75, label=f"FY-1C (n={len(fy_miss)})", density=True)
    ax2.hist(nf_miss, bins=bins2, color=ACCENT_BLUE, alpha=0.55, label=f"Non-FY-1C (n={len(nf_miss)})", density=True)
    ax2.set_title("Miss Distance: FY-1C vs Rest of LEO")
    ax2.set_xlabel("Miss Distance (km)")
    ax2.set_ylabel("Density")
    ax2.legend(loc="upper right", framealpha=0.8)
    ax2.axvline(x=fy_miss.median(), color=ACCENT_ORANGE, linestyle="--", linewidth=1.5, alpha=0.8)
    ax2.axvline(x=nf_miss.median(), color=ACCENT_BLUE, linestyle="--", linewidth=1.5, alpha=0.8)

    # Headline
    median_ratio = comparisons["Median Pc"]["ratio"]
    direction = "HIGHER" if median_ratio > 1 else "LOWER"
    fig.suptitle(
        f"FY-1C conjunctions show {median_ratio:.1f}x {direction} median collision probability than non-FY-1C events",
        fontsize=13, fontweight="bold", color=ACCENT_RED if direction == "HIGHER" else ACCENT_BLUE, y=1.02,
    )

    fig.savefig(OUTPUT / "comparison_fy_vs_nonfy.png", dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"\n  Chart -> output/analysis/comparison_fy_vs_nonfy.png")

    # Save findings
    headline = (
        f"FY-1C conjunctions have {median_ratio:.1f}x {direction.lower()} median Pc "
        f"({comparisons['Median Pc']['fy1c']:.2e} vs {comparisons['Median Pc']['non_fy']:.2e}) "
        f"compared to all other LEO conjunction events."
    )
    result = {"headline": headline, "comparisons": comparisons}
    with open(OUTPUT / "comparison.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"\n  >>> {headline}")


if __name__ == "__main__":
    print("\n=== FY-1C vs NON-FY-1C COMPARISON ===\n")
    main()
    print()
