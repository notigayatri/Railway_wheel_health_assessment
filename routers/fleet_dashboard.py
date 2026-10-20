"""
routers/fleet_dashboard.py
==========================
Extended Fleet Dashboard — REST endpoint.

GET  /api/fleet/dashboard     Complete fleet health & maintenance overview
GET  /api/fleet/trains        Alias → same as /api/trains
GET  /api/fleet/wheels/{wheel_asset_id}/history   Full drill-down history
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Path as FPath
from pydantic import BaseModel, Field

from core.wheel_lifecycle.fleet_repository import FleetRepository
from core.wheel_lifecycle.repository import WheelRepository

router = APIRouter(prefix="/api/fleet", tags=["Fleet Dashboard"])


class FleetDashboardResponse(BaseModel):
    total_trains: int
    total_coaches: int
    total_wheels: int
    total_inspections: int
    total_inspection_events: int
    inspected_wheels: int
    uninspected_wheels: int
    healthy_wheels: int
    monitor_wheels: int
    critical_wheels: int
    pending_maintenance_jobs: int
    scheduled_maintenance_jobs: int
    train_health_summaries: List[Dict[str, Any]]
    critical_wheels_by_train: List[Dict[str, Any]]
    upcoming_maintenance: List[Dict[str, Any]]
    operating_schedule_conflicts: List[Dict[str, Any]]


@router.get(
    "/dashboard",
    response_model=FleetDashboardResponse,
    summary="Complete fleet health dashboard",
    description=(
        "Returns fleet-wide statistics: total trains/coaches/wheels, "
        "health breakdown, pending maintenance, train-wise summaries, "
        "critical wheel groupings, and scheduling conflicts."
    ),
)
def fleet_dashboard():
    repo = FleetRepository()
    stats = repo.get_fleet_dashboard()
    return FleetDashboardResponse(**stats)


@router.get(
    "/wheels/{wheel_asset_id}/history",
    summary="Full inspection & maintenance drill-down for a wheel",
    description=(
        "Returns the wheel record, all inspection events (with their defect rows), "
        "and all maintenance jobs for the given wheel."
    ),
)
def wheel_full_history(wheel_asset_id: str = FPath(...)):
    wheel_repo = WheelRepository()
    fleet_repo = FleetRepository()

    wheel = wheel_repo.get_wheel(wheel_asset_id)
    if not wheel:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Wheel '{wheel_asset_id}' not found.")

    inspection_events = fleet_repo.list_inspection_events_for_wheel(wheel_asset_id)
    defect_history = wheel_repo.get_history(wheel_asset_id)
    maintenance_jobs = fleet_repo.list_jobs(wheel_asset_id=wheel_asset_id)

    return {
        "wheel": dict(wheel),
        "inspection_events": inspection_events,
        "defect_records": defect_history,
        "maintenance_jobs": maintenance_jobs,
    }
