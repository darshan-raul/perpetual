# `stacks` package

**Owns:** stack grouping, services, and RTO scope classification (spec §24, §24.1, §25).
**Tracker:** P1-03 (RTO scope); stack discovery lands in M1 P3.
**Depends on:** `config`, `graph`, `models`.

## Files

| File | Responsibility |
|---|---|
| `scope.py` | `classify_resource_scope`, `classify_stack_scopes`: classifies each stack resource as `in_scope` or `out_of_scope` using `rto_scope.yaml` type-key defaults (monitoring, logging, CI/CD) while honoring explicit `StackResource` overrides. |

## Tests

Covered in `apps/api/tests/simulator/test_simulator_core.py`.
