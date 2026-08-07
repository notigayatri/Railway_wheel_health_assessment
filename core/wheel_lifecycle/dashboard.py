from core.wheel_lifecycle.repository import WheelRepository


class Dashboard:

    def __init__(self):
        self.repo = WheelRepository()

    def summary(self):
        return self.repo.get_dashboard_stats()