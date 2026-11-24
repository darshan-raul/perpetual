"""The `perpetual` command and its sub-commands."""

import typer

from perpetual.cli.fixtures import fixtures_app
from perpetual.cli.graph import graph_app
from perpetual.cli.simulate import plan_cmd, simulate_cmd

app = typer.Typer(
    name="perpetual",
    help="AWS disaster-recovery readiness: dependency graph, Region-failure simulation, DR plans.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(fixtures_app, name="fixtures")
app.add_typer(graph_app, name="graph")
app.command("simulate")(simulate_cmd)
app.command("plan")(plan_cmd)


def main() -> None:
    app()
