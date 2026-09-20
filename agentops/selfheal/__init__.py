"""Self-healing maintenance subsystem for the local supervisor.

Runtime recoveries + failure-pattern registry. Does not touch live trading,
broker, secrets, security policy, or spend limits without human approval.
"""

from .maintenance import MaintenanceLoop

__all__ = ["MaintenanceLoop"]
