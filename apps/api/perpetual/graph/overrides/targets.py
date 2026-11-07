"""Stable targets keep reviews independent of scan-generated edge IDs."""

import json

from perpetual.models import DependencyEdge
from perpetual.models.override import AddEdgePayload


def edge_target(edge: DependencyEdge | AddEdgePayload) -> str:
    """An unambiguous endpoint-and-type target for confirm/edit/add edge overrides.

    JSON escaping keeps slashes, colons, and quotes inside resource IDs safe.
    A rejection instead targets evidence.edge_fingerprint on the source edge.
    """
    return "edge:" + json.dumps(
        [edge.from_resource_id, edge.to_resource_id, edge.relationship_type.value],
        ensure_ascii=False,
        separators=(",", ":"),
    )
