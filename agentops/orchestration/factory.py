"""Select orchestration backend from Settings. Default remains legacy."""
from agentops.orchestration.legacy_backend import LegacyBackend


def create_backend(cfg, controller, healer):
    backend = (getattr(cfg, "orchestration_backend", None) or "maf_durable").strip().lower()
    if backend == "maf_durable":
        from agentops.orchestration.maf_durable.backend import MafDurableBackend

        return MafDurableBackend(cfg, controller, healer)
    if backend == "legacy":
        return LegacyBackend(controller, healer)
    raise ValueError(
        f"Unknown ORCHESTRATION_BACKEND={backend!r}; expected 'legacy' or 'maf_durable'"
    )
