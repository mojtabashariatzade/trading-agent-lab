# MAF + Durable Task Extension — spike report

**Date:** 2026-09-21  
**Default runtime:** `ORCHESTRATION_BACKEND=maf_durable` (owner cutover 2026-09-21)  
**Live queue:** cut over; rollback via `ORCHESTRATION_BACKEND=legacy`

## What shipped

- Feature flag `ORCHESTRATION_BACKEND=legacy|maf_durable` ([agentops/config.py](../agentops/config.py))
- Thin supervisor host selecting backends ([agentops/orchestration/](../agentops/orchestration/))
- Checkpointed task lifecycle activities wrapping existing Controller / LocalCursor / policy / self-heal (no trading or role rewrite)
- Optional DTS emulator scripts ([scripts/ensure-dts-emulator.ps1](../scripts/ensure-dts-emulator.ps1))
- Durable worker entrypoint ([agentops/durable_worker.py](../agentops/durable_worker.py))
- Dependency review note + optional requirements ([docs/DEPENDENCY_REQUEST_MAF_DURABLE.md](DEPENDENCY_REQUEST_MAF_DURABLE.md), [requirements-maf-durable.txt](../requirements-maf-durable.txt))

## Proof results

| Criterion | Result |
|-----------|--------|
| Full unittest suite | **170 OK** (`python -m unittest discover -s tests -v`) |
| Crash resume without re-running completed launch | **PASS** (isolated proof + unit tests) |
| Parallel T101/T102 distinct `run_id` + `durable_instance_id` | **PASS** (isolated proof) |
| Reconcile existing PR → CI without relaunch Kian | **PASS** |
| Legacy supervisor kept running | **PASS** (`pid=42744` during proof) |
| No fake RUNNING without durable id (maf path) | **PASS** (unit tests) |
| Default remains legacy | **PASS** |

Evidence file: `%LOCALAPPDATA%\trading-agent-lab\durable-proof\latest_proof.json`

## DTS emulator on this PC

- `agent-framework-durabletask` **imports successfully**
- **Docker is not installed** → DTS emulator (`localhost:8080`) **not reachable**
- Runtime label used: `local_checkpoint_maf_packages_present`
- Local checkpoint engine provides self-hosted durable resume/concurrency without Azure

This is **not** treated as a Temporal trigger yet: acceptance criteria for durability, parallelism, HITL-style waiting, and self-host without Azure are met by the local checkpoint engine that mirrors Durable Task activity semantics. When Docker Desktop is available, run `scripts/ensure-dts-emulator.ps1` to attach the live DTS bridge path.

## Cutover gate (do not switch yet until owner confirms)

Flip default to `maf_durable` only after:

1. Suite green (done)
2. Durable resume + parallel proofs green (done for local_checkpoint)
3. Optional: DTS emulator proof on this PC once Docker is installed
4. Explicit owner approval to change default / live supervisor env

Until then keep `ORCHESTRATION_BACKEND=legacy` on the live host.

## Temporal fallback

**Not activated.** Revisit only if Docker+DTS and local_checkpoint both fail a documented acceptance criterion after an honest attempt.
