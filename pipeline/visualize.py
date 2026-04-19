"""
Fengyun-1C Debris LEO Conjunction Risk -- Visualizations
Generates 6 publication-quality charts from the clean dataset.

Usage:
    python -m pipeline.visualize
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for PNG output

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# ──────────────────────────────────────────────
# Theme & Constants
# ──────────────────────────────────────────────

# Dark professional palette
BG_DARK = "#0d1117"
BG_CARD = "#161b22"
TEXT_PRIMARY = "#e6edf3"
TEXT_SECONDARY = "#8b949e"
GRID_COLOR = "#21262d"
ACCENT_ORANGE = "#f0883e"
ACCENT_BLUE = "#58a6ff"
ACCENT_RED = "#f85149"
ACCENT_GREEN = "#3fb950"
ACCENT_PURPLE = "#bc8cff"
ACCENT_CYAN = "#39d2c0"
ACCENT_YELLOW = "#d29922"

PALETTE = [ACCENT_ORANGE, ACCENT_BLUE, ACCENT_RED, ACCENT_GREEN, ACCENT_PURPLE, ACCENT_CYAN, ACCENT_YELLOW]

OUTPUT_DIR = Path("output/charts")
DATA_DIR = Path("data/clean")
RAW_DIR = Path("data/raw")


def setup_style():
    """Apply dark theme globally."""
    plt.rcParams.update({
        "figure.facecolor": BG_DARK,
        "axes.facecolor": BG_CARD,
        "axes.edgecolor": GRID_COLOR,
        "axes.labelcolor": TEXT_PRIMARY,
        "axes.grid": True,
        "grid.color": GRID_COLOR,
        "grid.alpha": 0.5,
        "text.color": TEXT_PRIMARY,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 16,
        "axes.titleweight": "bold",
        "figure.titlesize": 18,
        "figure.titleweight": "bold",
        "legend.facecolor": BG_CARD,
        "legend.edgecolor": GRID_COLOR,
        "legend.labelcolor": TEXT_PRIMARY,
        "savefig.facecolor": BG_DARK,
        "savefig.edgecolor": BG_DARK,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


def load_data():
    """Load the clean dataset and GP data."""
    csv_path = DATA_DIR / "fengyun_conjunctions.csv"
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run the pipeline first.")
        sys.exit(1)

    df = pd.read_csv(csv_path, parse_dates=["tca"])
    df["tca_date"] = df["tca"].dt.date

    # Load GP data for altitude info
    gp_data = []
    for gp_file in sorted(RAW_DIR.glob("gp_batch_*.json")):
        with open(gp_file, "r") as f:
            gp_data.extend(json.load(f))

    return df, gp_data


# ──────────────────────────────────────────────
# Chart 1: Event Distribution Over Time
# ──────────────────────────────────────────────

def chart_event_timeline(df: pd.DataFrame):
    """Daily conjunction count with trend line."""
    daily = df.groupby("tca_date").size().reset_index(name="count")
    daily["tca_date"] = pd.to_datetime(daily["tca_date"])

    fig, ax = plt.subplots(figsize=(14, 6))

    # Bar chart for daily counts
    ax.bar(
        daily["tca_date"], daily["count"],
        color=ACCENT_ORANGE, alpha=0.8, width=0.8,
        edgecolor=ACCENT_ORANGE, linewidth=0.5,
        label="Daily conjunction count",
    )

    # Rolling 3-day average trend
    if len(daily) > 3:
        daily["rolling"] = daily["count"].rolling(3, center=True, min_periods=1).mean()
        ax.plot(
            daily["tca_date"], daily["rolling"],
            color=ACCENT_CYAN, linewidth=2.5, linestyle="-",
            label="3-day rolling avg", zorder=5,
        )

    # Annotations
    total = int(daily["count"].sum())
    avg_per_day = daily["count"].mean()
    peak_idx = daily["count"].idxmax()
    peak_date = daily.loc[peak_idx, "tca_date"]
    peak_count = daily.loc[peak_idx, "count"]

    ax.annotate(
        f"Peak: {peak_count} events",
        xy=(peak_date, peak_count),
        xytext=(peak_date, peak_count + 3),
        fontsize=10, color=ACCENT_RED, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=ACCENT_RED, lw=1.5),
        ha="center",
    )

    ax.set_title("Fengyun-1C Debris Conjunctions Over Time", pad=15)
    ax.set_xlabel("Date (TCA)")
    ax.set_ylabel("Number of Conjunction Events")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    plt.xticks(rotation=45, ha="right")
    ax.legend(loc="upper left", framealpha=0.8)

    # Stats box
    stats_text = f"Total: {total} events | Avg: {avg_per_day:.1f}/day"
    ax.text(
        0.98, 0.95, stats_text,
        transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
        ha="right", va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor=BG_DARK, edgecolor=GRID_COLOR, alpha=0.9),
    )

    save(fig, "01_event_timeline")


# ──────────────────────────────────────────────
# Chart 2: Fengyun Contribution %
# ──────────────────────────────────────────────

def chart_fengyun_contribution(df: pd.DataFrame):
    """
    Donut chart showing Fengyun-1C's share of conjunction events.
    Uses partner type breakdown to tell the story.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: Donut showing ALL Fengyun events = 100% of our dataset
    # Context: FY-1C generates X events per day in LEO
    total_events = len(df)
    fy_debris_count = len(df[df["fy1c_object_type"] == "DEBRIS"])
    payload_threats = len(df[df["other_object_type"] == "PAYLOAD"])
    debris_on_debris = len(df[df["is_debris_on_debris"]])

    sizes = [payload_threats, debris_on_debris, total_events - payload_threats - debris_on_debris]
    labels = [
        f"Threatening Payloads\n({payload_threats})",
        f"Debris-on-Debris\n({debris_on_debris})",
        f"Other (R/B, Unknown)\n({sizes[2]})",
    ]
    colors = [ACCENT_RED, ACCENT_ORANGE, ACCENT_BLUE]
    explode = (0.05, 0, 0)

    wedges, texts, autotexts = ax1.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct="%1.0f%%", startangle=90,
        textprops={"color": TEXT_PRIMARY, "fontsize": 10},
        wedgeprops={"edgecolor": BG_DARK, "linewidth": 2},
        pctdistance=0.75,
    )
    for at in autotexts:
        at.set_fontweight("bold")
        at.set_fontsize(12)

    # Inner circle for donut effect
    centre = plt.Circle((0, 0), 0.55, fc=BG_CARD)
    ax1.add_artist(centre)
    ax1.text(0, 0.05, f"{total_events}", fontsize=28, fontweight="bold",
             color=ACCENT_ORANGE, ha="center", va="center")
    ax1.text(0, -0.15, "Total Events", fontsize=10, color=TEXT_SECONDARY,
             ha="center", va="center")
    ax1.set_title("Fengyun-1C Conjunction Breakdown", pad=15)

    # Right: Headline stats
    ax2.axis("off")
    stats = [
        ("Total Conjunctions", f"{total_events}", ACCENT_ORANGE),
        ("Active Payloads at Risk", f"{payload_threats}", ACCENT_RED),
        ("Debris-on-Debris", f"{debris_on_debris}", ACCENT_YELLOW),
        ("Unique FY-1C Fragments", f"{df['fy1c_norad_id'].nunique()}", ACCENT_BLUE),
        ("Max Collision Prob", f"{df['collision_probability'].max():.2%}", ACCENT_RED),
        ("Min Miss Distance", f"{df['miss_distance_km'].min():.0f} km", ACCENT_PURPLE),
    ]

    y_start = 0.92
    for i, (label, value, color) in enumerate(stats):
        y = y_start - i * 0.15
        ax2.text(0.1, y, value, fontsize=22, fontweight="bold", color=color,
                 transform=ax2.transAxes, va="center")
        ax2.text(0.1, y - 0.05, label, fontsize=11, color=TEXT_SECONDARY,
                 transform=ax2.transAxes, va="center")

    ax2.set_title("Headline Statistics", pad=15)

    fig.suptitle("Fengyun-1C: A Single Event Dominating LEO Risk", fontsize=16, fontweight="bold", y=1.02)
    save(fig, "02_fengyun_contribution")


# ──────────────────────────────────────────────
# Chart 3: Altitude Distribution
# ──────────────────────────────────────────────

def chart_altitude_distribution(df: pd.DataFrame, gp_data: list[dict]):
    """Histogram of perigee altitudes with FY-1C peak region highlighted."""
    # Build perigee map from GP data
    perigee_values = []
    fy1c_perigees = []
    other_perigees = []

    fy1c_ids = set(df["fy1c_norad_id"].astype(str).unique())
    other_ids = set(df["other_norad_id"].astype(str).unique())

    for gp in gp_data:
        nid = str(gp.get("NORAD_CAT_ID", ""))
        periapsis = gp.get("PERIAPSIS")
        if periapsis:
            try:
                alt = float(periapsis)
                if alt < 2000:  # LEO only
                    perigee_values.append(alt)
                    if nid in fy1c_ids:
                        fy1c_perigees.append(alt)
                    if nid in other_ids:
                        other_perigees.append(alt)
            except (ValueError, TypeError):
                pass

    if not perigee_values:
        print("  SKIP: No perigee data available for altitude chart")
        return

    fig, ax = plt.subplots(figsize=(14, 6))

    bins = np.arange(200, 1600, 25)

    # FY-1C debris perigees
    if fy1c_perigees:
        ax.hist(
            fy1c_perigees, bins=bins, color=ACCENT_ORANGE, alpha=0.7,
            edgecolor=BG_DARK, linewidth=0.5, label=f"FY-1C Debris ({len(fy1c_perigees)} objects)",
        )

    # Conjunction partner perigees
    if other_perigees:
        ax.hist(
            other_perigees, bins=bins, color=ACCENT_BLUE, alpha=0.5,
            edgecolor=BG_DARK, linewidth=0.5, label=f"Conjunction Partners ({len(other_perigees)} objects)",
        )

    # Highlight the peak danger zone
    ax.axvspan(700, 900, alpha=0.15, color=ACCENT_RED, label="Peak Risk Zone (700-900 km)")
    ax.axvline(x=865, color=ACCENT_RED, linestyle="--", linewidth=1.5, alpha=0.7)
    ax.text(
        868, ax.get_ylim()[1] * 0.85, "FY-1C original\naltitude ~865 km",
        fontsize=9, color=ACCENT_RED, style="italic",
    )

    ax.set_title("Altitude Distribution of Conjunction Objects", pad=15)
    ax.set_xlabel("Perigee Altitude (km)")
    ax.set_ylabel("Number of Objects")
    ax.legend(loc="upper right", framealpha=0.8)

    # Stats annotation
    if fy1c_perigees:
        median_alt = np.median(fy1c_perigees)
        ax.text(
            0.02, 0.95,
            f"FY-1C debris median perigee: {median_alt:.0f} km",
            transform=ax.transAxes, fontsize=10, color=TEXT_SECONDARY,
            va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=BG_DARK, edgecolor=GRID_COLOR, alpha=0.9),
        )

    save(fig, "03_altitude_distribution")


# ──────────────────────────────────────────────
# Chart 4: Object Type Breakdown
# ──────────────────────────────────────────────

def chart_object_type_breakdown(df: pd.DataFrame):
    """Horizontal bar chart of conjunction partner types."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1.2, 1]})

    # Left: Partner type bar chart
    type_counts = df["other_object_type"].value_counts()
    types = type_counts.index.tolist()
    counts = type_counts.values

    color_map = {
        "DEBRIS": ACCENT_ORANGE,
        "PAYLOAD": ACCENT_RED,
        "ROCKET BODY": ACCENT_BLUE,
        "UNKNOWN": ACCENT_PURPLE,
    }
    colors = [color_map.get(t, TEXT_SECONDARY) for t in types]

    bars = ax1.barh(range(len(types)), counts, color=colors, edgecolor=BG_DARK, linewidth=0.5, height=0.6)
    ax1.set_yticks(range(len(types)))
    ax1.set_yticklabels(types, fontsize=12)
    ax1.invert_yaxis()
    ax1.set_xlabel("Number of Conjunction Events")
    ax1.set_title("Conjunction Partner Types", pad=15)

    # Add count labels on bars
    for bar, count in zip(bars, counts):
        ax1.text(
            bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
            f"{count}", fontsize=12, fontweight="bold",
            color=TEXT_PRIMARY, va="center",
        )

    # Right: FY-1C debris vs active payloads story
    ax2.axis("off")

    payload_count = int(type_counts.get("PAYLOAD", 0))
    debris_count = int(type_counts.get("DEBRIS", 0))
    rb_count = int(type_counts.get("ROCKET BODY", 0))
    total = len(df)

    # Stacked proportion bar
    bar_y = 0.7
    bar_height = 0.08
    cumulative = 0
    for label, count, color in [
        ("Debris", debris_count, ACCENT_ORANGE),
        ("Payload", payload_count, ACCENT_RED),
        ("R/B", rb_count, ACCENT_BLUE),
        ("Other", total - debris_count - payload_count - rb_count, ACCENT_PURPLE),
    ]:
        width = count / total
        ax2.barh(bar_y, width, left=cumulative, height=bar_height, color=color, edgecolor=BG_DARK,
                 transform=ax2.transAxes)
        if width > 0.08:
            ax2.text(cumulative + width / 2, bar_y, f"{count}",
                     transform=ax2.transAxes, ha="center", va="center",
                     fontsize=9, fontweight="bold", color=TEXT_PRIMARY)
        cumulative += width

    ax2.text(0.5, 0.85, "Event Composition", transform=ax2.transAxes,
             ha="center", fontsize=13, fontweight="bold", color=TEXT_PRIMARY)

    # Key insight
    pct_payload = payload_count / total * 100
    ax2.text(0.5, 0.45,
             f"{payload_count} of {total} events\nthreaten active payloads",
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=14, fontweight="bold", color=ACCENT_RED)
    ax2.text(0.5, 0.28,
             f"That's {pct_payload:.0f}% of all FY-1C conjunctions",
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=11, color=TEXT_SECONDARY)

    ax2.set_title("The Payload Threat", pad=15)

    save(fig, "04_object_type_breakdown")


# ──────────────────────────────────────────────
# Chart 5: Top Affected Satellites
# ──────────────────────────────────────────────

def chart_top_satellites(df: pd.DataFrame):
    """Top 10 conjunction partners by event count."""
    # Exclude FY-1C debris-on-debris for this chart (focus on affected third parties)
    non_fy = df[~df["is_debris_on_debris"]].copy()

    top = non_fy.groupby(["other_norad_id", "other_object_name", "other_object_type"]).size() \
        .reset_index(name="count") \
        .sort_values("count", ascending=False) \
        .head(10)

    fig, ax = plt.subplots(figsize=(14, 7))

    y_pos = range(len(top))
    color_map = {
        "DEBRIS": ACCENT_ORANGE,
        "PAYLOAD": ACCENT_RED,
        "ROCKET BODY": ACCENT_BLUE,
        "UNKNOWN": ACCENT_PURPLE,
    }
    colors = [color_map.get(row["other_object_type"], TEXT_SECONDARY) for _, row in top.iterrows()]

    bars = ax.barh(
        y_pos, top["count"].values,
        color=colors, edgecolor=BG_DARK, linewidth=0.5, height=0.65,
    )

    # Labels with NORAD ID
    labels = [
        f"{row['other_object_name']}  (#{int(row['other_norad_id'])})"
        for _, row in top.iterrows()
    ]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()

    # Count labels
    for bar, count in zip(bars, top["count"].values):
        ax.text(
            bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
            f"{count}", fontsize=13, fontweight="bold",
            color=TEXT_PRIMARY, va="center",
        )

    ax.set_xlabel("Number of Conjunction Events with FY-1C Debris")
    ax.set_title("Top 10 Most Affected Objects", pad=15)

    # Legend for object types
    from matplotlib.patches import Patch
    legend_items = []
    for otype, color in color_map.items():
        if otype in top["other_object_type"].values:
            legend_items.append(Patch(facecolor=color, edgecolor=BG_DARK, label=otype))
    ax.legend(handles=legend_items, loc="lower right", framealpha=0.8)

    # Count payloads in top 10
    payloads_in_top = top[top["other_object_type"] == "PAYLOAD"]
    if not payloads_in_top.empty:
        ax.text(
            0.98, 0.02,
            f"{len(payloads_in_top)} active payload(s) in top 10",
            transform=ax.transAxes, fontsize=10, color=ACCENT_RED,
            ha="right", va="bottom", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=BG_DARK, edgecolor=ACCENT_RED, alpha=0.9),
        )

    save(fig, "05_top_affected_satellites")


# ──────────────────────────────────────────────
# Chart 6: Pc Distribution
# ──────────────────────────────────────────────

def chart_pc_distribution(df: pd.DataFrame):
    """Collision probability distribution on log scale."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    pc = df["collision_probability"].dropna()
    pc_log = df["pc_log10"].dropna()

    # Left: Log-scale histogram of Pc
    bins = np.logspace(np.floor(np.log10(pc.min())), np.ceil(np.log10(pc.max())), 30)

    ax1.hist(
        pc, bins=bins, color=ACCENT_ORANGE, alpha=0.8,
        edgecolor=BG_DARK, linewidth=0.5,
    )
    ax1.set_xscale("log")
    ax1.set_title("Collision Probability Distribution", pad=15)
    ax1.set_xlabel("Probability of Collision (Pc)")
    ax1.set_ylabel("Number of Events")

    # Reference lines for common thresholds
    thresholds = [
        (1e-4, "Screening\nthreshold", ACCENT_YELLOW),
        (1e-3, "High risk", ACCENT_RED),
    ]
    for thresh, label, color in thresholds:
        ax1.axvline(x=thresh, color=color, linestyle="--", linewidth=1.5, alpha=0.8)
        ax1.text(
            thresh * 1.3, ax1.get_ylim()[1] * 0.85, label,
            fontsize=9, color=color, fontweight="bold",
        )

    # Right: Pc vs Miss Distance scatter
    ax2.scatter(
        df["miss_distance_km"], df["collision_probability"],
        c=df["pc_log10"], cmap="YlOrRd_r", s=30, alpha=0.7,
        edgecolors=BG_DARK, linewidth=0.3,
    )
    ax2.set_yscale("log")
    ax2.set_title("Pc vs Miss Distance", pad=15)
    ax2.set_xlabel("Miss Distance (km)")
    ax2.set_ylabel("Collision Probability")
    ax2.axhline(y=1e-4, color=ACCENT_YELLOW, linestyle="--", linewidth=1, alpha=0.6)
    ax2.text(
        df["miss_distance_km"].max() * 0.7, 1.3e-4,
        "1e-4 threshold", fontsize=9, color=ACCENT_YELLOW,
    )

    # Highlight the closest approach
    closest = df.loc[df["miss_distance_km"].idxmin()]
    ax2.annotate(
        f"{closest['miss_distance_km']:.0f} km\nPc={closest['collision_probability']:.2e}",
        xy=(closest["miss_distance_km"], closest["collision_probability"]),
        xytext=(closest["miss_distance_km"] + 80, closest["collision_probability"] * 2),
        fontsize=9, color=ACCENT_RED, fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=ACCENT_RED, lw=1.5),
    )

    fig.suptitle("Collision Risk Severity Analysis", fontsize=16, fontweight="bold", y=1.02)
    save(fig, "06_pc_distribution")


# ──────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────

def save(fig: plt.Figure, name: str):
    """Save figure to output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"  [OK] {path}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    setup_style()

    print()
    print("=" * 60)
    print("  FENGYUN-1C DEBRIS -- VISUALIZATION SUITE")
    print("=" * 60)
    print()

    print("Loading data...")
    df, gp_data = load_data()
    print(f"  Dataset: {len(df)} records, {df['fy1c_norad_id'].nunique()} FY-1C pieces")
    print()

    print("Generating charts...")
    chart_event_timeline(df)
    chart_fengyun_contribution(df)
    chart_altitude_distribution(df, gp_data)
    chart_object_type_breakdown(df)
    chart_top_satellites(df)
    chart_pc_distribution(df)

    print()
    print("=" * 60)
    print(f"  ALL 6 CHARTS GENERATED -> {OUTPUT_DIR}/")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
