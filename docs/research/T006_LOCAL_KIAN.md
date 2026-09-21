# T006 — historical-data sampling readiness

This delivery is a local-only import contract. It has no downloader, broker,
credential, paid-data, or live-trading capability.

## Contract

- Every imported artifact records the exact provider and provider version,
  observed half-open UTC coverage, explicit gaps, record/byte counts, and SHA-256.
- `fixtures/` is reserved for synthetic unit-test inputs.
- `real-observations/` is reserved for actual supplied provider observations.
- A path cannot be manifested under the wrong storage class.
- Verification re-hashes the local artifact and fails after content or path changes.
- Sampling reports use one explicit state: `downloaded` or `unverified`.
  A downloaded claim requires a matching manifest plus a recorded UTC terms check
  that explicitly allowed the automated sample.
- Original macro releases and revisions stay separate. If the original release is
  missing, the importer raises instead of substituting a later revised value.

## Dukascopy sampling adapter boundary

The future adapter may translate a user-supplied or separately authorized sample
into the local contract above. Before acquisition it must record the exact provider
format/version and a current provider-terms decision. It must write only below
`real-observations/`, preserve bid/ask and source timestamps, record actual—not
requested—coverage, and enumerate gaps. It must then create and verify the SHA-256
manifest before any downstream use.

This PR does not implement HTTP, browser automation, scraping, retries, or bulk
history acquisition. It does not claim that Dukascopy terms permit automation.

## Sampling report

| Field | Value |
|---|---|
| Provider | Dukascopy |
| Provider version | `documented-format-v1` (adapter contract only) |
| State | `unverified` |
| Downloaded | No |
| Actual coverage | None |
| Checksum | None |
| Gaps | Not measurable without an authorized sample |
| Limitation | Provider permission/terms approval has not been recorded |

Unit tests use temporary synthetic files only. They do not represent historical
GBPJPY observations and cannot populate a performance report or leaderboard.
