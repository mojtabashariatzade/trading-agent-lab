# T101 Legacy scheduler smoke note (2026-09-24)

## Scope
This note records a **legacy** local-runtime smoke check for issue #10:
"Check that a local worker can run alongside another task."

This is not trading logic, does not use live data, and does not grant authority to re-enable deprecated LocalCursor production routing.

## What is verified
- Two `LocalCursor` runs can be created back-to-back.
- The runs execute independently (one Kian-style run, one Negar-style run).
- Both runs reach `FINISHED` with isolated per-run payloads.

## Constraints
- Test-only verification through a focused unit test.
- No changes under protected control-plane paths.
- No live trading, no external data access, no secrets handling.

## Evidence location
- Unit test: `tests/added/test_t101_local_worker_parallel_smoke.py`
- Suite command: `python -m unittest discover -s tests -v`
