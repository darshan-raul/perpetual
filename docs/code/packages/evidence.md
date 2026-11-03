# `evidence` package

**Owns:** turning an edge's evidence into one confidence (with the breakdown behind it), and the evidence fingerprint that decides whether a rejected edge comes back.
**Spec:** §14.1, §22, §23. **Tracker:** P0-09 (edge resolvers arrive in P2b).
**Depends on:** `models`, `config`. **Used by:** the graph and review stages (P0-10, P0-11, P1-07), and later the edge resolvers.

## In one paragraph

An edge usually has several pieces of evidence: a Terraform reference, a security-group path, a CloudTrail call. Adding their confidences would overcount, because many come from the same underlying configuration. So each evidence kind belongs to a **correlation group** (from [`config`](config.md)); within a group only the strongest item counts, and the groups are combined with a pluggable function (`noisy_or` by default). The result is a `CombinedConfidence` with a per-group breakdown, so a reviewer can see why an edge scored what it did. The **fingerprint** is a hash of the edge's endpoints and the material facts in its evidence: a user's rejection is stored against it, and the edge is proposed again only when that fingerprint changes.

## Files

| File | What it holds |
|---|---|
| `combination.py` | `combine`, `group_of`, `noisy_or`, the `COMBINATIONS` registry, `CombinedConfidence`, `GroupContribution`, `UnknownEvidenceKindError` |
| `fingerprint.py` | `evidence_fingerprint`, `edge_fingerprint` |

## How combination works

```text
 edge evidence                       group_of(item, config.evidence)
 ─────────────                       ──────────────────────────────────────────────
 Evidence kind=security_group_path   ─> weights[kind] ─> (network_permissions, 0.75)
 Evidence kind=network_policy_…      ─> weights[kind] ─> (network_permissions, 0.70)
 Evidence kind=iam_resource_permission ─────────────────> (iam_permissions,     0.80)
 Evidence kind=None, source=user_confirmation, c=1.0 ───> (source:user_confirmation, 1.0)
 Evidence kind=made_up ──> not in config ──> UnknownEvidenceKindError (resolver bug)
                │
                ▼  within each group: maximum
 network_permissions   max(0.75, 0.70) = 0.75     evidence_ids (np, sg)
 iam_permissions       0.80                       evidence_ids (iam,)
 source:user_conf…     1.00                       evidence_ids (u1,)
                │
                ▼  across groups: COMBINATIONS[config.combination]   (noisy_or)
 1 - (1-0.75)(1-0.80)(1-1.00) = 1.0
                │
                ▼
 CombinedConfidence(confidence=1.0, function="noisy_or", groups=(…sorted by name…))
```

Rules behind each step:

- **Which value an item counts with.** A kind listed in config counts with the configured weight, so changing a weight in config changes every edge's confidence on the next evaluation, without a rescan. Only a user confirmation may have no kind; it counts with its own `confidence` in the group `source:user_confirmation`. Any other kind-less item raises `UnknownEvidenceKindError`, like an unlisted kind: a resolver that forgets `kind=` must not silently bypass the weights table, and LLM inference must never add confidence on its own (spec §2 rule 11).
- **Supporting-only kinds** (an SG rule open to `0.0.0.0/0`, IAM `Resource: "*"`) have weight 0: they add nothing to the number, but stay on the edge as evidence and as a basis.
- **No evidence** gives 0.0.
- **Order never matters**: groups are sorted by name and IDs within a group are sorted.

## How the fingerprint works

```text
 edge  from=svc-checkout  to=rds/db/checkout
   evidence: (terraform, env.DB_HOST, "matches endpoint")  id=ev-1, collected Mon
             (cloudtrail, None, "rds-db:connect")          id=ev-2, count=42
                │
                ▼ keep only the material facts, as a set, sorted
 {"from": "...svc-checkout", "to": "...rds/db/checkout",
  "evidence": [["cloudtrail", null, "rds-db:connect"],
               ["terraform", "env.DB_HOST", "matches endpoint"]]}
                │ compact JSON, UTF-8, sha256
                ▼
 sha256:3f9c…   ◄── a rejection is stored against this (P0-10)

 next scan, same facts (new evidence IDs, new times, new counts)  -> same fingerprint
                                                                     -> stays rejected
 next scan, a new fact or a changed value                          -> new fingerprint
                                                                     -> proposed again, linked
                                                                        to the old rejection
```

Included besides the evidence facts: the endpoints and the **relationship type**. Parallel typed edges between the same two resources are kept apart (§19.1), and one evidence item can back both `connects_to` and `encrypted_by`; without the type, rejecting one would reject both.

Left out on purpose: evidence IDs, collection times, observation windows and counts, confidences and the edge ID. They change from scan to scan without changing what the evidence says. `None` and `""` are different facts.

## Using it

```python
from perpetual.config import load_config
from perpetual.evidence import combine, edge_fingerprint

config = load_config().evidence
result = combine(edge.evidence, config)
result.confidence                  # 0.95
[(g.group, g.confidence) for g in result.groups]
result.confidence < config.review_confidence_threshold   # needs review? (gate in P1-07)

edge_fingerprint(edge)             # 'sha256:…'
```

## Rules it enforces, and why

| Rule | Where | Why (spec) |
|---|---|---|
| Within a correlation group take the maximum; across groups use the configured function | `combine` | Correlated evidence must not count twice (§22) |
| Configured kinds use configured weights; unknown kinds raise | `group_of` | "Weights should be configuration" (§22); an unlisted kind is a resolver bug |
| The combination function is chosen by name from a registry | `COMBINATIONS` | Pluggable, to tune against confirmed/rejected edges (§22) |
| Fingerprint = endpoints + sorted set of `(source_type, attribute, value_summary)` | `evidence_fingerprint` | §23 |

## Tests

`apps/api/tests/evidence/test_combination_and_fingerprint.py`: noisy-or; every configurable function is registered; correlated evidence takes the maximum; independent groups combine; permitted + observed beats either; configured weight wins; tuned weights apply; supporting-only adds nothing; only user confirmations may omit a kind (other sources, including LLM inference, raise); no evidence; unknown kind; order independence; fingerprint format, stability, what it ignores, order and duplicates, what changes it, endpoints, `None` vs `""`, edge fingerprint ignores ID and confidence; parallel typed edges get different fingerprints.

## Not here yet

- Edge resolvers that create evidence from Terraform, AWS APIs, CloudTrail and flow logs: P2b.
- Excluding ambiguous attribution from uplift: observations stay separate (`ResolvedObservation`), and resolvers must not turn ambiguous ones into exact evidence (P2b-09).
- Applying the review threshold to readiness (`graph_not_reviewed`): P1-07.
