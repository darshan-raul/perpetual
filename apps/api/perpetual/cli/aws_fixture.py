"""CLI command: `perpetual import-aws-fixture` (`P1b-03`)."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from perpetual.normalization.aws import (
    AwsFixtureError,
    import_aws_fixture_file,
    resolve_aws_fixture_path,
)


def import_aws_fixture_command(
    fixture: Annotated[
        str,
        typer.Argument(help="Fixture name under fixtures/aws/ (e.g. ecs-rds-sample) or JSON path."),
    ],
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON output."),
    ] = False,
) -> None:
    """Normalize a recorded AWS API response fixture into canonical ResourceNodes."""
    try:
        path = resolve_aws_fixture_path(fixture)
        result = import_aws_fixture_file(path)
    except (AwsFixtureError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if as_json:
        payload = {
            "account_id": result.account_id,
            "collected_at": result.collected_at.isoformat(),
            "resource_count": len(result.nodes),
            "counts_by_type": result.counts_by_type,
            "conflict_count": len(result.conflicts),
            "resources": [node.model_dump(mode="json") for node in result.nodes],
        }
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(f"Imported recorded AWS fixture: {path.name}")
    typer.echo(f"  Account:   {result.account_id}")
    typer.echo(f"  Resources: {len(result.nodes)}")
    typer.echo(f"  Conflicts: {len(result.conflicts)}")
    typer.echo("  By type:")
    for type_key, count in result.counts_by_type.items():
        typer.echo(f"    - {type_key}: {count}")
