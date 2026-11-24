"""Graph snapshots, overrides and traversal helpers (spec §17, §18, §19.1, §23)."""

from perpetual.graph.manifest import (
    SnapshotManifest,
    build_snapshot_manifest,
    canonical_digest,
    canonical_json,
    config_digest,
    evaluation_input_digest,
)
from perpetual.graph.overrides import (
    GraphData,
    OverrideError,
    OverrideResult,
    Reproposal,
    apply_overrides,
    dump_overrides,
    edge_target,
    load_overrides,
    merge_overrides,
    parse_overrides,
)
from perpetual.graph.snapshot import DependencyGraph, GraphError, GroupMember, build_graph
from perpetual.graph.traversal import (
    ancestors_of,
    dependency_closure,
    detect_cycles,
    has_cycles,
    project_graph,
    shortest_dependency_path,
)

__all__ = [
    "DependencyGraph",
    "GraphData",
    "GraphError",
    "GroupMember",
    "OverrideError",
    "OverrideResult",
    "Reproposal",
    "SnapshotManifest",
    "ancestors_of",
    "apply_overrides",
    "build_graph",
    "build_snapshot_manifest",
    "canonical_digest",
    "canonical_json",
    "config_digest",
    "dependency_closure",
    "detect_cycles",
    "dump_overrides",
    "edge_target",
    "evaluation_input_digest",
    "has_cycles",
    "load_overrides",
    "merge_overrides",
    "parse_overrides",
    "project_graph",
    "shortest_dependency_path",
]
