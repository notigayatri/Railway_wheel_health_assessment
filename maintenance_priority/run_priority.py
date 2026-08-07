"""
Run the Maintenance Priority Engine on a single image.

Usage:
    python maintenance_priority/run_priority.py <image_path> [asset_id]

If asset_id is omitted, the engine still runs (defect + severity +
reliability), it just skips the historical-trend factor (treated as
neutral) since there's no wheel to look up history for.
"""

import sys
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maintenance_priority.risk_engine import assess_wheel


def print_report(result):
    print("\n===== MAINTENANCE PRIORITY REPORT =====")
    print(f"Image      : {result['image']}")
    print(f"Asset ID   : {result['asset_id'] or '(none given)'}")
    print(f"Wheel Risk : {result['wheel_risk_score']}  ->  {result['wheel_action']}")

    for d in result["defects"]:
        print(f"\n  Defect        : {d['defect']}")
        print(f"    Severity           : {d['severity']}")
        print(f"    Reliability        : {d['reliability']}")
        print(f"    Weights (defect/severity/trend): "
              f"{d['defect_weight']} / {d['severity_weight']} / {d['trend_weight']}")
        print(f"    Trend note         : {d['trend_note']}")
        print(f"    Reliability factor : {d['reliability_factor']}")
        print(f"    Risk score         : {d['risk_score']}")
        print(f"    Recommended action : {d['action']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        image_path = PROJECT_ROOT / "images" / "test_image_6.jpg"
        asset_id = None
    else:
        image_path = Path(sys.argv[1])
        asset_id = sys.argv[2] if len(sys.argv) > 2 else None

    result = assess_wheel(image_path, asset_id)
    print_report(result)
