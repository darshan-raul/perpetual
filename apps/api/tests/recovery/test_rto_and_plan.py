"""P1-09..P1-14, P1-16, P1-17: duration catalog, DAG builder, buffer, §93 RTO tests & CLI."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from perpetual.cli import app
from perpetual.fixtures import load_fixture
from perpetual.graph import build_graph
from perpetual.models import (
    BufferPolicy,
    DurationEstimate,
    EstimateConfidence,
    TargetComparison,
)
from perpetual.recovery import (
    AutomationLevel,
    PlanError,
    RecoveryAction,
    RecoveryPhase,
    build_recovery_dag,
    compare_target,
    load_duration_catalog,
    plan_stack_recovery,
)

REPO = Path(__file__).resolve().parents[4]
runner = CliRunner()


def _dur(minutes: int) -> DurationEstimate:
    secs = minutes * 60
    return DurationEstimate(
        low_seconds=secs,
        expected_seconds=secs,
        high_seconds=secs,
        confidence=EstimateConfidence.MEDIUM,
        basis="test",
    )


def _spec_93_actions(*, refine_ecs: bool, db_manual: bool = False) -> list[RecoveryAction]:
    """Exact actions from spec §93 (5, 30, 8, 3, 2 minutes)."""
    return [
        RecoveryAction(
            id="network",
            name="Network",
            action_type="network",
            phase=RecoveryPhase.FOUNDATION,
            estimated_duration=_dur(5),
            automation_level=AutomationLevel.AUTOMATIC,
        ),
        RecoveryAction(
            id="database",
            name="Database",
            action_type="database",
            phase=RecoveryPhase.DATA,
            estimated_duration=_dur(30),
            automation_level=AutomationLevel.MANUAL if db_manual else AutomationLevel.AUTOMATIC,
        ),
        RecoveryAction(
            id="ecs",
            name="ECS",
            action_type="ecs",
            phase=RecoveryPhase.COMPUTE,
            prerequisites=["network"] if refine_ecs else [],
            refined_prerequisites=refine_ecs,
            estimated_duration=_dur(8),
            automation_level=AutomationLevel.AUTOMATIC,
        ),
        RecoveryAction(
            id="validation",
            name="Validation",
            action_type="validation",
            phase=RecoveryPhase.TRAFFIC,
            prerequisites=["database", "ecs"],
            refined_prerequisites=True,
            estimated_duration=_dur(3),
            automation_level=AutomationLevel.AUTOMATIC,
        ),
        RecoveryAction(
            id="dns",
            name="DNS",
            action_type="dns",
            phase=RecoveryPhase.TRAFFIC,
            prerequisites=["validation"],
            refined_prerequisites=True,
            estimated_duration=_dur(2),
            automation_level=AutomationLevel.AUTOMATIC,
        ),
    ]


# --- Spec §93 RTO tests (40 / 48 / 49.5 minutes) ------------------------------


def test_spec_93_refined_dag_rto_is_40_minutes() -> None:
    plan = build_recovery_dag(_spec_93_actions(refine_ecs=True), stack_id="checkout")
    assert plan.rto.expected_seconds == 40 * 60
    assert plan.rto.critical_path_action_ids == ("network", "database", "validation", "dns")
    assert plan.rto.parallel_action_ids == ("ecs",)


def test_spec_93_phase_barrier_dag_rto_is_48_minutes() -> None:
    plan = build_recovery_dag(_spec_93_actions(refine_ecs=False), stack_id="checkout")
    assert plan.rto.expected_seconds == 48 * 60
    assert plan.rto.critical_path_action_ids == ("network", "database", "ecs", "validation", "dns")


def test_spec_93_buffer_case_rto_is_49_point_5_minutes() -> None:
    buffer = BufferPolicy(
        handoff=_dur(5),
        stack_validation=None,
        contingency_percent=Decimal("10"),
    )
    plan = build_recovery_dag(
        _spec_93_actions(refine_ecs=True, db_manual=True),
        stack_id="checkout",
        buffer=buffer,
    )
    # critical path = 5 + (5 + 30) + 3 + 2 = 45m; * 1.10 = 49.5m = 2970s
    assert plan.rto.expected_seconds == 49.5 * 60
    assert plan.rto.handoff_applied_action_ids == ("database",)


# --- Catalog, UNKNOWN propagation, cycles & target comparison -----------------


def test_duration_catalog_buckets_missing_entry_and_overrides() -> None:
    catalog = load_duration_catalog()

    small = catalog.estimate("rds_promote_read_replica", attributes={"allocated_storage_gb": 100})
    large = catalog.estimate("rds_promote_read_replica", attributes={"allocated_storage_gb": 1000})
    assert small.expected_seconds == 600
    assert large.expected_seconds == 900
    assert catalog.catalog_version in small.basis
    assert "allocated_storage_gb:<500" in small.basis

    # Missing catalog entry -> None (UNKNOWN), never zero (§49.1).
    missing = catalog.estimate("nonexistent_action_type")
    assert missing.expected_seconds is None

    # Explicit resource override wins.
    custom = _dur(7)
    assert catalog.estimate("nonexistent_action_type", override=custom) == custom


def test_unknown_action_duration_makes_rto_unknown_not_zero() -> None:
    unknown_action = RecoveryAction(
        id="unknown-step",
        name="Unmodeled step",
        action_type="unmodeled",
        phase=RecoveryPhase.DATA,
        estimated_duration=DurationEstimate(
            low_seconds=None,
            expected_seconds=None,
            high_seconds=None,
            confidence=EstimateConfidence.LOW,
            basis="missing catalog entry",
        ),
        automation_level=AutomationLevel.MANUAL,
    )
    plan = build_recovery_dag([unknown_action], stack_id="stk")
    assert plan.rto.expected_seconds is None
    assert plan.rto.unknown_action_ids == ("unknown-step",)
    assert compare_target(plan.rto.low_seconds, plan.rto.high_seconds, 1800) is (
        TargetComparison.UNCERTAIN
    )


def test_recovery_dag_rejects_cycles() -> None:
    a = RecoveryAction(
        id="a",
        name="A",
        action_type="a",
        phase=RecoveryPhase.DATA,
        prerequisites=["b"],
        refined_prerequisites=True,
        estimated_duration=_dur(5),
        automation_level=AutomationLevel.AUTOMATIC,
    )
    b = RecoveryAction(
        id="b",
        name="B",
        action_type="b",
        phase=RecoveryPhase.DATA,
        prerequisites=["a"],
        refined_prerequisites=True,
        estimated_duration=_dur(5),
        automation_level=AutomationLevel.AUTOMATIC,
    )
    with pytest.raises(PlanError, match="cycle"):
        build_recovery_dag([a, b], stack_id="stk")


def test_target_comparison_boundaries() -> None:
    assert compare_target(600, 1800, 1800) is TargetComparison.PASS
    assert compare_target(1801, 2400, 1800) is TargetComparison.FAIL
    assert compare_target(1200, 2400, 1800) is TargetComparison.UNCERTAIN
    assert compare_target(None, 1200, 1800) is TargetComparison.UNCERTAIN


def test_plan_stack_recovery_and_cli_simulate_and_plan_on_canonical_demos() -> None:
    fixture = load_fixture(REPO / "fixtures/graphs/ecs-remediated.yaml")
    graph = build_graph(
        resources=fixture.resources,
        edges=fixture.edges,
        groups=fixture.groups,
        mechanisms=fixture.mechanisms,
        stacks=fixture.stacks,
        stack_resources=fixture.stack_resources,
        stack_services=fixture.stack_services,
    )
    plan = plan_stack_recovery(
        graph,
        "checkout",
        requirement=fixture.requirements[0],
        mechanisms={m.primary_resource_id: m for m in fixture.mechanisms},
    )
    assert plan.rto.expected_seconds is not None
    assert "act:decide" in plan.rto.critical_path_action_ids
    # Out-of-scope log group adds no action to the plan.
    assert not any("log-group" in aid for aid in plan.actions)

    # CLI: perpetual simulate on ecs-broken -> UNAVAILABLE / NOT_READY
    sim_broken = runner.invoke(
        app,
        [
            "simulate",
            "checkout",
            "--fixture",
            str(REPO / "fixtures/graphs/ecs-broken.yaml"),
            "--failure",
            "region:ap-south-1",
            "--json",
        ],
    )
    assert sim_broken.exit_code == 0, sim_broken.output
    broken_payload = json.loads(sim_broken.output)
    assert broken_payload["stack_state"] == "UNAVAILABLE"
    assert broken_payload["readiness"]["status"] == "NOT_READY"

    # CLI: perpetual simulate on ecs-remediated -> RECOVERABLE
    sim_ok = runner.invoke(
        app,
        [
            "simulate",
            "checkout",
            "--fixture",
            str(REPO / "fixtures/graphs/ecs-remediated.yaml"),
            "--failure",
            "region:ap-south-1",
            "--json",
        ],
    )
    assert sim_ok.exit_code == 0, sim_ok.output
    ok_payload = json.loads(sim_ok.output)
    assert ok_payload["stack_state"] == "RECOVERABLE"
    assert ok_payload["rto"]["expected_seconds"] is not None

    # CLI: perpetual plan on ecs-remediated
    plan_res = runner.invoke(
        app,
        [
            "plan",
            "checkout",
            "--fixture",
            str(REPO / "fixtures/graphs/ecs-remediated.yaml"),
            "--failure",
            "region:ap-south-1",
            "--json",
        ],
    )
    assert plan_res.exit_code == 0, plan_res.output
    plan_payload = json.loads(plan_res.output)
    assert plan_payload["stack_id"] == "checkout"
    assert plan_payload["rto"]["expected_seconds"] is not None
