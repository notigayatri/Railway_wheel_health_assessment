from core.wheel_lifecycle.repository import WheelRepository


class HistoryManager:

    def __init__(self):
        self.repo = WheelRepository()

    def get_history(self, asset_id):
        return self.repo.get_history(asset_id)

    def get_defect_history(self, asset_id, defect_type):
        return self.repo.get_defect_history(asset_id, defect_type)

    def get_latest_inspection(self, asset_id):

        history = self.repo.get_history(asset_id)

        if len(history) == 0:
            return None

        return history[0]

    def get_total_inspections(self, asset_id):

        return len(self.repo.get_history(asset_id))

    def get_latest_status(self, asset_id):

        wheel = self.repo.get_wheel(asset_id)

        if wheel:
            return wheel["status"]

        return None