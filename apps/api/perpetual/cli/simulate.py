"""`perpetual simulate` and `perpetual plan` CLI commands (P1-16, spec §45, §50)."""

import json
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from perpetual.fixtures import (
    FIXTURE_PROJECT_ID,
    Fixture,
    FixtureError,
    load_fixture,
    resolve_fixture,
)
from perpetual.graph import DependencyGraph, GraphData, GraphError, OverrideError, apply_overrides
from perpetual.models import RecoveryMechanism, RecoveryRequirement, RtoScope, TargetComparison
from perpetual.recovery import PlanError, RecoveryPlan, plan_stack_recovery
from perpetual.simulator import (
    SimulationResult,
    UnsupportedScenarioError,
    parse_scenario,
    simulate_failure,
)

console = Console(soft_wrap=True)
errors = Console(stderr=True, soft_wrap=True)


def simulate_cmd(
    stack: Annotated[str, typer.Argument(help="Stack ID or name to simulate.")],
    fixture_name: Annotated[str, typer.Option("--fixture", help="Fixture name or path.")],
    failure: Annotated[
        str,
        typer.Option("--failure", help="Failure scenario (e.g. region:ap-south-1)."),
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Output structured JSON.")] = False,
) -> None:
    """Simulate a Region failure for a stack and report recoverability, blockers and RTO."""
    fixture, graph, stack_id = _load_stack(fixture_name, stack)
    scenario = _parse_scenario_or_exit(failure)
    requirement = _find_requirement(fixture, stack_id)
    mechanisms = _mechanisms_by_primary(graph)

    plan: RecoveryPlan | None = None
    rto_comparison = TargetComparison.UNCERTAIN
    if requirement is not None:
        try:
            plan = plan_stack_recovery(
                graph,
                stack_id,
                requirement=requirement,
                mechanisms=mechanisms,
            )
            if plan.rto_comparison is not None:
                rto_comparison = plan.rto_comparison
        except (PlanError, GraphError) as error:
            errors.print(f"[red]error[/red] {error}")
            raise typer.Exit(1) from error

    try:
        result = simulate_failure(
            graph,
            stack_id,
            scenario,
            mechanisms=mechanisms,
            rto_comparison=rto_comparison,
        )
    except (UnsupportedScenarioError, GraphError) as error:
        errors.print(f"[red]error[/red] {error}")
        raise typer.Exit(1) from error

    if as_json:
        typer.echo(json.dumps(_simulate_json(result, plan), indent=2, sort_keys=True))
        return

    _render_simulation(result, plan)


def plan_cmd(
    stack: Annotated[str, typer.Argument(help="Stack ID or name to plan recovery for.")],
    fixture_name: Annotated[str, typer.Option("--fixture", help="Fixture name or path.")],
    failure: Annotated[
        str,
        typer.Option("--failure", help="Failure scenario (e.g. region:ap-south-1)."),
    ] = "region:ap-south-1",
    as_json: Annotated[bool, typer.Option("--json", help="Output structured JSON.")] = False,
) -> None:
    """Build a stack's recovery DAG and print its critical-path RTO breakdown."""
    fixture, graph, stack_id = _load_stack(fixture_name, stack)
    _parse_scenario_or_exit(failure)
    requirement = _find_requirement(fixture, stack_id)
    if requirement is None:
        errors.print(f"[red]error[/red] no RecoveryRequirement found for stack {stack_id!r}")
        raise typer.Exit(1)

    try:
        plan = plan_stack_recovery(
            graph,
            stack_id,
            requirement=requirement,
            mechanisms=_mechanisms_by_primary(graph),
        )
    except (PlanError, GraphError) as error:
        errors.print(f"[red]error[/red] {error}")
        raise typer.Exit(1) from error

    if as_json:
        typer.echo(json.dumps(_plan_json(plan), indent=2, sort_keys=True))
        return

    _render_plan(plan, requirement.target_rto_seconds)


# --- helpers ------------------------------------------------------------------


def _load_stack(fixture_name: str, selector: str) -> tuple[Fixture, DependencyGraph, str]:
    try:
        fixture = load_fixture(resolve_fixture(fixture_name))
        project_id = fixture.overrides[0].project_id if fixture.overrides else FIXTURE_PROJECT_ID
        override_result = apply_overrides(
            GraphData(
                resources=fixture.resources,
                edges=fixture.edges,
                stacks=fixture.stacks,
                stack_resources=fixture.stack_resources,
                stack_services=fixture.stack_services,
            ),
            fixture.overrides,
            project_id=project_id,
        )
        graph = DependencyGraph.from_override_result(
            override_result,
            groups=fixture.groups,
            mechanisms=fixture.mechanisms,
        )
    except (FixtureError, OverrideError, GraphError) as error:
        errors.print(f"[red]error[/red] {error}")
        raise typer.Exit(1) from error

    for candidate in graph.stacks.values():
        if selector in {candidate.id, candidate.name}:
            return fixture, graph, candidate.id
    errors.print(f"[red]error[/red] no stack {selector!r}")
    raise typer.Exit(1)


def _parse_scenario_or_exit(text: str) -> Any:
    try:
        return parse_scenario(text)
    except (ValueError, UnsupportedScenarioError) as error:
        errors.print(f"[red]error[/red] {error}")
        raise typer.Exit(1) from error


def _find_requirement(fixture: Fixture, stack_id: str) -> RecoveryRequirement | None:
    for req in fixture.requirements:
        if req.stack_id == stack_id:
            return req
    return None


def _mechanisms_by_primary(graph: DependencyGraph) -> dict[str, RecoveryMechanism]:
    return {mech.primary_resource_id: mech for mech in graph.mechanisms.values()}


def _simulate_json(result: SimulationResult, plan: RecoveryPlan | None) -> dict[str, Any]:
    return {
        "stack_id": result.stack_id,
        "scenario": result.scenario.model_dump(mode="json"),
        "stack_state": result.stack_state.value,
        "readiness": {
            "status": result.readiness.readiness.value,
            "evaluation_kind": result.readiness.evaluation_kind.value,
            "reasons": list(result.readiness.reasons),
        },
        "resources": {
            rid: {
                "state": item.state.value,
                "rto_scope": item.rto_scope.value,
                "possible_impact": item.possible_impact,
                "mechanism_kind": item.mechanism_kind.value if item.mechanism_kind else None,
                "reason": item.reason,
            }
            for rid, item in sorted(result.resources.items())
        },
        "reason_chains": [
            {
                "root_resource_id": chain.root_resource_id,
                "target_resource_id": chain.target_resource_id,
                "state": chain.state.value,
                "steps": list(chain.steps),
                "summary": chain.summary,
            }
            for chain in result.reason_chains
        ],
        "cycles": [list(cycle) for cycle in result.cycles],
        "unreviewed_required_edge_ids": list(result.unreviewed_required_edge_ids),
        "rto": _plan_json(plan)["rto"] if plan is not None else None,
    }


def _plan_json(plan: RecoveryPlan) -> dict[str, Any]:
    return {
        "stack_id": plan.stack_id,
        "rto": {
            "low_seconds": plan.rto.low_seconds,
            "expected_seconds": plan.rto.expected_seconds,
            "high_seconds": plan.rto.high_seconds,
            "contingency_percent": str(plan.rto.contingency_percent),
            "critical_path_action_ids": list(plan.rto.critical_path_action_ids),
            "parallel_action_ids": list(plan.rto.parallel_action_ids),
            "unknown_action_ids": list(plan.rto.unknown_action_ids),
            "rto_comparison": plan.rto_comparison.value if plan.rto_comparison else None,
        },
        "actions": [
            {
                "id": action.id,
                "name": action.name,
                "action_type": action.action_type,
                "phase": action.phase.value,
                "automation_level": action.automation_level.value,
                "expected_seconds": action.estimated_duration.expected_seconds,
            }
            for action in plan.actions.values()
        ],
        "edges": [list(edge) for edge in plan.edges],
    }


def _render_simulation(result: SimulationResult, plan: RecoveryPlan | None) -> None:
    console.print(f"[bold]Stack:[/bold]       {result.stack_id}")
    console.print(f"[bold]Stack state:[/bold] {result.stack_state.value}")
    console.print(
        f"[bold]Readiness:[/bold]   {result.readiness.readiness.value} "
        f"({', '.join(result.readiness.reasons) or 'all gates passed'})"
    )
    if plan is not None and plan.rto.expected_seconds is not None:
        low_m = (plan.rto.low_seconds or 0.0) / 60.0
        exp_m = plan.rto.expected_seconds / 60.0
        high_m = (plan.rto.high_seconds or 0.0) / 60.0
        console.print(
            f"[bold]Stack RTO:[/bold]   {low_m:.1f}-{high_m:.1f}m (expected {exp_m:.1f}m)"
        )

    table = Table(title="Resources (in RTO scope)")
    table.add_column("Resource", overflow="fold")
    table.add_column("State")
    table.add_column("Reason")
    for rid, item in sorted(result.resources.items()):
        if item.rto_scope is RtoScope.IN_SCOPE:
            table.add_row(rid, item.state.value, item.reason)
    console.print(table)

    if result.reason_chains:
        console.print("[bold]Failure reason chains:[/bold]")
        for chain in result.reason_chains:
            console.print(f"  {' -> '.join(chain.steps)}  ({chain.summary})")


def _render_plan(plan: RecoveryPlan, target_rto_seconds: int) -> None:
    rto = plan.rto
    console.print(f"[bold]Recovery Plan:[/bold] {plan.stack_id}")
    if rto.expected_seconds is None:
        console.print("[bold]Stack RTO:[/bold]     UNKNOWN")
    else:
        low_m = (rto.low_seconds or 0.0) / 60.0
        high_m = (rto.high_seconds or 0.0) / 60.0
        exp_m = rto.expected_seconds / 60.0
        target_m = target_rto_seconds / 60.0
        comp = plan.rto_comparison.value if plan.rto_comparison else "N/A"
        console.print(
            f"[bold]Stack RTO:[/bold]     {low_m:.1f}-{high_m:.1f}m "
            f"(expected {exp_m:.1f}m, target {target_m:.1f}m, comparison={comp})"
        )

    crit = Table(title="Critical Path Actions")
    crit.add_column("Phase")
    crit.add_column("Action")
    crit.add_column("Expected (s)")
    crit.add_column("Automation")
    for aid in rto.critical_path_action_ids:
        action = plan.actions[aid]
        crit.add_row(
            action.phase.value,
            action.name,
            str(action.estimated_duration.expected_seconds),
            action.automation_level.value,
        )
    console.print(crit)
