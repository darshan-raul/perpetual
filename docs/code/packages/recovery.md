# `recovery` package

**Owns:** versioned duration catalog, recovery actions, DAG builder, plan buffer, critical-path RTO, target comparison, and bounded alternative-group path selection (spec §19.1, §47–§52).
**Tracker:** P1-09 through P1-14, P1-18.
**Depends on:** `config`, `graph`, `models`, `simulator`, `stacks`; NetworkX.

## Files

| File | Responsibility |
|---|---|
| `catalog.py` | `DurationCatalog`, `load_duration_catalog` reading `config/defaults/duration_catalog.yaml`; volumetric buckets, per-resource overrides, generic fallback actions, `None` (UNKNOWN) on missing entries. |
| `actions.py` | `RecoveryPhase`, `AutomationLevel`, `RecoveryAction`, `actions_for_mechanism`. |
| `planner.py` | `build_recovery_dag`, `plan_stack_recovery`, `compare_target`, `RecoveryPlan`, `RtoBreakdown`, `PlanError` (phase barriers + refined prerequisites, `decide` and `stack_validation`, handoff + contingency buffer, topological longest-path RTO). |
| `selection.py` | `SelectedPathResult`, `select_recovery_paths` (bounded search over ALL/ANY/quorum groups capped by `alternative_selection_cap`, shared-prerequisite deduplication, non-optimal/infeasible reporting). |

## Tests

`apps/api/tests/recovery/test_rto_and_plan.py` (spec §93 `40 / 48 / 49.5` tests, catalog, UNKNOWN propagation, DAG cycles, CLI) and `apps/api/tests/recovery/test_selected_paths_and_persistence.py` (selected-path and P1-15 persistence regressions).
