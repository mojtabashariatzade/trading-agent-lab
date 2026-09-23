"""Sampling-readiness contracts. No provider network calls are implemented here."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from trading_lab.fundamentals import EconomicRelease, validate_release_pit_constraints

from .imports import (
    AcquisitionStatus,
    DataClass,
    DataManifest,
    verify_manifest_bindings,
)


class TermsStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED_ALLOWED = "VERIFIED_ALLOWED"
    VERIFIED_BLOCKED = "VERIFIED_BLOCKED"


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class SamplePlan:
    provider_id: str
    adapter_version: str
    instrument: str
    requested_start: datetime
    requested_end: datetime
    terms_status: TermsStatus
    network_enabled: bool

    def __post_init__(self) -> None:
        for name in ("provider_id", "adapter_version", "instrument"):
            value = str(getattr(self, name)).strip()
            if not value:
                raise ValueError(f"{name} is required")
            object.__setattr__(self, name, value)
        start = _aware_utc(self.requested_start)
        end = _aware_utc(self.requested_end)
        if end <= start:
            raise ValueError("requested_end must be after requested_start")
        if not isinstance(self.terms_status, TermsStatus):
            raise ValueError("Typed TermsStatus required")
        if self.terms_status != TermsStatus.VERIFIED_ALLOWED and self.network_enabled:
            raise ValueError("Network sampling cannot be enabled before terms are verified allowed")
        object.__setattr__(self, "requested_start", start)
        object.__setattr__(self, "requested_end", end)


@dataclass(frozen=True)
class SamplingReport:
    provider_id: str
    adapter_version: str
    status: AcquisitionStatus
    terms_status: TermsStatus
    downloaded: bool
    manifest: DataManifest | None
    note: str

    def __post_init__(self) -> None:
        if not isinstance(self.status, AcquisitionStatus):
            raise ValueError("Typed AcquisitionStatus required")
        if not isinstance(self.terms_status, TermsStatus):
            raise ValueError("Typed TermsStatus required")
        if self.downloaded:
            if self.status != AcquisitionStatus.DOWNLOADED or self.manifest is None:
                raise ValueError("Downloaded report requires DOWNLOADED status and manifest")
            if self.terms_status != TermsStatus.VERIFIED_ALLOWED:
                raise ValueError("Downloaded report requires verified-allowed terms")
        else:
            if self.status == AcquisitionStatus.DOWNLOADED:
                raise ValueError("DOWNLOADED status requires downloaded=True")


class DukascopySamplingAdapter:
    """Metadata-only adapter plan until current provider terms are verified."""

    provider_id = "dukascopy"
    adapter_version = "readiness-1"

    def plan(
        self,
        *,
        instrument: str,
        requested_start: datetime,
        requested_end: datetime,
        terms_status: TermsStatus = TermsStatus.UNVERIFIED,
    ) -> SamplePlan:
        # T006 intentionally has no HTTP/download implementation. A future
        # reviewed collector may enable network access only after terms review.
        return SamplePlan(
            provider_id=self.provider_id,
            adapter_version=self.adapter_version,
            instrument=instrument,
            requested_start=requested_start,
            requested_end=requested_end,
            terms_status=terms_status,
            network_enabled=False,
        )

    def readiness_report(self, plan: SamplePlan) -> SamplingReport:
        if plan.provider_id != self.provider_id:
            raise ValueError("Plan provider does not match adapter")
        if plan.terms_status == TermsStatus.VERIFIED_BLOCKED:
            status = AcquisitionStatus.BLOCKED
            note = "Current provider terms were reviewed and block this sample."
        else:
            status = AcquisitionStatus.UNVERIFIED
            note = (
                "No sample downloaded. Current provider terms/permissions and actual "
                "historical coverage remain unverified."
            )
        return SamplingReport(
            provider_id=self.provider_id,
            adapter_version=self.adapter_version,
            status=status,
            terms_status=plan.terms_status,
            downloaded=False,
            manifest=None,
            note=note,
        )

    def downloaded_report(
        self,
        plan: SamplePlan,
        manifest: DataManifest,
    ) -> SamplingReport:
        """Record a sample that an external authorized collector already produced."""
        if plan.provider_id != self.provider_id or manifest.provider_id != self.provider_id:
            raise ValueError("Provider mismatch")
        if plan.terms_status != TermsStatus.VERIFIED_ALLOWED:
            raise PermissionError("Cannot mark sample downloaded before terms are verified allowed")
        if manifest.data_class != DataClass.REAL_OBSERVATION:
            raise ValueError("Provider samples must be stored as REAL_OBSERVATION, not fixtures")
        if not manifest.source_provenance or not manifest.legal_source:
            raise ValueError("Downloaded provider samples require source_provenance and legal_source")
        if (
            not manifest.payload_snapshot_sha256
            or manifest.payload_snapshot_sha256 != manifest.checksum_sha256
        ):
            raise ValueError("Downloaded provider samples require immutable payload snapshot binding")
        verify_manifest_bindings(manifest)
        return SamplingReport(
            provider_id=self.provider_id,
            adapter_version=self.adapter_version,
            status=AcquisitionStatus.DOWNLOADED,
            terms_status=plan.terms_status,
            downloaded=True,
            manifest=manifest,
            note="Authorized sample bytes exist locally and are covered by the attached manifest.",
        )


def original_macro_value(release: EconomicRelease) -> float | None:
    """Use the immutable first release; never substitute a later revision."""
    validate_release_pit_constraints(release)
    return release.first_actual
