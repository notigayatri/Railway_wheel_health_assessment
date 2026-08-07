from core.wheel_lifecycle.history import HistoryManager

history = HistoryManager()

asset_id = "WH000001"

print("Latest Inspection")
print(history.get_latest_inspection(asset_id))

print()

print("History")
print(history.get_history(asset_id))

print()

print("Total")
print(history.get_total_inspections(asset_id))

print()

print("Status")
print(history.get_latest_status(asset_id))