"""
routers/trains.py
=================
Train Registration Module — REST endpoints.

POST   /api/trains                  Register a train
GET    /api/trains                  List all trains
GET    /api/trains/{train_id}       Get a specific train
PATCH  /api/trains/{train_id}       Update a train

POST   /api/trains/{train_id}/coaches           Add a coach
GET    /api/trains/{train_id}/coaches           List coaches for a train
GET    /api/trains/{train_id}/coaches/{coach_id} Get a specific coach

GET    /api/coaches/{coach_id}/wheels           List wheels in a coach
POST   /api/coaches/{coach_id}/wheels           Register a wheel under a coach

GET    /api/trains/{train_id}/inspection-events  Inspection events for a train
GET    /api/trains/{train_id}/health             Health summary for a train
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path as FPath
from pydantic import BaseModel, Field

from core.wheel_lifecycle.fleet_repository import FleetRepository
from core.wheel_lifecycle.repository import WheelRepository
from core.wheel_lifecycle.models import Wheel
from core.wheel_lifecycle.id_generator import generate_asset_id

router = APIRouter(prefix="/api", tags=["Trains & Coaches"])


# ── Pydantic request/response models ──────────────────────────────────────────

class TrainCreate(BaseModel):
    train_number: str = Field(..., description="Unique train number e.g. T001")
    train_name: str = Field(..., description="Human-readable train name")
    train_type: Optional[str] = Field(None, description="e.g. Express, Passenger, Freight")
    operational_status: str = Field("Active", description="Active | Inactive | Under Maintenance")
    registration_date: Optional[str] = Field(None, description="YYYY-MM-DD, defaults to today")


class TrainUpdate(BaseModel):
    train_name: Optional[str] = None
    train_type: Optional[str] = None
    operational_status: Optional[str] = None


class TrainResponse(BaseModel):
    id: int
    train_number: str
    train_name: str
    train_type: Optional[str]
    operational_status: str
    registration_date: str
    created_at: str
    last_updated: str


class CoachCreate(BaseModel):
    coach_number: str = Field(..., description="Coach identifier e.g. C1, AC-01")
    coach_type: Optional[str] = Field(None, description="e.g. AC, Sleeper, General")


class CoachResponse(BaseModel):
    id: int
    coach_number: str
    coach_type: Optional[str]
    train_id: int
    created_at: str
    last_updated: str


class WheelRegisterRequest(BaseModel):
    wheel_identifier: Optional[str] = Field(None, description="Human label e.g. W-L1")
    axle_number: Optional[int] = Field(None, description="Axle number within the coach")
    position: Optional[str] = Field(None, description="Left | Right")


class WheelResponse(BaseModel):
    asset_id: str
    wheel_identifier: Optional[str]
    coach_id: Optional[str]
    train_id: Optional[str]
    axle_number: Optional[int]
    position: Optional[str]
    status: str
    inspection_count: int
    latest_inspection: Optional[str]
    created_at: str
    last_updated: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _train_or_404(repo: FleetRepository, train_id: int):
    train = repo.get_train_by_id(train_id)
    if not train:
        raise HTTPException(status_code=404, detail=f"Train {train_id} not found.")
    return train


def _coach_or_404(repo: FleetRepository, coach_id: int):
    coach = repo.get_coach_by_id(coach_id)
    if not coach:
        raise HTTPException(status_code=404, detail=f"Coach {coach_id} not found.")
    return coach


# ═════════════════════════════════════════════════════════════════════════════
# TRAIN ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/trains",
    response_model=TrainResponse,
    status_code=201,
    summary="Register a new train",
    description="Create a new train record. Train numbers must be unique.",
)
def register_train(body: TrainCreate):
    repo = FleetRepository()
    if repo.get_train_by_number(body.train_number):
        raise HTTPException(
            status_code=409,
            detail=f"Train number '{body.train_number}' is already registered.",
        )
    train = repo.create_train(
        train_number=body.train_number,
        train_name=body.train_name,
        train_type=body.train_type,
        operational_status=body.operational_status,
        registration_date=body.registration_date,
    )
    return TrainResponse(**train)


@router.get(
    "/trains",
    response_model=List[TrainResponse],
    summary="List all registered trains",
)
def list_trains():
    repo = FleetRepository()
    return [TrainResponse(**t) for t in repo.list_trains()]


@router.get(
    "/trains/{train_id}",
    response_model=TrainResponse,
    summary="Get a specific train",
)
def get_train(train_id: int = FPath(..., description="Internal train ID")):
    repo = FleetRepository()
    train = _train_or_404(repo, train_id)
    return TrainResponse(**train)


@router.patch(
    "/trains/{train_id}",
    response_model=TrainResponse,
    summary="Update a train record",
)
def update_train(
    body: TrainUpdate,
    train_id: int = FPath(..., description="Internal train ID"),
):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    train = repo.update_train(
        train_id,
        train_name=body.train_name,
        train_type=body.train_type,
        operational_status=body.operational_status,
    )
    return TrainResponse(**train)


# ═════════════════════════════════════════════════════════════════════════════
# COACH ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/trains/{train_id}/coaches",
    response_model=CoachResponse,
    status_code=201,
    summary="Add a coach to a train",
)
def add_coach(
    body: CoachCreate,
    train_id: int = FPath(..., description="Internal train ID"),
):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    if repo.get_coach_by_number(train_id, body.coach_number):
        raise HTTPException(
            status_code=409,
            detail=f"Coach '{body.coach_number}' already exists on train {train_id}.",
        )
    coach = repo.add_coach(
        train_id=train_id,
        coach_number=body.coach_number,
        coach_type=body.coach_type,
    )
    return CoachResponse(**coach)


@router.get(
    "/trains/{train_id}/coaches",
    response_model=List[CoachResponse],
    summary="List coaches for a train",
)
def list_coaches(train_id: int = FPath(..., description="Internal train ID")):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    return [CoachResponse(**c) for c in repo.list_coaches_for_train(train_id)]


@router.get(
    "/trains/{train_id}/coaches/{coach_id}",
    response_model=CoachResponse,
    summary="Get a specific coach",
)
def get_coach(
    train_id: int = FPath(...),
    coach_id: int = FPath(...),
):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    coach = _coach_or_404(repo, coach_id)
    if coach["train_id"] != train_id:
        raise HTTPException(status_code=404, detail="Coach does not belong to this train.")
    return CoachResponse(**coach)


# ═════════════════════════════════════════════════════════════════════════════
# WHEEL ENDPOINTS (within a coach)
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/coaches/{coach_id}/wheels",
    response_model=List[WheelResponse],
    summary="List all wheels in a coach",
)
def list_wheels_in_coach(coach_id: int = FPath(..., description="Internal coach ID")):
    fleet_repo = FleetRepository()
    _coach_or_404(fleet_repo, coach_id)
    wheels = fleet_repo.list_wheels_for_coach(coach_id)
    return [WheelResponse(**_wheel_dict(w)) for w in wheels]


@router.post(
    "/coaches/{coach_id}/wheels",
    response_model=WheelResponse,
    status_code=201,
    summary="Register a new wheel under a coach",
    description=(
        "Creates a new wheel asset and associates it with the given coach. "
        "The asset_id is auto-generated. Use the returned asset_id for inspections."
    ),
)
def register_wheel_in_coach(
    body: WheelRegisterRequest,
    coach_id: int = FPath(..., description="Internal coach ID"),
):
    fleet_repo = FleetRepository()
    coach = _coach_or_404(fleet_repo, coach_id)
    train_id = str(coach["train_id"])

    asset_id = generate_asset_id()
    now_str = datetime.now().isoformat(timespec="seconds")

    wheel = Wheel(
        asset_id=asset_id,
        wheel_identifier=body.wheel_identifier,
        train_id=train_id,
        coach_id=str(coach_id),
        axle_number=body.axle_number,
        position=body.position,
        status="Healthy",
        inspection_count=0,
        latest_inspection=None,
        created_at=datetime.now(),
        last_updated=datetime.now(),
    )

    wheel_repo = WheelRepository()
    wheel_repo.create_wheel(wheel)
    saved = wheel_repo.get_wheel(asset_id)
    return WheelResponse(**_wheel_dict(saved))


@router.get(
    "/trains/{train_id}/inspection-events",
    summary="List all inspection events for a train",
    tags=["Inspection"],
)
def list_train_inspection_events(train_id: int = FPath(...)):
    repo = FleetRepository()
    _train_or_404(repo, train_id)
    return repo.list_inspection_events_for_train(train_id)


@router.get(
    "/trains/{train_id}/health",
    summary="Health summary drill-down for a train",
)
def get_train_health(train_id: int = FPath(...)):
    """
    Returns train info, all coaches, wheels per coach with their status,
    and recent inspection events.
    """
    fleet_repo = FleetRepository()
    wheel_repo = WheelRepository()
    train = _train_or_404(fleet_repo, train_id)
    coaches_raw = fleet_repo.list_coaches_for_train(train_id)
    coaches_out = []
    for c in coaches_raw:
        wheels = fleet_repo.list_wheels_for_coach(c["id"])
        coaches_out.append({
            **c,
            "wheels": [_wheel_dict(w) for w in wheels],
        })
    events = fleet_repo.list_inspection_events_for_train(train_id)
    return {
        "train": dict(train),
        "coaches": coaches_out,
        "recent_inspection_events": events[:20],
    }


# ── Helper ────────────────────────────────────────────────────────────────────

def _wheel_dict(w: dict) -> dict:
    """Normalise a raw DB wheel row to the WheelResponse shape."""
    return {
        "asset_id": w.get("asset_id", ""),
        "wheel_identifier": w.get("wheel_identifier"),
        "coach_id": w.get("coach_id"),
        "train_id": w.get("train_id"),
        "axle_number": w.get("axle_number"),
        "position": w.get("position"),
        "status": w.get("status", "Healthy"),
        "inspection_count": w.get("inspection_count", 0) or 0,
        "latest_inspection": w.get("latest_inspection"),
        "created_at": w.get("created_at", ""),
        "last_updated": w.get("last_updated", ""),
    }
