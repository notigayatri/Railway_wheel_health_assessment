"""
Maintenance Priority Engine.

Combines four existing signals into one risk score per defect:

    defect type        -> detection/YOLO         (via severity module's labels)
    severity            -> severity/ (K-Means clustering module)
    reliability          -> reliability/ (Test-Time Augmentation module)
    historical trend      -> core/wheel_lifecycle/ (digital health record)

    risk = (defect_weight + severity_weight + trend_weight) * reliability_factor

This module does NOT modify or import from main.py, and does not change
any existing file -- it calls the same underlying functions main.py
already uses (predict_image, calculate_reliability) and adds the risk
layer on top.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maintenance_priority.config import (
    DEFECT_TYPE_WEIGHT,
    DEFAULT_DEFECT_WEIGHT,
    SEVERITY_WEIGHT,
    DEFAULT_SEVERITY_WEIGHT,
    RELIABILITY_FACTOR,
    DEFAULT_RELIABILITY_FACTOR,
    action_for_score,
)
from maintenance_priority.trend import get_trend_weight


def score_defect(defect_name, severity_label, reliability_label, asset_id=None):
    """
    Compute the risk score (and recommended action) for ONE defect
    found on ONE wheel image.
    """
    defect_weight = DEFECT_TYPE_WEIGHT.get(defect_name, DEFAULT_DEFECT_WEIGHT)
    severity_weight = SEVERITY_WEIGHT.get(severity_label, DEFAULT_SEVERITY_WEIGHT)
    reliability_factor = RELIABILITY_FACTOR.get(reliability_label, DEFAULT_RELIABILITY_FACTOR)
    trend_weight, trend_note = get_trend_weight(asset_id)

    raw_score = (defect_weight + severity_weight + trend_weight) * reliability_factor
    risk_score = round(min(raw_score, 100), 1)  # cap at 100 for readability

    return {
        "defect": defect_name,
        "severity": severity_label,
        "reliability": reliability_label,
        "defect_weight": defect_weight,
        "severity_weight": severity_weight,
        "trend_weight": trend_weight,
        "trend_note": trend_note,
        "reliability_factor": reliability_factor,
        "risk_score": risk_score,
        "action": action_for_score(risk_score),
    }


def _relative_display_path(image_path):
    """Show paths relative to the project root instead of a full
    absolute path (e.g. 'images/test_image_1.jpg' instead of
    'C:\\Users\\...\\Railway_wheel_health_assessment\\images\\test_image_1.jpg')."""
    try:
        return str(Path(image_path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(image_path)


def assess_wheel(image_path, asset_id=None):
    """
    Runs the FULL pipeline for one image:
      severity module -> reliability module -> risk scoring per defect
    Returns a list of per-defect risk dicts (worst defect first) plus
    the wheel-level score (its single worst defect's score, since that's
    what should drive an inspection decision).
    """
    from severity.predict_severity import predict_image
    from reliability.reliability import calculate_reliability

    severity_results = predict_image(image_path)          # {defect: severity_label}
    reliability_results = calculate_reliability(image_path)  # {defect: {...}}

    defect_scores = []
    for defect, rel_info in reliability_results.items():
        severity_label = severity_results.get(defect, "Unknown")
        reliability_label = rel_info["reliability"]
        result = score_defect(defect, severity_label, reliability_label, asset_id)

        if severity_label == "Unknown":
            result["trend_note"] += (
                " | NOTE: this defect was only picked up during test-time "
                "augmentation (flip/brightness/rotation), not the primary scan. "
                "Severity weight defaulted to a neutral placeholder -- treat "
                "this reading as a borderline/unconfirmed detection."
            )

        defect_scores.append(result)

    defect_scores.sort(key=lambda d: d["risk_score"], reverse=True)

    wheel_risk_score = defect_scores[0]["risk_score"] if defect_scores else 0
    wheel_action = action_for_score(wheel_risk_score)

    return {
        "asset_id": asset_id,
        "image": _relative_display_path(image_path),
        "wheel_risk_score": wheel_risk_score,
        "wheel_action": wheel_action,
        "defects": defect_scores,
    }
