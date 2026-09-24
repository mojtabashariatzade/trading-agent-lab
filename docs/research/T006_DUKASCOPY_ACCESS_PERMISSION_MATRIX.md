# T006 — Dukascopy access-permission matrix for Issue #58 (unblocks #37/#22)

Date (UTC): 2026-09-24
Owner lane: Kian (integration handoff for Saman)
Related tracker items: #58, #37, #22, #57

## Route matrix (zero-cost first, fail-closed)

| Route | Source link(s) | Auth required | Cost / billing risk | Automation constraints observed | Storage / redistribution constraint status | Verdict |
|---|---|---:|---|---|---|---|
| Direct historical endpoint (`datafeed.dukascopy.com`) for GBPJPY hourly tick file | Attempted URL: `https://datafeed.dukascopy.com/datafeed/GBPJPY/2024/00/02/00h_ticks.bi5` | No credential requested in this request | Zero direct payment in request itself, but access is currently blocked by provider throttling | Returned HTTP `429 Too Many Requests` with provider instruction to use data-export docs | No explicit license terms returned by this endpoint response; redistribution/storage permission unresolved in this task | **BLOCKED** for unattended import use until provider-approved access pattern is confirmed |
| Dukascopy wiki data-export path | `https://www.dukascopy.com/wiki/en/development/data-export/` | Not validated for authenticated flows in this task | Wiki page metadata states `Public S3 Bucket with Requester Pays Policy` (can imply non-zero requester billing) | Indicates provider-specific export workflow outside current direct endpoint call | Terms/license details not adjudicated in this task; requires owner-approved interpretation before bulk/history ingestion | **BLOCKED (policy gate)** pending owner decision on whether requester-pays path is permitted |

## Key evidence anchors

- Direct endpoint response body explicitly states:
  - `{"error": "Too Many Requests. For instructions, see: https://www.dukascopy.com/wiki/en/development/data-export/"}`
- Wiki page metadata includes:
  - `Accessing Historical Price Data from Public S3 Bucket with Requester Pays Policy`

## Decision for #37 / #22 handoff

Current decision: **BLOCKED**.

Blocking dependency:
1. Provider access path is throttled for unattended direct pulls (HTTP 429).
2. The documented alternate path references requester-pays billing semantics that require explicit owner approval under project non-negotiable boundaries.
3. Redistribution/storage permissions remain unresolved from retrieved artifacts alone.

Explicit unblock condition:
- Owner confirms one authorized route (either approved requester-pays usage with spend boundary, or approved non-billed alternative source), and confirms permissible storage/redistribution scope for project artifacts.
