"""
fleet_repository.py
===================
Database access layer for Trains, Coaches, Operating Schedules,
Inspection Events, and Maintenance Jobs.

Separate from the original WheelRepository so the existing code is
never touched; both repositories share the same underlying SQLite
connection through DatabaseManager.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.wheel_lifecycle.database import DatabaseManager


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class FleetRepository:
    """Central repository for all fleet-management tables."""

    def __init__(self):
        self.db = DatabaseManager().get_connection()

    # ==================================================================
    # TRAINS
    # ==================================================================

    def create_train(
        self,
        train_number: str,
        train_name: str,
        train_type: Optional[str],
        operational_status: str = "Active",
        registration_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now_iso()
        reg_date = registration_date or now[:10]
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO trains
                (train_number, train_name, train_type, operational_status,
                 registration_date, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (train_number, train_name, train_type, operational_status,
             reg_date, now, now),
        )
        self.db.commit()
        return self.get_train_by_id(cursor.lastrowid)

    def get_train_by_id(self, train_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM trains WHERE id=?", (train_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_train_by_number(self, train_number: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM trains WHERE train_number=?", (train_number,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_trains(self) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM trains ORDER BY id")
        return [dict(r) for r in cursor.fetchall()]

    def update_train(
        self,
        train_id: int,
        train_name: Optional[str] = None,
        train_type: Optional[str] = None,
        operational_status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now = _now_iso()
        fields, values = [], []
        if train_name is not None:
            fields.append("train_name=?"); values.append(train_name)
        if train_type is not None:
            fields.append("train_type=?"); values.append(train_type)
        if operational_status is not None:
            fields.append("operational_status=?"); values.append(operational_status)
        if not fields:
            return self.get_train_by_id(train_id)
        fields.append("last_updated=?"); values.append(now)
        values.append(train_id)
        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE trains SET {', '.join(fields)} WHERE id=?", values
        )
        self.db.commit()
        return self.get_train_by_id(train_id)

    # ==================================================================
    # COACHES
    # ==================================================================

    def add_coach(
        self,
        train_id: int,
        coach_number: str,
        coach_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now_iso()
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO coaches (coach_number, coach_type, train_id, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?)
            """,
            (coach_number, coach_type, train_id, now, now),
        )
        self.db.commit()
        return self.get_coach_by_id(cursor.lastrowid)

    def get_coach_by_id(self, coach_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM coaches WHERE id=?", (coach_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_coach_by_number(self, train_id: int, coach_number: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM coaches WHERE train_id=? AND coach_number=?",
            (train_id, coach_number),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_coaches_for_train(self, train_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM coaches WHERE train_id=? ORDER BY id", (train_id,)
        )
        return [dict(r) for r in cursor.fetchall()]

    # ==================================================================
    # WHEELS (extended queries on the existing wheels table)
    # ==================================================================

    def list_wheels_for_coach(self, coach_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM wheels WHERE coach_id=? ORDER BY asset_id",
            (str(coach_id),),
        )
        return [dict(r) for r in cursor.fetchall()]

    def get_wheel_by_asset_id(self, asset_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM wheels WHERE asset_id=?", (asset_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def validate_wheel_belongs_to_coach(self, asset_id: str, coach_id: int) -> bool:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT 1 FROM wheels WHERE asset_id=? AND coach_id=?",
            (asset_id, str(coach_id)),
        )
        return cursor.fetchone() is not None

    # ==================================================================
    # OPERATING SCHEDULES
    # ==================================================================

    def add_schedule(
        self,
        train_id: int,
        schedule_type: str,
        departure_datetime: Optional[str] = None,
        arrival_datetime: Optional[str] = None,
        operating_date: Optional[str] = None,
        depot_location: Optional[str] = None,
        notes: Optional[str] = None,
        status: str = "ACTIVE",
    ) -> Dict[str, Any]:
        now = _now_iso()
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO operating_schedules
                (train_id, schedule_type, departure_datetime, arrival_datetime,
                 operating_date, depot_location, notes, status, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (train_id, schedule_type, departure_datetime, arrival_datetime,
             operating_date, depot_location, notes, status, now, now),
        )
        self.db.commit()
        return self.get_schedule_by_id(cursor.lastrowid)

    def get_schedule_by_id(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM operating_schedules WHERE id=?", (schedule_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_schedules_for_train(
        self, train_id: int, active_only: bool = False
    ) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        if active_only:
            cursor.execute(
                "SELECT * FROM operating_schedules WHERE train_id=? AND status='ACTIVE' ORDER BY departure_datetime",
                (train_id,),
            )
        else:
            cursor.execute(
                "SELECT * FROM operating_schedules WHERE train_id=? ORDER BY departure_datetime",
                (train_id,),
            )
        return [dict(r) for r in cursor.fetchall()]

    def update_schedule(
        self,
        schedule_id: int,
        status: Optional[str] = None,
        departure_datetime: Optional[str] = None,
        arrival_datetime: Optional[str] = None,
        depot_location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now = _now_iso()
        fields, values = [], []
        if status is not None:
            fields.append("status=?"); values.append(status)
        if departure_datetime is not None:
            fields.append("departure_datetime=?"); values.append(departure_datetime)
        if arrival_datetime is not None:
            fields.append("arrival_datetime=?"); values.append(arrival_datetime)
        if depot_location is not None:
            fields.append("depot_location=?"); values.append(depot_location)
        if notes is not None:
            fields.append("notes=?"); values.append(notes)
        if not fields:
            return self.get_schedule_by_id(schedule_id)
        fields.append("last_updated=?"); values.append(now)
        values.append(schedule_id)
        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE operating_schedules SET {', '.join(fields)} WHERE id=?", values
        )
        self.db.commit()
        return self.get_schedule_by_id(schedule_id)

    def get_maintenance_windows_for_train(self, train_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT * FROM operating_schedules
            WHERE train_id=? AND schedule_type='MAINTENANCE_WINDOW' AND status='ACTIVE'
            ORDER BY departure_datetime
            """,
            (train_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def get_operating_dates_in_range(
        self, train_id: int, start_dt: str, end_dt: str
    ) -> List[Dict[str, Any]]:
        """Return OPERATING schedules that overlap the given time window."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT * FROM operating_schedules
            WHERE train_id=?
              AND schedule_type='OPERATING'
              AND status='ACTIVE'
              AND departure_datetime IS NOT NULL
              AND arrival_datetime IS NOT NULL
              AND departure_datetime < ?
              AND arrival_datetime > ?
            ORDER BY departure_datetime
            """,
            (train_id, end_dt, start_dt),
        )
        return [dict(r) for r in cursor.fetchall()]

    # ==================================================================
    # INSPECTION EVENTS
    # ==================================================================

    def create_inspection_event(
        self,
        asset_id: str,
        train_id: Optional[int],
        coach_id: Optional[int],
        image_name: str,
        image_path: str,
        inspection_date: str,
        wheel_risk_score: float,
        wheel_recommended_action: str,
        trend_status: str,
        total_defects: int,
        annotated_image_path: Optional[str] = None,
        gradcam_image_path: Optional[str] = None,
        processing_time: Optional[float] = None,
    ) -> str:
        event_id = "EVT" + uuid.uuid4().hex[:10].upper()
        now = _now_iso()
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO inspection_events
                (event_id, asset_id, train_id, coach_id, image_name, image_path,
                 inspection_date, wheel_risk_score, wheel_recommended_action,
                 trend_status, total_defects, annotated_image_path,
                 gradcam_image_path, processing_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, asset_id, train_id, coach_id, image_name, image_path,
                inspection_date, wheel_risk_score, wheel_recommended_action,
                trend_status, total_defects, annotated_image_path,
                gradcam_image_path, processing_time, now,
            ),
        )
        self.db.commit()
        return event_id

    def get_inspection_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM inspection_events WHERE event_id=?", (event_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_inspection_events_for_wheel(self, asset_id: str) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM inspection_events WHERE asset_id=? ORDER BY inspection_date DESC",
            (asset_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    def list_inspection_events_for_train(self, train_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM inspection_events WHERE train_id=? ORDER BY inspection_date DESC",
            (train_id,),
        )
        return [dict(r) for r in cursor.fetchall()]

    # ==================================================================
    # MAINTENANCE JOBS
    # ==================================================================

    def has_open_job_for_wheel(self, wheel_asset_id: str) -> bool:
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT 1 FROM maintenance_jobs
            WHERE wheel_asset_id=?
              AND job_status NOT IN ('COMPLETED', 'CANCELLED')
            LIMIT 1
            """,
            (wheel_asset_id,),
        )
        return cursor.fetchone() is not None

    def create_maintenance_job(
        self,
        wheel_asset_id: str,
        risk_score: float,
        priority: str,
        recommended_action: str,
        train_id: Optional[int] = None,
        coach_id: Optional[int] = None,
        inspection_event_id: Optional[str] = None,
        suggested_start: Optional[str] = None,
        suggested_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now_iso()
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO maintenance_jobs
                (train_id, coach_id, wheel_asset_id, inspection_event_id,
                 risk_score, priority, recommended_action,
                 suggested_start, suggested_end,
                 job_status, created_at, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                train_id, coach_id, wheel_asset_id, inspection_event_id,
                risk_score, priority, recommended_action,
                suggested_start, suggested_end,
                now, now,
            ),
        )
        self.db.commit()
        return self.get_maintenance_job(cursor.lastrowid)

    def get_maintenance_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM maintenance_jobs WHERE id=?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_maintenance_job(
        self,
        job_id: int,
        job_status: Optional[str] = None,
        confirmed_start: Optional[str] = None,
        completion_notes: Optional[str] = None,
        suggested_start: Optional[str] = None,
        suggested_end: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now = _now_iso()
        fields, values = [], []
        if job_status is not None:
            fields.append("job_status=?"); values.append(job_status)
        if confirmed_start is not None:
            fields.append("confirmed_start=?"); values.append(confirmed_start)
        if completion_notes is not None:
            fields.append("completion_notes=?"); values.append(completion_notes)
        if suggested_start is not None:
            fields.append("suggested_start=?"); values.append(suggested_start)
        if suggested_end is not None:
            fields.append("suggested_end=?"); values.append(suggested_end)
        if not fields:
            return self.get_maintenance_job(job_id)
        fields.append("last_updated=?"); values.append(now)
        values.append(job_id)
        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE maintenance_jobs SET {', '.join(fields)} WHERE id=?", values
        )
        self.db.commit()
        return self.get_maintenance_job(job_id)

    def list_jobs(
        self,
        train_id: Optional[int] = None,
        coach_id: Optional[int] = None,
        wheel_asset_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses, values = [], []
        if train_id is not None:
            clauses.append("train_id=?"); values.append(train_id)
        if coach_id is not None:
            clauses.append("coach_id=?"); values.append(coach_id)
        if wheel_asset_id is not None:
            clauses.append("wheel_asset_id=?"); values.append(wheel_asset_id)
        if status is not None:
            clauses.append("job_status=?"); values.append(status)
        if priority is not None:
            clauses.append("priority=?"); values.append(priority)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self.db.cursor()
        cursor.execute(
            f"SELECT * FROM maintenance_jobs {where} ORDER BY risk_score DESC, created_at DESC",
            values,
        )
        return [dict(r) for r in cursor.fetchall()]

    def has_confirmed_job_overlap(
        self, wheel_asset_id: str, start_dt: str, end_dt: str, exclude_job_id: Optional[int] = None
    ) -> bool:
        """
        Check whether a confirmed/in-progress job for this wheel overlaps
        the requested [start_dt, end_dt] window.

        Standard interval overlap: A overlaps B  iff  A.start < B.end AND A.end > B.start.
        Since we only store confirmed_start (not confirmed_end), we use suggested_end
        as a proxy.  If suggested_end is NULL we assume a default 4-hour window.
        """
        cursor = self.db.cursor()
        # An existing job overlaps [start_dt, end_dt] when:
        #   confirmed_start < end_dt  (existing job starts before new window ends)
        #   AND COALESCE(suggested_end, confirmed_start) > start_dt  (existing job ends after new window starts)
        exclude_clause = ""
        params: list = [wheel_asset_id, end_dt, start_dt]
        if exclude_job_id is not None:
            exclude_clause = "AND id != ?"
            params.append(exclude_job_id)
        cursor.execute(
            f"""
            SELECT 1 FROM maintenance_jobs
            WHERE wheel_asset_id=?
              AND job_status IN ('SCHEDULED', 'IN_PROGRESS')
              AND confirmed_start IS NOT NULL
              AND confirmed_start < ?
              AND COALESCE(suggested_end, datetime(confirmed_start, '+4 hours')) > ?
              {exclude_clause}
            LIMIT 1
            """,
            params,
        )
        return cursor.fetchone() is not None

    # ==================================================================
    # FLEET DASHBOARD
    # ==================================================================

    def get_fleet_dashboard(self) -> Dict[str, Any]:
        cursor = self.db.cursor()
        stats: Dict[str, Any] = {}

        cursor.execute("SELECT COUNT(*) FROM trains")
        stats["total_trains"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM coaches")
        stats["total_coaches"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM wheels")
        stats["total_wheels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM inspections")
        stats["total_inspections"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM inspection_events")
        stats["total_inspection_events"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM wheels WHERE inspection_count > 0")
        stats["inspected_wheels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM wheels WHERE inspection_count = 0 OR inspection_count IS NULL")
        stats["uninspected_wheels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM wheels WHERE status='Healthy'")
        stats["healthy_wheels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM wheels WHERE status='Monitor'")
        stats["monitor_wheels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM wheels WHERE status='Critical'")
        stats["critical_wheels"] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM maintenance_jobs
            WHERE job_status='PENDING'
        """)
        stats["pending_maintenance_jobs"] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM maintenance_jobs
            WHERE job_status='SCHEDULED'
        """)
        stats["scheduled_maintenance_jobs"] = cursor.fetchone()[0]

        # Train-wise health summary
        cursor.execute("""
            SELECT t.id, t.train_number, t.train_name, t.operational_status,
                   COUNT(w.asset_id) AS total_wheels,
                   SUM(CASE WHEN w.status='Healthy' THEN 1 ELSE 0 END) AS healthy,
                   SUM(CASE WHEN w.status='Monitor' THEN 1 ELSE 0 END) AS monitor,
                   SUM(CASE WHEN w.status='Critical' THEN 1 ELSE 0 END) AS critical
            FROM trains t
            LEFT JOIN coaches c ON c.train_id = t.id
            LEFT JOIN wheels w ON w.coach_id = CAST(c.id AS TEXT)
            GROUP BY t.id
            ORDER BY t.id
        """)
        stats["train_health_summaries"] = [dict(r) for r in cursor.fetchall()]

        # Critical wheels grouped by train
        cursor.execute("""
            SELECT t.train_number, t.train_name, w.asset_id, w.wheel_identifier,
                   w.status, w.latest_inspection, c.coach_number
            FROM wheels w
            LEFT JOIN coaches c ON c.id = CAST(w.coach_id AS INTEGER)
            LEFT JOIN trains t ON t.id = c.train_id
            WHERE w.status = 'Critical'
            ORDER BY t.id, w.asset_id
        """)
        stats["critical_wheels_by_train"] = [dict(r) for r in cursor.fetchall()]

        # Upcoming scheduled maintenance
        cursor.execute("""
            SELECT mj.id, mj.wheel_asset_id, mj.priority, mj.risk_score,
                   mj.recommended_action, mj.confirmed_start, mj.job_status,
                   t.train_number, t.train_name
            FROM maintenance_jobs mj
            LEFT JOIN trains t ON t.id = mj.train_id
            WHERE mj.job_status = 'SCHEDULED'
              AND mj.confirmed_start IS NOT NULL
            ORDER BY mj.confirmed_start
            LIMIT 20
        """)
        stats["upcoming_maintenance"] = [dict(r) for r in cursor.fetchall()]

        # Critical/urgent conflicts: high-risk jobs for active trains
        cursor.execute("""
            SELECT mj.id AS job_id, t.train_number, mj.wheel_asset_id,
                   mj.priority, mj.risk_score, mj.recommended_action,
                   mj.job_status
            FROM maintenance_jobs mj
            LEFT JOIN trains t ON t.id = mj.train_id
            WHERE mj.priority = 'CRITICAL'
              AND mj.job_status IN ('PENDING', 'SCHEDULED')
        """)
        stats["operating_schedule_conflicts"] = [dict(r) for r in cursor.fetchall()]

        return stats
