"""Market data helpers and sampling-readiness contracts; no live feeds."""
from .imports import (
    AcquisitionStatus,
    DataClass,
    DataManifest,
    Gap,
    StorageLayout,
    build_manifest,
    sha256_file,
    verify_manifest,
)
from .sampling import (
    DukascopySamplingAdapter,
    SamplePlan,
    SamplingReport,
    TermsStatus,
    original_macro_value,
)

__all__ = [
    "AcquisitionStatus",
    "DataClass",
    "DataManifest",
    "DukascopySamplingAdapter",
    "Gap",
    "SamplePlan",
    "SamplingReport",
    "StorageLayout",
    "TermsStatus",
    "build_manifest",
    "original_macro_value",
    "sha256_file",
    "verify_manifest",
]
