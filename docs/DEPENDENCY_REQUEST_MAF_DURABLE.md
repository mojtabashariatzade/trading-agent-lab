# Dependency review request — MAF Durable Task Extension

**Status:** Owner-approved via migration plan (2026-09-21). Packages are optional until `ORCHESTRATION_BACKEND=maf_durable` is used with a live DTS endpoint.

## Requested packages (optional extra)

| Package | Purpose |
|---------|---------|
| `agent-framework-durabletask` | MAF Durable Task Extension worker/client |
| `agent-framework-core` | transitive |
| `durabletask` | Durable Task Python SDK |
| `durabletask-azuremanaged` | DTS worker/client bindings |

Install only when exercising the DTS bridge:

```text
pip install -r requirements-maf-durable.txt
```

## Local proof without Docker

This PC may not have Docker. The migration ships a **local checkpoint durable engine** (`agentops.orchestration.maf_durable.engine`) that implements the same task-lifecycle orchestration, activity checkpointing, crash resume, and parallel instances. The DTS bridge activates when:

1. Optional packages import successfully, and
2. `DTS_ENDPOINT` (default `http://localhost:8080`) is reachable (DTS emulator via `scripts/ensure-dts-emulator.ps1`).

Default runtime remains `ORCHESTRATION_BACKEND=legacy` until parity gates pass.

## Temporal

Not requested. Revisit only if the spike documents a failed acceptance criterion that Durable Task Extension / local durable engine cannot meet.
