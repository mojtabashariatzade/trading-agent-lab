# T006 historical-data sampling readiness

Status: READY FOR AUTHORIZED LOCAL SAMPLE IMPORT. No provider sample was downloaded by this task.

## Local import contract

Every local payload that is claimed as downloaded/observed data must have a manifest containing:

- dataset id,
- exact provider id,
- provider/adapter version,
- TEST_FIXTURE or REAL_OBSERVATION class,
- SHA-256 checksum and payload byte size,
- actual first and last observation timestamps,
- record count,
- expected interval,
- explicit detected gaps.

verify_manifest re-hashes the payload so later mutation invalidates the evidence.

## Storage separation

StorageLayout writes TEST_FIXTURE and REAL_OBSERVATION to different roots:

- fixtures/
- real_observations/

Path traversal is rejected. A provider sample cannot be promoted through the Dukascopy sampling contract if its manifest says TEST_FIXTURE.

## Dukascopy adapter readiness

Provider id: dukascopy
Adapter version: readiness-1
Instrument target: GBPJPY
Network implementation: disabled
Current terms/permissions status in this repository: UNVERIFIED
Historical coverage status: UNVERIFIED
Sample downloaded by T006: NO

The adapter is metadata-only. It can create a bounded sample plan, but it does not perform HTTP/network acquisition. A downloaded report can only be created for bytes produced by an external authorized collector after terms_status is explicitly VERIFIED_ALLOWED and a REAL_OBSERVATION manifest exists.

This document intentionally makes no claim about current Dukascopy terms, entitlement, URL stability, archive depth or legal permission. Those items must be checked at sampling time before any network acquisition.

## Sampling report semantics

UNVERIFIED means no sample is claimed and provider permission/coverage is not established.
BLOCKED means a reviewed provider rule prevents sampling.
DOWNLOADED requires verified-allowed terms plus a checksum manifest for bytes actually present locally.

A missing sample never receives fabricated coverage.

## Macro originality guard

T005 keeps first_actual and revision separately. T006 original_macro_value reads only first_actual. If first_actual is missing, the result stays missing even when a revision exists. Revised values are never substituted for the original release.

## Safety

No full-history download, paid-data credential, broker integration or Live trading capability is added in T006.
