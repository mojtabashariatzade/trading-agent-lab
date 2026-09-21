"""Durable worker entrypoint for MAF + Durable Task Extension path.

Process: python -m agentops.durable_worker

When the DTS emulator is reachable and packages are installed, this process
registers with Durable Task Scheduler. Otherwise it idles as a heartbeat
watcher over the local checkpoint engine (supervisor host still advances work).

Does not enable live trading or broker access. Does not stop the legacy queue.
"""
import logging
import os
import sys
import time
from pathlib import Path

from agentops.config import Settings
from agentops.orchestration.maf_durable.availability import (
    dts_endpoint_reachable,
    maf_packages_available,
)
from agentops.orchestration.maf_durable.dts_bridge import try_describe_dts


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )
    # Minimal env for Settings when used only as a probe worker.
    os.environ.setdefault("TELEGRAM_OPTIONAL", "true")
    os.environ.setdefault("AGENT_RUNTIME", "local")
    os.environ.setdefault("ORCHESTRATION_BACKEND", "maf_durable")
    try:
        cfg = Settings.from_env()
    except (KeyError, ValueError) as exc:
        logging.error("durable_worker settings unavailable: %s", exc)
        return 2

    info = try_describe_dts(cfg.dts_endpoint, cfg.dts_task_hub)
    logging.info(
        "Durable worker start runtime=%s packages=%s reachable=%s endpoint=%s",
        info.get("runtime"),
        info.get("packages_available"),
        info.get("reachable"),
        cfg.dts_endpoint,
    )

    if maf_packages_available() and dts_endpoint_reachable(cfg.dts_endpoint):
        logging.info(
            "DTS emulator reachable — host uses local_checkpoint activities until "
            "full DurableAIAgentWorker registration is wired for Dev Core tools. "
            "Dashboard typically http://localhost:8082"
        )
        # Future: register DurableAIAgentWorker activities that call TaskActivities.
        # For now keep a heartbeat so ensure scripts can detect the process.
    else:
        logging.info(
            "DTS not reachable; supervisor maf_durable backend uses local checkpoint "
            "engine under DURABLE_CHECKPOINT_DIR / AppData trading-agent-lab/durable"
        )

    heartbeat_path = Path(
        os.environ.get(
            "DURABLE_WORKER_HEARTBEAT",
            str(Path.home() / "AppData" / "Local" / "trading-agent-lab" / "status" / "durable_worker.heartbeat"),
        )
    )
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        heartbeat_path.write_text(str(time.time()), encoding="utf-8")
        time.sleep(max(10, min(cfg.poll_seconds, 60)))


if __name__ == "__main__":
    raise SystemExit(main())
