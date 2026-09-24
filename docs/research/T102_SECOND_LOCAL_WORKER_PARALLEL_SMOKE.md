# T102 Legacy Smoke: second local worker parallel execution

## Scope
Legacy scheduler smoke check for issue #11 (`[team:T102]`).

This note documents a bounded local-runtime behavior test only:
- no trading logic changes,
- no live trading,
- no market-data download,
- no control-plane policy changes.

## What is being checked
`agentops.local_runtime.LocalCursor.create(...)` starts each worker via a background thread.
The legacy question for T102 is whether launching a second local worker can overlap with the first one instead of waiting for strict serial completion.

## Evidence path
Deterministic unit test:
- `tests/added/test_t102_local_worker_parallel.py`

The test monkeypatches the local worker body with a bounded sleep and tracks concurrent in-flight worker count. PASS requires observed overlap (`max_running >= 2`) and successful completion for both runs.

## Limitations
- This is a local runtime smoke behavior check, not proof of production throughput.
- It does not validate cloud worker behavior.
- It does not authorize enabling deterministic local workers in normal operation.
