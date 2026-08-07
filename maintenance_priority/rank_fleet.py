"""
Rank multiple wheels by maintenance risk -- this produces the
"which wheels should engineers inspect first" table from the spec:

    Wheel   Risk Score   Action
    W101    92           Immediate inspection
    W205    68           Schedule maintenance
    W330    24           Monitor only

Usage:
    python maintenance_priority/rank_fleet.py

Edit the WHEELS list below to point at your own (asset_id, image_path)
pairs, or import assess_wheel()/rank_wheels() from this module and call
it programmatically with your own list.
"""

import sys
from pathlib import Path

import warnings
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maintenance_priority.risk_engine import assess_wheel

# Edit this list: (asset_id, image_path). asset_id should match an
# asset_id already in the wheel_lifecycle database if you want the
# historical-trend factor to kick in; otherwise trend defaults to neutral.
WHEELS = [
    ("WH000001", PROJECT_ROOT / "images" / "test_image_1.jpg"),
    ("WH000002", PROJECT_ROOT / "images" / "test_image_2.jpg"),
    ("WH000003", PROJECT_ROOT / "images" / "test_image_3.jpg"),
    ("WH000004", PROJECT_ROOT / "images" / "test_image_4.jpg"),
    ("WH000005", PROJECT_ROOT / "images" / "test_image_5.jpg"),
    ("WH000006", PROJECT_ROOT / "images" / "test_image_6.jpg"),
]


def rank_wheels(wheel_list):
    results = []
    for asset_id, image_path in wheel_list:
        try:
            results.append(assess_wheel(image_path, asset_id))
        except Exception as exc:
            print(f"Skipping {asset_id} ({image_path}): {exc}")

    results.sort(key=lambda r: r["wheel_risk_score"], reverse=True)
    return results


def print_table(results):
    print("\n===== FLEET MAINTENANCE PRIORITY =====")
    print(f"{'Wheel':<12}{'Risk Score':<14}{'Action'}")
    print("-" * 45)
    for r in results:
        wheel_label = r["asset_id"] or Path(r["image"]).stem
        print(f"{wheel_label:<12}{r['wheel_risk_score']:<14}{r['wheel_action']}")


if __name__ == "__main__":
    ranked = rank_wheels(WHEELS)
    print_table(ranked)
