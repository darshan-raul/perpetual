"""Two-pass failure simulator, scenarios, readiness and reason chains (spec §31, §43-§46)."""

from perpetual.simulator.engine import ReasonChain, SimulationResult, simulate_failure
from perpetual.simulator.impact import ImpactRecord, run_impact_pass
from perpetual.simulator.readiness import (
    EvaluationKind,
    FindingEffect,
    ReadinessInputs,
    ReadinessResult,
    compose_readiness,
)
from perpetual.simulator.recovery import ResourceSimulationResult, run_recovery_pass
from perpetual.simulator.scenarios import (
    AZFailure,
    FailureScenario,
    LogicalCorruption,
    RegionFailure,
    UnsupportedScenarioError,
    parse_scenario,
    seed_failed_resources,
)

__all__ = [
    "AZFailure",
    "EvaluationKind",
    "FailureScenario",
    "FindingEffect",
    "ImpactRecord",
    "LogicalCorruption",
    "ReadinessInputs",
    "ReadinessResult",
    "ReasonChain",
    "RegionFailure",
    "ResourceSimulationResult",
    "SimulationResult",
    "UnsupportedScenarioError",
    "compose_readiness",
    "parse_scenario",
    "run_impact_pass",
    "run_recovery_pass",
    "seed_failed_resources",
    "simulate_failure",
]
