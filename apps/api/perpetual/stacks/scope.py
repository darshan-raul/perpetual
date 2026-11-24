"""RTO scope classification with config defaults and per-resource overrides (spec §24.1)."""

from __future__ import annotations

from perpetual.config import RtoScopeConfig
from perpetual.graph import DependencyGraph
from perpetual.models import ResourceNode, RtoScope, ScopeSource, StackResource


def classify_resource_scope(
    resource: ResourceNode,
    config: RtoScopeConfig,
    *,
    override: StackResource | None = None,
) -> tuple[RtoScope, ScopeSource]:
    """Return `(rto_scope, scope_source)` for one resource.

    An explicit `StackResource` entry (user override or rule-pack assignment)
    takes precedence over type-key config defaults. Monitoring, logging, and
    CI/CD type keys in `config.out_of_scope` default to `out_of_scope`.
    """
    if override is not None:
        return override.rto_scope, override.scope_source

    type_key = f"{resource.service}/{resource.resource_type}"
    if type_key in config.out_of_scope_type_keys:
        return RtoScope.OUT_OF_SCOPE, ScopeSource.RULE_DEFAULT
    return RtoScope.IN_SCOPE, ScopeSource.RULE_DEFAULT


def classify_stack_scopes(
    graph: DependencyGraph,
    stack_id: str,
    config: RtoScopeConfig,
) -> dict[str, tuple[RtoScope, ScopeSource]]:
    """Classify every resource in `graph` for `stack_id`, honoring stack overrides."""
    scopes: dict[str, tuple[RtoScope, ScopeSource]] = {}
    for resource_id, resource in graph.resources.items():
        override = graph.stack_resources.get((stack_id, resource_id))
        scopes[resource_id] = classify_resource_scope(resource, config, override=override)
    return scopes
