"""`perpetual poc fix`: M0 PoC compile loop CLI (P1c-05)."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from perpetual.fixtures import FIXTURE_PROJECT_ID, FixtureError, load_fixture, resolve_fixture
from perpetual.graph import DependencyGraph, GraphData, GraphError, OverrideError, apply_overrides
from perpetual.iac import PocFixResult, run_poc_fix
from perpetual.models.properties import ECSServiceProperties
from perpetual.runbooks import render_poc_recovery_script

poc_app = typer.Typer(help="M0 proof-of-concept compile loop commands.", no_args_is_help=True)
console = Console(soft_wrap=True)
errors = Console(stderr=True, soft_wrap=True)


@poc_app.command("fix")
def poc_fix_cmd(
    fixture_name: Annotated[
        str,
        typer.Option("--fixture", help="Fixture name or path (e.g. ecs-broken)."),
    ] = "ecs-broken",
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Directory to write Terraform, recovery script and summary."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output structured JSON before/after summary."),
    ] = False,
) -> None:
    """Apply the PoC DR change set, generate Terraform + failover script, and re-simulate."""
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

    if not fixture.stacks or not fixture.requirements:
        errors.print("[red]error[/red] fixture must define at least one stack and requirement")
        raise typer.Exit(1)

    stack = fixture.stacks[0]
    requirement = fixture.requirements[0]
    result = run_poc_fix(graph, stack_id=stack.id, requirement=requirement)

    rds_replica_id, ecs_cluster, ecs_service, ecs_desired = _script_inputs(result)
    script_text = render_poc_recovery_script(
        stack_name=stack.name,
        primary_region=result.primary_region,
        target_region=result.target_region,
        rds_replica_id=rds_replica_id,
        ecs_cluster=ecs_cluster,
        ecs_service=ecs_service,
        ecs_target_desired_count=ecs_desired,
    )

    written: list[str] = []
    if out is not None:
        tf_dir = out / "terraform"
        rec_dir = out / "recovery"
        tf_dir.mkdir(parents=True, exist_ok=True)
        rec_dir.mkdir(parents=True, exist_ok=True)
        for name, content in sorted(result.terraform_files.items()):
            target_file = tf_dir / name
            target_file.write_text(content, encoding="utf-8")
            written.append(str(target_file))
        script_path = rec_dir / "failover.py"
        script_path.write_text(script_text, encoding="utf-8")
        written.append(str(script_path))
        summary_path = out / "SUMMARY.md"
        summary_path.write_text(_markdown_summary(result), encoding="utf-8")
        written.append(str(summary_path))

    payload = {
        "stack_id": result.stack_id,
        "primary_region": result.primary_region,
        "target_region": result.target_region,
        "before_state": result.before_simulation.stack_state.value,
        "after_state": result.after_simulation.stack_state.value,
        "before_readiness": result.before_simulation.readiness.readiness.value,
        "after_readiness": result.after_simulation.readiness.readiness.value,
        "after_evaluation_kind": result.after_simulation.readiness.evaluation_kind.value,
        "after_rto_expected_seconds": result.after_plan.rto.expected_seconds,
        "changes_applied": list(result.changes_applied),
        "terraform_files": sorted(result.terraform_files),
        "written_files": written,
    }
    if as_json:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    _render_summary(result, written)


def _script_inputs(result: PocFixResult) -> tuple[str, str, str, int]:
    rds_replica_id = f"{result.stack_id}-orders-dr"
    ecs_cluster = f"{result.stack_id}-dr"
    ecs_service = f"{result.stack_id}-api-dr"
    desired = 4
    for node in result.modeled_graph.resources.values():
        if (
            node.region == result.target_region
            and node.service == "rds"
            and node.resource_type == "db"
            and node.name is not None
        ):
            rds_replica_id = node.name
        if (
            node.region == result.target_region
            and node.service == "ecs"
            and node.resource_type == "service"
        ):
            if node.name is not None:
                ecs_service = node.name
            if (
                isinstance(node.typed_properties, ECSServiceProperties)
                and node.typed_properties.cluster_arn
            ):
                ecs_cluster = node.typed_properties.cluster_arn.rsplit("/", 1)[-1]
        if (
            node.region == result.primary_region
            and node.service == "ecs"
            and node.resource_type == "service"
            and isinstance(node.typed_properties, ECSServiceProperties)
        ):
            desired = node.typed_properties.desired_count
    return rds_replica_id, ecs_cluster, ecs_service, desired


def _markdown_summary(result: PocFixResult) -> str:
    after_rto = result.after_plan.rto.expected_seconds
    rto_str = f"{after_rto / 60.0:.1f}m" if after_rto is not None else "UNKNOWN"
    before_state = result.before_simulation.stack_state.value
    before_ready = result.before_simulation.readiness.readiness.value
    after_state = result.after_simulation.stack_state.value
    lines = [
        f"# Perpetual PoC DR Fix Summary — `{result.stack_id}`",
        "",
        f"- **Regions:** `{result.primary_region}` -> `{result.target_region}`",
        f"- **Before:** `{before_state}` / `{before_ready}`",
        f"- **After (modeled design):** `{after_state}` / expected RTO `{rto_str}`",
        "",
        "## Changes applied",
        *[f"- {change}" for change in result.changes_applied],
        "",
    ]
    return "\n".join(lines)


def _render_summary(result: PocFixResult, written: list[str]) -> None:
    table = Table(title=f"Perpetual PoC Fix: {result.stack_id}")
    table.add_column("Metric")
    table.add_column("Before")
    table.add_column("After (modeled design)")
    table.add_row(
        "Stack state",
        result.before_simulation.stack_state.value,
        result.after_simulation.stack_state.value,
    )
    table.add_row(
        "Readiness",
        result.before_simulation.readiness.readiness.value,
        result.after_simulation.readiness.readiness.value,
    )
    after_rto = result.after_plan.rto.expected_seconds
    table.add_row(
        "Expected RTO",
        "N/A (blocked)",
        f"{after_rto / 60.0:.1f}m" if after_rto is not None else "UNKNOWN",
    )
    console.print(table)
    if written:
        console.print(f"[green]wrote[/green] {len(written)} artifact(s):")
        for path in written:
            console.print(f"  {path}")
