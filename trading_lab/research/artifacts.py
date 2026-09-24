"""Auditable local research artifact writer for tournament runs."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any

from trading_lab.tournament.core import REQUIRED_INTEGRITY_GATES, TournamentRun


def _encode(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_encode(item) for item in value]
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    return value


def run_artifact(run: TournamentRun) -> dict:
    """Return a complete JSON-safe audit artifact."""
    payload = _encode(run)
    payload["schema"] = "trading-agent-lab.tournament-run.v1"
    payload["leaderboard_eligible"] = run.leaderboard_eligible
    payload["integrity_required_gates"] = list(REQUIRED_INTEGRITY_GATES)
    payload["integrity_completed_gates"] = list(run.integrity_gates_completed)
    payload["integrity_missing_gates"] = list(run.integrity_missing_gates)
    payload["ranking_blockers"] = list(run.ranking_blockers())
    payload["synthetic_warning"] = (
        "SYNTHETIC_TEST_ONLY: fixture results are not real historical performance "
        "and cannot populate a real-performance leaderboard."
    )
    return payload


def write_run_artifact(run: TournamentRun, path: str | Path) -> Path:
    """Atomically save proposals, decisions, trades, config and run manifest."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(run_artifact(run), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
