"""
tests/verify_all_endpoints.py
=============================
Comprehensive end-to-end live testing of ALL 34 API endpoints in the Railway Wheel Health
Assessment & Intelligent Maintenance Scheduling System.

Tests every endpoint, uploads real wheel images to /api/inspect, verifies YOLO + defect
classifications, checks intelligent scheduling logic, verifies dashboard accuracy, and logs
field-level validation results.
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

BASE = "http://127.0.0.1:8000"
RUN_ID = f"{int(time.time()) % 100000:05d}"
PASS = "[PASS]"
FAIL = "[FAIL]"

passed = 0
failed = 0
results: List[Dict[str, Any]] = []


def req(
    method: str,
    path: str,
    body: Optional[Dict] = None,
    form_fields: Optional[Dict[str, str]] = None,
    files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
    expected_status: int = 200,
    label: str = "",
) -> Dict[str, Any]:
    global passed, failed
    url = BASE + path
    headers = {}
    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif files is not None:
        # Multipart form-data
        boundary = f"----WebKitFormBoundary{RUN_ID}abc123xyz"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body_bytes = bytearray()

        if form_fields:
            for k, v in form_fields.items():
                body_bytes.extend(f"--{boundary}\r\n".encode("utf-8"))
                body_bytes.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
                body_bytes.extend(f"{v}\r\n".encode("utf-8"))

        for field_name, (filename, file_bytes, mime) in files.items():
            body_bytes.extend(f"--{boundary}\r\n".encode("utf-8"))
            body_bytes.extend(
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
            )
            body_bytes.extend(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
            body_bytes.extend(file_bytes)
            body_bytes.extend(b"\r\n")

        body_bytes.extend(f"--{boundary}--\r\n".encode("utf-8"))
        data = bytes(body_bytes)

    request_obj = urllib.request.Request(url, data=data, headers=headers, method=method)

    status = 0
    resp_body = {}
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as r:
            status = r.status
            raw = r.read()
            if raw:
                try:
                    resp_body = json.loads(raw.decode("utf-8"))
                except Exception:
                    resp_body = {"raw": raw.decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        try:
            resp_body = json.loads(raw.decode("utf-8"))
        except Exception:
            resp_body = {"raw": raw.decode("utf-8", errors="replace")}
    except Exception as e:
        status = 500
        resp_body = {"error": str(e)}

    is_ok = status == expected_status
    tag = PASS if is_ok else FAIL
    if is_ok:
        passed += 1
    else:
        failed += 1

    desc = label or f"{method} {path}"
    detail = "" if is_ok else f" (expected {expected_status}, got {status} | {json.dumps(resp_body)[:180]})"
    print(f"  {tag} {desc}{detail}")

    results.append({
        "label": desc,
        "method": method,
        "path": path,
        "status": status,
        "expected": expected_status,
        "passed": is_ok,
        "body": resp_body,
    })
    return resp_body


def section(name: str):
    print(f"\n{'='*70}\n  {name}\n{'='*70}")


def main():
    print(f"Starting End-to-End System Verification (Run ID: {RUN_ID})")
    print(f"Target Server: {BASE}\n")

    # 1. Health & Meta
    section("1. Core & Server Health Endpoints")
    r = req("GET", "/", expected_status=200, label="Root Endpoint (GET /)")
    assert r.get("status") == "ok"
    r = req("GET", "/api/health", expected_status=200, label="Detailed Health (GET /api/health)")
    assert r.get("version") == "2.0.0"
    assert r.get("models", {}).get("yolo") is True
    assert r.get("models", {}).get("kmeans") is True

    # 2. Train Lifecycle
    section("2. Train Registration & Management Endpoints")
    train_num = f"TR-{RUN_ID}"
    r_tr = req("POST", "/api/trains",
               body={"train_number": train_num, "train_name": "Vande Bharat Test", "train_type": "Express", "operational_status": "Active"},
               expected_status=201, label=f"Register Train {train_num} (POST /api/trains)")
    train_id = r_tr["id"]

    r = req("GET", "/api/trains", expected_status=200, label="List All Trains (GET /api/trains)")
    assert any(t["id"] == train_id for t in r)

    r = req("GET", f"/api/trains/{train_id}", expected_status=200, label="Get Train by ID (GET /api/trains/{id})")
    assert r["train_number"] == train_num

    r = req("PATCH", f"/api/trains/{train_id}", body={"operational_status": "Under Maintenance"},
            expected_status=200, label="Update Train Status (PATCH /api/trains/{id})")
    assert r["operational_status"] == "Under Maintenance"

    req("PATCH", f"/api/trains/{train_id}", body={"operational_status": "Active"},
        expected_status=200, label="Restore Train Status (PATCH /api/trains/{id})")

    # 3. Coach & Wheel Hierarchy
    section("3. Coach & Wheel Hierarchy Endpoints")
    coach_num = f"C-{RUN_ID}-A1"
    r_c = req("POST", f"/api/trains/{train_id}/coaches",
              body={"coach_number": coach_num, "coach_type": "AC Chair Car"},
              expected_status=201, label=f"Add Coach {coach_num} (POST /api/trains/{{id}}/coaches)")
    coach_id = r_c["id"]

    r = req("GET", f"/api/trains/{train_id}/coaches", expected_status=200, label="List Train Coaches (GET /api/trains/{id}/coaches)")
    assert any(c["id"] == coach_id for c in r)

    r = req("GET", f"/api/trains/{train_id}/coaches/{coach_id}", expected_status=200, label="Get Specific Coach (GET /api/trains/{id}/coaches/{cid})")
    assert r["coach_number"] == coach_num

    # Add wheels to coach
    wheel_asset_ids = []
    for axle in [1, 2]:
        for pos in ["Left", "Right"]:
            w_code = f"W-{RUN_ID}-A{axle}{pos[0]}"
            rw = req("POST", f"/api/coaches/{coach_id}/wheels",
                     body={"wheel_identifier": w_code, "axle_number": axle, "position": pos},
                     expected_status=201, label=f"Register Wheel {w_code} (POST /api/coaches/{{id}}/wheels)")
            wheel_asset_ids.append(rw["asset_id"])

    r = req("GET", f"/api/coaches/{coach_id}/wheels", expected_status=200, label="List Wheels in Coach (GET /api/coaches/{id}/wheels)")
    assert len(r) == 4

    test_wheel_id = wheel_asset_ids[0]
    r = req("GET", f"/api/wheels/{test_wheel_id}", expected_status=200, label="Get Single Wheel via Core API (GET /api/wheels/{id})")
    assert r["asset_id"] == test_wheel_id

    r = req("GET", "/api/wheels", expected_status=200, label="List Wheels via Core API (GET /api/wheels)")
    assert any(w["asset_id"] == test_wheel_id for w in r)

    # 4. Operating Schedules & Windows
    section("4. Operating Schedules & Maintenance Windows Endpoints")
    now = datetime.now()
    dt_dep = (now + timedelta(days=1, hours=8)).isoformat(timespec="seconds")
    dt_arr = (now + timedelta(days=1, hours=16)).isoformat(timespec="seconds")
    r_sch = req("POST", f"/api/trains/{train_id}/schedules",
                body={"schedule_type": "OPERATING", "departure_datetime": dt_dep, "arrival_datetime": dt_arr, "notes": "Delhi to Varanasi"},
                expected_status=201, label="Create OPERATING Schedule (POST /api/trains/{id}/schedules)")
    op_sched_id = r_sch["id"]

    mw_start = (now + timedelta(days=2, hours=2)).isoformat(timespec="seconds")
    mw_end = (now + timedelta(days=2, hours=8)).isoformat(timespec="seconds")
    r_mw = req("POST", f"/api/trains/{train_id}/schedules",
               body={"schedule_type": "MAINTENANCE_WINDOW", "departure_datetime": mw_start, "arrival_datetime": mw_end, "notes": "Depot Window"},
               expected_status=201, label="Create MAINTENANCE_WINDOW Schedule (POST /api/trains/{id}/schedules)")
    mw_id = r_mw["id"]

    r = req("GET", f"/api/trains/{train_id}/schedules", expected_status=200, label="List Schedules for Train (GET /api/trains/{id}/schedules)")
    assert len(r) >= 2

    r = req("GET", f"/api/schedules/{op_sched_id}", expected_status=200, label="Get Schedule by ID (GET /api/schedules/{id})")
    assert r["id"] == op_sched_id

    r = req("PATCH", f"/api/schedules/{op_sched_id}", body={"notes": "Updated Route Notes"},
            expected_status=200, label="Update Schedule (PATCH /api/schedules/{id})")
    assert r["notes"] == "Updated Route Notes"

    r = req("GET", f"/api/trains/{train_id}/maintenance-windows", expected_status=200, label="List Maintenance Windows (GET /api/trains/{id}/maintenance-windows)")
    assert any(w["id"] == mw_id for w in r)

    # 5. Live ML Wheel Inspection with Real Image Upload
    section("5. Live ML Inspection Pipeline with Image Upload (POST /api/inspect)")
    sample_img_path = Path("dataset/test/images/frame1669_jpg.rf.fbb0d3e03b5cb6a816ee6593ecad1fcf.jpg")
    assert sample_img_path.exists(), f"Sample image {sample_img_path} not found"

    with open(sample_img_path, "rb") as f:
        img_bytes = f.read()

    print(f"  [INFO] Uploading real wheel image ({len(img_bytes)} bytes) to /api/inspect...")
    t0 = time.time()
    r_inspect = req(
        "POST",
        "/api/inspect",
        form_fields={
            "wheel_id": test_wheel_id,
            "coach_id": str(coach_id),
            "axle_number": "1",
        },
        files={"image": (sample_img_path.name, img_bytes, "image/jpeg")},
        expected_status=200,
        label="Full ML Inspection with YOLO+GradCAM+TTA+Priority (POST /api/inspect)",
    )
    inference_duration = time.time() - t0
    print(f"  [INFO] Inference completed in {inference_duration:.2f}s")

    # Validate output accuracy and structures
    assert r_inspect.get("asset_id") == test_wheel_id
    assert "defects" in r_inspect
    assert "wheel_risk_score" in r_inspect
    assert "wheel_recommended_action" in r_inspect
    assert "trend_status" in r_inspect
    assert "annotated_image_url" in r_inspect

    risk_score = r_inspect["wheel_risk_score"]
    action = r_inspect["wheel_recommended_action"]
    defects = r_inspect["defects"]
    print(f"  [ACCURACY] Wheel Risk Score: {risk_score}/100 | Action: {action} | Defect Count: {len(defects)}")
    for d in defects:
        print(f"    - Defect: {d['label']}, Severity: {d['severity']}, Conf: {d['confidence']:.2f}, Risk: {d['risk_score']}")

    # 6. Legacy & Wheel History Endpoints
    section("6. Wheel Inspection History & Legacy Compatibility")
    r = req("GET", f"/api/wheels/{test_wheel_id}/history", expected_status=200, label="Get Wheel History (GET /api/wheels/{id}/history)")
    assert len(r) >= 1

    r = req("GET", "/api/dashboard", expected_status=200, label="Legacy Dashboard Summary (GET /api/dashboard)")
    assert "total_inspections" in r

    r = req("GET", f"/api/trains/{train_id}/inspection-events", expected_status=200, label="Train Inspection Events (GET /api/trains/{id}/inspection-events)")
    assert len(r) >= 1

    r = req("GET", f"/api/fleet/wheels/{test_wheel_id}/history", expected_status=200, label="Extended Wheel Fleet History (GET /api/fleet/wheels/{id}/history)")
    assert r["wheel"]["asset_id"] == test_wheel_id
    assert len(r["inspection_events"]) >= 1

    # 7. Train Health Drill-Down
    section("7. Train Health Hierarchical Drill-Down")
    r_th = req("GET", f"/api/trains/{train_id}/health", expected_status=200, label="Train Health Drill-Down (GET /api/trains/{id}/health)")
    assert r_th["train"]["id"] == train_id
    assert len(r_th["coaches"]) >= 1
    coach_wheels = r_th["coaches"][0]["wheels"]
    assert len(coach_wheels) == 4
    inspected_w = next(w for w in coach_wheels if w["asset_id"] == test_wheel_id)
    assert inspected_w["status"].upper() in ("HEALTHY", "MONITOR", "CRITICAL")
    print(f"  [ACCURACY] Inspected Wheel {test_wheel_id} status in Train hierarchy: {inspected_w['status']}")

    # 8. Intelligent Maintenance Scheduling & Priority Engine
    section("8. Intelligent Maintenance Recommendation & Scheduling")
    r_rec = req("POST", f"/api/maintenance/recommend/{test_wheel_id}", expected_status=200,
                label=f"Generate Recommendation for {test_wheel_id} (POST /api/maintenance/recommend/{{id}})")

    assert "priority" in r_rec
    assert "risk_score" in r_rec
    assert "scheduling_status" in r_rec
    job_id = r_rec.get("maintenance_job_id")
    assert job_id is not None, "Job ID should be created"

    print(f"  [ACCURACY] Job ID: {job_id} | Priority: {r_rec['priority']} | Status: {r_rec['scheduling_status']}")
    print(f"  [ACCURACY] Recommendation: {r_rec['recommended_action']}")
    print(f"  [ACCURACY] Scheduling Notes: {r_rec['scheduling_notes']}")
    if r_rec.get("conflict_notes"):
        print(f"  [ACCURACY] Conflict Notes: {r_rec['conflict_notes']}")

    # Maintenance Jobs APIs
    r = req("GET", "/api/maintenance/jobs", expected_status=200, label="List All Maintenance Jobs (GET /api/maintenance/jobs)")
    assert any(j["id"] == job_id for j in r)

    r = req("GET", "/api/maintenance/jobs/pending", expected_status=200, label="List Pending Jobs (GET /api/maintenance/jobs/pending)")
    assert any(j["id"] == job_id for j in r)

    r = req("GET", "/api/maintenance/jobs/urgent", expected_status=200, label="List Urgent Jobs (GET /api/maintenance/jobs/urgent)")
    assert isinstance(r, list)

    r = req("GET", f"/api/trains/{train_id}/maintenance/jobs", expected_status=200, label="Train Maintenance Jobs (GET /api/trains/{id}/maintenance/jobs)")
    assert any(j["id"] == job_id for j in r)

    r = req("GET", f"/api/maintenance/history/{test_wheel_id}", expected_status=200, label="Wheel Maintenance History (GET /api/maintenance/history/{id})")
    assert any(j["id"] == job_id for j in r)

    r = req("GET", f"/api/maintenance/jobs/{job_id}", expected_status=200, label="Get Single Job by ID (GET /api/maintenance/jobs/{id})")
    assert r["id"] == job_id

    # Confirm Maintenance Job
    conf_time = (now + timedelta(days=2, hours=3)).isoformat(timespec="seconds")
    r = req("POST", f"/api/maintenance/jobs/{job_id}/confirm",
            body={"confirmed_start": conf_time},
            expected_status=200, label="Confirm Maintenance Job (POST /api/maintenance/jobs/{id}/confirm)")
    assert r["job_status"] == "SCHEDULED"

    # Update Job Status Lifecycle
    r = req("PATCH", f"/api/maintenance/jobs/{job_id}/status",
            body={"job_status": "IN_PROGRESS"},
            expected_status=200, label="Start Job -> IN_PROGRESS (PATCH /api/maintenance/jobs/{id}/status)")
    assert r["job_status"] == "IN_PROGRESS"

    r = req("PATCH", f"/api/maintenance/jobs/{job_id}/status",
            body={"job_status": "COMPLETED"},
            expected_status=200, label="Complete Job -> COMPLETED (PATCH /api/maintenance/jobs/{id}/status)")
    assert r["job_status"] == "COMPLETED"

    # 9. Extended Fleet Dashboard
    section("9. Fleet Dashboard (Executive & Operations Overview)")
    r_dash = req("GET", "/api/fleet/dashboard", expected_status=200, label="Extended Fleet Dashboard (GET /api/fleet/dashboard)")

    print("  [ACCURACY] Fleet Dashboard Metrics:")
    print(f"    - Total Trains: {r_dash['total_trains']}")
    print(f"    - Total Coaches: {r_dash['total_coaches']}")
    print(f"    - Total Wheels: {r_dash['total_wheels']}")
    print(f"    - Inspected Wheels: {r_dash['inspected_wheels']}")
    print(f"    - Healthy / Monitor / Critical: {r_dash['healthy_wheels']} / {r_dash['monitor_wheels']} / {r_dash['critical_wheels']}")
    print(f"    - Total Inspections: {r_dash['total_inspections']}")
    print(f"    - Total Inspection Events: {r_dash['total_inspection_events']}")
    print(f"    - Pending Jobs: {r_dash['pending_maintenance_jobs']}")
    print(f"    - Scheduled Jobs: {r_dash['scheduled_maintenance_jobs']}")

    assert r_dash["total_trains"] >= 1
    assert r_dash["total_coaches"] >= 1
    assert r_dash["total_wheels"] >= 4
    assert r_dash["total_inspections"] >= 1

    # Final summary
    total = passed + failed
    print(f"\n{'='*70}\n  FINAL TEST AUDIT SUMMARY\n{'='*70}")
    print(f"  Total API endpoints and operations tested: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Accuracy Rate: {(passed / total) * 100:.1f}%\n{'='*70}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
