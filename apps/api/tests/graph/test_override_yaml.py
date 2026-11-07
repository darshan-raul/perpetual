"""Override documents are project-scoped, lossless, and safe to import repeatedly."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from perpetual.graph.overrides import (
    GraphData,
    OverrideError,
    apply_overrides,
    dump_overrides,
    load_overrides,
    merge_overrides,
    parse_overrides,
)
from perpetual.models import GraphOverride, OverrideKind, OverrideStatus


@pytest.fixture
def override() -> GraphOverride:
    return GraphOverride(
        id="rejection",
        project_id="p1",
        kind=OverrideKind.REJECT_EDGE,
        target="sha256:" + "a" * 64,
        payload={},
        reason="reviewed café dependency",
        author="operator",
        created_at=datetime(2026, 11, 7, tzinfo=UTC),
        status=OverrideStatus.ORPHANED,
    )


def test_yaml_round_trip_keeps_all_metadata_and_orphans(
    override: GraphOverride, tmp_path: Path
) -> None:
    text = dump_overrides([override], project_id="p1")
    assert "café" in text
    assert parse_overrides(text, project_id="p1") == [override]
    path = tmp_path / "overrides.yaml"
    path.write_text(text, encoding="utf-8")
    assert load_overrides(path, project_id="p1") == [override]
    assert dump_overrides(load_overrides(path, project_id="p1"), project_id="p1") == text


def test_export_order_is_deterministic(override: GraphOverride) -> None:
    other = override.model_copy(update={"id": "another"})
    assert dump_overrides([override, other], project_id="p1") == dump_overrides(
        [other, override], project_id="p1"
    )


def test_import_is_idempotent_and_does_not_trust_cached_status(override: GraphOverride) -> None:
    active = override.model_copy(update={"status": OverrideStatus.ACTIVE})
    assert merge_overrides([override], [active], project_id="p1") == [override]
    imported = parse_overrides(dump_overrides([active], project_id="p1"), project_id="p1")
    result = apply_overrides(GraphData(), imported, project_id="p1")
    assert result.overrides[0].status is OverrideStatus.ORPHANED


def test_import_preserves_existing_records_and_adds_new_ones(override: GraphOverride) -> None:
    other = override.model_copy(update={"id": "z-new"})
    merged = merge_overrides([override], [other], project_id="p1")
    assert merged == [override, other]
    assert merge_overrides(merged, [other], project_id="p1") == merged


def test_import_refuses_conflicting_content_under_an_existing_id(override: GraphOverride) -> None:
    changed = override.model_copy(update={"reason": "different decision"})
    with pytest.raises(OverrideError, match="different content"):
        merge_overrides([override], [changed], project_id="p1")


def test_cross_project_document_and_rows_are_rejected(override: GraphOverride) -> None:
    text = dump_overrides([override], project_id="p1")
    with pytest.raises(OverrideError, match="another project"):
        parse_overrides(text, project_id="p2")
    document = yaml.safe_load(text)
    document["overrides"][0]["project_id"] = "p2"
    with pytest.raises(OverrideError, match="another project"):
        parse_overrides(yaml.safe_dump(document), project_id="p1")
    with pytest.raises(OverrideError, match="another project"):
        dump_overrides([override], project_id="p2")


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        "overrides: []",
        "format: [unclosed",
        "!!python/object/apply:os.system ['echo unsafe']",
        "format: perpetual-overrides\nversion: 2\nproject_id: p1\noverrides: []",
        "format: perpetual-overrides\nversion: 1\nproject_id: p1\nextra: true",
    ],
)
def test_malformed_or_unsupported_yaml_is_refused(text: str) -> None:
    with pytest.raises(OverrideError):
        parse_overrides(text, project_id="p1")


def test_duplicate_override_ids_are_refused(override: GraphOverride) -> None:
    document = yaml.safe_load(dump_overrides([override], project_id="p1"))
    document["overrides"].append(document["overrides"][0])
    with pytest.raises(OverrideError, match="duplicate override"):
        parse_overrides(yaml.safe_dump(document), project_id="p1")


def test_invalid_payload_is_refused_before_application(override: GraphOverride) -> None:
    document = yaml.safe_load(dump_overrides([override], project_id="p1"))
    document["overrides"][0]["payload"] = {"confidence": 1}
    with pytest.raises(OverrideError, match="Extra inputs"):
        parse_overrides(yaml.safe_dump(document), project_id="p1")


def test_unreadable_and_non_utf8_files_raise_override_error(tmp_path: Path) -> None:
    with pytest.raises(OverrideError, match="can't read"):
        load_overrides(tmp_path / "absent.yaml", project_id="p1")
    path = tmp_path / "binary.yaml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(OverrideError, match="can't read"):
        load_overrides(path, project_id="p1")


def test_empty_document_is_valid() -> None:
    assert parse_overrides(dump_overrides([], project_id="p1"), project_id="p1") == []


def test_merge_revalidates_mutated_payloads(override: GraphOverride) -> None:
    override.payload["unrecognized"] = True
    with pytest.raises(OverrideError, match="Extra inputs"):
        merge_overrides([], [override], project_id="p1")
