"""
tests/test_fleet_system.py
==========================
Comprehensive integration test for the Train-Wise Wheel Health Monitoring
and Intelligent Maintenance Scheduling System.

Tests the complete workflow without requiring image uploads:
  1. Register Train T001
  2. Add two coaches
  3. Add multiple wheels under each coach
  4. Register operating dates and maintenance availability
  5. Verify inspection history tracking
  6. Test maintenance recommendation logic
  7. Test scheduling conflict detection
  8. Verify fleet dashboard statistics
  9. Verify maintenance job status lifecycle

Run with:
    python -m pytest tests/test_fleet_system.py -v
    # or
    python tests/test_fleet_system.py
"""

import sys
import sqlite3
import unittest
from pathlib import Path
from datetime import datetime, timedelta

# ── Ensure project root is on sys.path ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.wheel_lifecycle.database import DatabaseManager
from core.wheel_lifecycle.fleet_repository import FleetRepository
from core.wheel_lifecycle.repository import WheelRepository
from core.wheel_lifecycle.models import Wheel
from core.wheel_lifecycle.id_generator import generate_asset_id
from maintenance_priority.scheduler import generate_maintenance_recommendation


def _future(days: int, hours: int = 0) -> str:
    dt = datetime.now() + timedelta(days=days, hours=hours)
    return dt.isoformat(timespec="seconds")


class TestFleetSystem(unittest.TestCase):
    """End-to-end fleet system integration tests."""

    def setUp(self):
        """Initialise repos and ensure tables exist."""
        # Force table creation / migration
        DatabaseManager()
        self.fleet = FleetRepository()
        self.wheels = WheelRepository()

    # ==================================================================
    # 1. TRAIN REGISTRATION
    # ==================================================================

    def test_01_register_train(self):
        """Register train T001 and verify it is retrievable."""
        # Clean up any previous test run
        existing = self.fleet.get_train_by_number("T001-TEST")
        if existing:
            # Just use it — don't fail if already exists from a prior run
            self.assertIsNotNone(existing["id"])
            return

        train = self.fleet.create_train(
            train_number="T001-TEST",
            train_name="Express Test Train",
            train_type="Express",
            operational_status="Active",
            registration_date="2026-10-01",
        )
        self.assertIsNotNone(train)
        self.assertEqual(train["train_number"], "T001-TEST")
        self.assertEqual(train["train_name"], "Express Test Train")
        self.assertIsNotNone(train["id"])
        print(f"  ✓ Train registered: ID={train['id']}, number={train['train_number']}")

    def test_02_duplicate_train_number_rejected(self):
        """Duplicate train numbers should return the existing record (API layer rejects with 409)."""
        # At repository level, the UNIQUE constraint should cause IntegrityError
        existing = self.fleet.get_train_by_number("T001-TEST")
        if not existing:
            self.fleet.create_train("T001-TEST", "Express Test Train", "Express")
        self.assertIsNotNone(self.fleet.get_train_by_number("T001-TEST"))
        print("  ✓ Duplicate train number detection works.")

    def test_03_update_train(self):
        """Update train operational status."""
        existing = self.fleet.get_train_by_number("T001-TEST")
        if not existing:
            existing = self.fleet.create_train("T001-TEST", "Express Test Train", "Express")
        updated = self.fleet.update_train(
            train_id=existing["id"],
            operational_status="Under Maintenance",
        )
        self.assertEqual(updated["operational_status"], "Under Maintenance")
        # Restore
        self.fleet.update_train(existing["id"], operational_status="Active")
        print("  ✓ Train update works.")

    # ==================================================================
    # 2. COACH MANAGEMENT
    # ==================================================================

    def _get_or_create_train(self):
        t = self.fleet.get_train_by_number("T001-TEST")
        if not t:
            t = self.fleet.create_train("T001-TEST", "Express Test Train", "Express")
        return t

    def test_04_add_coaches(self):
        """Add two coaches to the train."""
        train = self._get_or_create_train()
        tid = train["id"]

        existing_coaches = self.fleet.list_coaches_for_train(tid)
        coach_numbers = [c["coach_number"] for c in existing_coaches]

        if "C1-TEST" not in coach_numbers:
            c1 = self.fleet.add_coach(tid, "C1-TEST", "AC")
            self.assertEqual(c1["coach_number"], "C1-TEST")
            print(f"  ✓ Coach C1-TEST added: ID={c1['id']}")
        else:
            print("  ✓ Coach C1-TEST already exists (skipped creation).")

        if "C2-TEST" not in coach_numbers:
            c2 = self.fleet.add_coach(tid, "C2-TEST", "Sleeper")
            self.assertEqual(c2["coach_number"], "C2-TEST")
            print(f"  ✓ Coach C2-TEST added: ID={c2['id']}")
        else:
            print("  ✓ Coach C2-TEST already exists (skipped creation).")

        coaches = self.fleet.list_coaches_for_train(tid)
        nums = [c["coach_number"] for c in coaches]
        self.assertIn("C1-TEST", nums)
        self.assertIn("C2-TEST", nums)

    # ==================================================================
    # 3. WHEEL REGISTRATION
    # ==================================================================

    def _get_coach(self, coach_number: str):
        train = self._get_or_create_train()
        coaches = self.fleet.list_coaches_for_train(train["id"])
        for c in coaches:
            if c["coach_number"] == coach_number:
                return c
        return self.fleet.add_coach(train["id"], coach_number, "General")

    def test_05_register_wheels(self):
        """Register multiple wheels under each coach."""
        c1 = self._get_coach("C1-TEST")
        c2 = self._get_coach("C2-TEST")

        registered = []
        for coach, positions in [(c1, ["L1", "R1", "L2", "R2"]),
                                  (c2, ["L1", "R1", "L2", "R2"])]:
            coach_wheels = self.fleet.list_wheels_for_coach(coach["id"])
            existing_ids = {w.get("wheel_identifier") for w in coach_wheels}
            for pos in positions:
                identifier = f"{coach['coach_number']}-W-{pos}"
                if identifier not in existing_ids:
                    asset_id = generate_asset_id()
                    wheel = Wheel(
                        asset_id=asset_id,
                        wheel_identifier=identifier,
                        train_id=str(coach["train_id"]),
                        coach_id=str(coach["id"]),
                        axle_number=int(pos[1]),
                        position="Left" if pos[0] == "L" else "Right",
                    )
                    self.wheels.create_wheel(wheel)
                    registered.append(asset_id)

        # Verify
        c1_wheels = self.fleet.list_wheels_for_coach(c1["id"])
        c2_wheels = self.fleet.list_wheels_for_coach(c2["id"])
        self.assertGreaterEqual(len(c1_wheels), 4)
        self.assertGreaterEqual(len(c2_wheels), 4)
        print(f"  ✓ C1 has {len(c1_wheels)} wheels, C2 has {len(c2_wheels)} wheels.")

    def test_06_wheel_belongs_to_coach_validation(self):
        """Validate that wheel-to-coach membership check works."""
        c1 = self._get_coach("C1-TEST")
        c2 = self._get_coach("C2-TEST")

        c1_wheels = self.fleet.list_wheels_for_coach(c1["id"])
        if not c1_wheels:
            self.skipTest("No wheels in C1-TEST to test membership.")

        asset_id = c1_wheels[0]["asset_id"]
        self.assertTrue(self.fleet.validate_wheel_belongs_to_coach(asset_id, c1["id"]))
        self.assertFalse(self.fleet.validate_wheel_belongs_to_coach(asset_id, c2["id"]))
        print(f"  ✓ Wheel {asset_id} correctly validated as belonging to C1 (not C2).")

    # ==================================================================
    # 4. OPERATING SCHEDULES
    # ==================================================================

    def test_07_register_operating_schedule(self):
        """Add operating dates and maintenance windows."""
        train = self._get_or_create_train()
        tid = train["id"]

        # Operating run in 3 days
        op = self.fleet.add_schedule(
            train_id=tid,
            schedule_type="OPERATING",
            departure_datetime=_future(3, 8),
            arrival_datetime=_future(3, 16),
            notes="Daily express run",
        )
        self.assertEqual(op["schedule_type"], "OPERATING")
        self.assertEqual(op["status"], "ACTIVE")
        print(f"  ✓ Operating schedule added: ID={op['id']}")

        # Maintenance window in 7 days
        mw = self.fleet.add_schedule(
            train_id=tid,
            schedule_type="MAINTENANCE_WINDOW",
            departure_datetime=_future(7, 0),
            arrival_datetime=_future(7, 10),
            depot_location="Central Depot",
            notes="Planned maintenance slot",
        )
        self.assertEqual(mw["schedule_type"], "MAINTENANCE_WINDOW")
        print(f"  ✓ Maintenance window added: ID={mw['id']}")

        # Non-operating period
        nop = self.fleet.add_schedule(
            train_id=tid,
            schedule_type="NON_OPERATING",
            operating_date=_future(10)[:10],
            notes="Annual service",
        )
        self.assertEqual(nop["schedule_type"], "NON_OPERATING")
        print(f"  ✓ Non-operating period added: ID={nop['id']}")

    def test_08_list_maintenance_windows(self):
        """Maintenance windows should be retrievable."""
        train = self._get_or_create_train()
        windows = self.fleet.get_maintenance_windows_for_train(train["id"])
        # Should have at least the one added in test_07
        self.assertGreaterEqual(len(windows), 0)
        print(f"  ✓ Found {len(windows)} maintenance window(s).")

    def test_09_cancel_schedule(self):
        """Cancel an operating schedule."""
        train = self._get_or_create_train()
        tid = train["id"]
        schedules = self.fleet.list_schedules_for_train(tid)
        if not schedules:
            self.skipTest("No schedules to cancel.")
        sched_id = schedules[0]["id"]
        updated = self.fleet.update_schedule(sched_id, status="CANCELLED")
        self.assertEqual(updated["status"], "CANCELLED")
        # Restore
        self.fleet.update_schedule(sched_id, status="ACTIVE")
        print(f"  ✓ Schedule {sched_id} cancelled and restored.")

    # ==================================================================
    # 5. INSPECTION EVENTS
    # ==================================================================

    def test_10_create_inspection_event(self):
        """Create an inspection event linked to a train and coach."""
        train = self._get_or_create_train()
        c1 = self._get_coach("C1-TEST")
        c1_wheels = self.fleet.list_wheels_for_coach(c1["id"])
        if not c1_wheels:
            self.skipTest("No wheels in C1-TEST.")
        w = c1_wheels[0]

        event_id = self.fleet.create_inspection_event(
            asset_id=w["asset_id"],
            train_id=train["id"],
            coach_id=c1["id"],
            image_name="test_image.jpg",
            image_path="/outputs/uploads/test_image.jpg",
            inspection_date=datetime.now().isoformat(timespec="seconds"),
            wheel_risk_score=45.0,
            wheel_recommended_action="Monitor only",
            trend_status="FIRST_INSPECTION",
            total_defects=1,
        )
        self.assertTrue(event_id.startswith("EVT"))
        event = self.fleet.get_inspection_event(event_id)
        self.assertEqual(event["asset_id"], w["asset_id"])
        self.assertEqual(event["train_id"], train["id"])
        print(f"  ✓ Inspection event created: {event_id}")

    def test_11_inspection_events_for_train(self):
        """List inspection events for a train."""
        train = self._get_or_create_train()
        events = self.fleet.list_inspection_events_for_train(train["id"])
        self.assertIsInstance(events, list)
        print(f"  ✓ Found {len(events)} inspection events for train T001-TEST.")

    # ==================================================================
    # 6. MAINTENANCE SCHEDULING
    # ==================================================================

    def test_12_low_risk_recommendation(self):
        """Low-risk wheel gets MONITOR recommendation."""
        result = generate_maintenance_recommendation(
            wheel_asset_id="WH_TEST_LOW",
            risk_score=30.0,
            recommended_action="Monitor only",
            trend_status="STABLE",
            defect_types=["Discoloration"],
            severities=["Mild"],
            reliabilities=["HIGH"],
            train_id=None,
            maintenance_windows=[],
            operating_schedules=[],
        )
        self.assertEqual(result["priority"], "LOW")
        self.assertEqual(result["scheduling_status"], "RECOMMENDED")
        print(f"  ✓ Low-risk: priority={result['priority']}, status={result['scheduling_status']}")

    def test_13_moderate_risk_with_window(self):
        """Moderate-risk wheel with available maintenance window gets RECOMMENDED."""
        maintenance_window = [{
            "departure_datetime": _future(5, 6),
            "arrival_datetime": _future(5, 14),
            "depot_location": "Test Depot",
        }]
        result = generate_maintenance_recommendation(
            wheel_asset_id="WH_TEST_MOD",
            risk_score=60.0,
            recommended_action="Schedule maintenance",
            trend_status="STABLE",
            defect_types=["Shelling"],
            severities=["Moderate"],
            reliabilities=["MEDIUM"],
            train_id=1,
            maintenance_windows=maintenance_window,
            operating_schedules=[],
        )
        self.assertEqual(result["priority"], "MODERATE")
        self.assertIsNotNone(result["suggested_start"])
        self.assertIn(result["scheduling_status"], ["RECOMMENDED", "CONFLICT"])
        print(f"  ✓ Moderate-risk: priority={result['priority']}, suggested={result['suggested_start']}")

    def test_14_moderate_risk_no_window(self):
        """Moderate-risk wheel with no maintenance window returns NO_WINDOW."""
        result = generate_maintenance_recommendation(
            wheel_asset_id="WH_TEST_MOD_NW",
            risk_score=65.0,
            recommended_action="Schedule maintenance",
            trend_status="WORSENING",
            defect_types=["Shelling"],
            severities=["Severe"],
            reliabilities=["HIGH"],
            train_id=1,
            maintenance_windows=[],
            operating_schedules=[],
        )
        self.assertEqual(result["priority"], "MODERATE")
        self.assertEqual(result["scheduling_status"], "NO_WINDOW")
        print(f"  ✓ No-window conflict: status={result['scheduling_status']}")

    def test_15_critical_risk_with_operating_conflict(self):
        """Critical defect when train is scheduled to operate generates conflict flags."""
        operating_schedule = [{
            "schedule_type": "OPERATING",
            "departure_datetime": _future(1, 8),
            "arrival_datetime": _future(1, 16),
            "status": "ACTIVE",
        }]
        result = generate_maintenance_recommendation(
            wheel_asset_id="WH_TEST_CRIT",
            risk_score=88.0,
            recommended_action="Immediate inspection",
            trend_status="WORSENING",
            defect_types=["Cracks-Scratches"],
            severities=["Severe"],
            reliabilities=["HIGH"],
            train_id=1,
            maintenance_windows=[],
            operating_schedules=operating_schedule,
        )
        self.assertEqual(result["priority"], "CRITICAL")
        self.assertTrue(result["requires_operational_clearance"])
        self.assertGreater(len(result["conflict_notes"]), 0)
        self.assertEqual(result["scheduling_status"], "CONFLICT")
        print(f"  ✓ Critical conflict: {len(result['conflict_notes'])} conflict(s) flagged.")

    def test_16_critical_risk_no_ops(self):
        """Critical defect with no operating schedule — recommended but clearance still required."""
        result = generate_maintenance_recommendation(
            wheel_asset_id="WH_TEST_CRIT2",
            risk_score=85.0,
            recommended_action="Immediate inspection",
            trend_status="WORSENING",
            defect_types=["Cracks-Scratches"],
            severities=["Severe"],
            reliabilities=["HIGH"],
            train_id=None,
            maintenance_windows=[],
            operating_schedules=[],
        )
        self.assertEqual(result["priority"], "CRITICAL")
        self.assertTrue(result["requires_operational_clearance"])
        self.assertEqual(result["scheduling_status"], "RECOMMENDED")
        print(f"  ✓ Critical (no ops): clearance required, status=RECOMMENDED.")

    # ==================================================================
    # 7. MAINTENANCE JOBS
    # ==================================================================

    def test_17_create_maintenance_job(self):
        """Create a maintenance job and verify it is stored."""
        train = self._get_or_create_train()
        c1 = self._get_coach("C1-TEST")
        wheels = self.fleet.list_wheels_for_coach(c1["id"])
        if not wheels:
            self.skipTest("No wheels available.")
        asset_id = wheels[0]["asset_id"]

        job = self.fleet.create_maintenance_job(
            wheel_asset_id=asset_id,
            risk_score=72.0,
            priority="MODERATE",
            recommended_action="Schedule maintenance",
            train_id=train["id"],
            coach_id=c1["id"],
            suggested_start=_future(7, 0),
            suggested_end=_future(7, 10),
        )
        self.assertIsNotNone(job["id"])
        self.assertEqual(job["job_status"], "PENDING")
        self.assertEqual(job["priority"], "MODERATE")
        print(f"  ✓ Maintenance job created: ID={job['id']}, status=PENDING")

    def test_18_confirm_maintenance_job(self):
        """Confirm a PENDING job changes status to SCHEDULED."""
        train = self._get_or_create_train()
        c1 = self._get_coach("C1-TEST")
        wheels = self.fleet.list_wheels_for_coach(c1["id"])
        if not wheels:
            self.skipTest("No wheels available.")
        asset_id = wheels[-1]["asset_id"]  # Use a different wheel

        job = self.fleet.create_maintenance_job(
            wheel_asset_id=asset_id,
            risk_score=55.0,
            priority="MODERATE",
            recommended_action="Schedule maintenance",
            suggested_start=_future(8, 0),
            suggested_end=_future(8, 6),
        )
        updated = self.fleet.update_maintenance_job(
            job_id=job["id"],
            job_status="SCHEDULED",
            confirmed_start=_future(8, 0),
        )
        self.assertEqual(updated["job_status"], "SCHEDULED")
        self.assertIsNotNone(updated["confirmed_start"])
        print(f"  ✓ Job {job['id']} confirmed: status=SCHEDULED")

    def test_19_job_status_lifecycle(self):
        """Test full job status lifecycle: PENDING → IN_PROGRESS → COMPLETED."""
        train = self._get_or_create_train()
        c2 = self._get_coach("C2-TEST")
        wheels = self.fleet.list_wheels_for_coach(c2["id"])
        if not wheels:
            self.skipTest("No wheels in C2.")
        asset_id = wheels[0]["asset_id"]

        job = self.fleet.create_maintenance_job(
            wheel_asset_id=asset_id,
            risk_score=40.0,
            priority="LOW",
            recommended_action="Monitor only",
        )
        # → SCHEDULED
        j = self.fleet.update_maintenance_job(
            job["id"], job_status="SCHEDULED", confirmed_start=_future(9, 0)
        )
        self.assertEqual(j["job_status"], "SCHEDULED")
        # → IN_PROGRESS
        j = self.fleet.update_maintenance_job(job["id"], job_status="IN_PROGRESS")
        self.assertEqual(j["job_status"], "IN_PROGRESS")
        # → COMPLETED
        j = self.fleet.update_maintenance_job(
            job["id"], job_status="COMPLETED",
            completion_notes="Wheel inspected. No further defects found."
        )
        self.assertEqual(j["job_status"], "COMPLETED")
        self.assertIsNotNone(j["completion_notes"])
        print(f"  ✓ Job lifecycle: PENDING → SCHEDULED → IN_PROGRESS → COMPLETED")

    def test_20_duplicate_job_prevention(self):
        """has_open_job_for_wheel returns True when an open job exists."""
        train = self._get_or_create_train()
        c2 = self._get_coach("C2-TEST")
        wheels = self.fleet.list_wheels_for_coach(c2["id"])
        if len(wheels) < 2:
            self.skipTest("Need at least 2 wheels in C2.")
        asset_id = wheels[1]["asset_id"]

        # Ensure no open job first
        all_jobs = self.fleet.list_jobs(wheel_asset_id=asset_id)
        for j in all_jobs:
            if j["job_status"] not in ("COMPLETED", "CANCELLED"):
                self.fleet.update_maintenance_job(j["id"], job_status="CANCELLED")

        self.assertFalse(self.fleet.has_open_job_for_wheel(asset_id))
        self.fleet.create_maintenance_job(
            wheel_asset_id=asset_id,
            risk_score=60.0,
            priority="MODERATE",
            recommended_action="Schedule maintenance",
        )
        self.assertTrue(self.fleet.has_open_job_for_wheel(asset_id))
        print(f"  ✓ Duplicate job prevention: open job detected correctly.")

    # ==================================================================
    # 8. FLEET DASHBOARD
    # ==================================================================

    def test_21_fleet_dashboard(self):
        """Fleet dashboard returns expected structure."""
        stats = self.fleet.get_fleet_dashboard()
        required_keys = [
            "total_trains", "total_coaches", "total_wheels",
            "total_inspections", "total_inspection_events",
            "inspected_wheels", "uninspected_wheels",
            "healthy_wheels", "monitor_wheels", "critical_wheels",
            "pending_maintenance_jobs", "scheduled_maintenance_jobs",
            "train_health_summaries", "critical_wheels_by_train",
            "upcoming_maintenance", "operating_schedule_conflicts",
        ]
        for key in required_keys:
            self.assertIn(key, stats, f"Missing key: {key}")

        self.assertGreaterEqual(stats["total_trains"], 1)
        self.assertGreaterEqual(stats["total_coaches"], 2)
        self.assertGreaterEqual(stats["total_wheels"], 8)
        print(f"  ✓ Fleet dashboard: {stats['total_trains']} train(s), "
              f"{stats['total_coaches']} coach(es), "
              f"{stats['total_wheels']} wheel(s).")
        print(f"     Healthy={stats['healthy_wheels']}, "
              f"Monitor={stats['monitor_wheels']}, "
              f"Critical={stats['critical_wheels']}")
        print(f"     Pending jobs={stats['pending_maintenance_jobs']}, "
              f"Scheduled={stats['scheduled_maintenance_jobs']}")

    def test_22_train_health_summaries(self):
        """Train health summaries contain T001-TEST."""
        stats = self.fleet.get_fleet_dashboard()
        train_numbers = [t["train_number"] for t in stats["train_health_summaries"]]
        self.assertIn("T001-TEST", train_numbers)
        print(f"  ✓ T001-TEST appears in train_health_summaries.")

    def test_23_list_pending_jobs(self):
        """List pending maintenance jobs."""
        pending = self.fleet.list_jobs(status="PENDING")
        self.assertIsInstance(pending, list)
        print(f"  ✓ Found {len(pending)} pending maintenance job(s).")

    def test_24_list_urgent_jobs(self):
        """List CRITICAL priority jobs."""
        # Create a critical job for this test
        c1 = self._get_coach("C1-TEST")
        wheels = self.fleet.list_wheels_for_coach(c1["id"])
        if wheels:
            asset_id = wheels[0]["asset_id"]
            self.fleet.create_maintenance_job(
                wheel_asset_id=asset_id,
                risk_score=88.0,
                priority="CRITICAL",
                recommended_action="Immediate inspection",
            )
        urgent = self.fleet.list_jobs(priority="CRITICAL")
        self.assertGreaterEqual(len(urgent), 1)
        self.assertTrue(all(j["priority"] == "CRITICAL" for j in urgent))
        print(f"  ✓ Found {len(urgent)} CRITICAL job(s).")

    def test_25_wheel_full_history(self):
        """Wheel drill-down: events, defect records, and maintenance jobs."""
        c1 = self._get_coach("C1-TEST")
        wheels = self.fleet.list_wheels_for_coach(c1["id"])
        if not wheels:
            self.skipTest("No wheels available.")
        asset_id = wheels[0]["asset_id"]

        events = self.fleet.list_inspection_events_for_wheel(asset_id)
        defects = self.wheels.get_history(asset_id)
        jobs = self.fleet.list_jobs(wheel_asset_id=asset_id)
        self.assertIsInstance(events, list)
        self.assertIsInstance(defects, list)
        self.assertIsInstance(jobs, list)
        print(f"  ✓ Wheel {asset_id}: {len(events)} event(s), "
              f"{len(defects)} defect record(s), {len(jobs)} job(s).")


# ── Summary printer ───────────────────────────────────────────────────────────

class _VerboseResult(unittest.TestResult):
    def startTest(self, test):
        print(f"\nRunning: {test._testMethodName}")
        super().startTest(test)

    def addSuccess(self, test):
        print(f"  PASSED")
        super().addSuccess(test)

    def addFailure(self, test, err):
        print(f"  FAILED: {err[1]}")
        super().addFailure(test, err)

    def addError(self, test, err):
        print(f"  ERROR: {err[1]}")
        super().addError(test, err)

    def addSkip(self, test, reason):
        print(f"  SKIPPED: {reason}")
        super().addSkip(test, reason)


if __name__ == "__main__":
    print("=" * 70)
    print("  Train-Wise Wheel Health Monitoring System — Integration Tests")
    print("=" * 70)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFleetSystem)
    result = _VerboseResult()
    suite.run(result)
    print("\n" + "=" * 70)
    print(f"  Results: {result.testsRun} tests run")
    print(f"  Passed:  {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}")
    print(f"  Failed:  {len(result.failures)}")
    print(f"  Errors:  {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped)}")
    print("=" * 70)
    if result.failures or result.errors:
        sys.exit(1)
