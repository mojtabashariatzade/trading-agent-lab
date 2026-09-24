# T006 — Dukascopy authorized sample evidence (bounded retrieval)

Date (UTC): 2026-09-24
Related: #58, #37, #22

## Scope and safety

- No full-history download attempted.
- Single bounded request attempted for one hourly GBPJPY tick object.
- No credentials used.
- No paid service activated.

## Requested sample window

- Instrument: GBPJPY
- Path requested: `datafeed/GBPJPY/2024/00/02/00h_ticks.bi5`
- Intended window: 2024-01-02 00:00 UTC hour (provider path semantics)

## Retrieved artifacts (immutable)

Committed evidence snapshots:

1. `docs/research/evidence/issue58/dukascopy_ticks_headers.txt`
   - Bytes: 82
   - SHA256: `fdcabf142f3d03f58c51c8a828b83ecdf9700e07a29ad5ebe6e6debbf38617ef`
   - Content summary: HTTP status/headers from provider response (`429 Too Many Requests`)
2. `docs/research/evidence/issue58/dukascopy_ticks_response.json`
   - Bytes: 114
   - SHA256: `7abc56790131ae53a95e37c55a86d1fdee25c88e979bb3c970a398a4bd7e39ee`
   - Content summary: JSON error payload (`Too Many Requests`, points to wiki data-export page)
3. `docs/research/evidence/issue58/dukascopy_wiki_meta_excerpt.txt`
   - Bytes: 237
   - SHA256: `4eaab1fa0f620ebf10ecf5c595d19b1e61b70878584ec4c342645798c9998101`
   - Content summary: title/meta excerpt from Dukascopy data-export wiki page including `Public S3 Bucket` and `Requester Pays Policy`

Local non-committed retrieval artifact used for hashing and inspection in this run:

- `artifacts/issue58/dukascopy_wiki_data_export.html`
  - Bytes: 257370
  - SHA256: `b3bfdb34b613c76a16be0945fc628ff9cd9d066bede09032b2ac4d493bcf92ed`

## Coverage and gap statement

- Observed direct market-data coverage from this bounded attempt: **none** (request was rate-limited).
- Gap type: provider throttling / access policy gate (`HTTP 429 Too Many Requests`).
- Resulting status for import-validation handoff (#22): **BLOCKED** pending authorized route decision.

## Repro commands used

```bash
curl -L --max-time 45 -D artifacts/issue58/dukascopy_ticks_headers.txt \
  'https://datafeed.dukascopy.com/datafeed/GBPJPY/2024/00/02/00h_ticks.bi5' \
  -o artifacts/issue58/dukascopy_ticks_response.json

curl -L --max-time 45 \
  'https://www.dukascopy.com/wiki/en/development/data-export/' \
  -o artifacts/issue58/dukascopy_wiki_data_export.html

wc -c artifacts/issue58/dukascopy_ticks_response.json \
     artifacts/issue58/dukascopy_ticks_headers.txt \
     artifacts/issue58/dukascopy_wiki_data_export.html

sha256sum artifacts/issue58/dukascopy_ticks_response.json \
          artifacts/issue58/dukascopy_ticks_headers.txt \
          artifacts/issue58/dukascopy_wiki_data_export.html
```
