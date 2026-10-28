"""`perpetual fixtures validate|schema`."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from perpetual.cli import app
from perpetual.fixtures import FIXTURES_DIR_ENV

REPO = Path(__file__).resolve().parents[4]
runner = CliRunner()


def test_validate_all_repository_fixtures() -> None:
    result = runner.invoke(
        app, ["fixtures", "validate", str(REPO / "fixtures/graphs/minimal.yaml")]
    )
    assert result.exit_code == 0, result.output
    assert "ok" in result.output


def test_validate_reports_problems_and_fails(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "format: perpetual-fixture\nversion: 1\nname: bad\ncaptured_at: 2026-10-28T12:00:00Z\n"
        "edges:\n  - id: e1\n    from_resource_id: x\n"
    )
    result = runner.invoke(app, ["fixtures", "validate", str(bad)])
    assert result.exit_code == 1
    assert "FAIL" in result.output
    assert "edges[0].to_resource_id: Field required" in result.output


def test_validate_with_no_fixtures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FIXTURES_DIR_ENV, str(tmp_path))
    result = runner.invoke(app, ["fixtures", "validate"])
    assert result.exit_code == 2
    assert "No fixtures found" in result.output


def test_schema_prints_json(tmp_path: Path) -> None:
    result = runner.invoke(app, ["fixtures", "schema"])
    assert result.exit_code == 0
    assert json.loads(result.output)["title"] == "Perpetual fixture v1"
    out = tmp_path / "schema.json"
    assert runner.invoke(app, ["fixtures", "schema", "--out", str(out)]).exit_code == 0
    assert json.loads(out.read_text())["title"] == "Perpetual fixture v1"
