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
        self.create_tables()
        self._migrate()

    def create_tables(self):
        cursor = self.connection.cursor()

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

        self.connection.commit()

    def _migrate(self):
        """
        Add any columns that exist in the new schema but are missing from
        an older on-disk database (safe no-op if columns already exist).
        """
        cursor = self.connection.cursor()
        existing = {
            row[1]
            for row in cursor.execute("PRAGMA table_info(inspections)")
        }
        new_columns = {
            "reliability":          "TEXT",
            "std_deviation":        "REAL",
            "risk_score":           "REAL",
            "recommended_action":   "TEXT",
            "annotated_image_path": "TEXT",
            "gradcam_image_path":   "TEXT",
        }
        for col, col_type in new_columns.items():
            if col not in existing:
                cursor.execute(
                    f"ALTER TABLE inspections ADD COLUMN {col} {col_type}"
                )
        self.connection.commit()

    def get_connection(self):
        return self.connection

    def close(self):
        self.connection.close()