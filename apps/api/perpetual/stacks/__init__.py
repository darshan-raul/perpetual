"""Stack grouping, services and RTO scope classification (spec §24, §24.1, §25)."""

from perpetual.stacks.scope import classify_resource_scope, classify_stack_scopes

__all__ = ["classify_resource_scope", "classify_stack_scopes"]
