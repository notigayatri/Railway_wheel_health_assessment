"""
tests/test_api_endpoints.py
============================
Live HTTP tests against the running FastAPI server.
Tests every new endpoint with real sample data and validates responses.

Run with:
    python tests/test_api_endpoints.py
Requires: uvicorn main:app running on localhost:8000
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

# Ensure UTF-8 output and immediate flushing on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

BASE = "http://127.0.0.1:8000"

# ── Colour helpers (Windows-safe) ─────────────────────────────────────────────
PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"
INFO = "[INFO]"

passed = 0
failed = 0
results_log = []


def _future(days: int, hours: int = 0) -> str:
    dt = datetime.now() + timedelta(days=days, hours=hours)
    return dt.isoformat(timespec="seconds")


def request(
    method: str,
    path: str,
    body: Optional[Dict] = None,
    form_data: Optional[bytes] = None,
    content_type: str = "application/json",
    expected_status: int = 200,
    label: str = "",
) -> Optional[Dict[str, Any]]:
    global passed, failed
    url = BASE + path
    try:
        if body is not None:
            data = json.dumps(body).encode()
            ct = "application/json"
        elif form_data is not None:
            data = form_data
            ct = content_type
        else:
            data = None
            ct = content_type

        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", ct)

        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            raw = resp.read()
            result = json.loads(raw) if raw else {}

        if status == expected_status:
            tag = PASS
            passed += 1
        else:
            tag = FAIL
            failed += 1
            result["_actual_status"] = status

    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
        try:
            result = json.loads(raw)
        except Exception:
            result = {"raw": raw.decode(errors="replace")}

        if status == expected_status:
            tag = PASS
            passed += 1
        else:
            tag = FAIL
            failed += 1
            result["_actual_status"] = status
    except Exception as exc:
        tag = FAIL
        failed += 1
        result = {"error": str(exc)}
        status = 0

    summary = f"{method:6} {path}"
    if label:
        summary = f"{label}: {summary}"
    extra = ""
    if tag == FAIL:
        extra = f"  -> expected {expected_status}, got {status} | {json.dumps(result)[:200]}"

    line = f"  {tag} {summary}{extra}"
    print(line)
    results_log.append({"tag": tag, "label": label, "path": path, "status": status, "result": result})
    return result if tag in (PASS,) else result  # always return result for chaining


def section(title: str):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. HEALTH CHECKS
# ─────────────────────────────────────────────────────────────────────────────
section("1. Health Checks")

r = request("GET", "/", expected_status=200, label="Root health check")
assert r.get("status") == "ok", "Root should return status=ok"

r = request("GET", "/api/health", expected_status=200, label="Detailed health check")
assert r.get("version") == "2.0.0", "Version should be 2.0.0"
assert r["models"]["yolo"] is True, "YOLO model should be loaded"

# ─────────────────────────────────────────────────────────────────────────────
# 2. TRAIN REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────
section("2. Train Registration Module")

RUN_ID = f"{int(datetime.now().timestamp()) % 100000:05d}"
train_number = f"T-API-{RUN_ID}"
coach1_number = f"C1-{RUN_ID}"
coach2_number = f"C2-{RUN_ID}"

r = request("POST", "/api/trains",
    body={"train_number": train_number, "train_name": f"API Test Express {RUN_ID}",
          "train_type": "Express", "operational_status": "Active",
          "registration_date": "2026-10-01"},
    expected_status=201, label=f"Register train {train_number}")

TRAIN_ID = r["id"]
print(f"  {INFO} Using TRAIN_ID={TRAIN_ID}")

# Verify required fields
r = request("GET", f"/api/trains/{TRAIN_ID}", expected_status=200, label="Get train by ID")
assert r.get("train_number") == train_number
assert r.get("train_type") == "Express"
assert "registration_date" in r
assert "created_at" in r
assert "last_updated" in r

# List all trains
r = request("GET", "/api/trains", expected_status=200, label="List all trains")
assert isinstance(r, list)
assert any(t["id"] == TRAIN_ID for t in r), "Created train should appear in list"

# Update train
r = request("PATCH", f"/api/trains/{TRAIN_ID}",
    body={"operational_status": "Under Maintenance"},
    expected_status=200, label="Update train status")
assert r.get("operational_status") == "Under Maintenance"

# Restore
request("PATCH", f"/api/trains/{TRAIN_ID}",
    body={"operational_status": "Active"},
    expected_status=200, label="Restore train status")

# Duplicate train number -> 409
request("POST", "/api/trains",
    body={"train_number": train_number, "train_name": "Duplicate"},
    expected_status=409, label="Duplicate train number rejected")

# Non-existent train -> 404
request("GET", "/api/trains/999999", expected_status=404, label="Non-existent train 404")

# ─────────────────────────────────────────────────────────────────────────────
# 3. COACH MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
section("3. Coach Management")

# Add Coach C1
r = request("POST", f"/api/trains/{TRAIN_ID}/coaches",
    body={"coach_number": coach1_number, "coach_type": "AC"},
    expected_status=201, label=f"Add coach {coach1_number}")
COACH1_ID = r["id"]

# Add Coach C2
r = request("POST", f"/api/trains/{TRAIN_ID}/coaches",
    body={"coach_number": coach2_number, "coach_type": "Sleeper"},
    expected_status=201, label=f"Add coach {coach2_number}")
COACH2_ID = r["id"]

print(f"  {INFO} COACH1_ID={COACH1_ID}, COACH2_ID={COACH2_ID}")

# List coaches
r = request("GET", f"/api/trains/{TRAIN_ID}/coaches", expected_status=200, label="List coaches for train")
assert isinstance(r, list)
coach_nums = [c["coach_number"] for c in r]
assert coach1_number in coach_nums, f"{coach1_number} missing from {coach_nums}"
assert coach2_number in coach_nums

# Get specific coach
r = request("GET", f"/api/trains/{TRAIN_ID}/coaches/{COACH1_ID}", expected_status=200, label="Get specific coach")
assert r.get("coach_number") == coach1_number
assert r.get("train_id") == TRAIN_ID

# Duplicate coach -> 409
request("POST", f"/api/trains/{TRAIN_ID}/coaches",
    body={"coach_number": coach1_number},
    expected_status=409, label="Duplicate coach rejected")

# Coach on wrong train -> 404
request("GET", f"/api/trains/999999/coaches/{COACH1_ID}", expected_status=404, label="Coach on wrong train 404")

# ─────────────────────────────────────────────────────────────────────────────
# 4. WHEEL MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
section("4. Wheel Management within Coach")

# Register wheels in C1
wheel_ids = []
for i, (axle, pos) in enumerate([(1, "Left"), (1, "Right"), (2, "Left"), (2, "Right")]):
    r = request("POST", f"/api/coaches/{COACH1_ID}/wheels",
        body={"wheel_identifier": f"C1-{RUN_ID}-{pos[0]}{axle}", "axle_number": axle, "position": pos},
        expected_status=201, label=f"Register wheel C1 axle{axle} {pos}")
    if "asset_id" in r:
        wheel_ids.append(r["asset_id"])

# Register wheels in C2
for axle, pos in [(1, "Left"), (1, "Right")]:
    r = request("POST", f"/api/coaches/{COACH2_ID}/wheels",
        body={"wheel_identifier": f"C2-{RUN_ID}-{pos[0]}{axle}", "axle_number": axle, "position": pos},
        expected_status=201, label=f"Register wheel C2 axle{axle} {pos}")
    if "asset_id" in r:
        wheel_ids.append(r["asset_id"])

print(f"  {INFO} Registered wheel IDs: {wheel_ids}")

# List wheels in coach
r = request("GET", f"/api/coaches/{COACH1_ID}/wheels", expected_status=200, label="List wheels in C1")
assert isinstance(r, list)
assert len(r) >= 4, f"C1 should have >=4 wheels, got {len(r)}"
for w in r:
    assert "asset_id" in w
    assert "status" in w
    assert w.get("coach_id") == str(COACH1_ID), f"coach_id mismatch: {w.get('coach_id')} != {COACH1_ID}"

# C2 wheels
r = request("GET", f"/api/coaches/{COACH2_ID}/wheels", expected_status=200, label="List wheels in C2")
assert isinstance(r, list)
assert len(r) >= 2

# Non-existent coach -> 404
request("GET", "/api/coaches/999999/wheels", expected_status=404, label="Non-existent coach 404")

# Check wheel appears in /api/wheels list
if wheel_ids:
    WHEEL_ID = wheel_ids[0]
    r = request("GET", f"/api/wheels/{WHEEL_ID}", expected_status=200, label="Get wheel via /api/wheels")
    assert r.get("asset_id") == WHEEL_ID
    assert "status" in r
    assert "inspection_count" in r
    assert "position" in r

# ─────────────────────────────────────────────────────────────────────────────
# 5. OPERATING SCHEDULES
# ─────────────────────────────────────────────────────────────────────────────
section("5. Operating Schedule Module")

# Add operating run
r = request("POST", f"/api/trains/{TRAIN_ID}/schedules",
    body={"schedule_type": "OPERATING",
          "departure_datetime": _future(2, 6),
          "arrival_datetime": _future(2, 14),
          "notes": "Morning express run"},
    expected_status=201, label="Add OPERATING schedule")
assert r.get("schedule_type") == "OPERATING"
assert r.get("status") == "ACTIVE"
SCHED_OP_ID = r.get("id")

# Add maintenance window
r = request("POST", f"/api/trains/{TRAIN_ID}/schedules",
    body={"schedule_type": "MAINTENANCE_WINDOW",
          "departure_datetime": _future(5, 0),
          "arrival_datetime": _future(5, 10),
          "depot_location": "Central Depot",
          "notes": "Scheduled maintenance slot"},
    expected_status=201, label="Add MAINTENANCE_WINDOW schedule")
assert r.get("schedule_type") == "MAINTENANCE_WINDOW"
assert r.get("depot_location") == "Central Depot"
SCHED_MW_ID = r.get("id")

# Add non-operating period
r = request("POST", f"/api/trains/{TRAIN_ID}/schedules",
    body={"schedule_type": "NON_OPERATING",
          "operating_date": _future(10)[:10],
          "notes": "Annual service week"},
    expected_status=201, label="Add NON_OPERATING schedule")
SCHED_NOP_ID = r.get("id")

# Invalid schedule_type -> 422
request("POST", f"/api/trains/{TRAIN_ID}/schedules",
    body={"schedule_type": "INVALID_TYPE"},
    expected_status=422, label="Invalid schedule_type rejected")

# List schedules
r = request("GET", f"/api/trains/{TRAIN_ID}/schedules", expected_status=200, label="List all schedules")
assert isinstance(r, list)
types = [s["schedule_type"] for s in r]
assert "OPERATING" in types
assert "MAINTENANCE_WINDOW" in types

# Get specific schedule
r = request("GET", f"/api/schedules/{SCHED_OP_ID}", expected_status=200, label="Get specific schedule")
assert r.get("id") == SCHED_OP_ID

# List maintenance windows
r = request("GET", f"/api/trains/{TRAIN_ID}/maintenance-windows", expected_status=200,
            label="List maintenance windows")
assert isinstance(r, list)
assert any(s["id"] == SCHED_MW_ID for s in r), "Maintenance window should appear"

# Cancel schedule
r = request("PATCH", f"/api/schedules/{SCHED_OP_ID}",
    body={"status": "CANCELLED", "notes": "Cancelled for testing"},
    expected_status=200, label="Cancel operating schedule")
assert r.get("status") == "CANCELLED"

# Restore
request("PATCH", f"/api/schedules/{SCHED_OP_ID}",
    body={"status": "ACTIVE"},
    expected_status=200, label="Restore schedule to ACTIVE")

# Invalid status -> 422
request("PATCH", f"/api/schedules/{SCHED_OP_ID}",
    body={"status": "INVALID_STATUS"},
    expected_status=422, label="Invalid schedule status rejected")

# List active-only
r = request("GET", f"/api/trains/{TRAIN_ID}/schedules?active_only=true", expected_status=200,
            label="List active-only schedules")
assert all(s["status"] == "ACTIVE" for s in r), "All returned schedules should be ACTIVE"

# ─────────────────────────────────────────────────────────────────────────────
# 6. EXISTING API BACKWARD COMPATIBILITY
# ─────────────────────────────────────────────────────────────────────────────
section("6. Existing Endpoints – Backward Compatibility")

# /api/wheels
r = request("GET", "/api/wheels", expected_status=200, label="GET /api/wheels (existing)")
assert isinstance(r, list)

# /api/dashboard (legacy)
r = request("GET", "/api/dashboard", expected_status=200, label="GET /api/dashboard (legacy)")
assert "total_wheels" in r
assert "total_inspections" in r
assert "healthy" in r
assert "monitor" in r
assert "critical" in r
assert "severity_distribution" in r
assert "defect_distribution" in r
assert "recent_inspections" in r

# /api/wheels/{id}/history
if wheel_ids:
    r = request("GET", f"/api/wheels/{wheel_ids[0]}/history", expected_status=200,
                label="GET /api/wheels/{id}/history (existing)")
    assert isinstance(r, list)

# Non-existent wheel history -> 404
request("GET", "/api/wheels/WH_NONEXISTENT_XYZXYZ/history", expected_status=404,
        label="Non-existent wheel history 404")

# ─────────────────────────────────────────────────────────────────────────────
# 7. TRAIN HEALTH DRILL-DOWN
# ─────────────────────────────────────────────────────────────────────────────
section("7. Train Health Drill-Down")

r = request("GET", f"/api/trains/{TRAIN_ID}/health", expected_status=200, label="Train health drill-down")
assert "train" in r
assert "coaches" in r
assert "recent_inspection_events" in r
assert r["train"]["id"] == TRAIN_ID
assert isinstance(r["coaches"], list)
assert len(r["coaches"]) >= 2
# Each coach should have a 'wheels' list
for c in r["coaches"]:
    assert "wheels" in c, f"Coach {c['coach_number']} missing 'wheels' key"

# Inspection events for train
r = request("GET", f"/api/trains/{TRAIN_ID}/inspection-events", expected_status=200,
            label="Train inspection events")
assert isinstance(r, list)

# ─────────────────────────────────────────────────────────────────────────────
# 8. FLEET DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
section("8. Fleet Dashboard (Extended)")

r = request("GET", "/api/fleet/dashboard", expected_status=200, label="GET /api/fleet/dashboard")
REQUIRED_DASHBOARD_KEYS = [
    "total_trains", "total_coaches", "total_wheels",
    "total_inspections", "total_inspection_events",
    "inspected_wheels", "uninspected_wheels",
    "healthy_wheels", "monitor_wheels", "critical_wheels",
    "pending_maintenance_jobs", "scheduled_maintenance_jobs",
    "train_health_summaries", "critical_wheels_by_train",
    "upcoming_maintenance", "operating_schedule_conflicts",
]
missing = [k for k in REQUIRED_DASHBOARD_KEYS if k not in r]
if missing:
    print(f"  {FAIL} Missing dashboard keys: {missing}")
    failed += 1
else:
    print(f"  {PASS} All {len(REQUIRED_DASHBOARD_KEYS)} dashboard keys present")
    passed += 1

assert r["total_trains"] >= 1
assert r["total_coaches"] >= 2
assert isinstance(r["train_health_summaries"], list)
assert isinstance(r["critical_wheels_by_train"], list)
assert isinstance(r["upcoming_maintenance"], list)
assert isinstance(r["operating_schedule_conflicts"], list)

# Print fleet stats
print(f"\n  Fleet Stats:")
print(f"    Trains            : {r['total_trains']}")
print(f"    Coaches           : {r['total_coaches']}")
print(f"    Total Wheels      : {r['total_wheels']}")
print(f"    Total Inspections : {r['total_inspections']}")
print(f"    Inspection Events : {r['total_inspection_events']}")
print(f"    Healthy / Monitor / Critical: {r['healthy_wheels']} / {r['monitor_wheels']} / {r['critical_wheels']}")
print(f"    Pending Jobs      : {r['pending_maintenance_jobs']}")
print(f"    Scheduled Jobs    : {r['scheduled_maintenance_jobs']}")

# Wheel drill-down
if wheel_ids:
    r = request("GET", f"/api/fleet/wheels/{wheel_ids[0]}/history", expected_status=200,
                label="Wheel full drill-down history")
    assert "wheel" in r
    assert "inspection_events" in r
    assert "defect_records" in r
    assert "maintenance_jobs" in r

# ─────────────────────────────────────────────────────────────────────────────
# 9. MAINTENANCE RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────────────────────
section("9. Maintenance Recommendations & Jobs")

# Recommend for a wheel that HAS inspection events
# First create a fake inspection event via fleet_repository directly so we can test
# (the /api/inspect endpoint needs a real image file, tested separately)
# Instead, test the 422 when no inspection exists for a fresh wheel

FRESH_WHEEL_ID = None
if wheel_ids:
    # Use one of the newly registered wheels (they have no inspection events)
    FRESH_WHEEL_ID = wheel_ids[-1]
    r = request("POST", f"/api/maintenance/recommend/{FRESH_WHEEL_ID}",
        expected_status=422, label="Recommend for wheel with no inspection -> 422")

# Test with non-existent wheel
request("POST", "/api/maintenance/recommend/WH_GHOST_WHEEL",
    expected_status=404, label="Recommend for non-existent wheel -> 404")

# List all maintenance jobs
r = request("GET", "/api/maintenance/jobs", expected_status=200, label="List all maintenance jobs")
assert isinstance(r, list)

# Validate all job fields
if r:
    job = r[0]
    REQUIRED_JOB_FIELDS = [
        "id", "wheel_asset_id", "priority", "risk_score",
        "recommended_action", "job_status", "created_at", "last_updated"
    ]
    missing = [f for f in REQUIRED_JOB_FIELDS if f not in job]
    if missing:
        print(f"  {FAIL} Job missing fields: {missing}")
        failed += 1
    else:
        print(f"  {PASS} All job fields present")
        passed += 1

# List pending jobs
r = request("GET", "/api/maintenance/jobs/pending", expected_status=200, label="List pending jobs")
assert isinstance(r, list)
assert all(j["job_status"] == "PENDING" for j in r), "All returned should be PENDING"

# List urgent jobs
r = request("GET", "/api/maintenance/jobs/urgent", expected_status=200, label="List urgent (CRITICAL) jobs")
assert isinstance(r, list)
assert all(j["priority"] == "CRITICAL" for j in r), "All returned should be CRITICAL"

# Filter by train
r = request("GET", f"/api/maintenance/jobs?train_id={TRAIN_ID}", expected_status=200,
            label="Filter jobs by train_id")
assert isinstance(r, list)

# Train-specific maintenance jobs
r = request("GET", f"/api/trains/{TRAIN_ID}/maintenance/jobs", expected_status=200,
            label="GET /api/trains/{train_id}/maintenance/jobs")
assert isinstance(r, list)

# Get specific job (use first available)
r_all = request("GET", "/api/maintenance/jobs", expected_status=200)
if r_all:
    JOB_ID = r_all[0]["id"]
    r = request("GET", f"/api/maintenance/jobs/{JOB_ID}", expected_status=200,
                label="Get specific maintenance job")
    assert r.get("id") == JOB_ID

    # Update job status to IN_PROGRESS (only if currently pending/scheduled)
    current_status = r_all[0]["job_status"]
    if current_status == "SCHEDULED":
        r = request("PATCH", f"/api/maintenance/jobs/{JOB_ID}/status",
            body={"job_status": "IN_PROGRESS"},
            expected_status=200, label="Update job status to IN_PROGRESS")
        assert r.get("job_status") == "IN_PROGRESS"
    elif current_status == "PENDING":
        # Try confirming it first, then updating
        r = request("POST", f"/api/maintenance/jobs/{JOB_ID}/confirm",
            body={"confirmed_start": _future(5, 8)},
            expected_status=200, label="Confirm pending job -> SCHEDULED")
        if "job_status" in r:
            assert r.get("job_status") == "SCHEDULED"
    else:
        print(f"  {SKIP} Job {JOB_ID} is {current_status}, skipping status update test")

    # Invalid status -> 422
    request("PATCH", f"/api/maintenance/jobs/{JOB_ID}/status",
        body={"job_status": "INVALID_STATUS"},
        expected_status=422, label="Invalid job status rejected")

# Non-existent job -> 404
request("GET", "/api/maintenance/jobs/999999", expected_status=404, label="Non-existent job 404")

# Maintenance history for a wheel
if wheel_ids:
    r = request("GET", f"/api/maintenance/history/{wheel_ids[0]}", expected_status=200,
                label="Maintenance history for wheel")
    assert isinstance(r, list)

# ─────────────────────────────────────────────────────────────────────────────
# 10. EDGE CASES & VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
section("10. Edge Cases & Validation")

# Train with no coaches health
r_new = request("POST", "/api/trains",
    body={"train_number": f"T-EMPTY-{RUN_ID}", "train_name": "Empty Train Test"},
    expected_status=201, label="Register train with no coaches")
if "id" in r_new:
    EMPTY_TRAIN_ID = r_new["id"]
    r = request("GET", f"/api/trains/{EMPTY_TRAIN_ID}/health", expected_status=200,
                label="Health drill-down for train with no coaches")
    assert r["coaches"] == [], f"Empty train should have 0 coaches"

    # Schedules for new train
    r = request("GET", f"/api/trains/{EMPTY_TRAIN_ID}/schedules", expected_status=200,
                label="Schedules for new train (empty)")
    assert r == [], "New train should have no schedules"

    # Add + active-only filter
    r = request("POST", f"/api/trains/{EMPTY_TRAIN_ID}/schedules",
        body={"schedule_type": "OPERATING", "departure_datetime": _future(1),
              "arrival_datetime": _future(1, 8)},
        expected_status=201, label="Add schedule to new train")
    assert r.get("status") == "ACTIVE"

# Test wrong coach/train combo
if COACH1_ID and TRAIN_ID:
    r = request("GET", f"/api/trains/999999/coaches/{COACH1_ID}", expected_status=404,
                label="Coach of a different train -> 404")

# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'='*65}")
print(f"  API ENDPOINT TEST RESULTS")
print(f"{'='*65}")
print(f"  Total tests : {total}")
print(f"  Passed      : {passed}")
print(f"  Failed      : {failed}")
print(f"{'='*65}")

if failed > 0:
    print(f"\n  FAILED TESTS:")
    for r in results_log:
        if r["tag"] == FAIL:
            print(f"    {r['path']} (expected/got: {r['status']})")
            if "error" in r["result"]:
                print(f"       Error: {r['result']['error']}")
            elif "detail" in r["result"]:
                print(f"       Detail: {r['result']['detail']}")
    sys.exit(1)
else:
    print(f"\n  All {total} endpoint tests passed successfully!")
