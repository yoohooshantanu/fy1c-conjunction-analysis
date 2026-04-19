"""
Fengyun-1C Debris LEO Conjunction Risk — Data Pipeline
Main entry point.

Usage:
    python -m pipeline.run_pipeline
    python -m pipeline.run_pipeline --from 2025-01-01 --to 2026-04-01
    python -m pipeline.run_pipeline --refresh          # ignore cache
    python -m pipeline.run_pipeline --no-leo-filter    # skip LEO filtering
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from pipeline.spacetrack_client import SpaceTrackClient
from pipeline.processor import process_cdms, compute_summary_stats

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fengyun-1C Debris LEO Conjunction Data Pipeline"
    )
    parser.add_argument(
        "--from", dest="date_from", default="2025-01-01",
        help="TCA start date (YYYY-MM-DD). Default: 2025-01-01"
    )
    parser.add_argument(
        "--to", dest="date_to", default="now",
        help="TCA end date (YYYY-MM-DD or 'now'). Default: now"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force re-download from Space-Track (ignore cache)"
    )
    parser.add_argument(
        "--no-leo-filter", action="store_true",
        help="Skip LEO perigee filtering"
    )
    parser.add_argument(
        "--output-dir", default="data/clean",
        help="Output directory for clean datasets. Default: data/clean"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Load credentials
    load_dotenv()
    username = os.getenv("SPACETRACK_EMAIL") or os.getenv("SPACETRACK_USER")
    password = os.getenv("SPACETRACK_PASSWORD") or os.getenv("SPACETRACK_PASS")

    if not username or not password:
        logger.error(
            "Missing credentials. Set SPACETRACK_EMAIL and SPACETRACK_PASSWORD in .env file.\n"
            "  -> Copy .env.example to .env and fill in your Space-Track.org credentials.\n"
            "  -> Register at https://www.space-track.org/auth/createAccount"
        )
        sys.exit(1)

    # ──────────────────────────────────────────
    # Initialize client
    # ──────────────────────────────────────────
    client = SpaceTrackClient(username, password)

    print()
    print("=" * 60)
    print("  FENGYUN-1C DEBRIS -- LEO CONJUNCTION DATA PIPELINE")
    print("=" * 60)
    print(f"  Date range : {args.date_from} -> {args.date_to}")
    print(f"  LEO filter : {'ON' if not args.no_leo_filter else 'OFF'}")
    print(f"  Cache      : {'REFRESH' if args.refresh else 'USE CACHED'}")
    print("=" * 60)
    print()

    # ──────────────────────────────────────────
    # Step 1: Fetch Fengyun-1C catalog
    # ──────────────────────────────────────────
    logger.info("STEP 1/4 — Fetching Fengyun-1C satellite catalog...")
    fy_catalog = client.get_fengyun_catalog(force_refresh=args.refresh)
    logger.info(f"Catalog: {len(fy_catalog)} objects")

    # ──────────────────────────────────────────
    # Step 2: Fetch CDM public data
    # ──────────────────────────────────────────
    logger.info("STEP 2/4 — Fetching public CDM data for Fengyun-1C...")
    raw_cdms = client.get_cdm_public_by_name(
        date_from=args.date_from,
        date_to=args.date_to,
        force_refresh=args.refresh,
    )
    logger.info(f"Raw CDMs fetched: {len(raw_cdms)}")

    if not raw_cdms:
        logger.warning("No CDM data returned. Check date range and API access.")
        sys.exit(0)

    # ──────────────────────────────────────────
    # Step 3: Fetch GP data for LEO filtering
    # ──────────────────────────────────────────
    gp_data = None
    if not args.no_leo_filter:
        logger.info("STEP 3/4 — Fetching GP orbital elements for LEO filtering...")

        # Collect all unique NORAD IDs from CDMs
        norad_ids = set()
        for cdm in raw_cdms:
            for key in ["SAT_1_ID", "SAT_2_ID"]:
                nid = cdm.get(key)
                if nid:
                    norad_ids.add(int(nid))

        logger.info(f"Unique objects in CDMs: {len(norad_ids)}")

        gp_data = client.get_gp_data(
            sorted(norad_ids),
            force_refresh=args.refresh,
        )
        logger.info(f"GP records fetched: {len(gp_data)}")
    else:
        logger.info("STEP 3/4 — Skipped (LEO filter disabled)")

    # ──────────────────────────────────────────
    # Step 4: Process and output
    # ──────────────────────────────────────────
    logger.info("STEP 4/4 — Processing and generating output...")

    df = process_cdms(
        raw_cdms=raw_cdms,
        fy1c_catalog=fy_catalog,
        gp_data=gp_data,
        leo_filter=not args.no_leo_filter,
    )

    if df.empty:
        logger.warning("Pipeline produced empty dataset. Exiting.")
        sys.exit(0)

    # Compute summary
    stats = compute_summary_stats(df)

    # Write outputs
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fix Windows console encoding for special chars
    import io, sys as _sys
    if hasattr(_sys.stdout, 'reconfigure'):
        _sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    csv_path = output_dir / "fengyun_conjunctions.csv"
    json_path = output_dir / "fengyun_conjunctions.json"
    stats_path = output_dir / "summary_stats.json"

    # CSV
    df.to_csv(csv_path, index=False)
    logger.info(f"[OK] CSV  -> {csv_path} ({len(df)} rows)")

    # JSON
    df.to_json(json_path, orient="records", indent=2, date_format="iso")
    logger.info(f"[OK] JSON -> {json_path} ({len(df)} records)")

    # Summary stats
    stats["pipeline_run"] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "date_from": args.date_from,
        "date_to": args.date_to,
        "leo_filter": not args.no_leo_filter,
    }
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"[OK] Stats -> {stats_path}")

    # ──────────────────────────────────────────
    # Print summary
    # ──────────────────────────────────────────
    print()
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Total CDM records       : {stats['total_cdm_records']}")
    print(f"  Unique FY-1C pieces     : {stats['unique_fy1c_debris_pieces']}")
    print(f"  Unique partners         : {stats['unique_conjunction_partners']}")
    print(f"  Date range              : {stats['date_range']['earliest_tca'][:10]}"
          f" -> {stats['date_range']['latest_tca'][:10]}")

    if "miss_distance_km" in stats:
        md = stats["miss_distance_km"]
        print(f"  Avg miss distance       : {md['mean']:.3f} km")
        print(f"  Min miss distance       : {md['min']:.3f} km")

    if "collision_probability" in stats:
        pc = stats["collision_probability"]
        print(f"  Max Pc                  : {pc['max']:.2e}")
        print(f"  Events Pc > 1e-4        : {pc['events_above_1e-4']}")
        print(f"  Events Pc > 1e-5        : {pc['events_above_1e-5']}")

    print(f"  Emergency reportable    : {stats['emergency_reportable_count']}")
    print(f"  Debris-on-debris        : {stats['debris_on_debris_count']}")

    if "conjunctions_by_partner_type" in stats:
        print(f"  Partner type breakdown  :")
        for ptype, count in sorted(stats["conjunctions_by_partner_type"].items(), key=lambda x: -x[1]):
            print(f"    {ptype:20s} : {count}")

    print("=" * 60)
    print(f"  Output files:")
    print(f"    {csv_path}")
    print(f"    {json_path}")
    print(f"    {stats_path}")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
