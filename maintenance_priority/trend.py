"""
Reads a wheel's inspection history from the digital wheel-lifecycle
database (core/wheel_lifecycle) and turns it into a trend weight and status:
is this wheel's condition worsening, stable, or improving over time?

Historical severity/risk is compared per defect type (e.g. Shelling only
compared with previous Shelling records, Cracks-Scratches only with previous
Cracks-Scratches records), never mixed across different defect types.

The wheel-level trend status is derived from individual defect trends
via an explicit safety-first aggregation rule.
"""

import sys
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

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


def calculate_defect_trend(
    asset_id: Optional[str],
    defect_type: Optional[str] = None,
    current_severity: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[int, str, str]:
    """
    Calculate the trend for a single defect type on a given wheel.

    Returns:
        (trend_weight, trend_note, trend_status)
    where trend_status is one of:
        "FIRST_INSPECTION" | "INSUFFICIENT_HISTORY" | "WORSENING" | "STABLE" | "IMPROVING"

    Comparison rule:
    - If current_severity is provided (evaluating a new/in-flight inspection before DB commit):
      'latest' is current_severity, compared against the average of all prior DB records
      matching this defect_type.
    - If current_severity is omitted (evaluating already-committed DB records):
      matching[0] is 'latest', compared against the average of matching[1:].
    """
    if not asset_id:
        return TREND_WEIGHT_NO_HISTORY, "No asset ID provided -- neutral trend", "FIRST_INSPECTION"

    if history is None:
        try:
            from core.wheel_lifecycle.history import HistoryManager
            history = HistoryManager().get_history(asset_id)
        except Exception as exc:
            return TREND_WEIGHT_NO_HISTORY, f"History unavailable ({exc}) -- neutral trend", "INSUFFICIENT_HISTORY"

    if not history:
        return TREND_WEIGHT_NO_HISTORY, "Not enough history yet -- neutral trend", "FIRST_INSPECTION"

    # Filter history strictly for this defect type
    if defect_type:
        matching = [
            row for row in history
            if row.get("defect_type") == defect_type and row.get("severity") in SEVERITY_RANK
        ]
    else:
        matching = [
            row for row in history
            if row.get("severity") in SEVERITY_RANK
        ]

    # Evaluate current vs past
    if current_severity and current_severity in SEVERITY_RANK:
        current_rank = SEVERITY_RANK[current_severity]
        if not matching:
            # First time this specific defect appears on this wheel
            return (
                TREND_WEIGHT_NO_HISTORY,
                f"Not enough history yet for {defect_type or 'defect'} -- neutral trend",
                "FIRST_INSPECTION",
            )
        past_ranks = [SEVERITY_RANK[row["severity"]] for row in matching]
        latest = current_rank
        previous_avg = sum(past_ranks) / len(past_ranks)
    else:
        if len(matching) < 2:
            return (
                TREND_WEIGHT_NO_HISTORY,
                f"Not enough history yet for {defect_type or 'defect'} -- neutral trend",
                "INSUFFICIENT_HISTORY",
            )
        latest = SEVERITY_RANK[matching[0]["severity"]]
        past_ranks = [SEVERITY_RANK[row["severity"]] for row in matching[1:]]
        previous_avg = sum(past_ranks) / len(past_ranks)

    # Compare latest vs previous average
    if latest > previous_avg:
        return (
            TREND_WEIGHT_WORSENING,
            f"Worsening trend (latest={latest} vs avg past={previous_avg:.1f})",
            "WORSENING",
        )
    elif latest < previous_avg:
        return (
            TREND_WEIGHT_IMPROVING,
            f"Improving trend (latest={latest} vs avg past={previous_avg:.1f})",
            "IMPROVING",
        )
    else:
        return (
            TREND_WEIGHT_STABLE,
            f"Stable trend (latest={latest} vs avg past={previous_avg:.1f})",
            "STABLE",
        )


def get_trend_weight(
    asset_id: Optional[str],
    defect_type: Optional[str] = None,
    current_severity: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[int, str]:
    """
    Backwards-compatible wrapper returning (trend_weight, explanation_str).
    """
    weight, note, _ = calculate_defect_trend(
        asset_id,
        defect_type=defect_type,
        current_severity=current_severity,
        history=history,
    )
    return weight, note


def aggregate_wheel_trend(
    defect_trends: List[str],
    has_prior_wheel_history: bool = True,
) -> str:
    """
    Derives the overall wheel trend status from individual per-defect trends
    using an explicit safety-first aggregation rule:

    1. If the wheel has no prior inspection history at all -> FIRST_INSPECTION.
    2. If no defect trends were supplied (i.e. zero defects on this inspection):
       - If wheel had defects previously -> IMPROVING.
       - Otherwise -> STABLE.
    3. Filter down to evaluated trends (WORSENING, STABLE, IMPROVING).
       If none evaluated (all defects are new / INSUFFICIENT_HISTORY):
       -> INSUFFICIENT_HISTORY.
    4. Safety-first priority:
       - If ANY defect is WORSENING -> WORSENING (escalating defect severity).
       - Else if ANY defect is STABLE -> STABLE (condition maintained).
       - Else if all evaluated defects are IMPROVING -> IMPROVING.
       - Default -> STABLE.
    """
    if not has_prior_wheel_history:
        return "FIRST_INSPECTION"

    if not defect_trends:
        return "IMPROVING"

    evaluated = [t for t in defect_trends if t in ("WORSENING", "STABLE", "IMPROVING")]
    if not evaluated:
        return "INSUFFICIENT_HISTORY"

    if "WORSENING" in evaluated:
        return "WORSENING"
    if "STABLE" in evaluated:
        return "STABLE"
    if all(t == "IMPROVING" for t in evaluated):
        return "IMPROVING"

    return "STABLE"
