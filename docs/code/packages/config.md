# `config` package

**Owns:** every number that tunes behaviour, as versioned YAML defaults loaded into typed models, with per-project overrides.
**Spec:** §19.1, §22, §23, §24.1, §31, §49.2, §59.1, §76.1; IMPL_PLAN D12. **Tracker:** P0-06.
**Depends on:** nothing else in Perpetual (an import rule enforces this); Pydantic and PyYAML. **Used by:** the evidence, stacks, rules, recovery and costing stages, as they are built.

## In one paragraph

Rule and engine code never hard-codes a weight, threshold or limit. The shipped defaults are YAML files in `config/defaults/`, one per section, each with its own `version`. `load_config()` reads them, merges a project's overrides on top and validates the result as a whole, so an override can't produce a weight above 1 or point at a correlation group that doesn't exist. Unknown keys are rejected, so a typo fails loudly. The loaded `Config` records which dotted paths an override changed, so results can show which values were not product defaults.

## Sections

| File | Model | Holds |
|---|---|---|
| `evidence.yaml` | `EvidenceConfig` | Weight and correlation group per evidence kind (§22), the combination function's name (`noisy_or`), and the review confidence threshold (§23) |
| `scoring.yaml` | `ScoringConfig` | Score weight per finding severity (§31). Descriptive only; readiness comes from the ordered table in §31 |
| `rto_scope.yaml` | `RtoScopeConfig` | Type keys out of RTO scope by default, grouped as monitoring, logging and CI/CD (§24.1) |
| `buffer.yaml` | `BufferConfig` | Contingency percent and the duration-catalog keys for handoff and stack validation (§49.2) |
| `freshness.yaml` | `FreshnessConfig` | Maximum ages for inventory, latest measurement and primary/DR skew (§76.1), as ISO 8601 durations |
| `limits.yaml` | `LimitsConfig` | Alternative-selection cap (§19.1); cost units: hours per month and maximum price age (§59.1) |

## Using it

```python
from perpetual.config import load_config, load_config_file

config = load_config()                                  # shipped defaults
config.evidence.weights["endpoint_string_match"].weight # 0.85
config.rto_scope.category_of("logs/log-group")          # OutOfScopeCategory.LOGGING

config = load_config({"buffer": {"contingency_percent": 20}})
config.overridden_paths                                 # ['buffer.contingency_percent']

config = load_config_file(Path("perpetual-config.yaml"))  # same, from YAML
```

**Merge rule:** mappings merge key by key, so changing one evidence weight keeps its group and every other weight. Anything else (numbers, strings, lists) replaces the default. Lists are replaced on purpose: merging them would make it impossible to remove a type key from the out-of-scope list. An override that equals the default isn't recorded as a change.

## Rules it enforces, and why

| Rule | Why |
|---|---|
| Weights are between 0 and 1; supporting-only evidence weighs 0 | Broad SG ranges and `Resource: "*"` only support other evidence (§22) |
| Every weight names a declared correlation group; groups don't repeat | Within a group the maximum is taken, so a typo'd group would count correlated evidence twice (§22) |
| The combination function is a known name | It is pluggable (§22): the evidence package (P0-09) registers implementations |
| Every severity has a weight; weights are ≤ 0 and less severe never costs more | A missing severity would silently score 0 |
| Type keys are `SERVICE/TYPE` and appear in one category, once | They must match the keys in resource IDs and typed properties |
| Durations and limits are positive | A zero freshness age would make every fact stale |

## Relation to other packages

`config` may not import `models`, so `FreshnessConfig` has the same fields as `models.FreshnessPolicy`, and callers build one from the other (`FreshnessPolicy.model_validate(config.freshness.model_dump())`). A test keeps the two in step.

Not here yet: the duration catalog (P1-09) and the price catalog (costing). Where project overrides live in `perpetual.yaml` is decided with the project file loader.

## Tests

`apps/api/tests/config/test_config.py`: defaults load with the spec values; out-of-scope categories; freshness builds the domain policy; overrides change one value and record it; equal overrides aren't recorded; lists replace; invalid overrides fail with clear messages (unknown section or key, weight range, unknown group, supporting-only weight, repeated groups, unknown combination, severity order, bad or repeated type keys, negative or zero values); override files, including empty, non-mapping, invalid and missing ones.
