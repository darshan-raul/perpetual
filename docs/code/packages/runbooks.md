# `runbooks` package

**Owns:** generated recovery scripts, prerequisite scripts, and explanatory runbooks (spec §63–§64). Perpetual generates and checks these artifacts and never executes them.
**Tracker:** P1c-04 (PoC Python failover script); P11 adds full runbooks and failback.
**Depends on:** Jinja2.

## Files

| File | Responsibility |
|---|---|
| `poc_script.py` | `render_poc_recovery_script`: renders a self-contained `uv run --script` Python failover script with `boto3` inline metadata. |
| `templates/failover.py.j2` | 3-step failover script (promote RDS replica, scale DR ECS service, check DR health) supporting `--dry-run`, verify-before-acting, and resumable checkpoint state. |

## Tests

`apps/api/tests/iac/test_poc_compile_loop.py` executes the generated script against `moto` (`@mock_aws`) for dry-run, live promotion/scaling, and resumable re-execution.
