"""Cross-cutting DR rules skeleton (spec §28.1; concrete rules land in P4-04)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from perpetual.rules.protocol import AssessmentContext


@runtime_checkable
class CrossCuttingRule(Protocol):
    """Interface for cross-service DR rules (`XREG-*`, `CTRL-PLANE-001`, `QUOTA-DR-001`, etc.)."""

    rule_id: str
    version: str

    def evaluate(self, context: AssessmentContext) -> list[str]:
        """Evaluate cross-cutting checks; concrete `Finding` output lands in P4-01/P4-04."""
        ...


CROSS_CUTTING_RULE_IDS: tuple[str, ...] = (
    "XREG-CONFIG-001",
    "XREG-IAM-002",
    "XREG-KMS-003",
    "CTRL-PLANE-001",
    "QUOTA-DR-001",
    "REGION-SVC-001",
    "ARC-RS-001",
    "SSM-PARITY-001",
    "OPS-ACCESS-001",
    "OPS-ACCESS-002",
)
"""Canonical cross-cutting rule IDs reserved by spec §28.1."""

__all__ = ["CROSS_CUTTING_RULE_IDS", "CrossCuttingRule"]
