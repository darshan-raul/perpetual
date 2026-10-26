> **Perpetual Engineering Specification (Revision 4)** — Part V — IaC Transformation, Verification & Runbooks (§61–§64)  
> [↑ Spec Overview & Index](../../spec.md) · [← 04-recovery-and-optimizer.md](04-recovery-and-optimizer.md) · [06-security-and-llm.md →](06-security-and-llm.md)

---

# 61. IaC Transformation

Perpetual implements an approved DR spec by changing the user's own infrastructure code. It does not write a separate DR codebase unless there is no code to change (section 62.1).

In scope for v0.1:

```text
Terraform       .tf and .tfvars files in the declared root modules and local modules
Kubernetes      plain manifests, Kustomize overlays, Helm values files (and chart
                templates when the chart lives in the repository)
```

Never in scope: Terraform state, remote modules from registries, generated files, CI pipeline definitions.

### Mapping resources to code

Before editing, Perpetual maps each resource in the DR spec to the code that defines it:

- Terraform: resource address -> file and block, from `terraform show -json` plus the configuration's source locations;
- Kubernetes: object identity (kind, namespace, name) -> manifest file, from scanning the declared paths and rendering Kustomize or Helm.

Resources with no code location are reported. Their changes go to manual steps, or to companion code (section 62.1) if the user chooses.

### Transformation agent

A LangGraph agent (section 69.2) does the work in a separate git worktree on a new branch `perpetual/dr/<stack>/<timestamp>`. The user's checkout is never modified.

```text
locate -> plan edits -> edit -> static checks -> plan and import -> verify
                ^                                                     |
                +---------------- failures (bounded retries) ---------+
                                                                      |
                                                                  package
```

Agent tools are an allowlist:

```text
read, search, edit and create files under the declared IaC paths
terraform fmt | init -backend=false | validate | plan -out | show -json
# Backend initialization for planning is a trusted runner operation, not an agent command.
kustomize build | helm template | kubeconform
load_skill | search_knowledge_base | get_stack_context
web_search | web_fetch  (sanitized queries only; persists fetched docs to KB)
```

Never available: `terraform apply`, `destroy`, `import`, `state`, `kubectl apply` or any command that changes cloud or cluster resources. Agent file access is confined to declared IaC paths in the worktree. Tool execution has only the read mounts, private scratch space and network capabilities specified below; agents cannot widen them.

### Enforced execution boundary

A command allowlist is necessary but insufficient: allowed tools can execute plugins/programs and read credentials. A trusted runner, separate from the agent, enforces isolation before executing any repository-controlled tool:

- Use an OS sandbox or isolated container with no host home, SSH agent, Docker socket or ambient credential/config mounts. Only the worktree's approved inputs and pinned dependencies are readable, declared IaC outputs are writable, and private temporary plan/cache files are isolated. Resolve real paths and reject symlink escapes; do not execute a shell or accept arbitrary command flags/environment.
- Provision reviewed provider/module versions from a checksum-verified lock/manifest. An agent cannot add providers, executables, module sources or relax policies. Reject executable data sources (`external`), provisioners, unapproved credential helpers, Helm plugins and Kustomize exec plugins before execution. Unsupported dependencies produce an explicit verification limitation, not an unsandboxed retry.
- Supply narrowly scoped, short-lived read-only cloud credentials through the runner only, never the model or persisted agent state. Deny infrastructure mutation and secret/application-data retrieval. Backend state access is sensitive read access; trusted initialization uses pinned configuration and cannot migrate or write remote state. Run planning with locking disabled (`-lock=false`) under read-only credentials and compare backend lineage/serial/digest before and after. A concurrent backend change invalidates the run; do not acquire write permissions as a fallback. If this read-only workflow is unsupported, require an attributable supplied plan or static-only checking.
- Deny network by default. Broker only required AWS/backend endpoints and approved artifact downloads; documentation and LLM tools use separate brokers. Terraform subprocesses cannot use the agent's LLM/web channels or arbitrary endpoints. Restrict subprocess capabilities, CPU, memory, output size and elapsed time; terminate descendants on cancellation.
- Scrub tool output before model feedback/checkpointing; raw state, saved plans, secrets and environment values never enter prompts/logs. Keep sensitive scratch files private and delete them after sanitized import or on failure. Record tool/input hashes and enforced capabilities in the verification report.

If the platform cannot enforce these controls, offer static analysis or a supplied-plan analysis with limitations; do not run plan or repository executables on the host as a fallback. Hostile fixtures must attempt external-program execution, unapproved providers/plugins, symlink escape, ambient credential reads, network exfiltration and cloud mutation, and prove denial. P10 isolation is a prerequisite to the transformation agent, not a P12-only audit.

Retries default to 3 per DR spec change.

---

# 61.1 Verification

A change is evaluated against the same engine that found the problem, with distinct evidence stages:

1. Static checks: `terraform fmt -check`, `terraform validate`, `kubeconform` on rendered manifests, a secret scanner on the diff, and a check that only allowed paths changed.
2. Planned graph: the isolated runner saves `terraform plan -out=<file>` and imports `terraform show -json <file>` with rendered Kubernetes objects using the authoritative snapshot rules in 15.4. Check approval and provenance under 56.3.
3. Re-assessment and re-simulation of the stack on the planned graph: rule packs, DR overlay, Region-failure simulation, recovery DAG, RTO, RPO, cost.
4. Design acceptance: every approved change is represented; no unresolved recovery blockers; all enforced RTO/RPO/budget comparisons are PASS under section 31; the evaluated assumptions match the approved design. "No worse than predicted" never substitutes for meeting a target. Any changed design requires renewed approval.

Every report separates `static_checks = pass | fail | incomplete`, `design_verification = pass | fail | unknown`, `deployment_prerequisites = pending | satisfied | failed | unknown`, and `observed_readiness` (31, or UNKNOWN when no matching live evaluation exists). A passing design is labeled "design verified — deployment and observation pending". It is not proof that the current stack is READY, and a model-based RTO is not a drill-proven RTO (53).

For not-yet-created resources, deterministic estimators may use versioned catalog assumptions for RTO/RPO/cost; label each estimate modeled and record its inputs. If no defensible estimator exists, design verification stays unknown. Plans cannot prove image digests are present, initial data copies have completed, secret values are populated, quotas have increased, or a new replica is healthy. Record these as typed deployment prerequisites with IDs, affected resources, owner, required evidence, status and checks for a later rescan. Such prerequisites may accompany a conditional passing design; known impossible prerequisites or a missing estimator cannot. No operational check is silently marked PASS merely because its configuration exists.

After the user's pipeline deploys, a fresh matching scan must establish operational prerequisites, measurements, coverage and review gates before observed readiness can become READY. Configuration drift from the verified tree or unresolved manual steps prevents that promotion. Tests distinguish passing design with pending seed/copy steps, unknown future lag, failed deployment prerequisites and a fully observed remediated stack.

When backend credentials or an enforceable runner are unavailable, or a supplied plan has no valid provenance, static checking may parse supported literal HCL and render only with isolated approved tools. Unknown expressions remain unknown; do not build a Terraform interpreter. Label this "static checks only" with design verification UNKNOWN, never "verified statically" or ready. A supplied plan with matching provenance can undergo full design verification without executing Terraform locally.

Failures go back to the agent as sanitized structured feedback (which check failed, on which resource, with the finding or simulation path). If retries run out, a reviewable branch may still be produced but is marked **unverified**, with failed/unknown checks and prerequisites listed. Security or approval invalidation stops execution; it must not be retried with weaker controls. Only design-pass artifacts carry a design-verified label; delivery retains the exact tree/report digest from 56.3.

---

# 62. Change Delivery

Output of a transformation:

- a git branch with one commit per DR spec change, in the DR spec's order;
- a pull request through `gh` or `glab` when the user enables it, otherwise the branch and a patch file;
- a description containing: the DR spec summary, before and after stack RTO, RPO and monthly cost, the verification report, files changed, the apply order, and manual steps.

Perpetual never merges, never pushes to a protected branch and never applies. The user's normal review and pipeline apply the change.

Changes that cannot be expressed as code (quota increases, account creation, one-off data seeding) are listed as manual steps and copied into the failover runbook prerequisites (section 63).

---

# 62.1 Companion Fallback

When no IaC repository is declared, or LLM features are disabled, Perpetual generates deterministic companion DR Terraform from templates, as in revision 3:

```text
generated/
  dr/
    versions.tf  providers.tf  network.tf  rds.tf  ecs.tf  ec2.tf  lambda.tf
    sqs_sns.tf   ecr.tf        secrets.tf  waf.tf  logs.tf route53.tf  outputs.tf
```

Generated configuration:

- is formatted with `terraform fmt`;
- passes `terraform validate` when supplied with required variables;
- contains clear generated comments;
- never embeds secrets;
- references existing values through variables;
- lists its assumptions.

The same templates are given to the transformation agent as reference patterns through the skills (section 69.4).

---

# 63. Runbook Generator

Generate both failover and failback runbooks.

Example:

```text
FAILOVER

1. Validate primary failure.
2. Freeze unsafe writes if required.
3. Promote database.
4. Validate DR database.
5. Scale application compute.
6. Validate container health.
7. Validate dependencies.
8. Switch traffic.
9. Run smoke checks.
10. Declare DR active.
```

Then:

```text
FAILBACK

1. Confirm primary Region stability.
2. Rebuild/revalidate primary.
3. Establish reverse replication.
4. Synchronize data.
5. Validate lag.
6. Quiesce writes if required.
7. Redirect traffic.
8. Confirm primary.
9. Restore normal replication direction.
10. Complete postmortem evidence.
```

The exact runbook must be generated from the recovery graph.

---

# 64. Failback Is First-Class

Every recovery mechanism should eventually declare:

```text
failover_supported
failback_supported
failback_complexity
data_resynchronization_required
```

A DR design is incomplete if Perpetual can explain failover but cannot explain how data created in DR returns to the restored primary.

---

---

> [↑ Spec Overview & Index](../../spec.md) · [← 04-recovery-and-optimizer.md](04-recovery-and-optimizer.md) · [06-security-and-llm.md →](06-security-and-llm.md)
