"""
main.py — FastAPI Backend for Railway Wheel Health Assessment System
====================================================================

Primary entry point for the REST API.
Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Swagger UI (API documentation):
    http://localhost:8000/docs

ReDoc:
    http://localhost:8000/redoc

CLI mode (backward-compatible, for manual testing):
    python main.py

The CLI mode is preserved under the  if __name__ == "__main__"  block.
"""

import sys
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# ── Project root on sys.path ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── FastAPI / Starlette ───────────────────────────────────────────────────────
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Path as FPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Project modules ───────────────────────────────────────────────────────────
# Severity: detailed per-instance detection + existing simple dict variant
from severity.predict_severity import predict_image, predict_image_detailed

# Reliability: Test-Time Augmentation
from reliability.reliability import calculate_reliability

# Grad-CAM explainability
from explainability.gradcam import generate_gradcam

# Maintenance priority engine
from maintenance_priority.risk_engine import assess_wheel, score_defect

# Digital wheel lifecycle records
from core.wheel_lifecycle.database import DatabaseManager
from core.wheel_lifecycle.models import Wheel, Inspection
from core.wheel_lifecycle.repository import WheelRepository
from core.wheel_lifecycle.id_generator import generate_asset_id, generate_inspection_id
from core.wheel_lifecycle.history import HistoryManager
from core.wheel_lifecycle.dashboard import Dashboard


# ── Static output directories ─────────────────────────────────────────────────
ANNOTATED_DIR = PROJECT_ROOT / "outputs" / "annotated"
GRADCAM_DIR   = PROJECT_ROOT / "outputs" / "gradcam"
UPLOADS_DIR   = PROJECT_ROOT / "outputs" / "uploads"

for _d in (ANNOTATED_DIR, GRADCAM_DIR, UPLOADS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════════════
# FastAPI Application
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Railway Wheel Health Assessment API",
    description=(
        "REST API for AI-powered railway wheel defect detection, severity "
        "assessment, reliability scoring, Grad-CAM explainability, and "
        "maintenance priority calculation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow any separately-running frontend ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Frontend team should tighten this in prod
    allow_credentials=False,      # Must be False when using wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving ───────────────────────────────────────────────────────
# Frontend can load images via:
#   http://localhost:8000/outputs/annotated/<filename>
#   http://localhost:8000/outputs/gradcam/<filename>
app.mount(
    "/outputs",
    StaticFiles(directory=str(PROJECT_ROOT / "outputs")),
    name="outputs",
)


# ═════════════════════════════════════════════════════════════════════════════
# Pydantic Response Models  (= API documentation for the frontend developer)
# ═════════════════════════════════════════════════════════════════════════════

class FeatureDetail(BaseModel):
    """Numerical shape/texture features extracted from one defect mask."""
    area: float         = Field(..., description="Defect area in pixels")
    perimeter: float    = Field(..., description="Defect perimeter in pixels")
    aspect_ratio: float = Field(..., description="Width/Height ratio of bounding rect")
    edge_density: float = Field(..., description="Edge pixel density within defect")
    entropy: float      = Field(..., description="Shannon entropy of defect mask")


class DefectDetail(BaseModel):
    """All per-defect-instance analysis results."""
    label: str                  = Field(..., description="Defect class e.g. 'Shelling'")
    confidence: float           = Field(..., description="YOLO detection confidence 0-1")
    severity: str               = Field(..., description="Mild | Moderate | Severe")
    mean_confidence: float      = Field(..., description="TTA mean confidence")
    std_deviation: float        = Field(..., description="TTA std deviation")
    reliability: str            = Field(..., description="HIGH | MEDIUM | LOW")
    defect_weight: int          = Field(..., description="Domain risk weight for defect type")
    severity_weight: int        = Field(..., description="Risk weight for severity level")
    trend_weight: int           = Field(..., description="Historical trend risk weight")
    reliability_factor: float   = Field(..., description="TTA reliability multiplier")
    risk_score: float           = Field(..., description="Combined risk score 0-100")
    recommended_action: str     = Field(..., description="Monitor only | Schedule maintenance | Immediate inspection")
    trend_note: str             = Field(..., description="Human-readable trend explanation")
    features: FeatureDetail


class InspectionResponse(BaseModel):
    """Complete structured result of POST /api/inspect."""
    inspection_id: str
    asset_id: str
    wheel_id: Optional[str]             = Field(None, description="User-supplied wheel ID if provided")
    image_name: str
    inspection_date: str
    trend_status: str                   = Field(..., description="FIRST_INSPECTION | WORSENING | STABLE | IMPROVING | INSUFFICIENT_HISTORY")
    wheel_risk_score: float
    wheel_recommended_action: str
    total_defects_detected: int
    defects: List[DefectDetail]
    annotated_image_url: Optional[str]  = Field(None, description="URL to annotated detection image")
    gradcam_image_url: Optional[str]    = Field(None, description="URL to Grad-CAM heatmap image")
    processing_time_seconds: float


class WheelSummary(BaseModel):
    """Summary row returned by GET /api/wheels."""
    asset_id: str
    wheel_identifier: Optional[str]
    train_id: Optional[str]
    coach_id: Optional[str]
    status: str
    inspection_count: int
    latest_inspection: Optional[str]
    created_at: str
    last_updated: str


class WheelDetail(WheelSummary):
    """Full wheel record returned by GET /api/wheels/{wheel_id}."""
    axle_number: Optional[int]
    position: Optional[str]


class InspectionHistoryEntry(BaseModel):
    """One row in the inspection history timeline."""
    inspection_id: str
    asset_id: str
    image_name: str
    inspection_date: str
    defect_type: Optional[str]
    severity: Optional[str]
    confidence: Optional[float]
    reliability: Optional[str]
    std_deviation: Optional[float]
    risk_score: Optional[float]
    recommended_action: Optional[str]
    annotated_image_path: Optional[str]
    gradcam_image_path: Optional[str]
    processing_time: Optional[float]
    notes: Optional[str]


class DashboardResponse(BaseModel):
    """Fleet-wide statistics returned by GET /api/dashboard."""
    total_wheels: int
    total_inspections: int
    healthy: int
    monitor: int
    critical: int
    severity_distribution: Dict[str, int]
    defect_distribution: Dict[str, int]
    recent_inspections: List[Dict[str, Any]]


# ═════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═════════════════════════════════════════════════════════════════════════════

def _url_for_file(relative_path: Optional[str]) -> Optional[str]:
    """
    Convert a local file path under outputs/ to a URL the frontend can fetch.
    e.g.  outputs/annotated/frame2304.jpg  ->  /outputs/annotated/frame2304.jpg
    """
    if not relative_path:
        return None
    p = Path(relative_path)
    try:
        rel = p.resolve().relative_to(PROJECT_ROOT.resolve())
        return "/" + str(rel).replace("\\", "/")
    except ValueError:
        return None


def _derive_wheel_status(wheel_risk_score: float) -> str:
    """Map the wheel-level risk score to a wheel status string for the DB."""
    if wheel_risk_score >= 80:
        return "Critical"
    if wheel_risk_score >= 50:
        return "Monitor"
    return "Healthy"


def _resolve_wheel_trend(
    asset_id: str,
    repo: WheelRepository,
    defect_trends: List[str],
) -> str:
    """
    Determine the overall wheel trend status from individual per-defect trends
    using an explicit aggregation rule.
    """
    from maintenance_priority.trend import aggregate_wheel_trend
    history = repo.get_history(asset_id)
    return aggregate_wheel_trend(defect_trends, has_prior_wheel_history=bool(history))


# ═════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════

@app.post(
    "/api/inspect",
    response_model=InspectionResponse,
    summary="Run complete wheel inspection",
    tags=["Inspection"],
    description=(
        "Upload a wheel image and optionally supply a wheel ID. "
        "Runs YOLO detection, severity clustering, TTA reliability, "
        "Grad-CAM explainability, and maintenance priority. "
        "Creates/updates the wheel record and stores the inspection. "
        "Returns a complete structured JSON result."
    ),
)
async def inspect_wheel(
    image: UploadFile = File(..., description="Wheel image (JPEG/PNG)"),
    wheel_id: Optional[str] = Form(
        None,
        description=(
            "Optional wheel asset ID (e.g. WH000001). "
            "If omitted a new ID is auto-generated. "
            "Supply the same ID on subsequent uploads for the same wheel "
            "to build inspection history and trend analysis."
        ),
    ),
):
    t_start = time.perf_counter()

    # ── 0. Sanitize wheel_id ──────────────────────────────────────────────
    # Swagger UI sends the literal placeholder "string" when the user
    # doesn't clear the field.  Treat that (and whitespace-only) as empty.
    if wheel_id is not None:
        wheel_id = wheel_id.strip()
        if not wheel_id or wheel_id.lower() == "string":
            wheel_id = None

    # ── 1. Validate and save uploaded image ───────────────────────────────
    if image.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported image type '{image.content_type}'. Use JPEG or PNG.",
        )

    upload_path = UPLOADS_DIR / image.filename
    try:
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(image.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {exc}")

    # ── 2. Validate the image can actually be read ─────────────────────────
    import cv2 as _cv2
    if _cv2.imread(str(upload_path)) is None:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded file is not a valid image.")

    # ── 3. Wheel record — look up or create ───────────────────────────────
    repo = WheelRepository()

    if wheel_id:
        wheel_record = repo.get_wheel(wheel_id)
        if wheel_record is None:
            # User supplied an ID that does not exist yet — create it
            asset_id = wheel_id
            new_wheel = Wheel(asset_id=asset_id)
            repo.create_wheel(new_wheel)
        else:
            asset_id = wheel_id
    else:
        asset_id = generate_asset_id()
        new_wheel = Wheel(asset_id=asset_id)
        repo.create_wheel(new_wheel)

    # ── 4. Retrieve prior history BEFORE saving this inspection ───────────
    prior_history = repo.get_history(asset_id)
    has_prior_history = len(prior_history) > 0

    # ── 5. YOLOv8 detection + severity (per-instance) ─────────────────────
    try:
        detections, yolo_result = predict_image_detailed(upload_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}")

    # ── 6. Save annotated detection image ─────────────────────────────────
    annotated_path: Optional[str] = None
    annotated_url: Optional[str] = None
    try:
        import cv2 as _cv2
        annotated_img = yolo_result.plot()
        ann_file = ANNOTATED_DIR / image.filename
        _cv2.imwrite(str(ann_file), annotated_img)
        annotated_path = str(ann_file)
        annotated_url = _url_for_file(annotated_path)
    except Exception:
        pass  # annotated image is non-critical

    # ── 7. Grad-CAM ────────────────────────────────────────────────────────
    gradcam_path: Optional[str] = None
    gradcam_url: Optional[str] = None
    try:
        gc_out = generate_gradcam(upload_path, output_path=GRADCAM_DIR / image.filename)
        gradcam_path = str(gc_out)
        gradcam_url = _url_for_file(gradcam_path)
    except Exception:
        pass  # Grad-CAM is non-critical; do not fail the whole request

    # ── 8. TTA Reliability ────────────────────────────────────────────────
    try:
        reliability_results = calculate_reliability(upload_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reliability calculation failed: {exc}")

    # ── 9. Maintenance priority — per defect ──────────────────────────────
    from maintenance_priority.config import (
        DEFECT_TYPE_WEIGHT, DEFAULT_DEFECT_WEIGHT,
        SEVERITY_WEIGHT, DEFAULT_SEVERITY_WEIGHT,
        RELIABILITY_FACTOR, DEFAULT_RELIABILITY_FACTOR,
        action_for_score,
    )
    from maintenance_priority.trend import calculate_defect_trend, aggregate_wheel_trend

    defect_details: List[DefectDetail] = []
    defect_trends: List[str] = []

    for det in detections:
        label        = det["label"]
        confidence   = det["confidence"]
        severity     = det["severity"]
        features_raw = det["features"]

        rel_info = reliability_results.get(label, {})
        mean_conf    = rel_info.get("mean_confidence", confidence)
        std_dev      = rel_info.get("std_deviation", 0.0)
        reliability  = rel_info.get("reliability", "MEDIUM")

        # Trend calculation: compared STRICTLY per defect type
        trend_weight, trend_note, defect_trend = calculate_defect_trend(
            asset_id=asset_id,
            defect_type=label,
            current_severity=severity,
            history=prior_history,
        )
        defect_trends.append(defect_trend)

        dw  = DEFECT_TYPE_WEIGHT.get(label, DEFAULT_DEFECT_WEIGHT)
        sw  = SEVERITY_WEIGHT.get(severity, DEFAULT_SEVERITY_WEIGHT)
        rf  = RELIABILITY_FACTOR.get(reliability, DEFAULT_RELIABILITY_FACTOR)
        raw = (dw + sw + trend_weight) * rf
        rs  = round(min(raw, 100.0), 1)
        action = action_for_score(rs)

        defect_details.append(DefectDetail(
            label=label,
            confidence=confidence,
            severity=severity,
            mean_confidence=mean_conf,
            std_deviation=std_dev,
            reliability=reliability,
            defect_weight=dw,
            severity_weight=sw,
            trend_weight=trend_weight,
            reliability_factor=rf,
            risk_score=rs,
            recommended_action=action,
            trend_note=trend_note,
            features=FeatureDetail(**features_raw),
        ))

    # Derive overall wheel-level trend status from per-defect trends
    trend_status = aggregate_wheel_trend(
        defect_trends,
        has_prior_wheel_history=has_prior_history,
    )

    # Sort worst-first
    defect_details.sort(key=lambda d: d.risk_score, reverse=True)

    wheel_risk_score = defect_details[0].risk_score if defect_details else 0.0
    wheel_action     = action_for_score(wheel_risk_score)

    # ── 10. Update wheel status ───────────────────────────────────────────
    wheel_status = _derive_wheel_status(wheel_risk_score)
    inspection_date_str = datetime.now().isoformat(timespec="seconds")
    repo.update_wheel_status(asset_id, wheel_status, inspection_date_str)

    # ── 11. Save inspection records (one row per defect instance) ─────────
    t_elapsed = round(time.perf_counter() - t_start, 3)
    first_inspection_id: Optional[str] = None

    if detections:
        for det_d in defect_details:
            iid = generate_inspection_id()
            if first_inspection_id is None:
                first_inspection_id = iid

            insp = Inspection(
                inspection_id=iid,
                asset_id=asset_id,
                image_name=image.filename,
                image_path=str(upload_path),
                inspection_date=datetime.now(),
                defect_type=det_d.label,
                severity=det_d.severity,
                confidence=det_d.confidence,
                processing_time=t_elapsed,
                notes=det_d.trend_note,
            )
            repo.create_inspection(
                insp,
                reliability=det_d.reliability,
                std_deviation=det_d.std_deviation,
                risk_score=det_d.risk_score,
                recommended_action=det_d.recommended_action,
                annotated_image_path=annotated_path,
                gradcam_image_path=gradcam_path,
            )
    else:
        # No defects found — still record the inspection
        iid = generate_inspection_id()
        first_inspection_id = iid
        insp = Inspection(
            inspection_id=iid,
            asset_id=asset_id,
            image_name=image.filename,
            image_path=str(upload_path),
            inspection_date=datetime.now(),
            defect_type=None,
            severity=None,
            confidence=None,
            processing_time=t_elapsed,
            notes="No defects detected.",
        )
        repo.create_inspection(
            insp,
            annotated_image_path=annotated_path,
            gradcam_image_path=gradcam_path,
        )

    # ── 12. Build and return response ─────────────────────────────────────
    return InspectionResponse(
        inspection_id=first_inspection_id,
        asset_id=asset_id,
        wheel_id=wheel_id,
        image_name=image.filename,
        inspection_date=inspection_date_str,
        trend_status=trend_status,
        wheel_risk_score=wheel_risk_score,
        wheel_recommended_action=wheel_action,
        total_defects_detected=len(defect_details),
        defects=defect_details,
        annotated_image_url=annotated_url,
        gradcam_image_url=gradcam_url,
        processing_time_seconds=t_elapsed,
    )


# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/wheels",
    response_model=List[WheelSummary],
    summary="List all wheel records",
    tags=["Wheels"],
    description="Returns all registered wheel assets with current status and inspection count.",
)
def list_wheels():
    repo = WheelRepository()
    wheels = repo.list_all_wheels()
    return [
        WheelSummary(
            asset_id=w["asset_id"],
            wheel_identifier=w.get("wheel_identifier"),
            train_id=w.get("train_id"),
            coach_id=w.get("coach_id"),
            status=w.get("status", "Healthy"),
            inspection_count=w.get("inspection_count", 0),
            latest_inspection=w.get("latest_inspection"),
            created_at=w.get("created_at", ""),
            last_updated=w.get("last_updated", ""),
        )
        for w in wheels
    ]


# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/wheels/{wheel_id}",
    response_model=WheelDetail,
    summary="Get a specific wheel record",
    tags=["Wheels"],
    description="Returns the current record for a wheel identified by its asset ID.",
)
def get_wheel(wheel_id: str = FPath(..., description="Wheel asset ID e.g. WH000001")):
    repo = WheelRepository()
    w = repo.get_wheel(wheel_id)
    if w is None:
        raise HTTPException(status_code=404, detail=f"Wheel '{wheel_id}' not found.")
    return WheelDetail(
        asset_id=w["asset_id"],
        wheel_identifier=w.get("wheel_identifier"),
        train_id=w.get("train_id"),
        coach_id=w.get("coach_id"),
        axle_number=w.get("axle_number"),
        position=w.get("position"),
        status=w.get("status", "Healthy"),
        inspection_count=w.get("inspection_count", 0),
        latest_inspection=w.get("latest_inspection"),
        created_at=w.get("created_at", ""),
        last_updated=w.get("last_updated", ""),
    )


# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/wheels/{wheel_id}/history",
    response_model=List[InspectionHistoryEntry],
    summary="Get inspection history for a wheel",
    tags=["Wheels"],
    description=(
        "Returns all inspections for the given wheel in reverse chronological order. "
        "Each entry includes defect type, severity, risk score, reliability, "
        "and links to annotated / Grad-CAM images."
    ),
)
def get_wheel_history(wheel_id: str = FPath(..., description="Wheel asset ID e.g. WH000001")):
    repo = WheelRepository()
    if repo.get_wheel(wheel_id) is None:
        raise HTTPException(status_code=404, detail=f"Wheel '{wheel_id}' not found.")
    rows = repo.get_history(wheel_id)
    return [
        InspectionHistoryEntry(
            inspection_id=r["inspection_id"],
            asset_id=r["asset_id"],
            image_name=r["image_name"],
            inspection_date=r["inspection_date"],
            defect_type=r.get("defect_type"),
            severity=r.get("severity"),
            confidence=r.get("confidence"),
            reliability=r.get("reliability"),
            std_deviation=r.get("std_deviation"),
            risk_score=r.get("risk_score"),
            recommended_action=r.get("recommended_action"),
            annotated_image_path=_url_for_file(r.get("annotated_image_path")),
            gradcam_image_path=_url_for_file(r.get("gradcam_image_path")),
            processing_time=r.get("processing_time"),
            notes=r.get("notes"),
        )
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/api/dashboard",
    response_model=DashboardResponse,
    summary="Fleet dashboard statistics",
    tags=["Dashboard"],
    description=(
        "Returns fleet-wide summary statistics: wheel counts by status, "
        "severity distribution, defect type breakdown, and last 10 inspections."
    ),
)
def get_dashboard():
    repo = WheelRepository()
    stats = repo.get_dashboard_stats()
    return DashboardResponse(
        total_wheels=stats["total_wheels"],
        total_inspections=stats["total_inspections"],
        healthy=stats["healthy"],
        monitor=stats["monitor"],
        critical=stats["critical"],
        severity_distribution=stats.get("severity_distribution", {}),
        defect_distribution=stats.get("defect_distribution", {}),
        recent_inspections=stats.get("recent_inspections", []),
    )


# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    """Quick health check — confirms the API is running."""
    return {
        "status": "ok",
        "message": "Railway Wheel Health Assessment API is running.",
        "docs": "/docs",
    }


@app.get("/api/health", tags=["Health"])
def health_check():
    """Detailed health check confirming models are loaded."""
    model_files = {
        "yolo":    (PROJECT_ROOT / "models" / "best.pt").exists(),
        "kmeans":  (PROJECT_ROOT / "severity" / "kmeans_model.pkl").exists(),
        "scaler":  (PROJECT_ROOT / "severity" / "scaler.pkl").exists(),
        "mapping": (PROJECT_ROOT / "severity" / "severity_mapping.json").exists(),
    }
    all_ok = all(model_files.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "models": model_files,
    }


# ═════════════════════════════════════════════════════════════════════════════
# CLI mode — backward compatible  (python main.py)
# ═════════════════════════════════════════════════════════════════════════════

def _cli_main(image_path: Path):
    """Original CLI pipeline preserved for manual testing."""
    print(f"\nProcessing image: {image_path.name}")

    severity_results = predict_image(image_path)
    from reliability.reliability import calculate_reliability
    reliability_results = calculate_reliability(image_path)

    print("\n===== FINAL HEALTH ASSESSMENT =====")
    for defect, info in reliability_results.items():
        severity = severity_results.get(defect, "Unknown")
        print(f"\nDefect: {defect}")
        print(f"  Severity        : {severity}")
        print(f"  Mean Confidence : {info['mean_confidence']}")
        print(f"  Std Deviation   : {info['std_deviation']}")
        print(f"  Reliability     : {info['reliability']}")

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    import uvicorn

    # Detect CLI-test mode: pass an image path as argument to run the old pipeline.
    # Otherwise start the FastAPI server.
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        IMAGE_PATH = Path(sys.argv[1])
        if not IMAGE_PATH.exists():
            IMAGE_PATH = (
                PROJECT_ROOT
                / "dataset" / "test" / "images"
                / "frame2304_jpg.rf.0188ac25e86fafbbdc3ca9a47b63a8e5.jpg"
            )
        _cli_main(IMAGE_PATH)
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )
