"""Failure scenario type hierarchy and dispatch (spec §43)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from perpetual.graph import DependencyGraph
from perpetual.models import DomainModel, NonEmptyStr


class UnsupportedScenarioError(ValueError):
    """Raised when a scenario kind is defined in the model but not supported in v0.1."""


class FailureScenario(DomainModel):
    """Base failure scenario. The simulator dispatches on `kind`."""

    kind: NonEmptyStr


class RegionFailure(FailureScenario):
    """Complete unavailability of one AWS Region (supported in v0.1)."""

    kind: Literal["region"] = "region"
    region: NonEmptyStr


class AZFailure(FailureScenario):
    """Single Availability Zone failure (defined for later milestones)."""

    kind: Literal["az"] = "az"
    availability_zone: NonEmptyStr


class LogicalCorruption(FailureScenario):
    """Data corruption/ransomware/bad deploy (defined for later milestones)."""

    kind: Literal["logical_corruption"] = "logical_corruption"
    resource_ids: list[NonEmptyStr] = Field(min_length=1)
    detected_after_seconds: int = Field(ge=0)


def parse_scenario(text: str) -> FailureScenario:
    """Parse a CLI scenario string such as `region:ap-south-1` or `az:ap-south-1a`."""
    kind, sep, value = text.partition(":")
    if not sep or not value:
        raise ValueError(
            f"invalid scenario {text!r}; expected '<kind>:<target>' (e.g. region:ap-south-1)"
        )
    if kind == "region":
        return RegionFailure(region=value)
    if kind == "az":
        return AZFailure(availability_zone=value)
    raise UnsupportedScenarioError(f"scenario kind {kind!r} is not supported in v0.1")


def seed_failed_resources(graph: DependencyGraph, scenario: FailureScenario) -> set[str]:
    """Return resource IDs directly inside `scenario`'s failure blast radius.

    Dispatches on `scenario.kind`. Global and external resources are not seeded
    directly by a Region failure.
    """
    if scenario.kind == "region" and isinstance(scenario, RegionFailure):
        return {
            resource_id
            for resource_id, node in graph.resources.items()
            if node.region == scenario.region
        }
    if scenario.kind in {"az", "logical_corruption"}:
        raise UnsupportedScenarioError(
            f"failure scenario {scenario.kind!r} is not supported in v0.1"
        )
    raise UnsupportedScenarioError(f"unknown failure scenario kind {scenario.kind!r}")
