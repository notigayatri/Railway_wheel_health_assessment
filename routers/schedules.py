"""
routers/schedules.py
====================
Train Operating Schedule Module — REST endpoints.

POST   /api/trains/{train_id}/schedules          Add a schedule entry
GET    /api/trains/{train_id}/schedules          List schedules for a train
GET    /api/schedules/{schedule_id}              Get a specific schedule
PATCH  /api/schedules/{schedule_id}              Update / cancel a schedule
GET    /api/trains/{train_id}/maintenance-windows  List maintenance windows
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path as FPath
from pydantic import BaseModel, Field

from core.wheel_lifecycle.fleet_repository import FleetRepository

router = APIRouter(prefix="/api", tags=["Operating Schedules"])

VALID_SCHEDULE_TYPES = {"OPERATING", "MAINTENANCE_WINDOW", "NON_OPERATING"}
VALID_STATUSES = {"ACTIVE", "CANCELLED", "COMPLETED"}


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    schedule_type: str = Field(
        "OPERATING",
        description="OPERATING | MAINTENANCE_WINDOW | NON_OPERATING",
    )
    departure_datetime: Optional[str] = Field(
        None, description="ISO8601 e.g. 2026-10-20T08:00:00"
    )
    arrival_datetime: Optional[str] = Field(
        None, description="ISO8601 e.g. 2026-10-20T14:00:00"
    )
    operating_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    depot_location: Optional[str] = Field(None, description="Depot or station name")
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    status: Optional[str] = Field(None, description="ACTIVE | CANCELLED | COMPLETED")
    departure_datetime: Optional[str] = None
    arrival_datetime: Optional[str] = None
    depot_location: Optional[str] = None
    notes: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: int
    train_id: int
    schedule_type: str
    departure_datetime: Optional[str]
    arrival_datetime: Optional[str]
    operating_date: Optional[str]
    depot_location: Optional[str]
    notes: Optional[str]
    status: str
    created_at: str
    last_updated: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _train_or_404(repo: FleetRepository, train_id: int):
    t = repo.get_train_by_id(train_id)
    if not t:
        raise HTTPException(status_code=404, detail=f"Train {train_id} not found.")
    return t


def _sched_or_404(repo: FleetRepository, schedule_id: int):
    s = repo.get_schedule_by_id(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found.")
    return s


# ═════════════════════════════════════════════════════════════════════════════
# SCHEDULE ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/trains/{train_id}/schedules",
    response_model=ScheduleResponse,
    status_code=201,
    summary="Add a schedule entry for a train",
    description=(
        "Add an OPERATING run, MAINTENANCE_WINDOW, or NON_OPERATING period. "
        "All entries are manually registered — no external timetable integration."
    ),
)
def add_schedule(
    body: ScheduleCreate,
    train_id: int = FPath(..., description="Internal train ID"),
):
    if body.schedule_type not in VALID_SCHEDULE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"schedule_type must be one of {sorted(VALID_SCHEDULE_TYPES)}.",
        )
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    sched = repo.add_schedule(
        train_id=train_id,
        schedule_type=body.schedule_type,
        departure_datetime=body.departure_datetime,
        arrival_datetime=body.arrival_datetime,
        operating_date=body.operating_date,
        depot_location=body.depot_location,
        notes=body.notes,
    )
    return ScheduleResponse(**sched)


@router.get(
    "/trains/{train_id}/schedules",
    response_model=List[ScheduleResponse],
    summary="List schedules for a train",
)
def list_schedules(
    train_id: int = FPath(...),
    active_only: bool = False,
):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    return [
        ScheduleResponse(**s)
        for s in repo.list_schedules_for_train(train_id, active_only=active_only)
    ]


@router.get(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Get a specific schedule entry",
)
def get_schedule(schedule_id: int = FPath(...)):
    repo = FleetRepository()
    s = _sched_or_404(repo, schedule_id)
    return ScheduleResponse(**s)


@router.patch(
    "/schedules/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Update or cancel a schedule entry",
)
def update_schedule(
    body: ScheduleUpdate,
    schedule_id: int = FPath(...),
):
    if body.status and body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(VALID_STATUSES)}.",
        )
    repo = FleetRepository()
    _sched_or_404(repo, schedule_id)
    updated = repo.update_schedule(
        schedule_id=schedule_id,
        status=body.status,
        departure_datetime=body.departure_datetime,
        arrival_datetime=body.arrival_datetime,
        depot_location=body.depot_location,
        notes=body.notes,
    )
    return ScheduleResponse(**updated)


@router.get(
    "/trains/{train_id}/maintenance-windows",
    response_model=List[ScheduleResponse],
    summary="List maintenance windows for a train",
    description="Returns MAINTENANCE_WINDOW schedule entries with status=ACTIVE.",
)
def list_maintenance_windows(train_id: int = FPath(...)):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    return [
        ScheduleResponse(**w)
        for w in repo.get_maintenance_windows_for_train(train_id)
    ]
