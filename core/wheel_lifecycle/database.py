import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_DIR.mkdir(exist_ok=True)   # Creates the folder if missing

DB_PATH = DATABASE_DIR / "railway.db"


class DatabaseManager:
    def __init__(self):
        self.connection = sqlite3.connect(DB_PATH)
        self.connection.row_factory = sqlite3.Row
        self.create_tables()

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
            FOREIGN KEY(asset_id) REFERENCES wheels(asset_id)
        )
        """)

        self.connection.commit()

    def get_connection(self):
        return self.connection

    def close(self):
        self.connection.close()