# `rules` package

**Owns:** per-service `DRRulePack` implementations and cross-cutting rules (spec §27.1, §28, §28.1).
**Tracker:** P1-01, P1-02 (mechanism resolution); P4 adds findings; P9 adds options.
**Depends on:** `graph`, `models`. Never imports `collectors` or `llm` (import-linter enforced).

## Files

| File | Responsibility |
|---|---|
| `protocol.py` | `DRRulePack` protocol, `AssessmentContext`, `ReproducibilityEvidence` (strict §27.1 criteria for `rebuild_from_iac`), `RulePackRegistry`, `RulePackError`. |
| `first_slice.py` | 9 real `DRRulePack` classes (`Route53RulePack`, `ELBRulePack`, `ECSRulePack`, `ECRRulePack`, `SecretsManagerRulePack`, `KMSRulePack`, `RDSRulePack`, `S3RulePack`, `LogsRulePack`) and `default_registry()`. |
| `cross/__init__.py` | `CrossCuttingRule` protocol and canonical `CROSS_CUTTING_RULE_IDS` skeleton for P4-04. |

## Tests

`apps/api/tests/rules/test_rule_packs_and_mechanisms.py` checks registry contracts, strict §27.1 reproducibility, RDS snapshot restore, external resources, and exact overlay parity against `ecs-broken.yaml` and `ecs-remediated.yaml`.
