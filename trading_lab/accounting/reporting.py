"""Deterministic ledger reporting artifacts for governance/evaluation outputs.

Research-only helper. No broker integration.
"""

from __future__ import annotations

from collections.abc import Sequence

from trading_lab.accounting.ledger import LedgerSnapshot


SCHEMA_VERSION = "ledger-evaluation.v1"
EPSILON = 1e-9


def build_ledger_evaluation_artifact(*, snapshots: Sequence[LedgerSnapshot]) -> dict[str, object]:
    """Build deterministic machine-readable reporting output from ledger snapshots."""
    if not snapshots:
        raise ValueError("snapshots must not be empty")

    latest = snapshots[-1]
    max_exposure = max(snapshot.exposure_abs for snapshot in snapshots)
    worst_drawdown = max(snapshot.drawdown for snapshot in snapshots)
    max_drawdown = max(snapshot.max_drawdown for snapshot in snapshots)

    equity_reconciliation_ok = (
        abs(
            latest.equity_total
            - (latest.trading_equity_ex_cashflows + latest.external_cashflow_total)
        )
        <= EPSILON
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_count": len(snapshots),
        "latest": {
            "position_qty": latest.position_qty,
            "exposure_abs": latest.exposure_abs,
            "realized_gross_pnl": latest.realized_gross_pnl,
            "realized_costs_total": latest.realized_costs_total,
            "rollover_total": latest.rollover_total,
            "unrealized_pnl": latest.unrealized_pnl,
            "trading_pnl_net": latest.trading_pnl_net,
            "external_cashflow_total": latest.external_cashflow_total,
            "cash_balance": latest.cash_balance,
            "equity_total": latest.equity_total,
            "drawdown": latest.drawdown,
            "max_drawdown": latest.max_drawdown,
            "recovery": latest.recovery,
        },
        "risk": {
            "max_exposure_abs": max_exposure,
            "worst_drawdown": worst_drawdown,
            "max_drawdown": max_drawdown,
        },
        "governance_summary": {
            "trading_performance": {
                "trading_pnl_net": latest.trading_pnl_net,
                "realized_gross_pnl": latest.realized_gross_pnl,
                "unrealized_pnl": latest.unrealized_pnl,
                "realized_costs_total": latest.realized_costs_total,
                "rollover_total": latest.rollover_total,
            },
            "cashflow": {
                "external_cashflow_total": latest.external_cashflow_total,
                "trading_equity_ex_cashflows": latest.trading_equity_ex_cashflows,
                "equity_total": latest.equity_total,
                "cash_balance": latest.cash_balance,
            },
            "invariants": {
                "equity_reconciliation_ok": equity_reconciliation_ok,
            },
        },
    }
