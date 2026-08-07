from core.wheel_lifecycle.models import Wheel, Inspection
from core.wheel_lifecycle.id_generator import (
    generate_asset_id,
    generate_inspection_id,
)
from core.wheel_lifecycle.repository import WheelRepository

repo = WheelRepository()

asset_id = generate_asset_id()

wheel = Wheel(
    asset_id=asset_id,
    train_id="TR101",
    coach_id="C01",
    axle_number=1,
    position="Left",
)

repo.create_wheel(wheel)

inspection = Inspection(
    inspection_id=generate_inspection_id(),
    asset_id=asset_id,
    image_name="wheel1.jpg",
    image_path="images/wheel1.jpg",
    defect_type="Shelling",
    severity="Moderate",
    confidence=0.94,
    processing_time=0.32,
    notes="Initial inspection"
)

repo.create_inspection(inspection)

repo.update_wheel_status(
    asset_id,
    "Monitor",
    inspection.inspection_id
)

print("\nWheels")
print(repo.list_all_wheels())

print("\nHistory")
print(repo.get_history(asset_id))

print("\nDashboard")
print(repo.get_dashboard_stats())