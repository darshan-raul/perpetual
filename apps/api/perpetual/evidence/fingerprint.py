"""Evidence fingerprints (spec §23).

A user rejection is stored against a fingerprint, so a rejected inferred edge is
not recreated on every scan. If a later scan produces a different fingerprint, the
evidence "materially changed" and the edge is proposed again, linked to the
earlier rejection.

The fingerprint is a stable hash of the edge endpoints and relationship type plus
the sorted set of `(source_type, attribute, value_summary)` over its evidence. It
deliberately leaves out what changes on every scan without changing what the
evidence says: evidence IDs, collection times, observation counts and windows,
confidences and the edge ID.

The relationship type is part of the fingerprint because parallel typed edges
between the same two resources are kept apart (spec §19.1): one piece of evidence
can back both `connects_to` and `encrypted_by`, and rejecting one must not reject
the other. A resolver that later re-types an edge is making a different claim, so
it is proposed again (decision log, 2026-11-03).
"""

import hashlib
import json
from collections.abc import Iterable

from perpetual.models import DependencyEdge, Evidence, RelationshipType


def evidence_fingerprint(
    from_resource_id: str,
    to_resource_id: str,
    relationship_type: RelationshipType,
    evidence: Iterable[Evidence],
) -> str:
    """`sha256:<hex>` over the endpoints, relationship type and the evidence's material facts."""
    facts = sorted(
        {(item.source_type.value, item.attribute, item.value_summary) for item in evidence},
        # None sorts before any string, so ordering never depends on Python's tuple rules.
        key=lambda fact: tuple("" if part is None else f"={part}" for part in fact),
    )
    canonical = json.dumps(
        {
            "from": from_resource_id,
            "to": to_resource_id,
            "relationship": relationship_type.value,
            "evidence": facts,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def edge_fingerprint(edge: DependencyEdge) -> str:
    return evidence_fingerprint(
        edge.from_resource_id, edge.to_resource_id, edge.relationship_type, edge.evidence
    )
