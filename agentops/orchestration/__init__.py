"""Orchestration backend protocol for Development Core (not Trading Decision Core)."""
from typing import Protocol


class OrchestrationBackend(Protocol):
    """Host-facing tick interface used by the supervisor loop."""

    name: str

    def tick(self) -> None:
        """Advance queue, workers, and self-heal for one poll cycle."""

    def flush(self) -> None:
        """Flush outbound notifications / provider buffers."""

    def handle(self, update: dict) -> None:
        """Handle an inbound Telegram (or equivalent) control update."""
