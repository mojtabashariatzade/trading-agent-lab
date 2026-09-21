"""Detect optional MAF Durable Task packages and DTS emulator reachability."""
import socket
import urllib.parse


def maf_packages_available() -> bool:
    try:
        import agent_framework_durabletask  # noqa: F401
        import durabletask  # noqa: F401

        return True
    except ImportError:
        return False


def dts_endpoint_reachable(endpoint: str, timeout_seconds: float = 1.5) -> bool:
    """Return True if the Durable Task Scheduler gRPC/HTTP host accepts TCP."""
    raw = (endpoint or "").strip()
    if not raw:
        return False
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlparse(raw)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False
