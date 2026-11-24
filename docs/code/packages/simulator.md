# `simulator` package

**Owns:** failure scenario dispatch, two-pass failure simulation, §31 readiness composition, and failure reason chains (spec §31, §43–§46).
**Tracker:** P1-04 through P1-08.
**Depends on:** `config`, `graph`, `models`, `rules`, `stacks`. Never imports `collectors` or `importers`.

## Pipeline

```text
FailureScenario (RegionFailure)
   -> Pass 1: impact.run_impact_pass (fixed-point, skips structural/replication/backup & out-of-scope)
   -> Pass 2: recovery.run_recovery_pass (memoised, cycle-safe over DR overlay & ALL/ANY/quorum groups)
   -> engine._build_reason_chains (root -> leaf BLOCKED/UNKNOWN path)
   -> readiness.compose_readiness (ordered 4-row §31 decision table)
   -> SimulationResult
```

## Files

| File | Responsibility |
|---|---|
| `scenarios.py` | `FailureScenario`, `RegionFailure`, `AZFailure`, `LogicalCorruption`, `UnsupportedScenarioError`, `parse_scenario`, `seed_failed_resources`. |
| `impact.py` | `ImpactRecord`, `run_impact_pass` (fixed-point loop, out-of-scope isolation, confidence thresholds, ALL/ANY/quorum). |
| `recovery.py` | `ResourceSimulationResult`, `run_recovery_pass` (memoised cycle-safe DR-overlay evaluation, `CTRL-PLANE-001` for `us-east-1`, external posture). |
| `readiness.py` | `EvaluationKind`, `FindingEffect`, `ReadinessInputs`, `ReadinessResult`, `compose_readiness`. |
| `engine.py` | `ReasonChain`, `SimulationResult`, `simulate_failure`. |

## Tests

`apps/api/tests/simulator/test_simulator_core.py` verifies §87 (`ecs-broken`), §88 (`ecs-remediated`), `cycle.yaml`, unsupported scenarios, review gate (`graph_not_reviewed`), quorum groups, and §31 precedence.
