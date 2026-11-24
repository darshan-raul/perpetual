"""DRRulePack protocol, strict reproducibility check, and registry (spec §27.1, §28)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from perpetual.graph import DependencyGraph
from perpetual.models import MechanismKind, RecoveryMechanism, ResourceNode


class RulePackError(ValueError):
    """Invalid rule-pack registration or resolution input."""


@dataclass(frozen=True)
class ReproducibilityEvidence:
    """Strict §27.1 criteria for `MechanismKind.REBUILD_FROM_IAC`.

    A resource is reproducible only when ALL four technical conditions hold, OR
    when a user explicitly confirms reproducibility (`user_confirmed=True`). If
    any condition is missing or unproven, the mechanism must stay `unknown`.
    """

    has_iac_origin: bool = False
    no_hardcoded_primary_refs: bool = False
    dr_region_supported: bool = False
    dr_dependencies_resolve: bool = False
    user_confirmed: bool = False

    @property
    def is_reproducible(self) -> bool:
        """True only when every §27.1 reproducibility requirement is satisfied."""
        if self.user_confirmed:
            return True
        return (
            self.has_iac_origin
            and self.no_hardcoded_primary_refs
            and self.dr_region_supported
            and self.dr_dependencies_resolve
        )


@dataclass(frozen=True)
class AssessmentContext:
    """Read-only context passed to rule packs during mechanism resolution and assessment."""

    graph: DependencyGraph
    target_region: str
    target_account_id: str
    reproducibility: dict[str, ReproducibilityEvidence] = field(default_factory=dict)

    def is_reproducible(self, resource: ResourceNode) -> bool:
        """Check strict §27.1 reproducibility for `resource`."""
        evidence = self.reproducibility.get(resource.id)
        if evidence is None:
            return False
        # Even if caller flagged has_iac_origin=False, a terraform_address alone
        # is never enough without the other three §27.1 checks.
        return evidence.is_reproducible


@runtime_checkable
class DRRulePack(Protocol):
    """Per-service DR rule pack interface (spec §28).

    P1-02 implements `resolve_mechanism` on real rule-pack classes; P1-10 adds
    `recovery_actions`, P4 adds `assess`, and P9 adds `recovery_options` to the
    same classes.
    """

    service: str
    version: str

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        """Determine how `resource` is recovered in `context.target_region`."""
        ...


class RulePackRegistry:
    """Registry mapping canonical AWS service names to their `DRRulePack`."""

    def __init__(self) -> None:
        self._packs: dict[str, DRRulePack] = {}

    def register(self, pack: DRRulePack) -> None:
        """Register one rule pack by its canonical `service` name."""
        if not pack.service:
            raise RulePackError("rule pack service name must not be empty")
        if pack.service in self._packs:
            raise RulePackError(f"duplicate rule pack for service {pack.service!r}")
        self._packs[pack.service] = pack

    def get(self, service: str) -> DRRulePack | None:
        """Return the registered pack for `service`, or `None` if unmodeled."""
        return self._packs.get(service)

    def services(self) -> tuple[str, ...]:
        """Sorted canonical service names registered in this registry."""
        return tuple(sorted(self._packs))

    def versions(self) -> dict[str, str]:
        """Map of service name to pack version for `EvaluationInput.rule_pack_versions`."""
        return {service: self._packs[service].version for service in sorted(self._packs)}

    def resolve_mechanism(
        self,
        resource: ResourceNode,
        context: AssessmentContext,
    ) -> RecoveryMechanism:
        """Resolve one resource's DR mechanism using its service pack or safe fallback."""
        if resource.provider == "external":
            return RecoveryMechanism(
                id=f"mech:{resource.id}",
                primary_resource_id=resource.id,
                target_region=context.target_region,
                target_account_id=context.target_account_id,
                kind=MechanismKind.EXTERNAL,
                control_plane_dependent=False,
                confidence=1.0,
            )

        pack = self._packs.get(resource.service)
        if pack is not None:
            return pack.resolve_mechanism(resource, context)

        # Unmodeled service: never guess `none` or `live_counterpart`. Only strict
        # §27.1 reproducibility yields `rebuild_from_iac`; otherwise `unknown`.
        if context.is_reproducible(resource):
            return RecoveryMechanism(
                id=f"mech:{resource.id}",
                primary_resource_id=resource.id,
                target_region=context.target_region,
                target_account_id=context.target_account_id,
                kind=MechanismKind.REBUILD_FROM_IAC,
                control_plane_dependent=True,
                confidence=0.9,
            )
        return RecoveryMechanism(
            id=f"mech:{resource.id}",
            primary_resource_id=resource.id,
            target_region=context.target_region,
            target_account_id=context.target_account_id,
            kind=MechanismKind.UNKNOWN,
            control_plane_dependent=False,
            confidence=0.0,
        )

    def resolve_all(
        self,
        resources: Iterable[ResourceNode],
        context: AssessmentContext,
    ) -> dict[str, RecoveryMechanism]:
        """Resolve mechanisms for every resource, keyed by canonical resource ID."""
        resolved: dict[str, RecoveryMechanism] = {}
        for resource in resources:
            resolved[resource.id] = self.resolve_mechanism(resource, context)
        return resolved
