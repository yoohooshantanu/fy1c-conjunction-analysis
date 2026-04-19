"""
The 'So What?' Metric:
How many FY-1C conjunction alerts does a typical satellite face per month?
"""
import json
from pathlib import Path
import pandas as pd

df = pd.read_csv("data/clean/fengyun_conjunctions.csv", parse_dates=["tca"])

# Load GP orbital data
gp_data = []
for f in sorted(Path("data/raw").glob("gp_batch_*.json")):
    gp_data.extend(json.load(open(f)))

orb = {}
for gp in gp_data:
    nid = str(gp.get("NORAD_CAT_ID", ""))
    try:
        orb[nid] = {
            "perigee": float(gp.get("PERIAPSIS", 0)),
            "inc": float(gp.get("INCLINATION", 0)),
        }
    except (ValueError, TypeError):
        pass

# Time span
date_range_days = (df["tca"].max() - df["tca"].min()).days
weeks = date_range_days / 7
months = date_range_days / 30.44

print(f"Date span: {date_range_days} days ({weeks:.1f} weeks, {months:.1f} months)")
print()

# --- PAYLOADS in 600-900km band ---
payloads = df[df["other_object_type"] == "PAYLOAD"].copy()
payloads["perigee"] = payloads["other_norad_id"].astype(str).map(
    lambda x: orb.get(x, {}).get("perigee", 0)
)
payloads["inc"] = payloads["other_norad_id"].astype(str).map(
    lambda x: orb.get(x, {}).get("inc", 0)
)

# SSO payloads (600-900km, inc 96-100)
sso = payloads[(payloads["perigee"] >= 600) & (payloads["perigee"] <= 900) &
               (payloads["inc"] >= 96) & (payloads["inc"] <= 100)]
per_sso = sso.groupby(["other_norad_id", "other_object_name"]).size().reset_index(name="events")

# All payloads in 600-900km
band = payloads[(payloads["perigee"] >= 600) & (payloads["perigee"] <= 900)]
per_band = band.groupby(["other_norad_id", "other_object_name"]).size().reset_index(name="events")

print("=== SSO PAYLOADS (600-900km, inc 96-100) ===")
print(f"  Satellites affected: {len(per_sso)}")
print(f"  Total events: {len(sso)}")
if not per_sso.empty:
    avg_per_month = per_sso["events"].mean() / months
    max_per_month = per_sso["events"].max() / months
    print(f"  Avg FY-1C alerts per satellite per month: {avg_per_month:.1f}")
    print(f"  Worst-case (max) per month: {max_per_month:.1f}")

print()
print("=== ALL PAYLOADS (600-900km, any inclination) ===")
print(f"  Satellites affected: {len(per_band)}")
print(f"  Total events: {len(band)}")
if not per_band.empty:
    avg_per_month = per_band["events"].mean() / months
    max_per_month = per_band["events"].max() / months
    print(f"  Avg FY-1C alerts per satellite per month: {avg_per_month:.1f}")
    print(f"  Worst-case (max) per month: {max_per_month:.1f}")

print()
print("=== HEADLINE METRIC ===")

# The killer stat: per satellite in risk zone
all_objects_in_band = df.copy()
all_objects_in_band["other_perigee"] = all_objects_in_band["other_norad_id"].astype(str).map(
    lambda x: orb.get(x, {}).get("perigee", 0)
)
risk_zone = all_objects_in_band[
    (all_objects_in_band["other_perigee"] >= 600) &
    (all_objects_in_band["other_perigee"] <= 900)
]
per_obj = risk_zone.groupby("other_norad_id").size()

avg_all = per_obj.mean() / months
median_all = per_obj.median() / months
p75 = per_obj.quantile(0.75) / months
worst = per_obj.max() / months

print(f"  Objects in 600-900km band: {len(per_obj)}")
print(f"  Avg FY-1C conjunctions per object per month: {avg_all:.1f}")
print(f"  Median: {median_all:.1f}")
print(f"  Top quartile (75th pct): {p75:.1f}")
print(f"  Worst satellite per month: {worst:.1f}")
print()

# Per week version
avg_week = per_obj.mean() / weeks
print(f"  >>> A typical satellite at 600-900km faces ~{avg_week:.1f} FY-1C conjunction alerts per week")
print(f"  >>> That's ~{avg_all:.0f} per month, from debris created by a single event 19 years ago")
print()

# Save
result = {
    "headline": f"A typical satellite at 600-900km altitude faces ~{avg_all:.0f} Fengyun-1C conjunction alerts per month",
    "detail": f"~{avg_week:.1f} alerts/week from debris of a single 2007 ASAT test",
    "avg_per_month": round(avg_all, 1),
    "avg_per_week": round(avg_week, 2),
    "median_per_month": round(median_all, 1),
    "p75_per_month": round(p75, 1),
    "worst_per_month": round(worst, 1),
    "sso_avg_per_month": round(per_sso["events"].mean() / months, 1) if not per_sso.empty else None,
    "objects_in_risk_zone": len(per_obj),
    "risk_zone_km": "600-900",
}
Path("output/analysis").mkdir(parents=True, exist_ok=True)
with open("output/analysis/impact_metric.json", "w") as f:
    json.dump(result, f, indent=2)
print(f"Saved -> output/analysis/impact_metric.json")
