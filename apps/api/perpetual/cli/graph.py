"""`perpetual graph ...`: inspect dependency graphs, DR overlays and YAML overrides (P0-12)."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from perpetual.config import load_config
from perpetual.fixtures import (
    FIXTURE_PROJECT_ID,
    Fixture,
    FixtureError,
    load_fixture,
    resolve_fixture,
)
from perpetual.graph import (
    DependencyGraph,
    GraphData,
    GraphError,
    OverrideError,
    OverrideResult,
    SnapshotManifest,
    apply_overrides,
    build_snapshot_manifest,
    detect_cycles,
    dump_overrides,
    load_overrides,
    merge_overrides,
)
from perpetual.models import DependencyEdge, RecoveryMechanism, ResourceNode, ReviewState, Stack

graph_app = typer.Typer(
    help="Inspect dependency graphs, DR overlays and graph overrides.",
    no_args_is_help=True,
)
overrides_app = typer.Typer(help="Export and apply YAML graph overrides.", no_args_is_help=True)
graph_app.add_typer(overrides_app, name="overrides")

console = Console(soft_wrap=True)
errors = Console(stderr=True, soft_wrap=True)


@graph_app.callback(invoke_without_command=True)
def inspect_graph(
    ctx: typer.Context,
    fixture_name: Annotated[
        str | None,
        typer.Option("--fixture", help="Fixture name or path to inspect."),
    ] = None,
    stack: Annotated[
        str | None,
        typer.Option("--stack", help="Filter output to one stack (by ID or name)."),
    ] = None,
    unreviewed: Annotated[
        bool,
        typer.Option("--unreviewed", help="Show only unreviewed edges."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output structured JSON instead of tables."),
    ] = False,
) -> None:
    """Print a fixture's dependency graph, DR overlay, and review diagnostics."""
    if ctx.invoked_subcommand is not None:
        return
    if fixture_name is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    fixture = _load_fixture_or_exit(fixture_name)
    project_id = _fixture_project_id(fixture)
    override_result, graph, manifest = _build_fixture_graph(
        fixture, fixture.overrides, project_id=project_id
    )

    selected_stack = _select_stack_or_exit(graph, stack) if stack is not None else None
    resources, edges, mechanisms = _filter_view(
        graph, selected_stack=selected_stack, unreviewed_only=unreviewed
    )
    cycles = detect_cycles(graph)
    threshold = load_config().evidence.review_confidence_threshold

    if as_json:
        payload = _graph_json_payload(
            fixture_name=fixture.name,
            manifest=manifest,
            selected_stack=selected_stack,
            resources=resources,
            edges=edges,
            mechanisms=mechanisms,
            cycles=cycles,
            override_result=override_result,
            review_threshold=threshold,
        )
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    _render_graph_tables(
        fixture_name=fixture.name,
        manifest=manifest,
        selected_stack=selected_stack,
        resources=resources,
        edges=edges,
        mechanisms=mechanisms,
        cycles=cycles,
        override_result=override_result,
        review_threshold=threshold,
    )


@overrides_app.command("export")
def export_overrides(
    fixture_name: Annotated[
        str,
        typer.Option("--fixture", help="Fixture name or path to export overrides from."),
    ],
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write YAML to this file instead of stdout."),
    ] = None,
) -> None:
    """Export graph overrides from a fixture as versioned YAML."""
    fixture = _load_fixture_or_exit(fixture_name)
    project_id = _fixture_project_id(fixture)
    try:
        yaml_text = dump_overrides(fixture.overrides, project_id=project_id)
    except OverrideError as error:
        errors.print(f"[red]error[/red] {error}", markup=True)
        raise typer.Exit(1) from error

    if out is None:
        typer.echo(yaml_text, nl=False)
    else:
        out.write_text(yaml_text, encoding="utf-8")
        console.print(f"wrote {out} ({len(fixture.overrides)} override(s))")


@overrides_app.command("apply")
def apply_overrides_cmd(
    overrides_file: Annotated[
        Path,
        typer.Argument(help="Versioned override YAML file to apply."),
    ],
    fixture_name: Annotated[
        str,
        typer.Option("--fixture", help="Fixture name or path to apply overrides against."),
    ],
    project_id: Annotated[
        str | None,
        typer.Option("--project", help="Project ID bound to the override YAML."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write merged overrides YAML to this file."),
    ] = None,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output structured JSON summary."),
    ] = False,
) -> None:
    """Merge and apply a YAML override file onto a fixture and validate the result."""
    fixture = _load_fixture_or_exit(fixture_name)
    effective_project = project_id or _fixture_project_id(fixture)
    try:
        incoming = load_overrides(overrides_file, project_id=effective_project)
        merged = merge_overrides(fixture.overrides, incoming, project_id=effective_project)
    except OverrideError as error:
        errors.print(f"[red]error[/red] {error}", markup=True)
        raise typer.Exit(1) from error

    override_result, graph, manifest = _build_fixture_graph(
        fixture, merged, project_id=effective_project
    )

    if out is not None:
        out.write_text(
            dump_overrides(override_result.overrides, project_id=effective_project),
            encoding="utf-8",
        )

    summary = {
        "fixture": fixture.name,
        "project_id": effective_project,
        "manifest_digest": manifest.manifest_digest,
        "applied_overrides": len(override_result.overrides),
        "orphaned_overrides": dict(sorted(override_result.orphan_reasons.items())),
        "rejected_edges": [edge.id for edge in override_result.rejected_edges],
        "reproposals": [
            {
                "edge_id": item.edge_id,
                "rejection_id": item.rejection_id,
                "old_fingerprint": item.old_fingerprint,
                "new_fingerprint": item.new_fingerprint,
            }
            for item in override_result.reproposals
        ],
        "resource_count": len(graph.resources),
        "edge_count": len(graph.edges),
    }

    if as_json:
        typer.echo(json.dumps(summary, indent=2, sort_keys=True))
        return

    console.print(
        f"[green]applied[/green] {len(override_result.overrides)} override(s) to "
        f"[bold]{fixture.name}[/bold] "
        f"({len(graph.resources)} resources, {len(graph.edges)} active edges, "
        f"{len(override_result.rejected_edges)} rejected)"
    )
    if override_result.orphan_reasons:
        for override_id, reason in sorted(override_result.orphan_reasons.items()):
            console.print(f"  [yellow]orphaned[/yellow] {override_id}: {reason}")
    if out is not None:
        console.print(f"wrote {out}")


# --- helpers ------------------------------------------------------------------


def _load_fixture_or_exit(name_or_path: str) -> Fixture:
    try:
        path = resolve_fixture(name_or_path)
        return load_fixture(path)
    except FixtureError as error:
        errors.print(f"[red]FAIL[/red] {error.source} ({len(error.issues)} problem(s))")
        for issue in error.issues:
            errors.print(f"  {issue}", markup=False, highlight=False)
        raise typer.Exit(1) from error


def _fixture_project_id(fixture: Fixture) -> str:
    if fixture.overrides:
        return fixture.overrides[0].project_id
    return FIXTURE_PROJECT_ID


def _build_fixture_graph(
    fixture: Fixture,
    overrides: list[Any],
    *,
    project_id: str,
) -> tuple[OverrideResult, DependencyGraph, SnapshotManifest]:
    graph_data = GraphData(
        resources=fixture.resources,
        edges=fixture.edges,
        stacks=fixture.stacks,
        stack_resources=fixture.stack_resources,
        stack_services=fixture.stack_services,
    )
    try:
        override_result = apply_overrides(graph_data, overrides, project_id=project_id)
        graph = DependencyGraph.from_override_result(
            override_result,
            groups=fixture.groups,
            mechanisms=fixture.mechanisms,
        )
    except (OverrideError, GraphError) as error:
        errors.print(f"[red]error[/red] {error}", markup=True)
        raise typer.Exit(1) from error

    versions = fixture.input_versions
    manifest = build_snapshot_manifest(
        graph,
        snapshot_id=f"fixture:{fixture.name}",
        captured_at=fixture.captured_at,
        coverage=fixture.coverage,
        graph_revision=versions.graph_revision if versions else 0,
        override_revision=versions.override_revision
        if versions
        else len(override_result.overrides),
        group_revision=versions.group_revision if versions else 0,
    )
    return override_result, graph, manifest


def _select_stack_or_exit(graph: DependencyGraph, selector: str) -> Stack:
    for candidate in graph.stacks.values():
        if selector in {candidate.id, candidate.name}:
            return candidate
    available = ", ".join(sorted(s.name for s in graph.stacks.values())) or "none"
    errors.print(f"[red]error[/red] no stack {selector!r} (available: {available})")
    raise typer.Exit(1)


def _filter_view(
    graph: DependencyGraph,
    *,
    selected_stack: Stack | None,
    unreviewed_only: bool,
) -> tuple[list[ResourceNode], list[DependencyEdge], list[RecoveryMechanism]]:
    if selected_stack is not None:
        member_ids = set(selected_stack.resource_ids)
        resources = [graph.resources[rid] for rid in sorted(member_ids) if rid in graph.resources]
        edges = [
            edge
            for edge in (graph.edges[eid] for eid in sorted(graph.edges))
            if edge.from_resource_id in member_ids
        ]
        mechanisms = [
            mech
            for mech in (graph.mechanisms[mid] for mid in sorted(graph.mechanisms))
            if mech.primary_resource_id in member_ids
        ]
    else:
        resources = [graph.resources[rid] for rid in sorted(graph.resources)]
        edges = [graph.edges[eid] for eid in sorted(graph.edges)]
        mechanisms = [graph.mechanisms[mid] for mid in sorted(graph.mechanisms)]

    if unreviewed_only:
        edges = [edge for edge in edges if edge.review_state is ReviewState.UNREVIEWED]

    return resources, edges, mechanisms


def _graph_json_payload(
    *,
    fixture_name: str,
    manifest: SnapshotManifest,
    selected_stack: Stack | None,
    resources: list[ResourceNode],
    edges: list[DependencyEdge],
    mechanisms: list[RecoveryMechanism],
    cycles: tuple[tuple[str, ...], ...],
    override_result: OverrideResult,
    review_threshold: float,
) -> dict[str, Any]:
    return {
        "fixture": fixture_name,
        "manifest_digest": manifest.manifest_digest,
        "stack": selected_stack.name if selected_stack is not None else None,
        "review_confidence_threshold": review_threshold,
        "resources": [
            {
                "id": node.id,
                "service": node.service,
                "resource_type": node.resource_type,
                "region": node.region,
                "name": node.name,
                "planned": node.planned,
            }
            for node in resources
        ],
        "edges": [
            {
                "id": edge.id,
                "from_resource_id": edge.from_resource_id,
                "to_resource_id": edge.to_resource_id,
                "relationship_type": edge.relationship_type.value,
                "criticality": edge.criticality.value,
                "confidence": edge.confidence,
                "bases": sorted(basis.value for basis in edge.bases),
                "review_state": edge.review_state.value,
                "needs_review": (
                    edge.review_state is ReviewState.UNREVIEWED
                    and edge.confidence < review_threshold
                ),
            }
            for edge in edges
        ],
        "mechanisms": [
            {
                "id": mech.id,
                "primary_resource_id": mech.primary_resource_id,
                "target_region": mech.target_region,
                "kind": mech.kind.value,
                "counterpart_resource_id": mech.counterpart_resource_id,
                "control_plane_dependent": mech.control_plane_dependent,
                "confidence": mech.confidence,
            }
            for mech in mechanisms
        ],
        "cycles": [list(cycle) for cycle in cycles],
        "orphaned_overrides": dict(sorted(override_result.orphan_reasons.items())),
        "rejected_edge_ids": [edge.id for edge in override_result.rejected_edges],
    }


def _render_graph_tables(
    *,
    fixture_name: str,
    manifest: SnapshotManifest,
    selected_stack: Stack | None,
    resources: list[ResourceNode],
    edges: list[DependencyEdge],
    mechanisms: list[RecoveryMechanism],
    cycles: tuple[tuple[str, ...], ...],
    override_result: OverrideResult,
    review_threshold: float,
) -> None:
    scope_label = f" (stack: {selected_stack.name})" if selected_stack else ""
    console.print(
        f"[bold]{fixture_name}[/bold]{scope_label}  "
        f"[dim]{manifest.manifest_digest[:19]}...[/dim]  "
        f"resources={len(resources)} edges={len(edges)} mechanisms={len(mechanisms)}"
    )

    res_table = Table(title="Resources")
    res_table.add_column("ID", overflow="fold")
    res_table.add_column("Type")
    res_table.add_column("Region")
    res_table.add_column("Name")
    for node in resources:
        res_table.add_row(
            node.id, f"{node.service}/{node.resource_type}", node.region or "-", node.name
        )
    console.print(res_table)

    edge_table = Table(title="Dependency Edges")
    edge_table.add_column("From -> To", overflow="fold")
    edge_table.add_column("Type")
    edge_table.add_column("Criticality")
    edge_table.add_column("Conf")
    edge_table.add_column("Basis")
    edge_table.add_column("Review")
    for edge in edges:
        bases = ",".join(sorted(basis.value for basis in edge.bases)) or "-"
        review_label = edge.review_state.value
        if edge.review_state is ReviewState.UNREVIEWED and edge.confidence < review_threshold:
            review_label = f"[yellow]{review_label}*[/yellow]"
        edge_table.add_row(
            f"{edge.from_resource_id} -> {edge.to_resource_id}",
            edge.relationship_type.value,
            edge.criticality.value,
            f"{edge.confidence:.2f}",
            bases,
            review_label,
        )
    console.print(edge_table)

    if mechanisms:
        mech_table = Table(title="DR Overlay (Recovery Mechanisms)")
        mech_table.add_column("Primary", overflow="fold")
        mech_table.add_column("Kind")
        mech_table.add_column("Target")
        mech_table.add_column("Counterpart", overflow="fold")
        mech_table.add_column("CP Dep")
        for mech in mechanisms:
            mech_table.add_row(
                mech.primary_resource_id,
                mech.kind.value,
                mech.target_region,
                mech.counterpart_resource_id or "-",
                "yes" if mech.control_plane_dependent else "no",
            )
        console.print(mech_table)

    if cycles:
        console.print(f"[yellow]Cycles detected ({len(cycles)}):[/yellow]")
        for cycle in cycles:
            console.print("  " + " -> ".join((*cycle, cycle[0])))

    if override_result.orphan_reasons:
        console.print(
            f"[yellow]Orphaned overrides ({len(override_result.orphan_reasons)}):[/yellow]"
        )
        for override_id, reason in sorted(override_result.orphan_reasons.items()):
            console.print(f"  {override_id}: {reason}")
