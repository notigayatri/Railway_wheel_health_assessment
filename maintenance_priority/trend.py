"""
Reads a wheel's inspection history from the digital wheel-lifecycle
database (core/wheel_lifecycle) and turns it into a trend weight:
is this wheel's condition worsening, stable, or improving over time?

If the wheel has no history yet (new asset, or DB not populated),
this falls back to a neutral "no history" weight -- it never fails
or blocks the rest of the risk calculation.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maintenance_priority.config import (
    SEVERITY_RANK,
    TREND_WEIGHT_WORSENING,
    TREND_WEIGHT_STABLE,
    TREND_WEIGHT_IMPROVING,
    TREND_WEIGHT_NO_HISTORY,
)


def get_trend_weight(asset_id):
    """
    Returns (trend_weight, explanation_str).

    Looks at past severities for this asset_id via the existing
    core.wheel_lifecycle.history.HistoryManager and compares the most
    recent inspection's severity to the average of earlier ones.
    """
    if not asset_id:
        return TREND_WEIGHT_NO_HISTORY, "No asset ID provided -- neutral trend"

    try:
        from core.wheel_lifecycle.history import HistoryManager
        history = HistoryManager().get_history(asset_id)
    except Exception as exc:
        # DB not set up yet, or asset_id unknown -- don't crash the
        # whole risk calculation over a missing/optional data source.
        return TREND_WEIGHT_NO_HISTORY, f"History unavailable ({exc}) -- neutral trend"

    ranked = [
        SEVERITY_RANK.get(row.get("severity"))
        for row in history
        if row.get("severity") in SEVERITY_RANK
    ]

    if len(ranked) < 2:
        return TREND_WEIGHT_NO_HISTORY, "Not enough history yet -- neutral trend"

    latest = ranked[0]           # get_history() is ordered newest-first
    previous_avg = sum(ranked[1:]) / len(ranked[1:])

    if latest > previous_avg:
        return TREND_WEIGHT_WORSENING, f"Worsening trend (latest={latest} vs avg past={previous_avg:.1f})"
    elif latest < previous_avg:
        return TREND_WEIGHT_IMPROVING, f"Improving trend (latest={latest} vs avg past={previous_avg:.1f})"
    else:
        return TREND_WEIGHT_STABLE, f"Stable trend (latest={latest} vs avg past={previous_avg:.1f})"
