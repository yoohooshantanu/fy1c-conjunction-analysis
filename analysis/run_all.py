"""
Run all 4 analysis scripts and compile findings.
Usage: python -m analysis.run_all
"""
import json
from pathlib import Path

from analysis import q1_prevalence, q2_orbits, q3_risk, q4_trends

OUTPUT_DIR = Path("output/analysis")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 60)
    print("  FENGYUN-1C CORE ANALYSIS -- PHASE 3")
    print("=" * 60)

    print("\n--- Q1: HOW COMMON IS FENGYUN DEBRIS? ---")
    f1 = q1_prevalence.run()

    print("\n--- Q2: WHICH ORBITS ARE MOST AFFECTED? ---")
    f2 = q2_orbits.run()

    print("\n--- Q3: WHO IS AT RISK? ---")
    f3 = q3_risk.run()

    print("\n--- Q4: TREND OVER TIME ---")
    f4 = q4_trends.run()

    # Compile all findings
    compiled = {
        "title": "Fengyun-1C Debris and Its Role in LEO Conjunction Risk (2026)",
        "findings": [
            f1.get("finding", ""),
            f2.get("finding", ""),
            f3.get("finding", ""),
            f4.get("finding", ""),
        ],
        "q1": f1,
        "q2": f2,
        "q3": f3,
        "q4": f4,
    }

    with open(OUTPUT_DIR / "all_findings.json", "w") as f:
        json.dump(compiled, f, indent=2, default=str)

    print()
    print("=" * 60)
    print("  COMPILED FINDINGS")
    print("=" * 60)
    for i, finding in enumerate(compiled["findings"], 1):
        print(f"\n  [{i}] {finding}")
    print()
    print(f"  All results -> {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
