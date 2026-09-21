"""Task lifecycle step names — map Development Core states to durable activities."""

# Order matters: engine skips any name already in completed_steps.
LIFECYCLE_STEPS: tuple[str, ...] = (
    "reconcile_existing_delivery",
    "prepare_and_launch_dev",
    "await_dev_worker",
    "ci_wait",
    "launch_qa",
    "await_qa_worker",
    "approval_or_merge",
)

# Steps that mean "keep instance Running but do not occupy a coding slot forever"
WAITING_STEPS = frozenset({"ci_wait", "approval_or_merge", "await_dev_worker", "await_qa_worker"})
