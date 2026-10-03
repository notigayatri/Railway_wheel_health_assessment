
from core.wheel_lifecycle.database import DatabaseManager
from core.wheel_lifecycle.models import Wheel, Inspection


class WheelRepository:

    def __init__(self):
        self.db = DatabaseManager().get_connection()

    # =====================================================
    # WHEEL OPERATIONS
    # =====================================================

    def create_wheel(self, wheel: Wheel):

        cursor = self.db.cursor()

        cursor.execute("""
        INSERT OR IGNORE INTO wheels
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            wheel.asset_id,
            wheel.wheel_identifier,
            wheel.train_id,
            wheel.coach_id,
            wheel.axle_number,
            wheel.position,
            wheel.status,
            wheel.inspection_count,
            wheel.latest_inspection,
            str(wheel.created_at),
            str(wheel.last_updated)
        ))

        self.db.commit()

    def get_wheel(self, asset_id: str):

        cursor = self.db.cursor()

        cursor.execute(
            "SELECT * FROM wheels WHERE asset_id=?",
            (asset_id,)
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    def list_all_wheels(self):

        cursor = self.db.cursor()

        cursor.execute("SELECT * FROM wheels")

        return [dict(row) for row in cursor.fetchall()]

    def update_wheel_status(
        self,
        asset_id: str,
        status: str,
        latest_inspection: str
    ):

        cursor = self.db.cursor()

        cursor.execute("""
        UPDATE wheels
        SET
            status=?,
            latest_inspection=?,
            inspection_count=inspection_count+1,
            last_updated=datetime('now')
        WHERE asset_id=?
        """, (
            status,
            latest_inspection,
            asset_id
        ))

        self.db.commit()

    def delete_wheel(self, asset_id):

        cursor = self.db.cursor()

        cursor.execute(
            "DELETE FROM wheels WHERE asset_id=?",
            (asset_id,)
        )

        self.db.commit()

    # =====================================================
    # INSPECTION OPERATIONS
    # =====================================================

    def create_inspection(self, inspection: Inspection,
                          reliability: str = None,
                          std_deviation: float = None,
                          risk_score: float = None,
                          recommended_action: str = None,
                          annotated_image_path: str = None,
                          gradcam_image_path: str = None):

        cursor = self.db.cursor()

        cursor.execute("""
        INSERT OR IGNORE INTO inspections (
            inspection_id, asset_id, image_name, image_path,
            inspection_date, defect_type, severity, confidence,
            processing_time, notes,
            reliability, std_deviation, risk_score,
            recommended_action, annotated_image_path, gradcam_image_path
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            inspection.inspection_id,
            inspection.asset_id,
            inspection.image_name,
            inspection.image_path,
            str(inspection.inspection_date),
            inspection.defect_type,
            inspection.severity,
            inspection.confidence,
            inspection.processing_time,
            inspection.notes,
            reliability,
            std_deviation,
            risk_score,
            recommended_action,
            annotated_image_path,
            gradcam_image_path,
        ))

        self.db.commit()

    def get_inspection(self, inspection_id):

        cursor = self.db.cursor()

        cursor.execute(
            "SELECT * FROM inspections WHERE inspection_id=?",
            (inspection_id,)
        )

        row = cursor.fetchone()

        if row:
            return dict(row)

        return None

    def get_history(self, asset_id):

        cursor = self.db.cursor()

        cursor.execute("""
        SELECT *
        FROM inspections
        WHERE asset_id=?
        ORDER BY inspection_date DESC
        """, (asset_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_defect_history(self, asset_id: str, defect_type: str):

        cursor = self.db.cursor()

        cursor.execute("""
        SELECT *
        FROM inspections
        WHERE asset_id=? AND defect_type=?
        ORDER BY inspection_date DESC
        """, (asset_id, defect_type))

        return [dict(row) for row in cursor.fetchall()]

    def list_all_inspections(self):

        cursor = self.db.cursor()

        cursor.execute("SELECT * FROM inspections")

        return [dict(row) for row in cursor.fetchall()]

    def delete_inspection(self, inspection_id):

        cursor = self.db.cursor()

        cursor.execute(
            "DELETE FROM inspections WHERE inspection_id=?",
            (inspection_id,)
        )

        self.db.commit()

    # =====================================================
    # DASHBOARD
    # =====================================================

    def get_dashboard_stats(self):

        cursor = self.db.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) FROM wheels")
        stats["total_wheels"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM inspections")
        stats["total_inspections"] = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM wheels
        WHERE status='Healthy'
        """)
        stats["healthy"] = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM wheels
        WHERE status='Monitor'
        """)
        stats["monitor"] = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM wheels
        WHERE status='Critical'
        """)
        stats["critical"] = cursor.fetchone()[0]

        # Severity distribution across all inspections
        cursor.execute("""
        SELECT severity, COUNT(*) as count
        FROM inspections
        WHERE severity IS NOT NULL
        GROUP BY severity
        """)
        stats["severity_distribution"] = {
            row["severity"]: row["count"]
            for row in cursor.fetchall()
        }

        # Defect type distribution
        cursor.execute("""
        SELECT defect_type, COUNT(*) as count
        FROM inspections
        WHERE defect_type IS NOT NULL
        GROUP BY defect_type
        """)
        stats["defect_distribution"] = {
            row["defect_type"]: row["count"]
            for row in cursor.fetchall()
        }

        # Recent inspections (last 10)
        cursor.execute("""
        SELECT inspection_id, asset_id, image_name, inspection_date,
               defect_type, severity, risk_score, recommended_action
        FROM inspections
        ORDER BY inspection_date DESC
        LIMIT 10
        """)
        stats["recent_inspections"] = [
            dict(row) for row in cursor.fetchall()
        ]

        return stats