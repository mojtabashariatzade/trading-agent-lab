# T005 point-in-time fundamentals and source register

T005 defines causal data contracts only. It does not claim that any provider has usable historical coverage yet and it does not require credentials or a purchase.

## Release record

Each economic release/version keeps these fields separate:

- scheduled_at: when the event was scheduled.
- published_at: provider/official publication time when known.
- observed_at: when the collector actually observed the release.
- available_at: earliest time the research pipeline is allowed to use it.
- event_period: the economic period the value describes.
- first_actual: first published actual value.
- pre_release_forecast: forecast known before release; missing remains null.
- previous_as_known: prior-period value as known before this release.
- revision: later revised value, separate from first_actual.

Records are immutable. Revisions are represented as later versions with their own observed_at/available_at and revision_seq. An as-of query cannot see a revision before that revision became available.

## Intraday timestamp precision

Same-day intraday use rejects DAY and UNKNOWN precision on scheduled, published, observed or available timestamps. A day-level timestamp from a prior day may be usable on a later day because its causal order is no longer ambiguous at intraday resolution.

## Source register

Every required source starts with history, licensing and coverage status UNVERIFIED until sampling/validation is completed.

| Source id | Name | Class | Initial status |
| --- | --- | --- | --- |
| forex_factory | Forex Factory | Secondary calendar | UNVERIFIED |
| ons | UK Office for National Statistics | Official | UNVERIFIED |
| boe | Bank of England | Official | UNVERIFIED |
| boj | Bank of Japan | Official | UNVERIFIED |
| statistics_bureau_japan | Statistics Bureau of Japan | Official | UNVERIFIED |
| esri_japan | Economic and Social Research Institute, Japan | Official | UNVERIFIED |
| mof_japan | Ministry of Finance Japan | Official | UNVERIFIED |
| federal_reserve | Federal Reserve | Official | UNVERIFIED |
| bls | U.S. Bureau of Labor Statistics | Official | UNVERIFIED |
| bea | U.S. Bureau of Economic Analysis | Official | UNVERIFIED |
| alfred | ALFRED | Revision archive | UNVERIFIED |
| licensed_forecast_provider | Licensed forecast provider | Licensed forecast class | UNVERIFIED |

The generic licensed-forecast entry is a placeholder class only. No vendor, entitlement, credential, price or license right is assumed.

## Missing forecasts

A missing pre-release forecast stays null. surprise() returns null when either first_actual or pre_release_forecast is missing; it never substitutes zero.

## Safety

No downloader, API credential, broker integration or Live trading capability is added in T005.
