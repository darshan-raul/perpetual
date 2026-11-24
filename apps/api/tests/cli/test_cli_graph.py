"""`perpetual graph` and `perpetual graph overrides export|apply` CLI tests (P0-12)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from perpetual.cli import app

REPO = Path(__file__).resolve().parents[4]
MINIMAL = str(REPO / "fixtures/graphs/minimal.yaml")
REVIEW_OVERRIDES = str(REPO / "fixtures/graphs/review-overrides.yaml")
runner = CliRunner()


def test_graph_prints_tables_and_dr_overlay() -> None:
    result = runner.invoke(app, ["graph", "--fixture", MINIMAL])
    assert result.exit_code == 0, result.output
    assert "minimal" in result.output
    assert "Resources" in result.output
    assert "Dependency Edges" in result.output
    assert "DR Overlay" in result.output


def test_graph_json_and_stack_filter() -> None:
    result = runner.invoke(app, ["graph", "--fixture", MINIMAL, "--stack", "checkout", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["fixture"] == "minimal"
    assert payload["stack"] == "checkout"
    assert payload["manifest_digest"].startswith("sha256:")
    assert len(payload["resources"]) == 2
    assert len(payload["edges"]) == 1
    assert len(payload["mechanisms"]) == 1
    assert payload["cycles"] == []


def test_graph_unknown_stack_fails_clearly() -> None:
    result = runner.invoke(app, ["graph", "--fixture", MINIMAL, "--stack", "nonexistent"])
    assert result.exit_code == 1
    assert "no stack 'nonexistent'" in result.output


def test_graph_unreviewed_filter_respects_applied_overrides() -> None:
    # review-overrides.yaml confirms/edits/rejects edges; --unreviewed keeps unreviewed only.
    result = runner.invoke(app, ["graph", "--fixture", REVIEW_OVERRIDES, "--unreviewed", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert all(edge["review_state"] == "unreviewed" for edge in payload["edges"])


def test_overrides_export_and_apply_round_trip(tmp_path: Path) -> None:
    exported = tmp_path / "overrides.yaml"
    export_res = runner.invoke(
        app,
        ["graph", "overrides", "export", "--fixture", REVIEW_OVERRIDES, "--out", str(exported)],
    )
    assert export_res.exit_code == 0, export_res.output
    assert exported.exists()
    text = exported.read_text(encoding="utf-8")
    assert "format: perpetual-overrides" in text

    merged_out = tmp_path / "merged.yaml"
    apply_res = runner.invoke(
        app,
        [
            "graph",
            "overrides",
            "apply",
            str(exported),
            "--fixture",
            REVIEW_OVERRIDES,
            "--out",
            str(merged_out),
            "--json",
        ],
    )
    assert apply_res.exit_code == 0, apply_res.output
    summary = json.loads(apply_res.output)
    assert summary["applied_overrides"] >= 1
    assert summary["manifest_digest"].startswith("sha256:")
    assert merged_out.exists()


def test_overrides_apply_rejects_foreign_project(tmp_path: Path) -> None:
    exported = tmp_path / "overrides.yaml"
    runner.invoke(
        app,
        ["graph", "overrides", "export", "--fixture", REVIEW_OVERRIDES, "--out", str(exported)],
    )
    bad_res = runner.invoke(
        app,
        [
            "graph",
            "overrides",
            "apply",
            str(exported),
            "--fixture",
            REVIEW_OVERRIDES,
            "--project",
            "other-project",
        ],
    )
    assert bad_res.exit_code == 1
    assert "another project" in bad_res.output
