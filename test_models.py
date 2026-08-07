from core.wheel_lifecycle.models import Wheel, Inspection

# Create a wheel
wheel = Wheel(asset_id="WH000001")

print("Wheel Object:")
print(wheel)

print("\n" + "=" * 50 + "\n")

# Create an inspection
inspection = Inspection(
    inspection_id="INS000001",
    asset_id="WH000001",
    image_name="wheel1.jpg",
    image_path="images/wheel1.jpg"
)

print("Inspection Object:")
print(inspection)