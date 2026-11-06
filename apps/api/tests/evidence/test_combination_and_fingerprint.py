"""Evidence combination with correlation groups, and evidence fingerprints (spec §22, §23)."""

from datetime import timedelta
from typing import Any, get_args

import pytest

from perpetual.config import EvidenceConfig, load_config
from perpetual.evidence import (
    COMBINATIONS,
    UnknownEvidenceKindError,
    combine,
    edge_fingerprint,
    evidence_fingerprint,
    noisy_or,
)
from perpetual.models import Basis, Evidence, RelationshipType, SourceType
from tests.models.builders import NOW, make_evidence
from tests.models.test_model_edge import make_edge

SVC = "aws://123456789012/ap-south-1/ecs/service/checkout"
DB = "aws://123456789012/ap-south-1/rds/db/checkout"


@pytest.fixture
def config() -> EvidenceConfig:
    return load_config().evidence


def fp(source: str, target: str, evidence: list[Evidence]) -> str:
    return evidence_fingerprint(source, target, RelationshipType.CONNECTS_TO, evidence)


def item(evidence_id: str, kind: str | None = None, **extra: Any) -> Any:
    return make_evidence(id=evidence_id, kind=kind, **extra)


# --- combination -------------------------------------------------------------------


def test_noisy_or() -> None:
    assert noisy_or([]) == 0.0
    assert noisy_or([0.5, 0.5]) == pytest.approx(0.75)
    assert noisy_or([1.0, 0.2]) == 1.0


def test_every_configurable_function_is_registered() -> None:
    allowed = set(get_args(EvidenceConfig.model_fields["combination"].annotation))
    assert allowed <= set(COMBINATIONS)


def test_correlated_evidence_takes_the_maximum(config: EvidenceConfig) -> None:
    # SG path and NetworkPolicy match are both network permissions: they may come
    # from the same configuration, so together they count as 0.75, not more.
    result = combine(
        [item("sg", "security_group_path"), item("np", "network_policy_service_match")], config
    )
    assert result.confidence == pytest.approx(0.75)
    assert [(g.group, g.evidence_ids) for g in result.groups] == [
        ("network_permissions", ("np", "sg"))
    ]


def test_independent_groups_combine(config: EvidenceConfig) -> None:
    evidence = [
        item("sg", "security_group_path"),
        item("iam", "iam_resource_permission"),
        item("ct", "cloudtrail_mapped_principal"),
    ]
    result = combine(evidence, config)
    assert result.confidence == pytest.approx(1 - 0.25 * 0.20 * 0.05)
    assert [g.group for g in result.groups] == [
        "cloudtrail",
        "iam_permissions",
        "network_permissions",
    ]
    assert result.function == "noisy_or"


def test_permitted_plus_observed_is_stronger_than_either(config: EvidenceConfig) -> None:
    permitted = combine([item("sg", "security_group_path")], config).confidence
    observed = combine([item("fl", "flow_log_resolved_flow")], config).confidence
    both = combine(
        [item("sg", "security_group_path"), item("fl", "flow_log_resolved_flow")], config
    ).confidence
    assert both > max(permitted, observed)


def test_configured_weight_wins_over_the_items_own_confidence(config: EvidenceConfig) -> None:
    result = combine([item("ep", "endpoint_string_match", confidence=0.1)], config)
    assert result.confidence == pytest.approx(0.85)


def test_tuned_weights_take_effect_without_a_rescan() -> None:
    tuned = load_config({"evidence": {"weights": {"endpoint_string_match": {"weight": 0.5}}}})
    assert combine([item("ep", "endpoint_string_match")], tuned.evidence).confidence == 0.5


def test_supporting_only_evidence_adds_nothing(config: EvidenceConfig) -> None:
    alone = combine([item("wide", "security_group_open_range")], config)
    assert alone.confidence == 0.0
    with_iam = combine(
        [item("wide", "security_group_open_range"), item("iam", "iam_resource_permission")], config
    )
    assert with_iam.confidence == pytest.approx(0.80)


def test_a_user_confirmation_without_a_kind_counts_by_its_confidence(
    config: EvidenceConfig,
) -> None:
    user = item(
        "u1", source_type=SourceType.USER_CONFIRMATION, basis=Basis.ASSERTED, confidence=1.0
    )
    result = combine([item("tf", "terraform_reference"), user], config)
    assert [(g.group, g.confidence) for g in result.groups] == [
        ("source:user_confirmation", 1.0),
        ("terraform", 1.0),
    ]
    assert result.confidence == 1.0


@pytest.mark.parametrize("source", [SourceType.TERRAFORM, SourceType.LLM_INFERENCE])
def test_other_evidence_without_a_kind_is_an_error(
    config: EvidenceConfig, source: SourceType
) -> None:
    # A forgotten kind must not bypass the weights table, and LLM output must not
    # add confidence by itself (spec §2 rule 11).
    with pytest.raises(UnknownEvidenceKindError, match="has no kind"):
        combine([item("x", source_type=source, confidence=0.9)], config)


def test_no_evidence_is_no_confidence(config: EvidenceConfig) -> None:
    result = combine([], config)
    assert (result.confidence, result.groups) == (0.0, ())


def test_unknown_kind_is_an_error(config: EvidenceConfig) -> None:
    with pytest.raises(UnknownEvidenceKindError, match="unknown kind 'made_up'"):
        combine([item("x", "made_up")], config)


def test_order_does_not_matter(config: EvidenceConfig) -> None:
    evidence = [item("sg", "security_group_path"), item("ct", "cloudtrail_mapped_principal")]
    assert combine(evidence, config) == combine(list(reversed(evidence)), config)


# --- fingerprints ------------------------------------------------------------------


def test_fingerprint_format_and_stability() -> None:
    evidence = [item("a", attribute="env.DB_HOST", value_summary="matches endpoint")]
    first = fp(SVC, DB, evidence)
    assert first.startswith("sha256:")
    assert len(first) == len("sha256:") + 64
    assert fp(SVC, DB, evidence) == first


def test_fingerprint_ignores_what_changes_every_scan() -> None:
    before = [item("ev-1", attribute="env.DB_HOST", value_summary="match", confidence=0.85)]
    after = [
        item(
            "ev-99",
            attribute="env.DB_HOST",
            value_summary="match",
            confidence=0.5,
            collected_at=NOW + timedelta(days=1),
        )
    ]
    assert fp(SVC, DB, before) == fp(SVC, DB, after)


def test_fingerprint_ignores_order_and_duplicates() -> None:
    a = item("a", attribute="x", value_summary="1")
    b = item("b", attribute="y", value_summary=None)
    duplicate = item("c", attribute="x", value_summary="1")
    assert fp(SVC, DB, [a, b]) == fp(SVC, DB, [b, duplicate, a])


@pytest.mark.parametrize(
    "changed",
    [
        {"attribute": "env.CACHE_HOST"},
        {"value_summary": "different"},
        {"source_type": SourceType.KUBERNETES},
    ],
)
def test_fingerprint_changes_when_evidence_materially_changes(changed: dict[str, Any]) -> None:
    base = {"attribute": "env.DB_HOST", "value_summary": "match"}
    original = fp(SVC, DB, [item("a", **base)])
    assert fp(SVC, DB, [item("a", **(base | changed))]) != original


def test_fingerprint_depends_on_endpoints_and_new_evidence() -> None:
    evidence = [item("a", attribute="x")]
    assert fp(SVC, DB, evidence) != fp(DB, SVC, evidence)
    more = [*evidence, item("b", attribute="y")]
    assert fp(SVC, DB, evidence) != fp(SVC, DB, more)


def test_none_and_empty_string_are_different_facts() -> None:
    assert fp(SVC, DB, [item("a", attribute=None)]) != fp(SVC, DB, [item("a", attribute="")])


def test_edge_fingerprint_ignores_id_and_confidence() -> None:
    edge = make_edge()
    renamed = edge.model_copy(update={"id": "edge-2", "confidence": 0.5})
    assert edge_fingerprint(edge) == edge_fingerprint(renamed)
    assert edge_fingerprint(edge) == evidence_fingerprint(
        edge.from_resource_id, edge.to_resource_id, edge.relationship_type, edge.evidence
    )


def test_parallel_typed_edges_have_different_fingerprints() -> None:
    # Spec §19.1 keeps parallel typed edges; one shared evidence item must not make
    # a rejection of `encrypted_by` also reject `connects_to` between the same nodes.
    connects = make_edge(relationship_type=RelationshipType.CONNECTS_TO)
    encrypted = connects.model_copy(
        update={"id": "edge-2", "relationship_type": RelationshipType.ENCRYPTED_BY}
    )
    assert edge_fingerprint(connects) != edge_fingerprint(encrypted)


def test_fingerprint_preserves_persisted_hash_format() -> None:
    # Rejections refer to these digests. Refactoring sorting or JSON encoding must
    # preserve existing fingerprints, including nulls, empty strings and Unicode.
    facts = [(None, None), ("", ""), ("=prefix", "café"), ("env.DB_HOST", "match")]
    evidence = [
        make_evidence(id=f"ev-{index}", attribute=attribute, value_summary=summary)
        for index, (attribute, summary) in enumerate(facts)
    ]
    expected = "sha256:868df86b2d77245a6e329ac7a83a96a4e4924faeeedd2665ca1b53e735d3af33"
    assert fp("service", "database", evidence) == expected
    assert fp("service", "database", list(reversed(evidence))) == expected
