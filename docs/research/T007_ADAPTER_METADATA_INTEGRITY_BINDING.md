# T007 adapter metadata integrity binding design (G06 / #40)

Status: DESIGN ONLY. This document defines the adapter contract for binding timestamp/coverage metadata to the exact parsed bytes. It does not introduce network acquisition, broker access, or Live capability.

## Goal

Prevent silent metadata drift by making every parsed record traceable to immutable source bytes and auditable provenance.

## 1) Canonical byte snapshot format (immutable payload capture)

Use a content-addressed immutable snapshot per imported payload.

Required snapshot artifacts for one import:

- raw snapshot bytes:
  - path: `research-data/immutable_payloads/sha256/<payload_sha256>.bin`
  - bytes: exact payload bytes as received by the adapter, unchanged
- envelope metadata:
  - path: `research-data/immutable_payloads/sha256/<payload_sha256>.json`
  - includes: dataset_id, provider_id, adapter_version, parser_version, captured_at_utc, payload_size_bytes, payload_sha256
- parse binding file:
  - path: `research-data/immutable_payloads/sha256/<payload_sha256>.records.jsonl`
  - one line per parsed record with:
    - `record_index`
    - `record_payload_sha256` (hash of canonical record bytes)
    - `source_byte_start` (inclusive offset in `.bin`)
    - `source_byte_end` (exclusive offset in `.bin`)
    - `parsed_timestamp_utc`

Canonical record bytes: for each parsed record, hash the exact byte slice from `.bin` at `[source_byte_start:source_byte_end]`. Do not hash normalized text fields.

This keeps one immutable root payload and exact offset bindings for each parsed record.

## 2) Digest/hash strategy and storage

Digest requirements:

- mandatory root digest: SHA-256 over full raw payload bytes (`payload_sha256`)
- mandatory per-record digest: SHA-256 over raw record byte slice (`record_payload_sha256`)
- optional acceleration digest: BLAKE3 (non-authoritative) may be added later, but SHA-256 remains the policy gate

Storage in contracts:

- keep existing `DataManifest.checksum_sha256` as full payload SHA-256
- keep `DataManifest.payload_snapshot_sha256` equal to full payload SHA-256 for backward compatibility
- add new manifest fields:
  - `payload_snapshot_path` (immutable `.bin` location)
  - `payload_records_path` (`.records.jsonl` location)
  - `records_root_sha256` (SHA-256 of concatenated ordered `record_payload_sha256` values with `\n` separators)

`records_root_sha256` enables fast verification that the record set/order still matches the payload-linked parse output.

## 3) Linkage model between parsed records and timestamp/coverage metadata

Use a two-level binding:

- payload-level binding: metadata set references `payload_sha256`
- record-level binding: each metadata record references `record_index` and `record_payload_sha256`

Coverage/timestamp metadata table (or structure) must include:

- `payload_sha256`
- `record_index`
- `record_payload_sha256`
- `timestamp_utc`
- `is_gap_boundary` / `gap_id` (if gap tracking applies)
- `availability_class` (real observation vs fixture)

Invariants:

- (`payload_sha256`, `record_index`) is unique
- `record_payload_sha256` must match the `.records.jsonl` row for that index
- timestamp sequence used for coverage metrics must be exactly the timestamp sequence derived from bound records

This removes any path where coverage/timestamp metadata can be replaced independently from parsed bytes.

## 4) Provenance fields preserved through transforms

Preserve these provenance fields from adapter ingest through downstream transforms and outputs:

- `source_provenance` (provider-specific lineage string)
- `legal_source` (license/permission ticket or policy reference)
- `provider_id`
- `provider_version`
- `adapter_version`
- `parser_version`
- `dataset_id`
- `captured_at_utc`
- `payload_sha256`
- `records_root_sha256`

Transform rules:

- derived artifacts must carry the full set above unchanged
- if a transform filters rows, keep original payload-level provenance and add transform metadata (`transform_id`, `parent_payload_sha256`, `parent_records_root_sha256`)
- never overwrite original provenance with derived provenance; append lineage

## 5) Failure modes and mandatory checks

Fail closed (no DOWNLOADED acceptance) on any mismatch.

Mandatory checks:

1. payload integrity check:
   - recompute SHA-256 of `.bin`; must equal `payload_sha256`
2. manifest consistency check:
   - `checksum_sha256 == payload_snapshot_sha256 == payload_sha256`
3. record binding check:
   - for every row in `.records.jsonl`, recompute hash of byte slice and compare to `record_payload_sha256`
4. metadata binding check:
   - every timestamp/coverage metadata row must resolve to an existing (`record_index`, `record_payload_sha256`) for same `payload_sha256`
5. ordered-root check:
   - recompute `records_root_sha256` from ordered rows and compare
6. monotonic timestamp check:
   - bound timestamps must be strictly increasing (existing rule)
7. coverage recomputation check:
   - recomputed gaps from bound timestamps must match stored gap metadata

On failure:

- mark sample `BLOCKED` (or reject `DOWNLOADED` report)
- emit explicit mismatch reason (`payload_hash_mismatch`, `record_hash_mismatch`, `metadata_orphan_record`, `gap_mismatch`, etc.)
- do not auto-repair or silently coerce metadata

## Short implementation plan for coding task

1. Extend `DataManifest` in `trading_lab/data/imports.py` with snapshot/binding path and `records_root_sha256` fields.
2. Add helper(s) to write immutable snapshot `.bin` and `.records.jsonl` under content-addressed path.
3. Extend `build_manifest(...)` to optionally accept parser bindings (record offsets + timestamps) and compute `records_root_sha256`.
4. Add `verify_manifest_bindings(...)` that performs payload, record, root, and metadata-link checks.
5. Update `DukascopySamplingAdapter.downloaded_report(...)` in `trading_lab/data/sampling.py` to require successful binding verification for REAL_OBSERVATION.
6. Add tests in `tests/added/` for:
   - happy path (all hashes and linkage valid)
   - payload mutation
   - record offset/hash mismatch
   - orphan metadata row
   - gap mismatch after metadata tampering

## Acceptance checklist for coding task

- [ ] Immutable payload `.bin` is stored under content-addressed SHA-256 path.
- [ ] Per-record binding file (`.records.jsonl`) exists with byte offsets and record digests.
- [ ] Manifest stores payload digest, snapshot path(s), and `records_root_sha256`.
- [ ] Timestamp/coverage metadata rows carry payload and record binding keys.
- [ ] Verification fails on any payload/record/metadata mismatch (no silent downgrade).
- [ ] `downloaded_report` cannot return DOWNLOADED unless binding verification passes.
- [ ] Unit tests cover all mismatch failure modes plus one valid path.
- [ ] Existing invariants (UTC-aware timestamps, increasing order, fixture/real separation, legal/source provenance) remain enforced.

## Safety

No claim of historical profitability, no provider entitlement claim, no credential use, no broker/live-trading change.