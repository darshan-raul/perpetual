"""Fixture format v1: expansion, validation, cross-references, lookup and schema
(spec §15, §15.1, §15.2, §19.1, §90.1, §104)."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from perpetual.fixtures import (
    FIXTURE_PROJECT_ID,
    FIXTURES_DIR_ENV,
    FixtureError,
    check_references,
    fixture_json_schema,
    fixture_names,
    load_fixture,
    parse_fixture,
    resolve_fixture,
)

REPO = Path(__file__).resolve().parents[4]
GRAPHS = REPO / "fixtures" / "graphs"
SVC = "aws://123456789012/ap-south-1/ecs/service/checkout"
DB = "aws://123456789012/ap-south-1/rds/db/checkout"


@pytest.fixture
def raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((GRAPHS / "minimal.yaml").read_text())
    return data


def problems(raw: dict[str, Any]) -> list[str]:
    """Every reported problem as 'path: message', from parsing or cross-references."""
    try:
        fixture = parse_fixture(raw)
    except FixtureError as error:
        return [str(issue) for issue in error.issues]
    return [str(issue) for issue in check_references(fixture)]


def test_every_fixture_in_the_repository_is_valid() -> None:
    names = fixture_names(REPO)
    assert "minimal" in names
    for name in names:
        load_fixture(GRAPHS / f"{name}.yaml")


# --- expansion ---------------------------------------------------------------------


def test_resource_fields_come_from_the_id(raw: dict[str, Any]) -> None:
    fixture = parse_fixture(raw)
    db = fixture.resources[1]
    assert (db.provider, db.account_id, db.region, db.service, db.resource_type) == (
        "aws",
        "123456789012",
        "ap-south-1",
        "rds",
        "db",
    )
    assert not db.planned
    assert db.discovered_at == fixture.captured_at
    assert fixture.edges[0].evidence[0].collected_at == fixture.captured_at


def test_a_value_that_contradicts_the_id_is_reported(raw: dict[str, Any]) -> None:
    raw["resources"][1]["region"] = "ap-south-2"
    raw["resources"][1]["service"] = "aurora"
    assert problems(raw) == [
        "resources[1].region: is 'ap-south-2' but the id says 'ap-south-1'",
        "resources[1].service: is 'aurora' but the id says 'rds'",
    ]


def test_planned_global_and_external_ids(raw: dict[str, Any]) -> None:
    raw["resources"] += [
        {"id": "aws://123456789012/ap-south-2/rds/db/tf:infra-prod:default:aws_db_instance.dr"},
        {"id": "aws://123456789012/global/route53/hostedzone/Z123"},
        {"id": "external://payments-gateway/stripe", "resource_type": "saas"},
    ]
    planned, zone, external = parse_fixture(raw).resources[2:]
    assert planned.planned
    assert planned.terraform_address == "aws_db_instance.dr"
    assert zone.region == "global"
    assert (external.provider, external.service, external.region) == (
        "external",
        "payments-gateway",
        None,
    )


def test_a_live_flag_on_a_planned_id_is_reported(raw: dict[str, Any]) -> None:
    raw["resources"].append(
        {"id": "aws://123456789012/ap-south-2/rds/db/tf:r:w:aws_db_instance.dr", "planned": False}
    )
    assert problems(raw) == ["resources[2].planned: is False but the id says True"]


def test_a_bad_id_is_reported_with_its_path(raw: dict[str, Any]) -> None:
    raw["resources"][0]["id"] = "aws://1/ap-south-1/ecs/service/checkout"
    found = problems(raw)
    assert found[0].startswith("resources[0].id: account must be 12 digits")


def test_overrides_get_the_fixture_project_and_time(raw: dict[str, Any]) -> None:
    raw["overrides"] = [
        {
            "id": "ov-1",
            "kind": "confirm_edge",
            "target": "checkout-needs-db",
            "payload": {},
            "author": "user",
        }
    ]
    override = parse_fixture(raw).overrides[0]
    assert override.project_id == FIXTURE_PROJECT_ID
    assert override.created_at == parse_fixture(raw).captured_at


def test_raw_data_is_not_changed(raw: dict[str, Any]) -> None:
    before = copy.deepcopy(raw)
    parse_fixture(raw)
    assert raw == before


# --- structure ---------------------------------------------------------------------


def test_model_errors_are_all_reported_with_paths(raw: dict[str, Any]) -> None:
    raw["edges"][0]["confidence"] = 2
    raw["stacks"][0]["criticality"] = "extreme"
    found = problems(raw)
    assert any(item.startswith("edges[0].confidence:") for item in found)
    assert any(item.startswith("stacks[0].criticality:") for item in found)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"format": "other"}, "format:"),
        ({"version": 2}, "version:"),
        ({"captured_at": "2026-10-28T12:00:00"}, "captured_at:"),
        ({"resourcez": []}, "resourcez: Extra inputs are not permitted"),
    ],
)
def test_header_and_unknown_keys(raw: dict[str, Any], change: dict[str, Any], message: str) -> None:
    raw.update(change)
    assert any(item.startswith(message) for item in problems(raw))


def test_not_a_mapping() -> None:
    with pytest.raises(FixtureError, match="mapping at the top level"):
        parse_fixture(["a"])


def test_bad_files(tmp_path: Path) -> None:
    with pytest.raises(FixtureError, match="can't read"):
        load_fixture(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("resources: [unclosed\n")
    with pytest.raises(FixtureError, match="not valid YAML"):
        load_fixture(bad)


# --- cross-references --------------------------------------------------------------


def test_missing_references_are_reported(raw: dict[str, Any]) -> None:
    raw["edges"][0]["to_resource_id"] = "aws://123456789012/ap-south-1/sqs/queue/gone"
    raw["mechanisms"][0]["counterpart_resource_id"] = "aws://123456789012/ap-south-2/rds/db/x"
    raw["requirements"][0]["stack_id"] = "other"
    raw["stacks"][0]["service_ids"] = ["api"]
    assert problems(raw) == [
        "edges[0].to_resource_id: no resource 'aws://123456789012/ap-south-1/sqs/queue/gone'",
        "mechanisms[0].counterpart_resource_id: no resource 'aws://123456789012/ap-south-2/rds/db/x'",
        "stacks[0].service_ids[0]: no service 'api'",
        "requirements[0].stack_id: no stack 'other'",
    ]


def test_duplicate_ids(raw: dict[str, Any]) -> None:
    raw["resources"].append(raw["resources"][0])
    assert problems(raw) == [f"resources: id {SVC!r} appears 2 times"]


def test_group_members_start_at_the_dependent_and_appear_once(raw: dict[str, Any]) -> None:
    group = {
        "id": "g1",
        "dependent_resource_id": DB,
        "member_edge_ids": ["checkout-needs-db", "nope"],
        "mode": "any",
        "scope": "primary",
    }
    raw["groups"] = [
        group,
        {
            **group,
            "id": "g2",
            "dependent_resource_id": SVC,
            "member_edge_ids": ["checkout-needs-db"],
        },
    ]
    assert problems(raw) == [
        "groups[0].member_edge_ids[0]: edge 'checkout-needs-db' does not start at the dependent",
        "groups[0].member_edge_ids[1]: no edge 'nope'",
        "groups[1].member_edge_ids[0]: edge 'checkout-needs-db' is already in group 'g1'",
    ]


def test_stack_resources_must_belong_to_their_stack(raw: dict[str, Any]) -> None:
    raw["resources"].append({"id": "aws://123456789012/ap-south-1/sqs/queue/orders"})
    member = {
        "resource_id": "aws://123456789012/ap-south-1/sqs/queue/orders",
        "rto_scope": "in_scope",
        "scope_source": "rule_default",
    }
    raw["stack_resources"] = [{**member, "stack_id": "checkout"}, {**member, "stack_id": "other"}]
    assert problems(raw) == [
        "stack_resources[0].resource_id: not a member of stack 'checkout'",
        "stack_resources[1].stack_id: no stack 'other'",
    ]


def test_facts_name_existing_coverage(raw: dict[str, Any]) -> None:
    raw["facts"] = [
        {
            "kind": "capability",
            "id": "f1",
            "account_id": "123456789012",
            "region": "ap-south-2",
            "collected_at": "2026-10-28T12:00:00Z",
            "coverage_id": "cov-x",
            "capability": "service:rds",
            "status": "available",
            "source": "api",
        }
    ]
    assert problems(raw) == ["facts[0].coverage_id: no coverage 'cov-x'"]


def test_overrides_may_target_missing_resources(raw: dict[str, Any]) -> None:
    # An orphaned override is a valid state (spec §23), not a fixture error.
    raw["overrides"] = [
        {
            "id": "ov-1",
            "kind": "reject_edge",
            "target": "gone-edge",
            "payload": {},
            "author": "u",
            "status": "orphaned",
        }
    ]
    assert problems(raw) == []


# --- lookup and schema -------------------------------------------------------------


def test_resolve_by_name_path_and_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_fixture("minimal", REPO / "apps") == GRAPHS / "minimal.yaml"
    assert resolve_fixture(str(GRAPHS / "minimal.yaml")) == GRAPHS / "minimal.yaml"
    (tmp_path / "graphs").mkdir()
    (tmp_path / "graphs" / "mine.yaml").write_text("")
    monkeypatch.setenv(FIXTURES_DIR_ENV, str(tmp_path))
    assert resolve_fixture("mine") == tmp_path / "graphs" / "mine.yaml"
    assert fixture_names() == ["mine"]
    with pytest.raises(FixtureError, match="no fixture with this name"):
        resolve_fixture("missing")


def test_committed_schema_is_current() -> None:
    committed = json.loads((REPO / "fixtures" / "schema" / "fixture-v1.schema.json").read_text())
    assert committed == fixture_json_schema(), "run: perpetual fixtures schema --out ..."


def test_schema_marks_derived_fields_optional() -> None:
    defs = fixture_json_schema()["$defs"]
    assert defs["ResourceNode"]["required"] == ["id"]
    assert "collected_at" not in defs["Evidence"]["required"]
    assert "project_id" not in defs["GraphOverride"]["required"]
