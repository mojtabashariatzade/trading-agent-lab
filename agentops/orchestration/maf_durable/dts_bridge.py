"""Optional bridge to Microsoft Durable Task Scheduler when emulator is reachable."""
import logging

from agentops.orchestration.maf_durable.availability import (
    dts_endpoint_reachable,
    maf_packages_available,
)

log = logging.getLogger(__name__)


def select_durable_runtime_label(endpoint: str) -> str:
    """Report which durable backend is active for status/config."""
    packages = maf_packages_available()
    reachable = dts_endpoint_reachable(endpoint)
    if packages and reachable:
        return "dts_emulator"
    if packages and not reachable:
        return "local_checkpoint_maf_packages_present"
    return "local_checkpoint"


def try_describe_dts(endpoint: str, task_hub: str) -> dict:
    """Best-effort DTS probe — never raises into the supervisor loop."""
    info = {
        "packages_available": maf_packages_available(),
        "endpoint": endpoint,
        "task_hub": task_hub,
        "reachable": dts_endpoint_reachable(endpoint),
        "runtime": select_durable_runtime_label(endpoint),
    }
    return info
