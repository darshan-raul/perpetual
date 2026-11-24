"""P1c PoC compile loop tests: modeled fix, Terraform fmt, moto dry-run & CLI (M0 gate)."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import boto3  # type: ignore[import-untyped]
import pytest
from moto import mock_aws
from typer.testing import CliRunner

from perpetual.cli import app
from perpetual.fixtures import load_fixture
from perpetual.graph import build_graph
from perpetual.iac import run_poc_fix
from perpetual.models import StackState
from perpetual.runbooks import render_poc_recovery_script
from perpetual.simulator import EvaluationKind

REPO = Path(__file__).resolve().parents[4]
ECS_BROKEN = REPO / "fixtures/graphs/ecs-broken.yaml"
runner = CliRunner()


def test_poc_fix_re_simulation_matches_ecs_remediated() -> None:
    fixture = load_fixture(ECS_BROKEN)
    graph = build_graph(
        resources=fixture.resources,
        edges=fixture.edges,
        groups=fixture.groups,
        mechanisms=fixture.mechanisms,
        stacks=fixture.stacks,
        stack_resources=fixture.stack_resources,
        stack_services=fixture.stack_services,
    )
    result = run_poc_fix(graph, stack_id="checkout", requirement=fixture.requirements[0])

    assert result.before_simulation.stack_state is StackState.UNAVAILABLE
    assert result.after_simulation.stack_state is StackState.RECOVERABLE
    assert result.after_simulation.readiness.evaluation_kind is EvaluationKind.DESIGN
    assert result.after_plan.rto.expected_seconds is not None
    assert set(result.terraform_files) == {"versions.tf", "kms.tf", "ecr.tf", "rds.tf"}


def test_poc_cli_writes_artifacts_and_terraform_passes_fmt(tmp_path: Path) -> None:
    out_dir = tmp_path / "poc-out"
    res = runner.invoke(
        app,
        ["poc", "fix", "--fixture", str(ECS_BROKEN), "--out", str(out_dir), "--json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["before_state"] == "UNAVAILABLE"
    assert payload["after_state"] == "RECOVERABLE"
    assert payload["after_evaluation_kind"] == "design"

    tf_dir = out_dir / "terraform"
    script_path = out_dir / "recovery" / "failover.py"
    summary_path = out_dir / "SUMMARY.md"
    assert (tf_dir / "versions.tf").exists()
    assert (tf_dir / "kms.tf").exists()
    assert (tf_dir / "ecr.tf").exists()
    assert (tf_dir / "rds.tf").exists()
    assert script_path.exists()
    assert summary_path.exists()

    # Generated Python script compiles cleanly.
    compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec")

    # Generated Terraform passes `terraform fmt -check` when terraform is installed.
    terraform_bin = shutil.which("terraform")
    if terraform_bin is not None:
        fmt = subprocess.run(
            [terraform_bin, "fmt", "-check", "-diff", str(tf_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert fmt.returncode == 0, f"terraform fmt failed:\n{fmt.stdout}\n{fmt.stderr}"


@mock_aws
def test_generated_recovery_script_dry_run_and_resumable_execution_on_moto(tmp_path: Path) -> None:
    dr_region = "ap-south-2"
    rds = boto3.client("rds", region_name=dr_region)
    ecs = boto3.client("ecs", region_name=dr_region)

    # Seed a primary + read replica in moto RDS and a 0-task DR ECS service.
    rds.create_db_instance(
        DBInstanceIdentifier="checkout-orders",
        DBInstanceClass="db.r6g.large",
        Engine="postgres",
    )
    rds.create_db_instance_read_replica(
        DBInstanceIdentifier="checkout-orders-dr",
        SourceDBInstanceIdentifier="checkout-orders",
    )
    ecs.create_cluster(clusterName="checkout-dr")
    ecs.register_task_definition(
        family="checkout-api",
        containerDefinitions=[{"name": "api", "image": "nginx:latest", "memory": 128}],
    )
    ecs.create_service(
        cluster="checkout-dr",
        serviceName="checkout-api-dr",
        taskDefinition="checkout-api",
        desiredCount=0,
    )

    script_text = render_poc_recovery_script(
        stack_name="checkout",
        primary_region="ap-south-1",
        target_region=dr_region,
        rds_replica_id="checkout-orders-dr",
        ecs_cluster="checkout-dr",
        ecs_service="checkout-api-dr",
        ecs_target_desired_count=4,
    )
    script_path = tmp_path / "failover.py"
    script_path.write_text(script_text, encoding="utf-8")

    spec = importlib.util.spec_from_file_location("generated_failover", script_path)
    assert spec is not None
    assert spec.loader is not None
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    state_file = tmp_path / "failover-state.json"

    # 1. Dry run: verifies resources without mutating AWS state.
    dry_result = module.run_failover(
        dry_run=True, skip_http=True, state_file=state_file, rds_client=rds, ecs_client=ecs
    )
    assert dry_result == {
        "promote_rds": "dry_run",
        "scale_ecs": "dry_run",
        "health_check": "dry_run",
    }
    svc = ecs.describe_services(cluster="checkout-dr", services=["checkout-api-dr"])["services"][0]
    assert svc["desiredCount"] == 0
    assert not state_file.exists()

    # 2. Live execution against moto: promotes replica and scales ECS to 4.
    live_result = module.run_failover(
        dry_run=False, skip_http=True, state_file=state_file, rds_client=rds, ecs_client=ecs
    )
    assert live_result == {
        "promote_rds": "promoted",
        "scale_ecs": "scaled",
        "health_check": "dry_run",
    }
    svc_after = ecs.describe_services(cluster="checkout-dr", services=["checkout-api-dr"])[
        "services"
    ][0]
    assert svc_after["desiredCount"] == 4

    # 3. Resumable second run: skips already-completed steps cleanly.
    resume_result = module.run_failover(
        dry_run=False, skip_http=True, state_file=state_file, rds_client=rds, ecs_client=ecs
    )
    assert resume_result == {
        "promote_rds": "already_promoted",
        "scale_ecs": "already_scaled",
        "health_check": "dry_run",
    }


@pytest.mark.parametrize("bad_fixture", ["nonexistent-fixture"])
def test_poc_cli_handles_missing_fixture(bad_fixture: str) -> None:
    res = runner.invoke(app, ["poc", "fix", "--fixture", bad_fixture])
    assert res.exit_code == 1
    assert "error" in res.output
