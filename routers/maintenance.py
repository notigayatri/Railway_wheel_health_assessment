"""
routers/maintenance.py
======================
Maintenance Job Management — REST endpoints.

POST   /api/maintenance/recommend/{wheel_asset_id}   Generate recommendation
GET    /api/maintenance/jobs                          List all jobs
GET    /api/maintenance/jobs/pending                  Pending jobs
GET    /api/maintenance/jobs/urgent                   CRITICAL priority jobs
GET    /api/maintenance/jobs/{job_id}                 Get a specific job
POST   /api/maintenance/jobs/{job_id}/confirm         Confirm a maintenance slot
PATCH  /api/maintenance/jobs/{job_id}/status          Update job status
GET    /api/maintenance/history/{wheel_asset_id}      Maintenance history for a wheel
GET    /api/trains/{train_id}/maintenance/jobs        Jobs for a specific train
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path as FPath, Query
from pydantic import BaseModel, Field

from core.wheel_lifecycle.fleet_repository import FleetRepository
from core.wheel_lifecycle.repository import WheelRepository
from maintenance_priority.scheduler import generate_maintenance_recommendation

router = APIRouter(prefix="/api", tags=["Maintenance Jobs"])

VALID_JOB_STATUSES = {"PENDING", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"}


# ── Pydantic models ───────────────────────────────────────────────────────────

class MaintenanceJobResponse(BaseModel):
    id: int
    train_id: Optional[int]
    coach_id: Optional[int]
    wheel_asset_id: str
    inspection_event_id: Optional[str]
    risk_score: Optional[float]
    priority: str
    recommended_action: Optional[str]
    suggested_start: Optional[str]
    suggested_end: Optional[str]
    confirmed_start: Optional[str]
    job_status: str
    completion_notes: Optional[str]
    created_at: str
    last_updated: str


class ConfirmSlotRequest(BaseModel):
    confirmed_start: str = Field(..., description="ISO8601 datetime to confirm e.g. 2026-10-25T08:00:00")


class StatusUpdateRequest(BaseModel):
    job_status: str = Field(..., description="PENDING | SCHEDULED | IN_PROGRESS | COMPLETED | CANCELLED")
    completion_notes: Optional[str] = None


class RecommendationResponse(BaseModel):
    wheel_asset_id: str
    risk_score: float
    priority: str
    recommended_action: str
    trend_status: str
    suggested_start: Optional[str]
    suggested_end: Optional[str]
    scheduling_status: str
    scheduling_notes: str
    conflict_notes: List[str]
    requires_operational_clearance: bool
    maintenance_job_id: Optional[int] = None
    duplicate_job: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_or_404(repo: FleetRepository, job_id: int):
    j = repo.get_maintenance_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail=f"Maintenance job {job_id} not found.")
    return j


# ═════════════════════════════════════════════════════════════════════════════
# RECOMMENDATION ENDPOINT
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/maintenance/recommend/{wheel_asset_id}",
    response_model=RecommendationResponse,
    summary="Generate maintenance recommendation for a wheel",
    description=(
        "Uses the existing risk score, defect info, trend status and train schedule "
        "to generate a maintenance recommendation. If no open job exists for the wheel, "
        "a PENDING maintenance job is automatically created. "
        "The job becomes SCHEDULED only after explicit confirmation."
    ),
)
def recommend_maintenance(
    wheel_asset_id: str = FPath(..., description="Wheel asset ID e.g. WH000001"),
    inspection_event_id: Optional[str] = Query(None, description="Link to a specific inspection event"),
):
    fleet_repo = FleetRepository()
    wheel_repo = WheelRepository()

    wheel = wheel_repo.get_wheel(wheel_asset_id)
    if not wheel:
        raise HTTPException(status_code=404, detail=f"Wheel '{wheel_asset_id}' not found.")

    # Gather context from most recent inspection event (if any)
    events = fleet_repo.list_inspection_events_for_wheel(wheel_asset_id)
    event: Optional[Dict[str, Any]] = None
    if inspection_event_id:
        event = fleet_repo.get_inspection_event(inspection_event_id)
    elif events:
        event = events[0]

    if not event:
        # No inspection data — cannot make a recommendation
        raise HTTPException(
            status_code=422,
            detail=(
                f"No inspection events found for wheel '{wheel_asset_id}'. "
                "Run an inspection first before requesting a maintenance recommendation."
            ),
        )

    risk_score = event.get("wheel_risk_score", 0.0) or 0.0
    recommended_action = event.get("wheel_recommended_action", "Monitor only") or "Monitor only"
    trend_status = event.get("trend_status", "FIRST_INSPECTION") or "FIRST_INSPECTION"
    train_id_raw = event.get("train_id") or wheel.get("train_id")
    coach_id_raw = event.get("coach_id") or wheel.get("coach_id")

    train_id: Optional[int] = None
    if train_id_raw:
        try:
            train_id = int(train_id_raw)
        except (ValueError, TypeError):
            pass

    coach_id: Optional[int] = None
    if coach_id_raw:
        try:
            coach_id = int(coach_id_raw)
        except (ValueError, TypeError):
            pass

    # Pull inspection defect rows for context
    history = wheel_repo.get_history(wheel_asset_id)
    if event.get("event_id"):
        # Defects from this specific event
        defect_rows = [
            r for r in history
            if r.get("inspection_event_id") == event.get("event_id")
        ]
        if not defect_rows:
            defect_rows = history[:5]
    else:
        defect_rows = history[:5]

    defect_types = [r["defect_type"] for r in defect_rows if r.get("defect_type")]
    severities = [r["severity"] for r in defect_rows if r.get("severity")]
    reliabilities = [r["reliability"] for r in defect_rows if r.get("reliability")]

    # Train operating schedule
    maintenance_windows: List[Dict] = []
    operating_schedules: List[Dict] = []
    if train_id:
        maintenance_windows = fleet_repo.get_maintenance_windows_for_train(train_id)
        operating_schedules = fleet_repo.list_schedules_for_train(train_id, active_only=True)

    recommendation = generate_maintenance_recommendation(
        wheel_asset_id=wheel_asset_id,
        risk_score=risk_score,
        recommended_action=recommended_action,
        trend_status=trend_status,
        defect_types=defect_types,
        severities=severities,
        reliabilities=reliabilities,
        train_id=train_id,
        maintenance_windows=maintenance_windows,
        operating_schedules=operating_schedules,
        inspection_event_id=event.get("event_id"),
    )

    # Check for existing open job (avoid duplicates)
    job_id: Optional[int] = None
    is_duplicate = fleet_repo.has_open_job_for_wheel(wheel_asset_id)
    if not is_duplicate:
        job = fleet_repo.create_maintenance_job(
            wheel_asset_id=wheel_asset_id,
            risk_score=risk_score,
            priority=recommendation["priority"],
            recommended_action=recommended_action,
            train_id=train_id,
            coach_id=coach_id,
            inspection_event_id=event.get("event_id"),
            suggested_start=recommendation.get("suggested_start"),
            suggested_end=recommendation.get("suggested_end"),
        )
        job_id = job["id"]

    return RecommendationResponse(
        **{k: v for k, v in recommendation.items() if k != "inspection_event_id"},
        maintenance_job_id=job_id,
        duplicate_job=is_duplicate,
    )


# ═════════════════════════════════════════════════════════════════════════════
# MAINTENANCE JOB LISTING
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/maintenance/jobs",
    response_model=List[MaintenanceJobResponse],
    summary="List all maintenance jobs",
)
def list_all_jobs(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    train_id: Optional[int] = Query(None),
):
    repo = FleetRepository()
    jobs = repo.list_jobs(train_id=train_id, status=status, priority=priority)
    return [MaintenanceJobResponse(**j) for j in jobs]


@router.get(
    "/maintenance/jobs/pending",
    response_model=List[MaintenanceJobResponse],
    summary="List pending maintenance jobs",
)
def list_pending_jobs():
    repo = FleetRepository()
    return [MaintenanceJobResponse(**j) for j in repo.list_jobs(status="PENDING")]


@router.get(
    "/maintenance/jobs/urgent",
    response_model=List[MaintenanceJobResponse],
    summary="List urgent (CRITICAL priority) maintenance jobs",
)
def list_urgent_jobs():
    repo = FleetRepository()
    return [MaintenanceJobResponse(**j) for j in repo.list_jobs(priority="CRITICAL")]


@router.get(
    "/trains/{train_id}/maintenance/jobs",
    response_model=List[MaintenanceJobResponse],
    summary="List maintenance jobs for a specific train",
)
def list_train_jobs(
    train_id: int = FPath(...),
    status: Optional[str] = Query(None),
):
    repo = FleetRepository()
    if not repo.get_train_by_id(train_id):
        raise HTTPException(status_code=404, detail=f"Train {train_id} not found.")
    jobs = repo.list_jobs(train_id=train_id, status=status)
    return [MaintenanceJobResponse(**j) for j in jobs]


@router.get(
    "/maintenance/history/{wheel_asset_id}",
    response_model=List[MaintenanceJobResponse],
    summary="Maintenance history for a wheel (all jobs including completed)",
)
def maintenance_history_for_wheel(wheel_asset_id: str = FPath(...)):
    repo = FleetRepository()
    jobs = repo.list_jobs(wheel_asset_id=wheel_asset_id)
    return [MaintenanceJobResponse(**j) for j in jobs]


@router.get(
    "/maintenance/jobs/{job_id}",
    response_model=MaintenanceJobResponse,
    summary="Get a specific maintenance job",
)
def get_job(job_id: int = FPath(...)):
    repo = FleetRepository()
    return MaintenanceJobResponse(**_job_or_404(repo, job_id))


# ═════════════════════════════════════════════════════════════════════════════
# JOB ACTIONS
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/maintenance/jobs/{job_id}/confirm",
    response_model=MaintenanceJobResponse,
    summary="Confirm a suggested maintenance slot",
    description=(
        "Moves the job from PENDING → SCHEDULED and records the confirmed start time. "
        "Validates for overlapping confirmed jobs on the same wheel."
    ),
)
def confirm_maintenance_slot(
    body: ConfirmSlotRequest,
    job_id: int = FPath(...),
):
    repo = FleetRepository()
    job = _job_or_404(repo, job_id)

    if job["job_status"] not in ("PENDING",):
        raise HTTPException(
            status_code=409,
            detail=f"Job is already in status '{job['job_status']}'. Only PENDING jobs can be confirmed.",
        )

    # Validate no overlapping confirmed jobs for the same wheel
    suggested_end = job.get("suggested_end") or body.confirmed_start
    if repo.has_confirmed_job_overlap(
        wheel_asset_id=job["wheel_asset_id"],
        start_dt=body.confirmed_start,
        end_dt=suggested_end,
        exclude_job_id=job_id,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"A confirmed maintenance job already exists for wheel "
                f"'{job['wheel_asset_id']}' overlapping the requested time slot. "
                "Choose a different time or cancel the existing job first."
            ),
        )

    # Validate against train operating schedule
    train_id_raw = job.get("train_id")
    if train_id_raw:
        conflicts = repo.get_operating_dates_in_range(
            train_id=int(train_id_raw),
            start_dt=body.confirmed_start,
            end_dt=suggested_end,
        )
        if conflicts and job.get("priority") not in ("CRITICAL",):
            # For non-critical, warn but allow with a note
            pass  # could raise 409 if stricter policy desired

    updated = repo.update_maintenance_job(
        job_id=job_id,
        job_status="SCHEDULED",
        confirmed_start=body.confirmed_start,
    )
    return MaintenanceJobResponse(**updated)


@router.patch(
    "/maintenance/jobs/{job_id}/status",
    response_model=MaintenanceJobResponse,
    summary="Update maintenance job status",
)
def update_job_status(
    body: StatusUpdateRequest,
    job_id: int = FPath(...),
):
    if body.job_status not in VALID_JOB_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"job_status must be one of {sorted(VALID_JOB_STATUSES)}.",
        )
    repo = FleetRepository()
    _job_or_404(repo, job_id)
    updated = repo.update_maintenance_job(
        job_id=job_id,
        job_status=body.job_status,
        completion_notes=body.completion_notes,
    )
    return MaintenanceJobResponse(**updated)
