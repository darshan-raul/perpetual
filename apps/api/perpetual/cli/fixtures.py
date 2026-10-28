"""`perpetual fixtures ...`: check fixture files and export their JSON Schema."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from perpetual.fixtures import (
    FixtureError,
    fixture_json_schema,
    fixture_names,
    load_fixture,
    resolve_fixture,
)

fixtures_app = typer.Typer(help="Work with fixture files.", no_args_is_help=True)
console = Console(soft_wrap=True)
errors = Console(stderr=True, soft_wrap=True)


@fixtures_app.command("validate")
def validate(
    fixtures: Annotated[
        list[str] | None,
        typer.Argument(help="Fixture names or paths. Default: every fixture in fixtures/graphs."),
    ] = None,
) -> None:
    """Check fixtures: format, domain-model rules and cross-references."""
    targets = fixtures or fixture_names()
    if not targets:
        errors.print("No fixtures found. Pass a path, or run inside the repository.")
        raise typer.Exit(2)
    failed = 0
    for target in targets:
        try:
            path = resolve_fixture(target)
            fixture = load_fixture(path)
        except FixtureError as error:
            failed += 1
            errors.print(f"[red]FAIL[/red] {error.source} ({len(error.issues)} problem(s))")
            for issue in error.issues:
                errors.print(f"  {issue}", markup=False, highlight=False)
            continue
        console.print(
            f"[green]ok[/green]   {path} "
            f"({len(fixture.resources)} resources, {len(fixture.edges)} edges)"
        )
    if failed:
        raise typer.Exit(1)


@fixtures_app.command("schema")
def schema(
    out: Annotated[
        Path | None, typer.Option("--out", help="Write to this file instead of stdout.")
    ] = None,
) -> None:
    """Print the JSON Schema for fixture files (format v1)."""
    text = json.dumps(fixture_json_schema(), indent=2, sort_keys=True) + "\n"
    if out is None:
        typer.echo(text, nl=False)
    else:
        out.write_text(text, encoding="utf-8")
        console.print(f"wrote {out}")
