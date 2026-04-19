"""
Q2: Which orbits are most affected by Fengyun-1C conjunctions?
Analyzes altitude bands and inclination clusters.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path("output/analysis")
DATA_DIR = Path("data/clean")
RAW_DIR = Path("data/raw")


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_DIR / "fengyun_conjunctions.csv")

    # Load GP data for orbital params
    gp_data = []
    for f in sorted(RAW_DIR.glob("gp_batch_*.json")):
        gp_data.extend(json.load(open(f)))

    # Build lookup: NORAD_ID -> {periapsis, apoapsis, inclination}
    orbital = {}
    for gp in gp_data:
        nid = str(gp.get("NORAD_CAT_ID", ""))
        try:
            orbital[nid] = {
                "periapsis": float(gp.get("PERIAPSIS", 0)),
                "apoapsis": float(gp.get("APOAPSIS", 0)),
                "inclination": float(gp.get("INCLINATION", 0)),
                "period": float(gp.get("PERIOD", 0)),
                "object_type": gp.get("OBJECT_TYPE", ""),
                "country": gp.get("COUNTRY_CODE", ""),
            }
        except (ValueError, TypeError):
            pass

    # Enrich dataset with orbital params for BOTH objects
    rows = []
    for _, row in df.iterrows():
        fy_id = str(row["fy1c_norad_id"])
        other_id = str(row["other_norad_id"])
        fy_orb = orbital.get(fy_id, {})
        other_orb = orbital.get(other_id, {})

        rows.append({
            "cdm_id": row["cdm_id"],
            "fy1c_norad_id": fy_id,
            "other_norad_id": other_id,
            "other_name": row["other_object_name"],
            "other_type": row["other_object_type"],
            "miss_distance_km": row["miss_distance_km"],
            "collision_probability": row["collision_probability"],
            # FY-1C orbital
            "fy_perigee": fy_orb.get("periapsis"),
            "fy_apogee": fy_orb.get("apoapsis"),
            "fy_inclination": fy_orb.get("inclination"),
            # Partner orbital
            "other_perigee": other_orb.get("periapsis"),
            "other_apogee": other_orb.get("apoapsis"),
            "other_inclination": other_orb.get("inclination"),
            "other_country": other_orb.get("country", ""),
        })

    edf = pd.DataFrame(rows)

    # --- Altitude band analysis ---
    alt_bins = [0, 400, 500, 600, 700, 800, 900, 1000, 1200, 2000]
    alt_labels = ["<400", "400-500", "500-600", "600-700", "700-800", "800-900", "900-1000", "1000-1200", "1200+"]

    # FY-1C debris altitude distribution
    fy_perigees = edf["fy_perigee"].dropna()
    fy_alt_dist = pd.cut(fy_perigees, bins=alt_bins, labels=alt_labels).value_counts().sort_index()

    # Partner altitude distribution
    other_perigees = edf["other_perigee"].dropna()
    other_alt_dist = pd.cut(other_perigees, bins=alt_bins, labels=alt_labels).value_counts().sort_index()

    # Peak altitude band
    peak_band = fy_alt_dist.idxmax()
    peak_count = int(fy_alt_dist.max())

    # --- Inclination analysis ---
    inc_bins = [0, 30, 60, 80, 90, 100, 110, 180]
    inc_labels = ["0-30", "30-60", "60-80", "80-90", "90-100", "100-110", "110+"]

    fy_inc = edf["fy_inclination"].dropna()
    fy_inc_dist = pd.cut(fy_inc, bins=inc_bins, labels=inc_labels).value_counts().sort_index()

    other_inc = edf["other_inclination"].dropna()
    other_inc_dist = pd.cut(other_inc, bins=inc_bins, labels=inc_labels).value_counts().sort_index()

    peak_inc_band = fy_inc_dist.idxmax()

    # --- Country analysis ---
    country_counts = edf[edf["other_country"] != ""]["other_country"].value_counts().head(10)

    findings = {
        "question": "Which orbits are most affected?",
        "altitude_bands": {
            "fy1c_distribution": {k: int(v) for k, v in fy_alt_dist.items()},
            "partner_distribution": {k: int(v) for k, v in other_alt_dist.items()},
            "peak_band_km": peak_band,
            "peak_count": peak_count,
        },
        "inclination_clusters": {
            "fy1c_distribution": {k: int(v) for k, v in fy_inc_dist.items()},
            "partner_distribution": {k: int(v) for k, v in other_inc_dist.items()},
            "dominant_cluster": peak_inc_band,
        },
        "fy1c_median_perigee_km": round(float(fy_perigees.median()), 1) if not fy_perigees.empty else None,
        "fy1c_median_inclination": round(float(fy_inc.median()), 1) if not fy_inc.empty else None,
        "countries_most_affected": {k: int(v) for k, v in country_counts.items()},
        "finding": (
            f"Conjunctions concentrate in the {peak_band} km altitude band "
            f"({peak_count} events). FY-1C debris clusters near "
            f"{round(float(fy_inc.median()), 1) if not fy_inc.empty else '?'}deg inclination (sun-synchronous). "
            f"Top affected countries: {', '.join(country_counts.head(3).index.tolist())}."
        ),
    }

    # Save enriched dataset for other analyses
    edf.to_csv(OUTPUT_DIR / "enriched_conjunctions.csv", index=False)

    with open(OUTPUT_DIR / "q2_orbits.json", "w") as f:
        json.dump(findings, f, indent=2)

    print(f"  FINDING: Peak altitude band = {peak_band} km ({peak_count} events)")
    print(f"  FINDING: Dominant inclination = {peak_inc_band} deg")
    print(f"  FINDING: Median FY-1C perigee = {fy_perigees.median():.0f} km")
    print(f"  FINDING: Top countries: {dict(country_counts.head(5))}")
    return findings


if __name__ == "__main__":
    print("\n=== Q2: WHICH ORBITS ARE MOST AFFECTED? ===\n")
    run()
    print()
