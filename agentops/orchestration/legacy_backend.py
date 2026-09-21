"""Legacy orchestration — existing Controller + MaintenanceLoop (unchanged behavior)."""


class LegacyBackend:
    """Default backend: poll Controller.tick and MaintenanceLoop.tick."""

    name = "legacy"

    def __init__(self, controller, healer):
        self.controller = controller
        self.healer = healer
        self.last_heal_reports: list[dict] = []

    def tick(self) -> None:
        self.last_heal_reports = self.healer.tick() or []
        self.controller.tick()

    def flush(self) -> None:
        self.controller.flush()

    def handle(self, update: dict) -> None:
        self.controller.handle(update)
