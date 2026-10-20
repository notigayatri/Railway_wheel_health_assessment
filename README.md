# Train-Wise Wheel Health Monitoring & Intelligent Maintenance Scheduling System

> **v2.0** — Extended from the original Railway Wheel Health Assessment backend into an end-to-end Fleet Health, Computer Vision Defect Detection, and Intelligent Maintenance Scheduling Platform for railway operations.

---

## Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Database Schema & Migrations](#2-database-schema--migrations)
3. [Complete API Endpoints Reference](#3-complete-api-endpoints-reference)
4. [Live Machine Learning Inspection Pipeline](#4-live-machine-learning-inspection-pipeline)
5. [Intelligent Maintenance Scheduling & Conflict Engine](#5-intelligent-maintenance-scheduling--conflict-engine)
6. [Request & Response Examples](#6-request--response-examples)
7. [Frontend Integration & UI Application](#7-frontend-integration--ui-application)
8. [Testing & Verification Suites (129 Tests)](#8-testing--verification-suites-129-tests)
9. [How to Start & Run Locally](#9-how-to-start--run-locally)
10. [Windows Performance & Network Optimization](#10-windows-performance--network-optimization)

---

## 1. System Overview & Architecture

The system tracks wheelsets within an operational railway fleet hierarchy:

```
Fleet
 └── Train (T001, T002, ...)
      ├── Coaches (C1, C2, ...)
      │    └── Axles & Wheels (WH000001, WH000002, ...)
      ├── Operating Schedules (Passenger / Freight runs)
      ├── Maintenance Windows (Depot service slots)
      └── Maintenance Jobs (Pending, Scheduled, In Progress, Completed)
```

### Directory Structure

```
Railway_wheel_health_assessment/
├── main.py                          # FastAPI application entry point (v2.0)
├── routers/
│   ├── trains.py                    # Train, coach, and wheel management APIs
│   ├── schedules.py                 # Operating schedules & maintenance windows APIs
│   ├── maintenance.py               # Maintenance recommendation & job lifecycle APIs
│   └── fleet_dashboard.py          # Executive fleet dashboard & drill-down APIs
├── core/wheel_lifecycle/
│   ├── database.py                  # SQLite schema manager & automatic migrations
│   ├── fleet_repository.py          # Fleet data access layer (trains, coaches, schedules, jobs)
│   ├── repository.py                # Core Wheel & Inspection repository
│   ├── models.py                    # Domain models (Wheel, Inspection, Defect)
│   ├── id_generator.py              # Unique ID generators (WH000001, INS000001, EVT...)
│   ├── history.py                   # Historical record manager
│   └── dashboard.py                 # Legacy dashboard aggregation
├── maintenance_priority/
│   ├── scheduler.py                 # Intelligent deterministic maintenance scheduler
│   ├── risk_engine.py               # Multi-factor risk calculation engine
│   ├── trend.py                     # Historical defect degradation analysis
│   └── config.py                    # Defect severity weights & safety thresholds
├── detection/                       # YOLOv8 wheel defect detection model & weights
├── severity/                        # Defect severity categorization (Mild, Moderate, Severe)
├── reliability/                     # Test-Time Augmentation (TTA) prediction confidence
├── explainability/                  # Grad-CAM heatmap visualization generator
├── dataset/                         # Real test images and validation samples
├── database/railway.db              # SQLite persistence layer
├── frontend/                        # React + Vite web dashboard
│   ├── src/                         # Dashboard, New Inspection, Wheels pages
│   ├── package.json                 # React 18, Vite, React Router, Recharts
│   └── .env                         # Backend API URL configuration
└── tests/
    ├── test_fleet_system.py         # 25 pytest integration & unit tests
    ├── test_api_endpoints.py        # 64 live HTTP validation tests (error codes, validation)
    └── verify_all_endpoints.py      # 40 live end-to-end tests (real YOLO image upload, scheduling)
```

---

## 2. Database Schema & Migrations

The database (`database/railway.db`) supports 7 interrelated tables with foreign key constraints:

```
trains (id PK, train_number UNIQUE, train_name, train_type, operational_status, ...)
  │
  ├── coaches (id PK, coach_number, train_id FK→trains.id, coach_type, ...)
  │     │
  │     └── wheels (asset_id PK, coach_id FK→coaches.id, train_id, axle_number, position, status, ...)
  │           │
  │           ├── inspection_events (event_id PK, asset_id FK→wheels, train_id, coach_id, risk_score, ...)
  │           │     └── inspections (inspection_id PK, asset_id, inspection_event_id FK, defect_type, ...)
  │           │
  │           └── maintenance_jobs (id PK, wheel_asset_id FK, train_id, coach_id, job_status, ...)
  │
  └── operating_schedules (id PK, train_id FK→trains.id, schedule_type, departure_datetime, arrival_datetime, ...)
```

### Automatic Migration
- Built with automatic schema migration in [`core/wheel_lifecycle/database.py`](file:///c:/Railway%20project/Railway_wheel_health_assessment/core/wheel_lifecycle/database.py).
- Tables and new columns (`coach_id`, `train_id`, `inspection_event_id`) are created idempotently (`IF NOT EXISTS`).
- Prior v1.0 data remains untouched and backward-compatible.

---

## 3. Complete API Endpoints Reference

The backend provides **34 active API routes**:

### 3.1 Train & Coach Management (`routers/trains.py`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/trains` | Register a new train (`train_number` must be unique) |
| `GET` | `/api/trains` | List all registered trains |
| `GET` | `/api/trains/{train_id}` | Get train details by ID |
| `PATCH` | `/api/trains/{train_id}` | Update train status (`Active`, `Under Maintenance`, `Decommissioned`) |
| `POST` | `/api/trains/{train_id}/coaches` | Add a coach to a train |
| `GET` | `/api/trains/{train_id}/coaches` | List all coaches for a train |
| `GET` | `/api/trains/{train_id}/coaches/{coach_id}` | Get specific coach details |
| `POST` | `/api/coaches/{coach_id}/wheels` | Register an axle wheel under a coach |
| `GET` | `/api/coaches/{coach_id}/wheels` | List all wheels belonging to a coach |
| `GET` | `/api/trains/{train_id}/health` | Hierarchical health drill-down (**Train → Coaches → Wheels**) |
| `GET` | `/api/trains/{train_id}/inspection-events` | All historical inspection events for a train |

### 3.2 Operating Schedules & Windows (`routers/schedules.py`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/trains/{train_id}/schedules` | Create schedule (`OPERATING`, `MAINTENANCE_WINDOW`, `NON_OPERATING`) |
| `GET` | `/api/trains/{train_id}/schedules` | List train schedules (optional `active_only=true` filter) |
| `GET` | `/api/schedules/{schedule_id}` | Get specific schedule by ID |
| `PATCH` | `/api/schedules/{schedule_id}` | Update schedule timestamps, status (`ACTIVE`, `CANCELLED`), or notes |
| `GET` | `/api/trains/{train_id}/maintenance-windows` | List available upcoming depot maintenance windows |

### 3.3 ML Inspection Pipeline (`main.py`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/inspect` | Upload wheel image for YOLOv8 detection, Grad-CAM, TTA reliability, and priority calculation |

### 3.4 Maintenance Scheduling Engine (`routers/maintenance.py`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/maintenance/recommend/{wheel_asset_id}` | Generate intelligent recommendation and detect schedule conflicts |
| `GET` | `/api/maintenance/jobs` | List all maintenance jobs across the fleet |
| `GET` | `/api/maintenance/jobs/pending` | List pending maintenance jobs requiring review |
| `GET` | `/api/maintenance/jobs/urgent` | List critical priority jobs |
| `GET` | `/api/trains/{train_id}/maintenance/jobs` | List maintenance jobs for a specific train |
| `GET` | `/api/maintenance/jobs/{job_id}` | Get specific maintenance job details |
| `POST` | `/api/maintenance/jobs/{job_id}/confirm` | Confirm maintenance slot (`PENDING` → `SCHEDULED`) with overlap validation |
| `PATCH` | `/api/maintenance/jobs/{job_id}/status` | Update lifecycle (`SCHEDULED` → `IN_PROGRESS` → `COMPLETED` / `CANCELLED`) |
| `GET` | `/api/maintenance/history/{wheel_asset_id}` | Complete maintenance service history for a wheel |

### 3.5 Fleet Dashboard & Core Wheel APIs (`routers/fleet_dashboard.py`, `main.py`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/fleet/dashboard` | Executive fleet overview with 16 aggregation metrics |
| `GET` | `/api/fleet/wheels/{wheel_asset_id}/history` | Deep drill-down of wheel events, defects, and service jobs |
| `GET` | `/api/wheels` | List all wheel records |
| `GET` | `/api/wheels/{wheel_id}` | Get single wheel asset record |
| `GET` | `/api/wheels/{wheel_id}/history` | Historical defect inspection list |
| `GET` | `/api/dashboard` | Legacy overview statistics |
| `GET` | `/api/health` | Service health status and ML model readiness |
| `GET` | `/` | Root service status |

---

## 4. Live Machine Learning Inspection Pipeline

The `/api/inspect` endpoint executes an automated multi-stage pipeline:

1. **YOLOv8 Defect Detection**: Detects wheel defects (`Shelling`, `Cracks-Scratches`, `Flat Spots`, `Flange Wear`).
2. **Defect Severity Classification**: Computes severity scores (Mild, Moderate, Severe) per defect instance.
3. **Test-Time Augmentation (TTA) Reliability**: Evaluates prediction stability across image transformations to assign confidence reliability (`LOW`, `MEDIUM`, `HIGH`).
4. **Grad-CAM Explainability**: Generates visual explainability heatmaps highlighting the exact pixel regions triggering the classification.
5. **Historical Trend Analysis**: Compares current defects against prior inspections for the same wheel (`IMPROVING`, `STABLE`, `WORSENING`).
6. **Multi-Factor Risk Score (0–100)**:
   $$\text{Risk Score} = \min\left(100, (\text{Defect Weight} + \text{Severity Weight} + \text{Trend Weight}) \times \text{Reliability Factor}\right)$$
7. **Wheel Status Update**: Automatically assigns `Healthy` ($<50$), `Monitor` ($50–79$), or `Critical` ($\ge 80$) to the wheel in the database.

---

## 5. Intelligent Maintenance Scheduling & Conflict Engine

The deterministic rule engine (`maintenance_priority/scheduler.py`) maps inspection results directly to operational train schedules:

| Wheel Risk Level | Trigger Condition | Scheduling Strategy | Operational Impact |
|---|---|---|---|
| **CRITICAL** | Risk $\ge 80$ or "Immediate inspection" | Suggests immediate 2-hour mobilization window | **Requires operational clearance**. Flags all overlapping operating train schedules as conflicts. Train cannot depart until cleared. |
| **MODERATE** | Risk $50–79$ or "Schedule maintenance" | Scans train's `MAINTENANCE_WINDOW` schedules for earliest fit | If an operating run conflicts with the window, flags a **Schedule Conflict** and notes conflicting departure/arrival times. |
| **LOW** | Risk $< 50$ or "Monitor only" | Routine monitoring | No operational disruption. Recommends routine maintenance during next depot turnaround. |

### Overlap Collision Prevention
When confirming a maintenance slot via `/api/maintenance/jobs/{id}/confirm`, the engine validates interval overlaps:
$$\text{Existing Start} < \text{Requested End} \quad \text{AND} \quad \text{Existing End} > \text{Requested Start}$$
If an overlapping confirmed job already exists for the wheel, the API rejects the request with HTTP `409 Conflict`.

---

## 6. Request & Response Examples

### 6.1 Register Train, Coach, and Wheels

```bash
# 1. Register Train
POST /api/trains
Content-Type: application/json

{
  "train_number": "TR-2048",
  "train_name": "Vande Bharat Express",
  "train_type": "Superfast Express",
  "operational_status": "Active"
}
# Returns: { "id": 1, "train_number": "TR-2048", ... }

# 2. Add Coach
POST /api/trains/1/coaches
Content-Type: application/json

{
  "coach_number": "C1",
  "coach_type": "Executive Chair Car"
}
# Returns: { "id": 1, "coach_number": "C1", "train_id": 1, ... }

# 3. Register Wheel
POST /api/coaches/1/wheels
Content-Type: application/json

{
  "wheel_identifier": "C1-A1-L",
  "axle_number": 1,
  "position": "Left"
}
# Returns: { "asset_id": "WH000001", "wheel_identifier": "C1-A1-L", "status": "Healthy", ... }
```

### 6.2 Inspect Wheel with Real Image

```bash
POST /api/inspect
Content-Type: multipart/form-data

image: <wheel_sample.jpg>
wheel_id: WH000001
coach_id: 1
```

**Response (200 OK):**
```json
{
  "inspection_id": "INS000001",
  "inspection_event_id": "EVT9F3A10",
  "asset_id": "WH000001",
  "train_id": 1,
  "coach_id": 1,
  "wheel_risk_score": 50.0,
  "wheel_recommended_action": "Schedule maintenance",
  "trend_status": "FIRST_INSPECTION",
  "total_defects_detected": 2,
  "defects": [
    {
      "label": "Shelling",
      "severity": "Mild",
      "confidence": 0.80,
      "risk_score": 50.0,
      "reliability": "HIGH"
    },
    {
      "label": "Cracks-Scratches",
      "severity": "Mild",
      "confidence": 0.78,
      "risk_score": 46.8,
      "reliability": "HIGH"
    }
  ],
  "annotated_image_url": "/outputs/annotated/wheel_sample.jpg",
  "gradcam_image_url": "/outputs/gradcam/wheel_sample.jpg",
  "processing_time_seconds": 4.54
}
```

### 6.3 Maintenance Recommendation & Conflict Detection

```bash
POST /api/maintenance/recommend/WH000001
```

**Response (200 OK):**
```json
{
  "wheel_asset_id": "WH000001",
  "risk_score": 50.0,
  "priority": "MODERATE",
  "recommended_action": "Schedule maintenance",
  "trend_status": "FIRST_INSPECTION",
  "suggested_start": "2026-10-22T18:00:00",
  "suggested_end": "2026-10-22T22:00:00",
  "scheduling_status": "CONFLICT",
  "scheduling_notes": "Moderate-risk defect. A maintenance window was found but conflicts with 1 operating schedule(s). Consider rescheduling the maintenance window or adjusting operations.",
  "conflict_notes": [
    "Conflicts with operating schedule (departure=2026-10-22T16:00:00, arrival=2026-10-22T23:00:00)"
  ],
  "requires_operational_clearance": false,
  "maintenance_job_id": 12,
  "duplicate_job": false
}
```

### 6.4 Executive Fleet Dashboard

```bash
GET /api/fleet/dashboard
```

**Response (200 OK):**
```json
{
  "total_trains": 8,
  "total_coaches": 11,
  "total_wheels": 42,
  "total_inspections": 18,
  "total_inspection_events": 10,
  "inspected_wheels": 7,
  "uninspected_wheels": 35,
  "healthy_wheels": 35,
  "monitor_wheels": 5,
  "critical_wheels": 2,
  "pending_maintenance_jobs": 14,
  "scheduled_maintenance_jobs": 8,
  "train_health_summaries": [...],
  "critical_wheels_by_train": [...],
  "upcoming_maintenance": [...],
  "operating_schedule_conflicts": [...]
}
```

---

## 7. Frontend Integration & UI Application

The `frontend/` directory contains a single-page React application built with **Vite**, **React 18**, **React Router v6**, and **Recharts**.

### Features
- **Fleet Dashboard**: Visual gauges, healthy/monitor/critical wheel metrics, and upcoming maintenance schedules.
- **New Inspection**: Drag-and-drop wheel image upload with live YOLO bounding boxes and Grad-CAM overlays.
- **Wheels Explorer**: Search, filter, and view historical defect degradation curves.

### Running the Frontend
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** in your browser.

> **Frontend Configuration (`frontend/.env`):**
> ```env
> VITE_USE_MOCK=false
> VITE_API_URL=http://127.0.0.1:8000
> ```

---

## 8. Testing & Verification Suites (129 Tests)

The system features three comprehensive automated test suites with a **100% pass rate (129/129)**:

| Test Suite File | Type | Test Count | Scope |
|---|---|:---:|---|
| [`tests/verify_all_endpoints.py`](file:///c:/Railway%20project/Railway_wheel_health_assessment/tests/verify_all_endpoints.py) | **End-to-End Live** | **40** | Multipart image upload, live YOLOv8 + Grad-CAM, priority scheduling, conflict detection, full job lifecycle, and dashboard metrics. |
| [`tests/test_api_endpoints.py`](file:///c:/Railway%20project/Railway_wheel_health_assessment/tests/test_api_endpoints.py) | **Live HTTP** | **64** | Field-level validation, 404/409/422 status code validation, duplicate rejection, and filtering across all 34 routes. |
| [`tests/test_fleet_system.py`](file:///c:/Railway%20project/Railway_wheel_health_assessment/tests/test_fleet_system.py) | **Pytest Unit / Integration** | **25** | Database foreign keys, hierarchy integrity, trend aggregation, scheduler logic, and job status transitions. |
| **Total** | | **129** | **All 129 Passed** |

### Run the Tests

```bash
# 1. Run live end-to-end ML & scheduling verification (against running server)
python tests/verify_all_endpoints.py

# 2. Run 64 live HTTP validation tests
python tests/test_api_endpoints.py

# 3. Run pytest unit test suite
python -m pytest tests/test_fleet_system.py -v
```

---

## 9. How to Start & Run Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the FastAPI Backend
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Browse to:
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`
- **Health Check**: `http://127.0.0.1:8000/api/health`

---

## 10. Windows Performance & Network Optimization

> [!TIP]
> **Use `http://127.0.0.1:8000` instead of `http://localhost:8000` on Windows.**  
> On Windows, requesting `localhost` triggers an IPv6 resolution attempt (`::1`) that times out after ~2,000 ms before falling back to IPv4 (`127.0.0.1`).  
> - Benchmark on this project:
>   - `localhost`: **2,047 ms / request**
>   - `127.0.0.1`: **3.66 ms / request** (560× faster)
> 
> Always point your frontend `.env` and automated API test clients to `http://127.0.0.1:8000`.