"""Evaluation inputs, verification reports, drills and operator access
(spec §28.1, §53, §56.3, §61.1)."""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from perpetual.models import (
    DeploymentPrerequisite,
    DRDrill,
    EvaluationInput,
    OperatorAccessProfile,
    PrerequisiteStatus,
    Readiness,
    VerificationReport,
    combined_prerequisite_status,
)
from tests.models.builders import NOW

D1 = "sha256:" + "a" * 64
D2 = "sha256:" + "b" * 64


def evaluation(**overrides: Any) -> EvaluationInput:
    fields: dict[str, Any] = {
        "id": "eval-1",
        "stack_id": "checkout",
        "failure_scenario": "region:ap-south-1",
        "primary_snapshot_id": "snap-p",
        "primary_inventory_completed_at": NOW,
        "dr_snapshot_id": "snap-dr",
        "dr_inventory_completed_at": NOW,
        "graph_revision": 3,
        "override_revision": 1,
        "group_revision": 0,
        "requirement_id": "req-1",
        "requirement_revision": 2,
        "engine_version": "0.0.1",
        "config_digest": D1,
        "duration_catalog_digest": D2,
        "freshness_policy_version": "1",
        "evaluated_at": NOW,
    }
    fields.update(overrides)
    return EvaluationInput(**fields)


def prerequisite(**overrides: Any) -> DeploymentPrerequisite:
    fields: dict[str, Any] = {
        "id": "pre-1",
        "kind": "image_present",
        "description": "checkout-api image replicated to DR ECR",
        "affected_resource_ids": ["aws://1/ap-south-2/ecr/repository/checkout-api"],
        "owner": "user pipeline",
        "required_evidence": "image digest present in DR ECR",
    }
    fields.update(overrides)
    return DeploymentPrerequisite(**fields)


def report(**overrides: Any) -> VerificationReport:
    fields: dict[str, Any] = {
        "id": "ver-1",
        "dr_spec_id": "spec-1",
        "approved_digest": D1,
        "tree_digest": D2,
        "saved_plan_digest": D1,
        "mode": "full",
        "static_checks": "pass",
        "design_verification": "pass",
        "prerequisites": [prerequisite()],
        "created_at": NOW,
    }
    fields.update(overrides)
    return VerificationReport(**fields)


# --- evaluation input --------------------------------------------------------------


def test_digests_have_one_format() -> None:
    with pytest.raises(ValidationError):
        evaluation(config_digest="a" * 64)
    with pytest.raises(ValidationError):
        evaluation(config_digest="sha256:" + "A" * 64)


def test_dr_snapshot_and_its_inventory_time_go_together() -> None:
    with pytest.raises(ValidationError, match="set together"):
        evaluation(dr_inventory_completed_at=None)
    built = evaluation(dr_snapshot_id=None, dr_inventory_completed_at=None)
    assert built.dr_snapshot_id is None


def test_inputs_used_are_sorted_and_listed_once() -> None:
    a = {"kind": "skill", "id": "rds-replica", "digest": D1}
    b = {"kind": "assumption", "id": "a-1", "digest": D2}
    assert [ref.id for ref in evaluation(inputs_used=[a, b]).inputs_used] == ["a-1", "rds-replica"]
    with pytest.raises(ValidationError, match="listed once"):
        evaluation(inputs_used=[a, a])


def test_iac_baseline_or_companion_design_not_both() -> None:
    baseline = {
        "repository_base_commit": "abc123",
        "tree_digest": D1,
        "roots": [{"path": "infra/prod"}],
    }
    companion = {"template_digest": D1, "input_digest": D2}
    assert evaluation(iac_baseline=baseline).iac_baseline is not None
    with pytest.raises(ValidationError, match="not both"):
        evaluation(iac_baseline=baseline, companion_design=companion)


def test_iac_baseline_roots_are_distinct() -> None:
    root = {"path": "infra/prod", "workspace": "default"}
    with pytest.raises(ValidationError, match="appears once"):
        evaluation(
            iac_baseline={
                "repository_base_commit": "abc123",
                "tree_digest": D1,
                "roots": [root, root],
            }
        )


# --- prerequisites -----------------------------------------------------------------


def test_settled_prerequisites_cite_evidence() -> None:
    for status in ("satisfied", "failed"):
        with pytest.raises(ValidationError, match="cites its evidence"):
            prerequisite(status=status)
    assert prerequisite(status="satisfied", evidence_ids=["ev-1"]).evidence_ids == ["ev-1"]


def test_combined_status_is_worst_first() -> None:
    satisfied = prerequisite(status="satisfied", evidence_ids=["ev"])
    pending = prerequisite()
    unknown = prerequisite(status="unknown")
    failed = prerequisite(status="failed", evidence_ids=["ev"])
    assert combined_prerequisite_status([]) is PrerequisiteStatus.SATISFIED
    assert combined_prerequisite_status([satisfied, pending]) is PrerequisiteStatus.PENDING
    assert combined_prerequisite_status([pending, unknown]) is PrerequisiteStatus.UNKNOWN
    assert combined_prerequisite_status([unknown, failed]) is PrerequisiteStatus.FAILED


# --- verification report -----------------------------------------------------------


def test_passing_design_with_pending_steps_is_labelled_pending() -> None:
    built = report()
    assert built.deployment_prerequisites is PrerequisiteStatus.PENDING
    assert built.label == "design verified — deployment and observation pending"
    assert built.observed_readiness is Readiness.UNKNOWN


def test_static_checks_only_cannot_pass_design() -> None:
    with pytest.raises(ValidationError, match="only in full mode"):
        report(mode="static_checks_only", saved_plan_digest=None)
    built = report(mode="static_checks_only", saved_plan_digest=None, design_verification="unknown")
    assert built.label == "static checks only"


def test_full_mode_names_its_saved_plan() -> None:
    with pytest.raises(ValidationError, match="names the saved plan"):
        report(saved_plan_digest=None)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"static_checks": "fail"}, "static checks didn't"),
        ({"unverified_change_ids": ["change-3"]}, "unverified changes"),
        (
            {"prerequisites": [prerequisite(status="failed", evidence_ids=["ev"])]},
            "failed prerequisite",
        ),
    ],
)
def test_design_cannot_pass_with(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        report(**overrides)
    assert report(**overrides, design_verification="fail").label == "unverified"


def test_observed_ready_needs_every_prerequisite_satisfied() -> None:
    with pytest.raises(ValidationError, match="observed READY"):
        report(observed_readiness="READY")
    done = prerequisite(status="satisfied", evidence_ids=["ev-scan"])
    assert report(prerequisites=[done], observed_readiness="READY").observed_readiness == "READY"


def test_prerequisite_ids_are_unique() -> None:
    with pytest.raises(ValidationError, match="unique"):
        report(prerequisites=[prerequisite(), prerequisite()])


# --- drills ------------------------------------------------------------------------


def test_drill_times_are_ordered_and_unmeasured_values_stay_unknown() -> None:
    fields: dict[str, Any] = {
        "id": "drill-1",
        "stack_id": "checkout",
        "source": "recovery_script_log",
        "source_reference": "logs/failover-2026-10-28.jsonl",
        "started_at": NOW,
        "completed_at": NOW + timedelta(minutes=24),
        "status": "succeeded",
    }
    built = DRDrill(**fields)
    assert built.achieved_rto_seconds is None
    with pytest.raises(ValidationError, match="completed_at must not be before"):
        DRDrill(**fields | {"completed_at": NOW - timedelta(seconds=1)})


# --- operator access ---------------------------------------------------------------


def test_operator_access_matches_the_spec_example() -> None:
    profile = OperatorAccessProfile.model_validate(
        {
            "identity": {
                "source": "iam_identity_center",
                "home_region": "ap-south-1",
                "replica_regions": [],
            },
            "break_glass": {
                "method": "iam_role",
                "description": "role in DR account, credentials in offline vault",
            },
            "network": [
                {"target": "eks_api_private", "path": "vpn", "terminates_in": "ap-south-1"}
            ],
            "tools": {"uv": "0.8", "kubectl": "1.33"},
        }
    )
    assert profile.identity is not None
    assert profile.identity.replica_regions == []


def test_unknown_replicas_differ_from_no_replicas() -> None:
    profile = OperatorAccessProfile.model_validate(
        {"identity": {"source": "iam_identity_center", "home_region": "ap-south-1"}}
    )
    assert profile.identity is not None
    assert profile.identity.replica_regions is None


def test_identity_regions_apply_only_to_identity_center() -> None:
    with pytest.raises(ValidationError, match="only to IAM Identity Center"):
        OperatorAccessProfile.model_validate(
            {"identity": {"source": "external_idp", "home_region": "ap-south-1"}}
        )


def test_home_region_is_not_its_own_replica() -> None:
    with pytest.raises(ValidationError, match="not one of its own replicas"):
        OperatorAccessProfile.model_validate(
            {
                "identity": {
                    "source": "iam_identity_center",
                    "home_region": "ap-south-1",
                    "replica_regions": ["ap-south-1"],
                }
            }
        )


def test_network_targets_are_declared_once_and_typos_fail() -> None:
    path = {"target": "eks_api_private", "path": "vpn", "terminates_in": "ap-south-1"}
    with pytest.raises(ValidationError, match="declared once"):
        OperatorAccessProfile.model_validate({"network": [path, path]})
    with pytest.raises(ValidationError):
        OperatorAccessProfile.model_validate({"break_glas": {"method": "x", "description": "y"}})
