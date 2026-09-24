"""Offline resumable collector interfaces and checkpoint storage for T007.

This module intentionally performs no provider network calls and uses no credentials.
It only models collection windows and persists local checkpoint state so a reviewed
collector adapter can resume safely.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path


def _aware_utc(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _required_text(value: str, *, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


class CollectionState(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class CollectionWindow:
    start_utc: datetime
    end_utc: datetime

    def __post_init__(self) -> None:
        start = _aware_utc(self.start_utc, name="start_utc")
        end = _aware_utc(self.end_utc, name="end_utc")
        if end <= start:
            raise ValueError("end_utc must be after start_utc")
        object.__setattr__(self, "start_utc", start)
        object.__setattr__(self, "end_utc", end)


@dataclass(frozen=True)
class CollectorCheckpoint:
    provider_id: str
    instrument: str
    dataset_id: str
    requested_window: CollectionWindow
    next_start_utc: datetime
    state: CollectionState
    attempt_count: int = 0
    blocker_reason: str = ""
    updated_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        provider = _required_text(self.provider_id, name="provider_id")
        instrument = _required_text(self.instrument, name="instrument")
        dataset = _required_text(self.dataset_id, name="dataset_id")
        next_start = _aware_utc(self.next_start_utc, name="next_start_utc")
        updated_at = _aware_utc(self.updated_at_utc, name="updated_at_utc")

        if not isinstance(self.state, CollectionState):
            raise ValueError("state must be a CollectionState")
        if isinstance(self.attempt_count, bool) or self.attempt_count < 0:
            raise ValueError("attempt_count must be >= 0")

        window = self.requested_window
        if not (window.start_utc <= next_start <= window.end_utc):
            raise ValueError("next_start_utc must be inside requested_window")

        blocker_reason = str(self.blocker_reason).strip()
        if self.state == CollectionState.BLOCKED and not blocker_reason:
            raise ValueError("blocker_reason is required when state is BLOCKED")
        if self.state != CollectionState.BLOCKED:
            blocker_reason = ""

        object.__setattr__(self, "provider_id", provider)
        object.__setattr__(self, "instrument", instrument)
        object.__setattr__(self, "dataset_id", dataset)
        object.__setattr__(self, "next_start_utc", next_start)
        object.__setattr__(self, "updated_at_utc", updated_at)
        object.__setattr__(self, "blocker_reason", blocker_reason)

    @property
    def is_complete(self) -> bool:
        return self.state == CollectionState.COMPLETE

    @property
    def remaining(self) -> CollectionWindow | None:
        if self.is_complete or self.next_start_utc >= self.requested_window.end_utc:
            return None
        return CollectionWindow(start_utc=self.next_start_utc, end_utc=self.requested_window.end_utc)

    def mark_chunk_success(self, *, chunk_end_utc: datetime, update_time_utc: datetime) -> "CollectorCheckpoint":
        chunk_end = _aware_utc(chunk_end_utc, name="chunk_end_utc")
        updated = _aware_utc(update_time_utc, name="update_time_utc")
        if chunk_end < self.next_start_utc:
            raise ValueError("chunk_end_utc cannot move backward")
        if chunk_end > self.requested_window.end_utc:
            raise ValueError("chunk_end_utc cannot exceed requested_window.end_utc")

        terminal = chunk_end >= self.requested_window.end_utc
        return replace(
            self,
            next_start_utc=chunk_end,
            attempt_count=self.attempt_count + 1,
            state=CollectionState.COMPLETE if terminal else CollectionState.IN_PROGRESS,
            blocker_reason="",
            updated_at_utc=updated,
        )

    def mark_blocked(self, *, reason: str, update_time_utc: datetime) -> "CollectorCheckpoint":
        updated = _aware_utc(update_time_utc, name="update_time_utc")
        reason_text = _required_text(reason, name="reason")
        return replace(
            self,
            state=CollectionState.BLOCKED,
            blocker_reason=reason_text,
            attempt_count=self.attempt_count + 1,
            updated_at_utc=updated,
        )


class LocalCheckpointStore:
    """JSON-backed checkpoint storage for offline, resumable collection state."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _checkpoint_path(self, *, provider_id: str, instrument: str, dataset_id: str) -> Path:
        provider = provider_id.strip().lower().replace("/", "-")
        symbol = instrument.strip().upper().replace("/", "-")
        dataset = dataset_id.strip().lower().replace("/", "-")
        if not provider or not symbol or not dataset:
            raise ValueError("provider_id, instrument, and dataset_id are required")
        return self._root / f"{provider}__{symbol}__{dataset}.json"

    def save(self, checkpoint: CollectorCheckpoint) -> Path:
        path = self._checkpoint_path(
            provider_id=checkpoint.provider_id,
            instrument=checkpoint.instrument,
            dataset_id=checkpoint.dataset_id,
        )
        payload = {
            "provider_id": checkpoint.provider_id,
            "instrument": checkpoint.instrument,
            "dataset_id": checkpoint.dataset_id,
            "requested_window": {
                "start_utc": checkpoint.requested_window.start_utc.isoformat(),
                "end_utc": checkpoint.requested_window.end_utc.isoformat(),
            },
            "next_start_utc": checkpoint.next_start_utc.isoformat(),
            "state": checkpoint.state.value,
            "attempt_count": checkpoint.attempt_count,
            "blocker_reason": checkpoint.blocker_reason,
            "updated_at_utc": checkpoint.updated_at_utc.isoformat(),
        }
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
        return path

    def load(self, *, provider_id: str, instrument: str, dataset_id: str) -> CollectorCheckpoint | None:
        path = self._checkpoint_path(provider_id=provider_id, instrument=instrument, dataset_id=dataset_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CollectorCheckpoint(
            provider_id=payload["provider_id"],
            instrument=payload["instrument"],
            dataset_id=payload["dataset_id"],
            requested_window=CollectionWindow(
                start_utc=datetime.fromisoformat(payload["requested_window"]["start_utc"]),
                end_utc=datetime.fromisoformat(payload["requested_window"]["end_utc"]),
            ),
            next_start_utc=datetime.fromisoformat(payload["next_start_utc"]),
            state=CollectionState(payload["state"]),
            attempt_count=int(payload["attempt_count"]),
            blocker_reason=payload.get("blocker_reason", ""),
            updated_at_utc=datetime.fromisoformat(payload["updated_at_utc"]),
        )

    def begin_or_resume(
        self,
        *,
        provider_id: str,
        instrument: str,
        dataset_id: str,
        requested_window: CollectionWindow,
        now_utc: datetime,
    ) -> CollectorCheckpoint:
        existing = self.load(provider_id=provider_id, instrument=instrument, dataset_id=dataset_id)
        if existing is not None:
            return existing
        return CollectorCheckpoint(
            provider_id=provider_id,
            instrument=instrument,
            dataset_id=dataset_id,
            requested_window=requested_window,
            next_start_utc=requested_window.start_utc,
            state=CollectionState.PLANNED,
            attempt_count=0,
            updated_at_utc=now_utc,
        )
