> **Perpetual Engineering Specification (Revision 4)** — Part V — IaC Transformation, Verification & Runbooks (§61–§64)  
> [↑ Spec Overview & Index](../../spec.md) · [← 04-recovery-and-optimizer.md](04-recovery-and-optimizer.md) · [06-security-and-llm.md →](06-security-and-llm.md)

---

# 61. IaC Transformation

Perpetual implements an approved DR spec by changing the user's own infrastructure code. It does not write a separate DR codebase unless there is no code to change (section 62.1).

This section ships in v0.2 (decision 2026-10-27). v0.1 delivers companion Terraform and suggested edits (62.1) and never runs repository tools.

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

### v0.1 verification

In v0.1 Perpetual runs only `terraform fmt`, `init -backend=false` and `validate` on the companion code it generated, with pinned, checksum-verified providers. It never runs `plan` or any tool against the user's existing code. Full design verification uses a saved plan that the user produces in their own environment (`terraform show -json <saved_plan>` for the root that includes the companion module) and supplies with matching provenance (56.3). Without one, the result is "static checks only" and design verification is UNKNOWN.

Failures go back to the agent as sanitized structured feedback (which check failed, on which resource, with the finding or simulation path). If retries run out, a reviewable branch may still be produced but is marked **unverified**, with failed/unknown checks and prerequisites listed. Security or approval invalidation stops execution; it must not be retried with weaker controls. Only design-pass artifacts carry a design-verified label; delivery retains the exact tree/report digest from 56.3.

---

# 62. Change Delivery

Output of a transformation:

- a git branch with one commit per DR spec change, in the DR spec's order;
- a pull request through `gh` or `glab` when the user enables it, otherwise the branch and a patch file;
- a description containing: the DR spec summary, before and after stack RTO, RPO and monthly cost, the verification report, files changed, the apply order, and manual steps.

Perpetual never merges, never pushes to a protected branch and never applies. The user's normal review and pipeline apply the change.

Terraform owns steady-state DR configuration: replication rules (ECR, S3, Secrets Manager replicas), standby resources, multi-Region keys and DR-Region KMS keys. Work that Terraform cannot or should not own is delivered as prerequisite scripts and SOPs (63.1): one-off backfill of data that existed before replication started, values Perpetual must not read, and account-level requests. Each becomes a typed deployment prerequisite (61.1).

---

# 62.1 Companion Fallback

In v0.1 companion Terraform is the delivery path. From v0.2 it is the fallback when no IaC repository is declared or LLM features are disabled. Perpetual generates deterministic companion DR Terraform from templates:

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

Companion code creates new resources only. A change to a resource the user's IaC already manages, such as enabling versioning on an existing bucket or a registry-wide ECR replication configuration, is delivered as a suggested edit: the Terraform address from the imported state or plan, the attribute change and a snippet, for the user to apply in their own code. Perpetual never generates a second owner for a managed resource.

The same templates are given to the transformation agent as reference patterns through the skills (section 69.4).

---

# 63. Recovery Artifacts

One recovery DAG (47) per stack and scenario compiles into:

```text
runbook                 explains the flow; not an execution method
recovery scripts        default execution method (63.2)
ARC Region switch plan  optional execution method (63.3)
```

plus prerequisite scripts and SOPs for deployment (63.1). All are generated from the same DAG, carry the same evaluation digest (56.3) and use the same step numbers. Regenerating one regenerates all of them. Perpetual generates and statically checks these artifacts; it never runs them.

## Runbook

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

The exact runbook must be generated from the recovery graph. Each runbook step names the script step or ARC execution block that performs it.

---

# 63.1 Prerequisite Scripts and SOPs

Delivered with the PR for work outside Terraform (62):

```text
SSM parameter copy       reads current parameters in the primary Region, lets the
                         operator review and edit them, then writes them to the DR
                         Region. Re-runnable. SecureString targets need the DR-Region
                         KMS key from the Terraform change first.
S3 backfill              S3 Batch Replication job for objects that existed before the
                         replication rule.
Quota requests           Service Quotas increase requests for DR capacity
                         (QUOTA-DR-001).
Identity Center replica  instructions to add a replica Region (OPS-ACCESS-001).
```

SOPs are instructions for ongoing operations, for example "when you create an SSM parameter for this stack, create it in the DR Region too". SSM-PARITY-001 detects a missed SOP on each scan.

Scripts that touch secret values run only on the operator's machine with the operator's credentials, and Perpetual never sees their output. Decrypted values go only to a private temporary file (owner-only permissions) for the edit step, are deleted on exit and are never logged (67).

---

# 63.2 Recovery Scripts

Failover and failback scripts are generated per stack and committed to the user's repository with the PR. Contract:

- one entry point runs the DAG's steps in order and pauses for confirmation at each human check;
- every step verifies the current state before acting and does nothing if the target state already holds, so a re-run never duplicates work (no second promotion, replica or scale-up);
- resumable from step N after an interrupted run;
- a dry-run mode prints the checks and actions without changing anything;
- explicit Regions, accounts and resource identifiers, never the profile's default Region;
- stops on the first error and prints the failing step and the command to resume;
- a timestamped log per step with no secret values; a game-day log is drill evidence (53);
- runs from an operator's laptop with pinned tool versions, never from CI, and never through endpoints in the failed Region;
- written in Python with boto3, each script self-contained and run with `uv run` (inline dependency metadata pins boto3); kubectl only for Kubernetes steps.

Script actions confirmed against AWS docs (2026-10-27):

```text
EFS failover        delete the replication configuration from the DR Region
                    (--deletion-mode LOCAL_CONFIGURATION_ONLY when the source
                    Region is unreachable). Takes several minutes; the replica
                    becomes writable and may contain a lost+found directory.
                    RPO is typically 15 minutes (TimeSinceLastSync).
EFS failback        replicate the replica back to the primary (initial sync time
                    grows with size), then re-create the original configuration.
ElastiCache Global  FailoverGlobalReplicationGroup promotes the DR secondary;
Datastore           allowed when the primary Region is unavailable. Replication
                    is asynchronous, so RPO equals replica lag. (ElastiCache
                    rules are post-MVP.)
```

Perpetual checks the scripts with a linter and a dry run against fixtures. It never executes them against AWS.

---

# 63.3 ARC Region Switch Plan

When the DR spec selects `arc_region_switch`, the DAG compiles into an `aws_arcregionswitch_plan` Terraform resource in the PR: two Regions, active/passive, the stack's target RTO, an application health alarm, a failover workflow (activate DR), a failback workflow, and a post-recovery workflow where needed.

Each recovery action maps to one of:

```text
no runtime action   replication already keeps the DR copy current (ECR, Secrets
                    Manager replicas, multi-Region KMS keys, DynamoDB global
                    tables, S3 replication). Perpetual verifies the prerequisite
                    instead.
execution block     ECS, EKS and ASG scaling; Aurora, RDS, DocumentDB and Neptune
                    recovery; Lambda event source mapping; Route 53 health check;
                    routing control; manual approval for the decide action.
script step         no block exists (EFS replication failover, ElastiCache
                    promotion): a manual approval block naming the recovery-script
                    step to run.
```

The Terraform provider expresses parallel work as a `Parallel` step whose `parallel_config` holds steps, one level deep; each layer of the DAG becomes one step. The compiler emits only execution block types that the pinned AWS provider version supports; anything else becomes a script step.

Route 53 record edits are never compiled; traffic moves through health checks or routing controls (8.1). Steps required in a Region failure are configured to run in ungraceful mode, and ARC-RS-001 flags any that would be skipped.

Static checks before delivery:

- every DAG action is covered;
- block order respects every prerequisite edge;
- every block target exists in the planned snapshot;
- the execution role grants each block's permissions;
- the Region pair matches the failure scenario;
- Terraform for scaled resources (ECS desired count, ASG min and desired) ignores those attributes, so a later apply does not undo a failover.

Plan evaluation status and execution reports are evidence (28.1, 53), never READY on their own.

---

# 63.4 Terraform After Failover

After a failover, scaled counts and database roles differ from the Terraform configuration. The runbook explains which attributes are ignored, which resources need a configuration change after failback, and that the user's normal pipeline makes those changes. Perpetual never touches state.

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

Failback runs by the same execution method as failover: the failback script or the ARC plan's failback workflow (63.2, 63.3).

---

---

> [↑ Spec Overview & Index](../../spec.md) · [← 04-recovery-and-optimizer.md](04-recovery-and-optimizer.md) · [06-security-and-llm.md →](06-security-and-llm.md)
