"""Canonical status vocabulary (spec §30.1).

One vocabulary is used across the engine, API and UI. UI colours map onto these
values; they are not separate states.
"""

from collections.abc import Iterable
from enum import StrEnum


class ResourceState(StrEnum):
    """State of a resource under simulation."""

    SURVIVES = "SURVIVES"
    """Unaffected by the failure."""
    RECOVERABLE = "RECOVERABLE"
    """Affected, but a resolved mechanism and all its DR dependencies are usable."""
    BLOCKED = "BLOCKED"
    """Affected, and the mechanism is none or a required DR dependency is BLOCKED."""
    UNKNOWN = "UNKNOWN"
    """Affected, and the mechanism or a required DR dependency is unknown."""


# Worst first: BLOCKED > UNKNOWN > RECOVERABLE > SURVIVES.
_SEVERITY: dict[ResourceState, int] = {
    ResourceState.BLOCKED: 3,
    ResourceState.UNKNOWN: 2,
    ResourceState.RECOVERABLE: 1,
    ResourceState.SURVIVES: 0,
}


def worst_state(states: Iterable[ResourceState]) -> ResourceState:
    """Combine resource states, worst first (spec §30.1).

    Raises ValueError for an empty input: a stack with no required resources has
    no defined state, and silently returning SURVIVES would overstate readiness.
    """
    items = list(states)
    if not items:
        raise ValueError("cannot combine an empty set of resource states")
    return max(items, key=_SEVERITY.__getitem__)


class StackState(StrEnum):
    """Simulation outcome for a stack."""

    RECOVERABLE = "RECOVERABLE"
    """The application can operate after failover."""
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


def stack_state(required_states: Iterable[ResourceState]) -> StackState:
    """Map the worst state of a stack's required resources to the stack state.

    SURVIVES and RECOVERABLE map to RECOVERABLE, UNKNOWN to UNKNOWN and BLOCKED to
    UNAVAILABLE. Target violations are evaluated separately (spec §31).
    """
    worst = worst_state(required_states)
    if worst is ResourceState.BLOCKED:
        return StackState.UNAVAILABLE
    if worst is ResourceState.UNKNOWN:
        return StackState.UNKNOWN
    return StackState.RECOVERABLE


class Readiness(StrEnum):
    """Overall readiness result (spec §31)."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"
    UNKNOWN = "UNKNOWN"


class TargetComparison(StrEnum):
    """Predicted value against a target (spec §52)."""

    PASS = "PASS"
    """Predicted high bound is within the target."""
    FAIL = "FAIL"
    """Predicted low bound exceeds the target."""
    UNCERTAIN = "UNCERTAIN"
    """The target lies within the predicted range, or the estimate is unknown."""
