# `iac` package

**Owns:** modeled DR change sets, Jinja2 companion Terraform generation, and (in M2 P10) suggested edits and supplied-plan verification (spec §61–§62.1).
**Tracker:** P1c-01..P1c-03 (M0 PoC compile loop); P10 extends templates for v0.1.
**Depends on:** `graph`, `ids`, `models`, `recovery`, `rules`, `simulator`; Jinja2. Never imports `llm`.

## Files

| File | Responsibility |
|---|---|
| `poc.py` | `apply_poc_change_set`, `render_poc_terraform`, `run_poc_fix`, `PocFixResult`: applies the fixed PoC DR change set as a modeled planned snapshot with `planned_id(...)` canonical IDs, re-resolves mechanisms through `default_registry()`, re-simulates under `EvaluationKind.DESIGN`, and renders `versions.tf`, `kms.tf`, `ecr.tf`, `rds.tf`. |
| `templates/poc/*.tf.j2` | Jinja2 companion Terraform templates with pinned `hashicorp/aws ~> 5.80` provider, verified with `terraform fmt -check`. |

## Tests

`apps/api/tests/iac/test_poc_compile_loop.py` verifies `ecs-broken` → `ecs-remediated` re-simulation parity, `terraform fmt -check`, and `perpetual poc fix`.
