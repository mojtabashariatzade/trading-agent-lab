"""Utilities for GitHub issue #27 Telegram↔ChatGPT bridge mailbox markers."""
from __future__ import annotations

from dataclasses import dataclass
import re

_MARKER_RE = re.compile(
    r"<!--\s*chatgpt-bridge:(?P<direction>inbound|outbound)\s+"
    r"(?P<field>[a-z_]+)=(?P<value>[^\s>]+)\s*-->"
)


@dataclass(frozen=True)
class BridgeMarker:
    """Parsed mailbox marker metadata."""

    direction: str
    reference: str


def parse_bridge_marker(text: str) -> BridgeMarker | None:
    """Return a parsed bridge marker or None when the marker is absent/invalid."""
    match = _MARKER_RE.search(text)
    if not match:
        return None

    direction = match.group("direction")
    field = match.group("field")
    value = match.group("value")
    expected = "update_id" if direction == "inbound" else "reply_to"

    if field != expected or not value.strip():
        return None

    return BridgeMarker(direction=direction, reference=value)


def format_inbound_marker(update_id: str) -> str:
    """Build the canonical inbound marker for issue #27 comments."""
    update_id = update_id.strip()
    if not update_id:
        raise ValueError("update_id cannot be blank")
    return f"<!-- chatgpt-bridge:inbound update_id={update_id} -->"


def format_outbound_marker(reply_to: str) -> str:
    """Build the canonical outbound marker for issue #27 comments."""
    reply_to = reply_to.strip()
    if not reply_to:
        raise ValueError("reply_to cannot be blank")
    return f"<!-- chatgpt-bridge:outbound reply_to={reply_to} -->"
