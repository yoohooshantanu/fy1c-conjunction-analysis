"""
Q1: How common is Fengyun-1C debris in LEO conjunctions?
Fetches total CDM count for the same period and computes FY-1C share.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Add parent dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.spacetrack_client import SpaceTrackClient

OUTPUT_DIR = Path("output/analysis")
DATA_DIR = Path("data/clean")
RAW_DIR = Path("data/raw")


def run():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    load_dotenv()

    # Load our FY-1C dataset
    df = pd.read_csv(DATA_DIR / "fengyun_conjunctions.csv", parse_dates=["tca"])
    date_from = df["tca_date"].min()
    date_to = df["tca_date"].max()
    print(f"  FY-1C dataset: {len(df)} events, {date_from} to {date_to}")

    # Fetch total CDM count for same period
    total_cache = RAW_DIR / "cdm_total_count.json"
    if total_cache.exists():
        with open(total_cache) as f:
            total_cdms = json.load(f)
        print(f"  Total CDMs (cached): {len(total_cdms)}")
    else:
        user = os.getenv("SPACETRACK_EMAIL") or os.getenv("SPACETRACK_USER")
        pwd = os.getenv("SPACETRACK_PASSWORD") or os.getenv("SPACETRACK_PASS")
        client = SpaceTrackClient(user, pwd)
        # Query ALL cdm_public for the period
        url = (
            f"https://www.space-track.org/basicspacedata/query"
            f"/class/cdm_public"
            f"/TCA/{date_from}--{date_to}"
            f"/orderby/TCA asc"
            f"/format/json"
        )
        total_cdms = client._query(url, cache_key="cdm_total_count")
        print(f"  Total CDMs fetched: {len(total_cdms)}")

    total_count = len(total_cdms)
    fy_count = len(df)
    fy_pct = (fy_count / total_count * 100) if total_count > 0 else 0

    # Breakdown by object type in total CDMs
    total_debris_events = 0
    for cdm in total_cdms:
        t1 = (cdm.get("SAT1_OBJECT_TYPE") or "").upper()
        t2 = (cdm.get("SAT2_OBJECT_TYPE") or "").upper()
        if "DEBRIS" in t1 or "DEBRIS" in t2:
            total_debris_events += 1

    debris_pct = (total_debris_events / total_count * 100) if total_count > 0 else 0
    fy_of_debris = (fy_count / total_debris_events * 100) if total_debris_events > 0 else 0

    # Unique FY-1C debris pieces in catalog vs involved in conjunctions
    cat = json.load(open(RAW_DIR / "fengyun_catalog.json"))
    total_fy_catalog = len([c for c in cat if c.get("OBJECT_TYPE") == "DEBRIS"])
    active_fy_pieces = df["fy1c_norad_id"].nunique()
    active_pct = (active_fy_pieces / total_fy_catalog * 100) if total_fy_catalog > 0 else 0

    findings = {
        "question": "How common is Fengyun-1C debris in LEO conjunctions?",
        "period": f"{date_from} to {date_to}",
        "total_cdm_events": total_count,
        "fengyun_cdm_events": fy_count,
        "fengyun_share_pct": round(fy_pct, 2),
        "total_debris_events": total_debris_events,
        "debris_share_of_all_pct": round(debris_pct, 2),
        "fengyun_share_of_debris_pct": round(fy_of_debris, 2),
        "total_fy1c_debris_cataloged": total_fy_catalog,
        "fy1c_pieces_in_conjunctions": active_fy_pieces,
        "fy1c_active_pct": round(active_pct, 2),
        "finding": (
            f"Fengyun-1C debris accounts for {fy_pct:.1f}% of ALL conjunction events "
            f"and {fy_of_debris:.1f}% of all debris-involved conjunctions in LEO. "
            f"Only {active_fy_pieces} of {total_fy_catalog} cataloged fragments "
            f"({active_pct:.1f}%) were involved in conjunction events during this period."
        ),
    }

    with open(OUTPUT_DIR / "q1_prevalence.json", "w") as f:
        json.dump(findings, f, indent=2)

    print(f"\n  FINDING 1: FY-1C = {fy_pct:.1f}% of ALL LEO conjunctions")
    print(f"  FINDING 2: FY-1C = {fy_of_debris:.1f}% of debris-involved conjunctions")
    print(f"  FINDING 3: {active_fy_pieces}/{total_fy_catalog} FY-1C pieces active ({active_pct:.1f}%)")
    return findings


if __name__ == "__main__":
    print("\n=== Q1: HOW COMMON IS FENGYUN DEBRIS? ===\n")
    run()
    print()
