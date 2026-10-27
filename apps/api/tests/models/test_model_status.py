"""Status vocabulary (spec §30.1)."""

import pytest

from perpetual.models import ResourceState, StackState, stack_state, worst_state

S = ResourceState


@pytest.mark.parametrize(
    ("states", "worst"),
    [
        ([S.SURVIVES, S.RECOVERABLE], S.RECOVERABLE),
        ([S.RECOVERABLE, S.UNKNOWN, S.SURVIVES], S.UNKNOWN),
        ([S.UNKNOWN, S.BLOCKED], S.BLOCKED),
        ([S.SURVIVES], S.SURVIVES),
    ],
)
def test_worst_state_orders_blocked_unknown_recoverable_survives(
    states: list[ResourceState], worst: ResourceState
) -> None:
    assert worst_state(states) is worst


def test_worst_state_refuses_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        worst_state([])


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ([S.SURVIVES], StackState.RECOVERABLE),
        ([S.SURVIVES, S.RECOVERABLE], StackState.RECOVERABLE),
        ([S.RECOVERABLE, S.UNKNOWN], StackState.UNKNOWN),
        ([S.UNKNOWN, S.BLOCKED], StackState.UNAVAILABLE),
    ],
)
def test_stack_state_mapping(states: list[ResourceState], expected: StackState) -> None:
    assert stack_state(states) is expected
