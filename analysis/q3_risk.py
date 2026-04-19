"""
Q3: Who is at risk from Fengyun-1C debris?
Identifies most threatened satellites, constellations, and operators.
"""
import json
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path("output/analysis")
DATA_DIR = Path("data/clean")
RAW_DIR = Path("data/raw")


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_DIR / "fengyun_conjunctions.csv")

    # Focus on events threatening active payloads
    payloads = df[df["other_object_type"] == "PAYLOAD"].copy()

    # Load GP data for country codes
    gp_data = []
    for f in sorted(RAW_DIR.glob("gp_batch_*.json")):
        gp_data.extend(json.load(open(f)))

    country_map = {}
    name_map = {}
    for gp in gp_data:
        nid = str(gp.get("NORAD_CAT_ID", ""))
        country_map[nid] = gp.get("COUNTRY_CODE", "UNKNOWN")
        name_map[nid] = gp.get("OBJECT_NAME", "")

    # Top affected payloads
    top_payloads = payloads.groupby(["other_norad_id", "other_object_name"]).agg(
        event_count=("cdm_id", "count"),
        max_pc=("collision_probability", "max"),
        min_miss_km=("miss_distance_km", "min"),
        avg_miss_km=("miss_distance_km", "mean"),
    ).reset_index().sort_values("event_count", ascending=False)

    top_payloads["country"] = top_payloads["other_norad_id"].astype(str).map(country_map).fillna("UNK")

    # Identify constellation patterns
    def detect_constellation(name):
        name = str(name).upper()
        constellations = {
            "IRIDIUM": "Iridium",
            "STARLINK": "Starlink",
            "ONEWEB": "OneWeb",
            "COSMOS": "COSMOS (Russia)",
            "GLOBALSTAR": "Globalstar",
            "ORBCOMM": "Orbcomm",
        }
        for key, label in constellations.items():
            if key in name:
                return label
        return "Other"

    top_payloads["constellation"] = top_payloads["other_object_name"].apply(detect_constellation)

    # Top 15 most affected payloads
    top15 = top_payloads.head(15)

    # Country risk breakdown (payloads only)
    country_risk = top_payloads.groupby("country").agg(
        satellites=("other_norad_id", "nunique"),
        total_events=("event_count", "sum"),
        max_pc=("max_pc", "max"),
    ).sort_values("total_events", ascending=False)

    # Constellation breakdown
    constellation_risk = top_payloads.groupby("constellation").agg(
        satellites=("other_norad_id", "nunique"),
        total_events=("event_count", "sum"),
    ).sort_values("total_events", ascending=False)

    # Most dangerous conjunction (highest Pc involving a payload)
    most_dangerous_idx = payloads["collision_probability"].idxmax()
    most_dangerous = payloads.loc[most_dangerous_idx]

    findings = {
        "question": "Who is at risk from Fengyun-1C debris?",
        "payloads_at_risk": int(top_payloads["other_norad_id"].nunique()),
        "total_payload_events": int(len(payloads)),
        "top_15_payloads": top15[[
            "other_object_name", "other_norad_id", "country",
            "constellation", "event_count", "max_pc", "min_miss_km"
        ]].to_dict(orient="records"),
        "country_risk": {
            row.Index: {"satellites": int(row.satellites), "events": int(row.total_events)}
            for row in country_risk.head(10).itertuples()
        },
        "constellation_risk": {
            row.Index: {"satellites": int(row.satellites), "events": int(row.total_events)}
            for row in constellation_risk.itertuples()
        },
        "most_dangerous_event": {
            "satellite": str(most_dangerous["other_object_name"]),
            "norad_id": int(most_dangerous["other_norad_id"]),
            "collision_probability": float(most_dangerous["collision_probability"]),
            "miss_distance_km": float(most_dangerous["miss_distance_km"]),
            "tca": str(most_dangerous.get("tca", "")),
        },
        "finding": (
            f"{int(top_payloads['other_norad_id'].nunique())} active payloads are at risk. "
            f"Most dangerous: {most_dangerous['other_object_name']} with Pc={most_dangerous['collision_probability']:.2e}. "
            f"Top countries: {', '.join(country_risk.head(3).index.tolist())}."
        ),
    }

    with open(OUTPUT_DIR / "q3_risk.json", "w") as f:
        json.dump(findings, f, indent=2)

    print(f"  FINDING: {top_payloads['other_norad_id'].nunique()} active payloads at risk")
    print(f"  FINDING: Most dangerous = {most_dangerous['other_object_name']} (Pc={most_dangerous['collision_probability']:.2e})")
    print(f"  Top payloads:")
    for _, row in top15.head(10).iterrows():
        print(f"    {row['other_object_name']:25s} | {row['country']:4s} | {int(row['event_count'])} events | max Pc={row['max_pc']:.2e}")
    print(f"  Country breakdown:")
    for country, data in list(country_risk.head(5).iterrows()):
        print(f"    {country:6s} | {int(data['satellites'])} sats | {int(data['total_events'])} events")
    return findings


if __name__ == "__main__":
    print("\n=== Q3: WHO IS AT RISK? ===\n")
    run()
    print()
