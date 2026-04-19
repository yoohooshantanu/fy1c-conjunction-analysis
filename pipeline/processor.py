"""
CDM Data Processor
Filters, normalizes, and enriches Fengyun-1C conjunction data.
"""

import logging
import math
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# LEO upper bound — perigee altitude in km
LEO_MAX_PERIGEE_KM = 2000

# Earth radius for perigee altitude calculation (km)
EARTH_RADIUS_KM = 6371.0


def build_fengyun_id_set(catalog: list[dict]) -> set[str]:
    """
    Build a set of NORAD catalog IDs for all Fengyun-1C related objects.
    These are used to cross-reference CDMs.
    """
    ids = set()
    for obj in catalog:
        norad_id = obj.get("NORAD_CAT_ID")
        if norad_id:
            ids.add(str(norad_id))

    logger.info(f"Fengyun-1C catalog: {len(ids)} objects (debris + parent body)")

    # Log breakdown by object type
    type_counts = {}
    for obj in catalog:
        otype = obj.get("OBJECT_TYPE", "UNKNOWN")
        type_counts[otype] = type_counts.get(otype, 0) + 1
    for otype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {otype}: {count}")

    return ids


def classify_cdm(cdm: dict, fy1c_ids: set[str]) -> Optional[dict]:
    """
    Classify a CDM record: identify which object is FY-1C debris
    and which is the conjunction partner. Returns a normalized dict
    or None if neither object is FY-1C debris.
    """
    sat1_id = str(cdm.get("SAT_1_ID", ""))
    sat2_id = str(cdm.get("SAT_2_ID", ""))
    sat1_name = cdm.get("SAT_1_NAME", "")
    sat2_name = cdm.get("SAT_2_NAME", "")

    # Determine which side is Fengyun-1C
    sat1_is_fy = sat1_id in fy1c_ids or "FENGYUN 1C" in (sat1_name or "").upper()
    sat2_is_fy = sat2_id in fy1c_ids or "FENGYUN 1C" in (sat2_name or "").upper()

    if not sat1_is_fy and not sat2_is_fy:
        return None  # Neither object is FY-1C

    # If both are FY-1C debris (debris-on-debris), mark SAT_1 as the primary
    if sat1_is_fy and sat2_is_fy:
        fy_prefix = "SAT_1"
        other_prefix = "SAT_2"
        is_fy_fy = True
    elif sat1_is_fy:
        fy_prefix = "SAT_1"
        other_prefix = "SAT_2"
        is_fy_fy = False
    else:
        fy_prefix = "SAT_2"
        other_prefix = "SAT_1"
        is_fy_fy = False

    # Parse miss distance
    min_rng = cdm.get("MIN_RNG")
    miss_distance_km = float(min_rng) if min_rng is not None else None

    # Parse collision probability
    pc_raw = cdm.get("PC")
    collision_prob = float(pc_raw) if pc_raw is not None else None

    # Compute log10(Pc) for analysis — handle zero/None
    pc_log10 = None
    if collision_prob is not None and collision_prob > 0:
        pc_log10 = round(math.log10(collision_prob), 4)

    # Parse TCA
    tca = cdm.get("TCA")
    tca_date = tca[:10] if tca and len(tca) >= 10 else None
    tca_year = int(tca[:4]) if tca and len(tca) >= 4 else None
    tca_month = int(tca[5:7]) if tca and len(tca) >= 7 else None

    # Map field names — handle the asymmetric naming in cdm_public schema
    # SAT_1_ID, SAT_1_NAME, SAT1_OBJECT_TYPE, SAT1_RCS, SAT_1_EXCL_VOL
    fy_id_key = f"{fy_prefix}_ID"
    fy_name_key = f"{fy_prefix}_NAME"
    # Object type uses different naming: SAT1_OBJECT_TYPE (no underscore before 1)
    fy_type_key = f"{fy_prefix.replace('_', '')}_OBJECT_TYPE"
    fy_rcs_key = f"{fy_prefix.replace('_', '')}_RCS"

    other_id_key = f"{other_prefix}_ID"
    other_name_key = f"{other_prefix}_NAME"
    other_type_key = f"{other_prefix.replace('_', '')}_OBJECT_TYPE"
    other_rcs_key = f"{other_prefix.replace('_', '')}_RCS"

    return {
        "cdm_id": cdm.get("CDM_ID"),
        "created": cdm.get("CREATED"),
        "tca": tca,
        "tca_date": tca_date,
        "tca_year": tca_year,
        "tca_month": tca_month,
        "emergency_reportable": cdm.get("EMERGENCY_REPORTABLE"),

        # Fengyun-1C debris side
        "fy1c_norad_id": cdm.get(fy_id_key),
        "fy1c_object_name": cdm.get(fy_name_key),
        "fy1c_object_type": cdm.get(fy_type_key),
        "fy1c_rcs": cdm.get(fy_rcs_key),

        # Conjunction partner
        "other_norad_id": cdm.get(other_id_key),
        "other_object_name": cdm.get(other_name_key),
        "other_object_type": cdm.get(other_type_key),
        "other_rcs": cdm.get(other_rcs_key),

        # Conjunction parameters
        "miss_distance_km": miss_distance_km,
        "miss_distance_m": round(miss_distance_km * 1000, 2) if miss_distance_km is not None else None,
        "collision_probability": collision_prob,
        "pc_log10": pc_log10,

        # Flags
        "is_debris_on_debris": is_fy_fy,
    }


def process_cdms(
    raw_cdms: list[dict],
    fy1c_catalog: list[dict],
    gp_data: Optional[list[dict]] = None,
    leo_filter: bool = True,
) -> pd.DataFrame:
    """
    Full processing pipeline:
    1. Build FY-1C ID set from catalog
    2. Classify each CDM (identify FY-1C side vs partner)
    3. Optionally filter for LEO using GP perigee data
    4. Return clean DataFrame
    """
    fy1c_ids = build_fengyun_id_set(fy1c_catalog)

    # Step 1: Classify all CDMs
    logger.info(f"Processing {len(raw_cdms)} raw CDMs...")
    classified = []
    skipped = 0
    for cdm in raw_cdms:
        record = classify_cdm(cdm, fy1c_ids)
        if record:
            classified.append(record)
        else:
            skipped += 1

    logger.info(f"Classified: {len(classified)} FY-1C CDMs, {skipped} skipped (no FY-1C match)")

    if not classified:
        logger.warning("No FY-1C CDMs found after classification!")
        return pd.DataFrame()

    df = pd.DataFrame(classified)

    # Step 2: Deduplicate mirrored CDM pairs
    # The same conjunction can appear twice (once with FY-1C as SAT_1, once as SAT_2)
    # Create a canonical key: sorted pair of NORAD IDs + TCA
    before_dedup = len(df)
    df["_pair_key"] = df.apply(
        lambda r: tuple(sorted([str(r["fy1c_norad_id"]), str(r["other_norad_id"])])) + (r["tca"],),
        axis=1,
    )
    # Keep the one with the latest CDM creation timestamp
    df = df.sort_values("created", ascending=False).drop_duplicates(subset=["_pair_key"], keep="first")
    df = df.drop(columns=["_pair_key"])
    after_dedup = len(df)
    logger.info(f"Deduplication: {before_dedup} -> {after_dedup} (removed {before_dedup - after_dedup} mirrored pairs)")

    # Step 3: LEO filter using GP perigee altitude
    if leo_filter and gp_data:
        df = _apply_leo_filter(df, gp_data)

    # Step 4: Sort by TCA
    df = df.sort_values("tca", ascending=True).reset_index(drop=True)

    logger.info(f"Final dataset: {len(df)} records")
    return df


def _apply_leo_filter(df: pd.DataFrame, gp_data: list[dict]) -> pd.DataFrame:
    """
    Filter conjunctions to LEO regime using GP perigee altitude.
    A conjunction is LEO if BOTH objects have perigee < 2000 km.
    """
    # Build perigee lookup from GP data
    perigee_map = {}
    for gp in gp_data:
        norad_id = str(gp.get("NORAD_CAT_ID", ""))
        # GP data provides PERIAPSIS (perigee altitude in km)
        periapsis = gp.get("PERIAPSIS")
        if norad_id and periapsis is not None:
            try:
                perigee_map[norad_id] = float(periapsis)
            except (ValueError, TypeError):
                pass

    logger.info(f"GP perigee data available for {len(perigee_map)} objects")

    before_count = len(df)

    # Check both objects are LEO
    def is_leo_conjunction(row):
        fy_id = str(row.get("fy1c_norad_id", ""))
        other_id = str(row.get("other_norad_id", ""))

        fy_perigee = perigee_map.get(fy_id)
        other_perigee = perigee_map.get(other_id)

        # If perigee data is missing, include by default
        # (most FY-1C debris is LEO anyway)
        if fy_perigee is not None and fy_perigee > LEO_MAX_PERIGEE_KM:
            return False
        if other_perigee is not None and other_perigee > LEO_MAX_PERIGEE_KM:
            return False
        return True

    df = df[df.apply(is_leo_conjunction, axis=1)].reset_index(drop=True)

    removed = before_count - len(df)
    logger.info(f"LEO filter: kept {len(df)}, removed {removed} non-LEO conjunctions")

    return df


def compute_summary_stats(df: pd.DataFrame) -> dict:
    """Compute aggregate statistics for the clean dataset."""
    if df.empty:
        return {"error": "No data to summarize"}

    stats = {
        "total_cdm_records": int(len(df)),
        "unique_fy1c_debris_pieces": int(df["fy1c_norad_id"].nunique()),
        "unique_conjunction_partners": int(df["other_norad_id"].nunique()),
        "date_range": {
            "earliest_tca": str(df["tca"].min()),
            "latest_tca": str(df["tca"].max()),
        },
    }

    # Miss distance stats
    md = df["miss_distance_km"].dropna()
    if not md.empty:
        stats["miss_distance_km"] = {
            "mean": round(float(md.mean()), 4),
            "median": round(float(md.median()), 4),
            "min": round(float(md.min()), 4),
            "max": round(float(md.max()), 4),
            "std": round(float(md.std()), 4),
        }

    # Collision probability stats
    pc = df["collision_probability"].dropna()
    if not pc.empty:
        stats["collision_probability"] = {
            "max": float(pc.max()),
            "mean": float(pc.mean()),
            "median": float(pc.median()),
            "events_above_1e-4": int((pc > 1e-4).sum()),
            "events_above_1e-5": int((pc > 1e-5).sum()),
            "events_above_1e-6": int((pc > 1e-6).sum()),
        }

    # Emergency reportable
    er = df["emergency_reportable"]
    stats["emergency_reportable_count"] = int((er == "Y").sum()) if not er.empty else 0

    # Partner object type breakdown
    partner_types = df["other_object_type"].value_counts().to_dict()
    stats["conjunctions_by_partner_type"] = {k: int(v) for k, v in partner_types.items()}

    # Debris-on-debris count
    stats["debris_on_debris_count"] = int(df["is_debris_on_debris"].sum())

    # Monthly distribution
    if "tca_year" in df.columns and "tca_month" in df.columns:
        monthly = df.groupby(["tca_year", "tca_month"]).size()
        stats["monthly_distribution"] = {
            f"{int(y)}-{int(m):02d}": int(c)
            for (y, m), c in monthly.items()
        }

    return stats
