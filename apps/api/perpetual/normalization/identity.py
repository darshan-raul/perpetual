"""Identity resolution across discovery sources (spec §15.1).

The same AWS resource can arrive from live AWS APIs, AWS Config, Resource
Explorer, and Terraform. This module merges those records into one canonical
`ResourceNode` using the four-step resolution order in spec §15.1:

1. ARN match.
2. Service-specific natural key (account + region + service + type + identifier).
3. Root/workspace-qualified Terraform address -> live resource ID mapping.
4. Unresolved: keep as a separate node (e.g. a planned Terraform resource).

When sources disagree on an attribute, the highest-precedence live source
(AWS API first) wins on the merged node, and every conflicting value is kept
as a separate `Evidence` record so callers can surface drift.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from perpetual.ids import AwsResourceId, parse
from perpetual.models.evidence import Evidence, SourceType
from perpetual.models.resource import ResourceNode, SourceReference

# Lower number = higher authority for live infrastructure configuration (spec §11, §15.1).
_SOURCE_PRECEDENCE: dict[SourceType, int] = {
    SourceType.AWS_API: 10,
    SourceType.AWS_CONFIG: 20,
    SourceType.RESOURCE_EXPLORER: 30,
    SourceType.KUBERNETES: 40,
    SourceType.TERRAFORM: 50,
    SourceType.USER_CONFIRMATION: 60,
    SourceType.CLOUDTRAIL: 70,
    SourceType.VPC_FLOW_LOGS: 75,
    SourceType.METRIC: 80,
    SourceType.INFERENCE: 90,
    SourceType.LLM_INFERENCE: 100,
}

_DEFAULT_PRECEDENCE = 999


@dataclass(frozen=True)
class AttributeConflict:
    """One disagreement between two sources describing the same resource."""

    resource_id: str
    attribute: str
    authoritative_source: SourceType
    authoritative_value: str
    conflicting_source: SourceType
    conflicting_value: str
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class IdentityResolutionResult:
    """Merged resources, ID remapping, and any cross-source attribute conflicts."""

    nodes: list[ResourceNode]
    id_remap: dict[str, str] = field(default_factory=dict)
    conflicts: list[AttributeConflict] = field(default_factory=list)
    conflict_evidence: list[Evidence] = field(default_factory=list)


class _UnionFind:
    """Small disjoint-set helper so transitive identity matches collapse cleanly."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, index: int) -> int:
        while self._parent[index] != index:
            self._parent[index] = self._parent[self._parent[index]]
            index = self._parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        root_l, root_r = self.find(left), self.find(right)
        if root_l != root_r:
            self._parent[root_r] = root_l


def resolve_identities(
    nodes: Sequence[ResourceNode],
    *,
    terraform_address_map: Mapping[str, str] | None = None,
) -> IdentityResolutionResult:
    """Merge duplicate resources across sources following spec §15.1."""
    if not nodes:
        return IdentityResolutionResult(nodes=[])

    groups = _group_nodes_by_identity(nodes, terraform_address_map or {})

    merged_nodes: list[ResourceNode] = []
    id_remap: dict[str, str] = {}
    conflicts: list[AttributeConflict] = []
    conflict_evidence: list[Evidence] = []

    for group in groups:
        merged, group_conflicts = _merge_group(group)
        merged_nodes.append(merged)
        for member in group:
            if member.id != merged.id:
                id_remap[member.id] = merged.id
        for conflict in group_conflicts:
            conflicts.append(conflict)
            conflict_evidence.extend(conflict.evidence)

    merged_nodes.sort(key=lambda n: n.id)
    conflicts.sort(key=lambda c: (c.resource_id, c.attribute, str(c.conflicting_source)))
    return IdentityResolutionResult(
        nodes=merged_nodes,
        id_remap=id_remap,
        conflicts=conflicts,
        conflict_evidence=conflict_evidence,
    )


def _group_nodes_by_identity(
    nodes: Sequence[ResourceNode],
    tf_map: Mapping[str, str],
) -> list[list[ResourceNode]]:
    """Group incoming nodes in strict §15.1 order: ARN -> natural key -> Terraform map."""
    uf = _UnionFind(len(nodes))
    by_arn: dict[str, int] = {}
    by_canonical_id: dict[str, int] = {}

    # Step 1: ARN match.
    for idx, node in enumerate(nodes):
        by_canonical_id.setdefault(node.id, idx)
        if node.arn:
            _link_key(uf, by_arn, node.arn.strip(), idx)

    # Step 2: Service-specific natural key (account + region + service + type + identifier).
    by_natural_key: dict[tuple[str, str, str, str, str], int] = {}
    for idx, node in enumerate(nodes):
        key = _natural_key(node)
        if key is not None:
            _link_key(uf, by_natural_key, key, idx)

    # Step 3: Terraform address -> live resource mapping (shared address or explicit map).
    _link_terraform_matches(uf, nodes, tf_map, by_canonical_id, by_arn)

    # Step 4: Unmatched nodes stay in singleton groups.
    buckets: dict[int, list[ResourceNode]] = {}
    for idx, node in enumerate(nodes):
        buckets.setdefault(uf.find(idx), []).append(node)
    return list(buckets.values())


def _link_key(uf: _UnionFind, index: dict[Any, int], key: Any, idx: int) -> None:
    if key in index:
        uf.union(index[key], idx)
    else:
        index[key] = idx


def _link_terraform_matches(
    uf: _UnionFind,
    nodes: Sequence[ResourceNode],
    tf_map: Mapping[str, str],
    by_canonical_id: Mapping[str, int],
    by_arn: Mapping[str, int],
) -> None:
    by_tf_address: dict[str, int] = {}
    for idx, node in enumerate(nodes):
        if node.terraform_address:
            _link_key(uf, by_tf_address, node.terraform_address, idx)

    for idx, node in enumerate(nodes):
        target = _lookup_terraform_target(node, tf_map)
        if target is None:
            continue
        target_idx = by_canonical_id.get(target)
        if target_idx is None:
            target_idx = by_arn.get(target.strip())
        if target_idx is not None:
            uf.union(target_idx, idx)


def _natural_key(node: ResourceNode) -> tuple[str, str, str, str, str] | None:
    if node.planned:
        return None
    parsed = parse(node.id)
    if not isinstance(parsed, AwsResourceId) or parsed.is_planned:
        return None
    return (
        parsed.account_id,
        parsed.region,
        parsed.service,
        parsed.resource_type,
        parsed.identifier,
    )


def _lookup_terraform_target(node: ResourceNode, tf_map: Mapping[str, str]) -> str | None:
    if node.id in tf_map:
        return tf_map[node.id]
    if node.terraform_address and node.terraform_address in tf_map:
        return tf_map[node.terraform_address]
    return None


def _node_precedence(node: ResourceNode) -> tuple[int, int]:
    planned_rank = 1 if node.planned else 0
    if not node.source_refs:
        return (planned_rank, _DEFAULT_PRECEDENCE)
    best = min(
        _SOURCE_PRECEDENCE.get(ref.source_type, _DEFAULT_PRECEDENCE) for ref in node.source_refs
    )
    return (planned_rank, best)


def _primary_source_type(node: ResourceNode) -> SourceType:
    if not node.source_refs:
        return SourceType.TERRAFORM if node.planned else SourceType.INFERENCE
    best = min(
        node.source_refs,
        key=lambda ref: _SOURCE_PRECEDENCE.get(ref.source_type, _DEFAULT_PRECEDENCE),
    )
    return best.source_type


def _primary_source_locator(node: ResourceNode) -> str:
    if not node.source_refs:
        return node.terraform_address or node.id
    best = min(
        node.source_refs,
        key=lambda ref: _SOURCE_PRECEDENCE.get(ref.source_type, _DEFAULT_PRECEDENCE),
    )
    return best.locator


def _merge_group(
    group: Sequence[ResourceNode],
) -> tuple[ResourceNode, list[AttributeConflict]]:
    if len(group) == 1:
        return group[0], []

    ordered = sorted(
        group,
        key=lambda n: (_node_precedence(n), -n.discovered_at.timestamp(), n.id),
    )
    primary = ordered[0]
    primary_source = _primary_source_type(primary)

    merged_tags = dict(primary.tags)
    merged_props = dict(primary.properties)
    merged_refs = _dedupe_source_refs([ref for node in ordered for ref in node.source_refs])
    typed_properties = primary.typed_properties
    conflicts: list[AttributeConflict] = []

    name = primary.name
    arn = primary.arn
    availability_zone = primary.availability_zone
    terraform_address = primary.terraform_address
    account_id = primary.account_id
    region = primary.region

    for secondary in ordered[1:]:
        sec_source = _primary_source_type(secondary)
        name = _merge_scalar(
            attribute="name",
            current=name,
            candidate=secondary.name,
            primary=primary,
            primary_source=primary_source,
            secondary=secondary,
            secondary_source=sec_source,
            conflicts=conflicts,
        )
        availability_zone = _merge_scalar(
            attribute="availability_zone",
            current=availability_zone,
            candidate=secondary.availability_zone,
            primary=primary,
            primary_source=primary_source,
            secondary=secondary,
            secondary_source=sec_source,
            conflicts=conflicts,
        )
        arn = arn or secondary.arn
        terraform_address = terraform_address or secondary.terraform_address
        account_id = account_id or secondary.account_id
        region = region or secondary.region
        _merge_tags(
            merged_tags=merged_tags,
            primary=primary,
            primary_source=primary_source,
            secondary=secondary,
            secondary_source=sec_source,
            conflicts=conflicts,
        )
        for prop_key, prop_val in secondary.properties.items():
            merged_props.setdefault(prop_key, prop_val)
        if typed_properties is None and secondary.typed_properties is not None:
            typed_properties = secondary.typed_properties
        else:
            _collect_typed_property_conflicts(
                primary_typed=typed_properties,
                primary=primary,
                primary_source=primary_source,
                secondary=secondary,
                secondary_source=sec_source,
                conflicts=conflicts,
            )

    merged = ResourceNode(
        id=primary.id,
        provider=primary.provider,
        service=primary.service,
        resource_type=primary.resource_type,
        account_id=account_id,
        region=region,
        availability_zone=availability_zone,
        name=name,
        arn=arn,
        tags=merged_tags,
        properties=merged_props,
        typed_properties=typed_properties,
        source_refs=merged_refs,
        terraform_address=terraform_address,
        planned=all(node.planned for node in ordered),
        discovered_at=max(node.discovered_at for node in ordered),
    )
    return merged, conflicts


def _merge_scalar(
    *,
    attribute: str,
    current: str | None,
    candidate: str | None,
    primary: ResourceNode,
    primary_source: SourceType,
    secondary: ResourceNode,
    secondary_source: SourceType,
    conflicts: list[AttributeConflict],
) -> str | None:
    if current is None:
        return candidate
    if candidate is not None and candidate != current:
        conflicts.append(
            _build_conflict(
                resource_id=primary.id,
                attribute=attribute,
                authoritative_node=primary,
                authoritative_source=primary_source,
                authoritative_value=current,
                conflicting_node=secondary,
                conflicting_source=secondary_source,
                conflicting_value=candidate,
            )
        )
    return current


def _merge_tags(
    *,
    merged_tags: dict[str, str],
    primary: ResourceNode,
    primary_source: SourceType,
    secondary: ResourceNode,
    secondary_source: SourceType,
    conflicts: list[AttributeConflict],
) -> None:
    for tag_key, tag_val in secondary.tags.items():
        if tag_key not in merged_tags:
            merged_tags[tag_key] = tag_val
        elif merged_tags[tag_key] != tag_val:
            conflicts.append(
                _build_conflict(
                    resource_id=primary.id,
                    attribute=f"tags.{tag_key}",
                    authoritative_node=primary,
                    authoritative_source=primary_source,
                    authoritative_value=merged_tags[tag_key],
                    conflicting_node=secondary,
                    conflicting_source=secondary_source,
                    conflicting_value=tag_val,
                )
            )


def _collect_typed_property_conflicts(
    *,
    primary_typed: Any,
    primary: ResourceNode,
    primary_source: SourceType,
    secondary: ResourceNode,
    secondary_source: SourceType,
    conflicts: list[AttributeConflict],
) -> None:
    secondary_typed = secondary.typed_properties
    if primary_typed is None or secondary_typed is None:
        return
    if type(primary_typed) is not type(secondary_typed):
        return
    primary_dump = primary_typed.model_dump(exclude_none=True)
    secondary_dump = secondary_typed.model_dump(exclude_none=True)
    for field_name in sorted(set(primary_dump) & set(secondary_dump)):
        if field_name in {"type_key", "unknown_fields"}:
            continue
        if primary_dump[field_name] != secondary_dump[field_name]:
            conflicts.append(
                _build_conflict(
                    resource_id=primary.id,
                    attribute=f"typed_properties.{field_name}",
                    authoritative_node=primary,
                    authoritative_source=primary_source,
                    authoritative_value=_summarize_value(primary_dump[field_name]),
                    conflicting_node=secondary,
                    conflicting_source=secondary_source,
                    conflicting_value=_summarize_value(secondary_dump[field_name]),
                )
            )


def _dedupe_source_refs(refs: Sequence[SourceReference]) -> list[SourceReference]:
    seen: set[tuple[SourceType, str, str | None]] = set()
    unique: list[SourceReference] = []
    for ref in refs:
        key = (ref.source_type, ref.locator, ref.scan_id)
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def _summarize_value(value: Any) -> str:
    text = repr(value) if not isinstance(value, str) else value
    return text[:197] + "..." if len(text) > 200 else text


def _evidence_id(resource_id: str, attribute: str, source_type: SourceType, value: str) -> str:
    digest = hashlib.sha256(
        f"{resource_id}|{attribute}|{source_type.value}|{value}".encode()
    ).hexdigest()[:12]
    return f"ev:conflict:{digest}"


def _build_conflict(
    *,
    resource_id: str,
    attribute: str,
    authoritative_node: ResourceNode,
    authoritative_source: SourceType,
    authoritative_value: str,
    conflicting_node: ResourceNode,
    conflicting_source: SourceType,
    conflicting_value: str,
) -> AttributeConflict:
    auth_ev = Evidence(
        id=_evidence_id(resource_id, attribute, authoritative_source, authoritative_value),
        source_type=authoritative_source,
        source=_primary_source_locator(authoritative_node),
        resource_id=resource_id,
        attribute=attribute,
        value_summary=authoritative_value,
        confidence=1.0 if authoritative_source is SourceType.AWS_API else 0.9,
        collected_at=authoritative_node.discovered_at,
    )
    conflict_ev = Evidence(
        id=_evidence_id(resource_id, attribute, conflicting_source, conflicting_value),
        source_type=conflicting_source,
        source=_primary_source_locator(conflicting_node),
        resource_id=resource_id,
        attribute=attribute,
        value_summary=conflicting_value,
        confidence=0.8,
        collected_at=conflicting_node.discovered_at,
    )
    return AttributeConflict(
        resource_id=resource_id,
        attribute=attribute,
        authoritative_source=authoritative_source,
        authoritative_value=authoritative_value,
        conflicting_source=conflicting_source,
        conflicting_value=conflicting_value,
        evidence=(auth_ev, conflict_ev),
    )
