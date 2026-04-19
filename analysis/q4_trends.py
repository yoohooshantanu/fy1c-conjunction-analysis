"""
Q4: Is the conjunction trend increasing or decreasing?
Analyzes daily rates, weekly trends, and severity trajectory.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path("output/analysis")
DATA_DIR = Path("data/clean")


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_DIR / "fengyun_conjunctions.csv", parse_dates=["tca"])
    df["tca_date"] = df["tca"].dt.date

    daily = df.groupby("tca_date").agg(
        event_count=("cdm_id", "count"),
        avg_pc=("collision_probability", "mean"),
        max_pc=("collision_probability", "max"),
        avg_miss_km=("miss_distance_km", "mean"),
        payload_events=("other_object_type", lambda x: (x == "PAYLOAD").sum()),
    ).reset_index()
    daily["tca_date"] = pd.to_datetime(daily["tca_date"])
    daily = daily.sort_values("tca_date")

    # Linear trend (events per day)
    days_numeric = (daily["tca_date"] - daily["tca_date"].min()).dt.days.values
    counts = daily["event_count"].values

    if len(days_numeric) > 2:
        slope, intercept = np.polyfit(days_numeric, counts, 1)
        trend_direction = "INCREASING" if slope > 0.1 else ("DECREASING" if slope < -0.1 else "STABLE")
        events_per_day_change = slope
    else:
        slope, intercept = 0, 0
        trend_direction = "INSUFFICIENT DATA"
        events_per_day_change = 0

    # Weekly aggregation
    daily["week"] = daily["tca_date"].dt.isocalendar().week
    weekly = daily.groupby("week").agg(
        events=("event_count", "sum"),
        avg_daily=("event_count", "mean"),
        max_pc=("max_pc", "max"),
        payload_events=("payload_events", "sum"),
    ).reset_index()

    # Severity trend (is Pc getting worse?)
    if len(daily) > 2:
        pc_slope, _ = np.polyfit(days_numeric, daily["avg_pc"].values, 1)
        severity_trend = "WORSENING" if pc_slope > 0 else "IMPROVING"
    else:
        pc_slope = 0
        severity_trend = "INSUFFICIENT DATA"

    # First half vs second half comparison
    midpoint = len(daily) // 2
    first_half = daily.iloc[:midpoint]
    second_half = daily.iloc[midpoint:]

    findings = {
        "question": "Is the conjunction trend increasing or decreasing?",
        "trend_direction": trend_direction,
        "slope_events_per_day": round(float(slope), 4),
        "severity_trend": severity_trend,
        "avg_events_per_day": round(float(daily["event_count"].mean()), 1),
        "max_events_single_day": int(daily["event_count"].max()),
        "peak_day": str(daily.loc[daily["event_count"].idxmax(), "tca_date"].date()),
        "first_half_avg": round(float(first_half["event_count"].mean()), 1),
        "second_half_avg": round(float(second_half["event_count"].mean()), 1),
        "weekly_breakdown": weekly.to_dict(orient="records"),
        "daily_stats": {
            "min_events": int(daily["event_count"].min()),
            "max_events": int(daily["event_count"].max()),
            "std_events": round(float(daily["event_count"].std()), 1),
        },
        "finding": (
            f"Trend is {trend_direction} ({slope:+.2f} events/day). "
            f"Average {daily['event_count'].mean():.1f} events/day, peak {int(daily['event_count'].max())} events. "
            f"Severity is {severity_trend}. "
            f"First half avg: {first_half['event_count'].mean():.1f}/day, "
            f"second half: {second_half['event_count'].mean():.1f}/day."
        ),
    }

    with open(OUTPUT_DIR / "q4_trends.json", "w") as f:
        json.dump(findings, f, indent=2, default=str)

    print(f"  FINDING: Trend = {trend_direction} ({slope:+.3f} events/day)")
    print(f"  FINDING: Avg {daily['event_count'].mean():.1f} events/day, peak = {daily['event_count'].max()}")
    print(f"  FINDING: Severity trend = {severity_trend}")
    print(f"  FINDING: 1st half avg = {first_half['event_count'].mean():.1f}, 2nd half = {second_half['event_count'].mean():.1f}")
    return findings


if __name__ == "__main__":
    print("\n=== Q4: TREND OVER TIME ===\n")
    run()
    print()
