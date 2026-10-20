"""
scheduler.py
============
Intelligent Maintenance Scheduling Engine.

Uses:
  - Wheel risk score & recommended action (from the existing risk engine)
  - Detected defect types and severities
  - Prediction reliability
  - Historical defect trends
  - Train operating schedule (from operating_schedules table)
  - Available maintenance windows

Scheduling rules (rule-based, not ML):

  CRITICAL (risk >= 80 or action == "Immediate inspection"):
    - Recommend immediate engineering inspection.
    - Flag conflicts with upcoming train operations.
    - Mark wheel/train as requiring operational clearance.
    - Does NOT automatically clear the train for service.
    - Does NOT postpone urgent maintenance because train is operating.

  MODERATE (risk >= 50 or action == "Schedule maintenance"):
    - Recommend the earliest suitable maintenance window.
    - Prioritise earlier windows if trend is WORSENING.
    - Flag if no window is available (scheduling conflict).

  LOW (risk < 50 or action == "Monitor only"):
    - Recommend monitoring or planned maintenance.
    - Propose non-operating window if maintenance is required.

IMPORTANT:
  - Recommendations are suggestions; they become scheduled only after
    explicit confirmation via the confirm endpoint.
  - No mandatory deadline is fabricated.
  - No regulatory certification is implied.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _parse_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    return None


def _determine_priority(risk_score: float, recommended_action: str) -> str:
    if risk_score >= 80 or recommended_action == "Immediate inspection":
        return "CRITICAL"
    if risk_score >= 50 or recommended_action == "Schedule maintenance":
        return "MODERATE"
    return "LOW"


def _find_earliest_maintenance_window(
    maintenance_windows: List[Dict[str, Any]],
    trend_status: str,
) -> Optional[Dict[str, Any]]:
    """
    Return the earliest available maintenance window.
    If WORSENING trend, still return earliest but note urgency.
    """
    now = datetime.now()
    future_windows = []
    for w in maintenance_windows:
        dep = _parse_dt(w.get("departure_datetime"))
        arr = _parse_dt(w.get("arrival_datetime"))
        if dep and arr and dep > now:
            future_windows.append((dep, arr, w))

    if not future_windows:
        return None

    future_windows.sort(key=lambda x: x[0])
    # For WORSENING trends, keep earliest (already sorted)
    _, _, window = future_windows[0]
    return window


def _check_operating_conflicts(
    operating_schedules: List[Dict[str, Any]],
    suggested_start: Optional[datetime],
    suggested_end: Optional[datetime],
) -> List[str]:
    """Return list of conflict descriptions with operating schedule entries."""
    conflicts = []
    if not suggested_start:
        return conflicts
    for sched in operating_schedules:
        dep = _parse_dt(sched.get("departure_datetime"))
        arr = _parse_dt(sched.get("arrival_datetime"))
        if not dep or not arr:
            continue
        # Check overlap: [suggested_start, suggested_end] ∩ [dep, arr]
        end_to_check = suggested_end or (suggested_start + timedelta(hours=4))
        if suggested_start < arr and end_to_check > dep:
            conflicts.append(
                f"Conflicts with operating schedule "
                f"(departure={dep.isoformat()}, arrival={arr.isoformat()})"
            )
    return conflicts


def generate_maintenance_recommendation(
    wheel_asset_id: str,
    risk_score: float,
    recommended_action: str,
    trend_status: str,
    defect_types: List[str],
    severities: List[str],
    reliabilities: List[str],
    train_id: Optional[int],
    maintenance_windows: List[Dict[str, Any]],
    operating_schedules: List[Dict[str, Any]],
    inspection_event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Core scheduling logic. Returns a recommendation dict ready to be stored
    as a maintenance_job or returned directly to the API caller.

    Returns:
        {
            priority: str,
            scheduling_status: str,     # "RECOMMENDED" | "CONFLICT" | "NO_WINDOW"
            suggested_start: str | None,
            suggested_end: str | None,
            conflict_notes: List[str],
            scheduling_notes: str,
            requires_operational_clearance: bool,
        }
    """
    priority = _determine_priority(risk_score, recommended_action)
    result: Dict[str, Any] = {
        "wheel_asset_id": wheel_asset_id,
        "risk_score": risk_score,
        "priority": priority,
        "recommended_action": recommended_action,
        "trend_status": trend_status,
        "inspection_event_id": inspection_event_id,
        "train_id": train_id,
        "suggested_start": None,
        "suggested_end": None,
        "conflict_notes": [],
        "scheduling_notes": "",
        "requires_operational_clearance": False,
        "scheduling_status": "RECOMMENDED",
    }

    now = datetime.now()

    # ── CRITICAL ────────────────────────────────────────────────────────
    if priority == "CRITICAL":
        result["requires_operational_clearance"] = True
        result["scheduling_notes"] = (
            "CRITICAL defect detected. Immediate engineering inspection is required. "
            "This wheel/train requires operational clearance before resuming service. "
            "Maintenance must not be postponed due to operational schedule."
        )
        # Check if train is currently operating or scheduled to operate
        upcoming_ops = [
            s for s in operating_schedules
            if _parse_dt(s.get("departure_datetime")) and
               _parse_dt(s.get("departure_datetime")) > now
        ]
        if upcoming_ops:
            for sched in upcoming_ops[:3]:  # show up to 3 conflicts
                dep = _parse_dt(sched.get("departure_datetime"))
                result["conflict_notes"].append(
                    f"Train is scheduled to operate from "
                    f"{sched.get('departure_datetime')} to "
                    f"{sched.get('arrival_datetime')} — "
                    f"operational clearance required before this run."
                )
        result["scheduling_status"] = "CONFLICT" if result["conflict_notes"] else "RECOMMENDED"
        # Suggest immediate window (now + small buffer for mobilisation)
        suggested = now + timedelta(hours=2)
        result["suggested_start"] = suggested.isoformat(timespec="seconds")
        result["suggested_end"] = (suggested + timedelta(hours=4)).isoformat(timespec="seconds")

    # ── MODERATE ────────────────────────────────────────────────────────
    elif priority == "MODERATE":
        window = _find_earliest_maintenance_window(maintenance_windows, trend_status)
        if window:
            dep = _parse_dt(window.get("departure_datetime"))
            arr = _parse_dt(window.get("arrival_datetime"))
            result["suggested_start"] = window.get("departure_datetime")
            result["suggested_end"] = window.get("arrival_datetime")
            # Check for operating conflicts with the suggested window
            conflicts = _check_operating_conflicts(
                operating_schedules, dep, arr
            )
            result["conflict_notes"] = conflicts
            if conflicts:
                result["scheduling_status"] = "CONFLICT"
                result["scheduling_notes"] = (
                    f"Moderate-risk defect. A maintenance window was found but conflicts "
                    f"with {len(conflicts)} operating schedule(s). Consider rescheduling "
                    f"the maintenance window or adjusting operations."
                )
            else:
                result["scheduling_status"] = "RECOMMENDED"
                urgency = "earliest available" if trend_status == "WORSENING" else "suitable"
                result["scheduling_notes"] = (
                    f"Moderate-risk defect. Scheduled in {urgency} maintenance window: "
                    f"{window.get('departure_datetime')} – {window.get('arrival_datetime')}. "
                    f"Depot: {window.get('depot_location', 'Not specified')}."
                )
        else:
            result["scheduling_status"] = "NO_WINDOW"
            result["scheduling_notes"] = (
                "Moderate-risk defect. No suitable maintenance window is currently available "
                "for this train. A scheduling conflict exists. Add a maintenance availability "
                "window or arrange out-of-schedule maintenance."
            )

    # ── LOW ─────────────────────────────────────────────────────────────
    else:
        # Low risk: recommend monitoring or planned non-operating maintenance
        non_op_windows = [
            w for w in maintenance_windows
            if _parse_dt(w.get("departure_datetime")) and
               _parse_dt(w.get("departure_datetime")) > now
        ]
        if non_op_windows:
            non_op_windows.sort(key=lambda w: _parse_dt(w.get("departure_datetime")))
            window = non_op_windows[0]
            result["suggested_start"] = window.get("departure_datetime")
            result["suggested_end"] = window.get("arrival_datetime")
            result["scheduling_notes"] = (
                f"Low-risk defect. Recommend monitoring. If maintenance is required, "
                f"a non-operating window is available: "
                f"{window.get('departure_datetime')} – {window.get('arrival_datetime')}."
            )
            result["scheduling_status"] = "RECOMMENDED"
        else:
            result["scheduling_notes"] = (
                "Low-risk defect. Recommend monitoring at next scheduled inspection. "
                "No maintenance window is currently registered for this train."
            )
            result["scheduling_status"] = "RECOMMENDED"

    return result
