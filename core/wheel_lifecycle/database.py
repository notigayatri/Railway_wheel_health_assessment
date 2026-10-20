import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_DIR.mkdir(exist_ok=True)   # Creates the folder if missing

DB_PATH = DATABASE_DIR / "railway.db"


class DatabaseManager:
    def __init__(self):
        self.connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self._migrate()

    def create_tables(self):
        cursor = self.connection.cursor()

        # ── Original tables (unchanged) ────────────────────────────────────

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS wheels (
            asset_id TEXT PRIMARY KEY,
            wheel_identifier TEXT,
            train_id TEXT,
            coach_id TEXT,
            axle_number INTEGER,
            position TEXT,
            status TEXT,
            inspection_count INTEGER,
            latest_inspection TEXT,
            created_at TEXT,
            last_updated TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            inspection_id TEXT PRIMARY KEY,
            asset_id TEXT,
            image_name TEXT,
            image_path TEXT,
            inspection_date TEXT,
            defect_type TEXT,
            severity TEXT,
            confidence REAL,
            processing_time REAL,
            notes TEXT,
            reliability TEXT,
            std_deviation REAL,
            risk_score REAL,
            recommended_action TEXT,
            annotated_image_path TEXT,
            gradcam_image_path TEXT,
            FOREIGN KEY(asset_id) REFERENCES wheels(asset_id)
        )
        """)

        # ── New tables ─────────────────────────────────────────────────────

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_number TEXT UNIQUE NOT NULL,
            train_name TEXT NOT NULL,
            train_type TEXT,
            operational_status TEXT NOT NULL DEFAULT 'Active',
            registration_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_number TEXT NOT NULL,
            coach_type TEXT,
            train_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            FOREIGN KEY(train_id) REFERENCES trains(id),
            UNIQUE(coach_number, train_id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS operating_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_id INTEGER NOT NULL,
            schedule_type TEXT NOT NULL DEFAULT 'OPERATING',
            departure_datetime TEXT,
            arrival_datetime TEXT,
            operating_date TEXT,
            depot_location TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            FOREIGN KEY(train_id) REFERENCES trains(id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS inspection_events (
            event_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            train_id INTEGER,
            coach_id INTEGER,
            image_name TEXT,
            image_path TEXT,
            inspection_date TEXT NOT NULL,
            wheel_risk_score REAL,
            wheel_recommended_action TEXT,
            trend_status TEXT,
            total_defects INTEGER DEFAULT 0,
            annotated_image_path TEXT,
            gradcam_image_path TEXT,
            processing_time REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(asset_id) REFERENCES wheels(asset_id),
            FOREIGN KEY(train_id) REFERENCES trains(id),
            FOREIGN KEY(coach_id) REFERENCES coaches(id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_id INTEGER,
            coach_id INTEGER,
            wheel_asset_id TEXT NOT NULL,
            inspection_event_id TEXT,
            risk_score REAL,
            priority TEXT NOT NULL DEFAULT 'NORMAL',
            recommended_action TEXT,
            suggested_start TEXT,
            suggested_end TEXT,
            confirmed_start TEXT,
            job_status TEXT NOT NULL DEFAULT 'PENDING',
            completion_notes TEXT,
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            FOREIGN KEY(train_id) REFERENCES trains(id),
            FOREIGN KEY(coach_id) REFERENCES coaches(id),
            FOREIGN KEY(wheel_asset_id) REFERENCES wheels(asset_id),
            FOREIGN KEY(inspection_event_id) REFERENCES inspection_events(event_id)
        )
        """)

        self.connection.commit()

    def _migrate(self):
        """
        Add any columns that exist in the new schema but are missing from
        an older on-disk database (safe no-op if columns already exist).
        """
        cursor = self.connection.cursor()

        # ── inspections table ─────────────────────────────────────────────
        existing_insp = {
            row[1]
            for row in cursor.execute("PRAGMA table_info(inspections)")
        }
        new_insp_columns = {
            "reliability":          "TEXT",
            "std_deviation":        "REAL",
            "risk_score":           "REAL",
            "recommended_action":   "TEXT",
            "annotated_image_path": "TEXT",
            "gradcam_image_path":   "TEXT",
            "inspection_event_id":  "TEXT",
        }
        for col, col_type in new_insp_columns.items():
            if col not in existing_insp:
                cursor.execute(
                    f"ALTER TABLE inspections ADD COLUMN {col} {col_type}"
                )

        # ── wheels table ──────────────────────────────────────────────────
        existing_wh = {
            row[1]
            for row in cursor.execute("PRAGMA table_info(wheels)")
        }
        new_wh_columns = {
            "wheel_identifier": "TEXT",
            "train_id":         "TEXT",
            "coach_id":         "TEXT",
            "axle_number":      "INTEGER",
            "position":         "TEXT",
        }
        for col, col_type in new_wh_columns.items():
            if col not in existing_wh:
                cursor.execute(
                    f"ALTER TABLE wheels ADD COLUMN {col} {col_type}"
                )

        self.connection.commit()

    def get_connection(self):
        return self.connection

    def close(self):
        self.connection.close()