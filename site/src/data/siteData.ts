export interface DocArticle {
  slug: string;
  category: 'getting-started' | 'engine' | 'security' | 'reference';
  categoryTitle: string;
  index: string;
  title: string;
  specRef: string;
  description: string;
  keywords: string[];
  sections: {
    heading: string;
    bodyHtml: string;
  }[];
}

export const DOC_CATEGORIES = [
  {
    id: 'getting-started',
    kicker: '// getting-started',
    title: 'Getting Started',
    desc: 'Product definition, core question, installation, and planned CLI/UI workflow',
  },
  {
    id: 'engine',
    kicker: '// engine-and-spec',
    title: 'Core Engine & Architecture',
    desc: 'Discovery, evidence graph, rule packs, two-pass simulator, optimizer, and IaC verification',
  },
  {
    id: 'security',
    kicker: '// security-and-llm',
    title: 'Security & LLM Guardrails',
    desc: 'Read-only AWS model, secret redaction, LangGraph workflows, and local hybrid RAG',
  },
  {
    id: 'reference',
    kicker: '// reference',
    title: 'CLI & Specification Reference',
    desc: 'CLI command reference, readiness status vocabulary, and §1–§109 spec index',
  },
] as const;

export const DOC_ARTICLES: DocArticle[] = [
  {
    slug: 'getting-started/overview',
    category: 'getting-started',
    categoryTitle: 'Getting Started',
    index: '01',
    title: 'Product Overview & Why Stack-Level DR Matters',
    specRef: 'spec §1–§4',
    description:
      'Why individual resource checks fail during an AWS Region outage, how Perpetual evaluates the whole stack against RTO, RPO, and budget, and the non-negotiable engineering invariants.',
    keywords: ['overview', 'rto', 'rpo', 'budget', 'stack', 'region outage', 'multi-az', 'invariants'],
    sections: [
      {
        heading: 'The Core Question (spec §1)',
        bodyHtml: `
          <p>Perpetual is a local AWS disaster recovery (DR) tool designed to find what would break during a Region outage and propose fixes in your own infrastructure code. It evaluates the whole <strong>stack</strong>—the compute services, databases, queues, storage, networking, DNS, WAF, secrets, KMS keys, and IAM roles a product needs to serve its users:</p>
          <blockquote><p><strong>If this stack loses its current AWS Region, can it continue operating within its promised RTO, RPO, and budget?</strong></p></blockquote>
          <p>Individual resource checks (<code>RDS Multi-AZ = true</code>) do not establish stack survivability (<code>Resource readiness != Stack readiness</code>). Multi-AZ protects against Availability Zone failures; it does not provide recovery from losing an entire Region.</p>
        `,
      },
      {
        heading: 'Why Individual Resource Checks Fail',
        bodyHtml: `
          <ul>
            <li><strong>Plans drift:</strong> New services, queues, and configuration changes quietly invalidate yesterday's DR plan.</li>
            <li><strong>Dependencies get missed:</strong> A database replica is little help if the container image in ECR, secret in Secrets Manager, or customer-managed KMS key is unavailable in the DR Region.</li>
            <li><strong>Permissions &amp; capacity block recovery:</strong> IAM policies may still reference the primary Region ARN, or DR service quotas may be too low to run production scale.</li>
            <li><strong>Kubernetes readiness is incomplete:</strong> A StatefulSet may need an EBS StorageClass while the DR EKS cluster lacks the EBS CSI driver or IRSA bindings.</li>
            <li><strong>Recovery estimates omit work:</strong> Detection, failover decisions, manual handoffs, and final validation all add time; other steps can run in parallel along the recovery DAG.</li>
            <li><strong>Fixes span repositories &amp; resources:</strong> Closing a gap requires coordinated changes across Terraform modules and Kubernetes deployment manifests.</li>
          </ul>
        `,
      },
      {
        heading: 'Three Recovery Constraints',
        bodyHtml: `
          <p>Every stack evaluation in Perpetual is scored against three explicit targets (<code>RecoveryRequirement</code>, <code>spec §26</code>):</p>
          <ul>
            <li><strong>Recovery Time Objective (RTO):</strong> How long the product can be unavailable, computed from the critical path of the stack-level recovery DAG plus explicit plan buffer (<code>spec §49.2, §50</code>).</li>
            <li><strong>Recovery Point Objective (RPO):</strong> How much recent data the product can afford to lose across all in-scope data stores and stateful SQS queues (<code>spec §51</code>).</li>
            <li><strong>Budget:</strong> Maximum steady-state monthly DR ownership cost; budget <code>PASS</code> requires the high bound of the cost estimate to stay within budget (<code>spec §59.1</code>).</li>
          </ul>
        `,
      },
      {
        heading: 'Non-Negotiable Architectural Invariants',
        bodyHtml: `
          <ol>
            <li><strong>Stack-level survivability (<code>§1, §47, §107</code>):</strong> One recovery plan, one RTO, one RPO, and one cost estimate per stack and failure scenario.</li>
            <li><strong>The LLM proposes; the engine verifies (<code>§2, §102 Rule 11</code>):</strong> Every number comes from the deterministic engine. Uncited proposals are discarded.</li>
            <li><strong>Missing evidence is <code>UNKNOWN</code>, never <code>PASS</code> or <code>READY</code> (<code>§30, §31, §76.1</code>):</strong> Missing catalog entries, stale metrics, or unreviewed low-confidence edges prevent <code>READY</code>.</li>
            <li><strong>Ordered readiness composition (<code>§30.1, §31</code>):</strong> Simulation recoverability (<code>RECOVERABLE / UNKNOWN / UNAVAILABLE</code>) is distinct from overall stack readiness (<code>READY / DEGRADED / NOT_READY / UNKNOWN</code>).</li>
            <li><strong>Planned snapshots vs. observed readiness (<code>§15.4, §61.1</code>):</strong> Design verification re-evaluates planned snapshots and never claims live observed <code>READY</code> until deployed and rescanned.</li>
            <li><strong>Immutable digests &amp; approval binding (<code>§56.3</code>):</strong> Evaluations, approvals, and verification reports bind to an immutable <code>EvaluationInput</code> SHA-256 digest.</li>
            <li><strong>Code only, in an isolated sandbox (<code>§61, §65</code>):</strong> Never runs <code>terraform apply</code> or <code>kubectl apply</code>, and never reads secret values.</li>
          </ol>
        `,
      },
    ],
  },
  {
    slug: 'getting-started/quickstart',
    category: 'getting-started',
    categoryTitle: 'Getting Started',
    index: '02',
    title: 'Installation, Local Web UI & CLI Workflow',
    specRef: 'spec §71–§79',
    description:
      'How to set up Perpetual from source today, and the planned local workbench launch the local single-process FastAPI + React Flow workbench, and run the end-to-end CLI workflow from scan to verified pull request.',
    keywords: ['install', 'quickstart', 'uv', 'cli', 'ui', 'localhost', 'workflow'],
    sections: [
      {
        heading: 'Local Single-Process Deployment (spec §71.1)',
        bodyHtml: `
          <p>Perpetual runs 100% locally on your workstation as a single Python 3.13 process serving both the FastAPI REST engine and the static React + React Flow web UI, backed by a local SQLite database.</p>
          <blockquote><p><strong>Pre-alpha status:</strong> Milestone M0 PoC is in active development. Perpetual is not published on PyPI yet (planned for v1.0), and the <code>perpetual</code> CLI commands on this site are planned, not available. Today you can clone the repository and run the checks.</p></blockquote>
          <pre><code class="language-bash"># Set up from source (all tooling is pinned in mise.toml)
git clone https://github.com/darshan-raul/perpetual
cd perpetual
mise install
mise run check   # lint + typecheck + tests

# Planned: launch the local web console &amp; graph workbench on http://127.0.0.1:8000
uv run perpetual ui</code></pre>
        `,
      },
      {
        heading: 'End-to-End CLI Workflow (spec §79)',
        bodyHtml: `
          <p><strong>Planned workflow.</strong> None of these commands exist yet; the first one to ship is the M0 demo, <code>perpetual poc fix --fixture ecs-broken</code>. Perpetual will use your existing read-only AWS credentials and local Terraform / Kubernetes repositories:</p>
          <pre><code class="language-bash"># 1. Scan live AWS account + CloudTrail / Flow Logs across primary &amp; DR Regions
perpetual scan --profile production --region ap-south-1 --dr-region ap-south-2

# 2. Inspect the evidence-backed dependency graph and unreviewed low-confidence edges
perpetual graph --stack checkout --unreviewed

# 3. Simulate losing the primary Region and trace failure chains
perpetual simulate checkout --failure region:ap-south-1

# 4. Compare DR designs against RTO, RPO, and monthly budget constraints
perpetual optimize checkout --rto 30m --rpo 5m --budget 1200

# 5. Approve the chosen digest-bound DR Spec
perpetual dr-spec checkout --approve

# 6. Transform Terraform &amp; K8s manifests in an isolated git worktree, verify, and open a PR
perpetual transform checkout --terraform ./infra/prod --k8s ./deploy/prod --open-pr</code></pre>
        `,
      },
      {
        heading: 'Example Checkout Stack Output',
        bodyHtml: `
          <p>Illustrative output for a production <code>checkout</code> stack migrating from unready single-Region deployment to a verified DR design:</p>
          <pre><code class="language-text">Stack             checkout
Primary Region    ap-south-1  ->  DR Region ap-south-2

                  Today        After proposed change
Status            NOT READY    Design meets targets
RTO (target 30m)  74-110m      21-29m
RPO (target 5m)   UNKNOWN      1-3m
DR cost / month   $0           $640

Blocking findings fixed
1. checkout-api image unavailable in DR ECR       -> ECR replication rule
2. DR execution role cannot decrypt the KMS key   -> multi-Region key + policy
3. Database recovery exceeds the RTO              -> cross-Region read replica

Pull request      perpetual/dr/checkout/2026-11-02  (7 files, design verified)
Deployment        Pending; fresh scan required for observed READY</code></pre>
        `,
      },
    ],
  },
  {
    slug: 'engine/discovery-and-graph',
    category: 'engine',
    categoryTitle: 'Core Engine & Architecture',
    index: '01',
    title: 'Evidence-Backed Discovery & Dependency Graph',
    specRef: 'spec §9–§26',
    description:
      'How Perpetual ingests AWS APIs, Terraform saved plans, Kubernetes manifests, CloudTrail, and VPC Flow Logs into a normalized NetworkX graph with Permitted, Referenced, and Observed evidence.',
    keywords: ['discovery', 'graph', 'evidence', 'permitted', 'referenced', 'observed', 'cloudtrail', 'flow logs', 'override'],
    sections: [
      {
        heading: 'Three Tiers of Dependency Evidence (spec §16–§22)',
        bodyHtml: `
          <p>Perpetual never guesses dependencies. Every directed edge (<code>dependent -&gt; dependency</code>) in the NetworkX graph snapshot carries structured evidence items from three distinct tiers:</p>
          <ul>
            <li><strong>Permitted:</strong> Security groups, Kubernetes NetworkPolicies, and IAM policies establish that a network or API connection is <em>allowed</em>.</li>
            <li><strong>Referenced:</strong> Terraform expressions, ECS task definitions, Lambda environment variables (matched facts only), and K8s ConfigMaps establish that configuration <em>names</em> a dependency.</li>
            <li><strong>Observed:</strong> CloudTrail events and VPC Flow Logs establish that runtime traffic or API calls <em>actually happen</em>.</li>
          </ul>
          <p>Confidence scores combine evidence across independent correlation groups so multiple signals from the same source do not artificially inflate confidence (<code>spec §22</code>). Ambiguous shared-role or shared-ENI observations remain candidate sets without exact-edge confidence uplift (<code>spec §14.1</code>).</p>
        `,
      },
      {
        heading: 'Edge Direction, Redundancy Groups & Cycles (spec §18–§20)',
        bodyHtml: `
          <p>Edge direction is strictly <code>dependent -&gt; dependency</code>. Replication and backup relationships (<code>replicates_to</code>, <code>backed_up_by</code>) are not "requires" edges: the impact pass skips them and only the DR recovery overlay follows them (<code>spec §20, §44</code>).</p>
          <p>Redundant dependencies are modeled explicitly via <code>DependencyGroup</code> semantics (<code>ALL</code>, <code>ANY</code>, or <code>quorum(k)</code>, <code>spec §19.1</code>), ensuring active-passive and multi-AZ/multi-Region targets are evaluated accurately.</p>
        `,
      },
      {
        heading: 'User Review Gate & GraphOverride Layer (spec §23)',
        bodyHtml: `
          <p>A stack cannot reach <code>READY</code> while any low-confidence edge on a required recovery path remains unreviewed—it displays <code>UNKNOWN</code> with reason <code>graph_not_reviewed</code>. Negative findings (<code>NOT_READY</code>) are never held back.</p>
          <p>When an engineer confirms, rejects, or adds a dependency in the UI or CLI, Perpetual stores an immutable <code>GraphOverride</code> record applied on top of subsequent scans—never mutating raw discovered data.</p>
        `,
      },
    ],
  },
  {
    slug: 'engine/rules-and-simulator',
    category: 'engine',
    categoryTitle: 'Core Engine & Architecture',
    index: '02',
    title: 'DR Rule Packs, Status Vocabulary & Two-Pass Simulator',
    specRef: 'spec §27–§46',
    description:
      'Service-specific and cross-cutting DR rule packs, strict rebuild_from_iac verification, canonical readiness states, and the two-pass Region outage simulator.',
    keywords: ['rules', 'simulator', 'two-pass', 'readiness', 'rebuild_from_iac', 'ecs', 'eks', 'rds', 'xreg'],
    sections: [
      {
        heading: 'Service & Cross-Cutting DR Rule Packs (spec §28–§41)',
        bodyHtml: `
          <p>Rule packs evaluate normalized resources and graph edges to emit both structured <code>Finding</code> records and candidate <code>RecoveryMechanism</code> overlays:</p>
          <ul>
            <li><strong>Cross-Cutting Rules (<code>§28.1</code>):</strong> Cross-Region hardcodes (<code>XREG-*</code>), AWS control-plane dependencies during outage (<code>CTRL-PLANE-001</code>), DR Region service quotas (<code>QUOTA-DR-001</code>), Regional service parity (<code>REGION-SVC-001</code>), Route 53 ARC readiness (<code>ARC-RS-001</code>), SSM/Secrets parity (<code>SSM-PARITY-001</code>), and operator break-glass access (<code>OPS-ACCESS-*</code>).</li>
            <li><strong>ECS, EC2 &amp; Serverless Packs (<code>§32</code>):</strong> Task definitions, ECR cross-Region replication, KMS decrypt permissions for DR execution roles, ALB/NLB target groups, and ASG launch templates.</li>
            <li><strong>EKS Deep Readiness Pack (<code>§33–§40</code>):</strong> Control plane, node groups/Karpenter, core add-ons (CoreDNS, VPC CNI, kube-proxy, EBS/EFS CSI drivers), IRSA &amp; Pod Identity OIDC parity, container images, and PVC/StorageClass topology.</li>
            <li><strong>Data Gravity &amp; RDS/Aurora/DynamoDB Packs (<code>§41–§42</code>):</strong> Cross-Region read replicas, Aurora Global Database, DynamoDB Global Tables, PITR/snapshot availability, and KMS key replication.</li>
          </ul>
        `,
      },
      {
        heading: 'Strict rebuild_from_iac Definition (spec §27.1)',
        bodyHtml: `
          <p>Perpetual never assumes a resource is "reproducible from Terraform" merely because it appears in IaC. A resource qualifies for <code>rebuild_from_iac</code> only when its IaC definition is present, parameterized for the DR Region, its state/artifacts/AMIs/images are accessible without the failed primary Region, and required quotas are verified; otherwise its mechanism is <code>unknown</code>.</p>
        `,
      },
      {
        heading: 'Two-Pass Failure Simulator & Ordered Readiness (spec §30–§31, §43–§46)',
        bodyHtml: `
          <p>The deterministic simulator runs in two passes for a failure scenario (e.g., <code>region:ap-south-1</code>):</p>
          <ol>
            <li><strong>Pass 1 — Impact Pass:</strong> Propagates failure from the outage scope along <code>requires</code> edges (respecting <code>ALL / ANY / quorum</code> groups and skipping <code>replicates_to</code> / <code>backed_up_by</code>).</li>
            <li><strong>Pass 2 — Recovery Pass:</strong> Evaluates the DR overlay mechanisms, traces whether every required service in RTO scope can recover in the DR Region, and records exact <code>FailureReasonChain</code> paths for any blocked resource.</li>
          </ol>
          <p>Simulation recoverability (<code>RECOVERABLE / UNKNOWN / UNAVAILABLE</code>) is combined with RPO, budget, review gates, and advisory status using the ordered readiness table in <code>spec §31</code> to produce the canonical stack status: <code>READY</code>, <code>DEGRADED</code>, <code>NOT_READY</code>, or <code>UNKNOWN</code>.</p>
        `,
      },
    ],
  },
  {
    slug: 'engine/recovery-and-optimizer',
    category: 'engine',
    categoryTitle: 'Core Engine & Architecture',
    index: '03',
    title: 'Recovery DAG, Critical-Path RTO/RPO & Pareto Optimizer',
    specRef: 'spec §47–§60',
    description:
      'How Perpetual constructs one stack-level Recovery DAG, computes critical-path RTO and RPO with explicit buffers, prices steady-state DR ownership, and optimizes across the Pareto frontier.',
    keywords: ['dag', 'rto', 'rpo', 'optimizer', 'pareto', 'cost', 'buffer', 'drspec', 'digest'],
    sections: [
      {
        heading: 'One Stack-Level Recovery DAG (spec §47–§50)',
        bodyHtml: `
          <p>DR results exist only per stack: one recovery plan, one RTO, and one RPO per stack and failure scenario. Perpetual builds the recovery DAG using a <strong>Phase Template + Refinement</strong> algorithm (<code>spec §47.1</code>):</p>
          <ol>
            <li><strong>Detection &amp; Decision:</strong> Outage verification, failover declaration, and operator authentication.</li>
            <li><strong>Prerequisites &amp; Data Promotion:</strong> KMS/IAM activation, RDS/Aurora replica promotion or snapshot restore, DynamoDB table readiness.</li>
            <li><strong>Compute &amp; Service Bring-Up:</strong> ECS task scaling, EKS workload rollouts, Lambda concurrency provisioning.</li>
            <li><strong>Traffic Cutover &amp; Validation:</strong> Route 53 DNS / ARC Region switch and synthetic health validation.</li>
          </ol>
          <p>Every action duration comes from the versioned YAML catalog (<code>apps/api/perpetual/config/defaults/</code>). An action with no catalog entry makes the RTO <code>UNKNOWN</code>, never zero (<code>spec §49.1</code>). Critical-path traversal plus explicit plan buffer yields the low/high RTO range (<code>spec §49.2, §50</code>).</p>
        `,
      },
      {
        heading: 'Pareto Optimizer & Steady-State Costing (spec §54–§60)',
        bodyHtml: `
          <p>When a stack misses its targets, the optimizer searches combinations of recovery options—from <em>Backup &amp; Restore</em> and <em>Pilot Light</em> to <em>Warm Standby</em> and <em>Hot Standby</em>—and scores every candidate with the deterministic engine.</p>
          <p>Steady-state DR cost (<code>spec §58–§59.1</code>) includes standby compute, replica instances, storage duplication, cross-Region data transfer, and KMS/Secrets overhead. A candidate passes the budget constraint only if its <strong>high bound</strong> is within budget.</p>
        `,
      },
      {
        heading: 'Immutable EvaluationInput & Approval Digests (spec §56.3)',
        bodyHtml: `
          <p>Every optimizer run, approved <code>DRSpec</code>, and verification report is cryptographically bound to an immutable <code>EvaluationInput</code> SHA-256 digest covering scan IDs, graph overrides, targets, catalog/pricing versions, and base git tree. Any change to inputs automatically invalidates stale approvals before code transformation.</p>
        `,
      },
    ],
  },
  {
    slug: 'engine/iac-and-runbooks',
    category: 'engine',
    categoryTitle: 'Core Engine & Architecture',
    index: '04',
    title: 'Isolated IaC Transformation, 4-Stage Verification & Runbooks',
    specRef: 'spec §61–§64',
    description:
      'How Perpetual compiles approved DR Specs into Terraform and Kubernetes PRs inside a sandboxed worktree, verifies planned snapshots across 4 stages, and generates digest-matched runbooks and scripts.',
    keywords: ['terraform', 'kubernetes', 'iac', 'worktree', 'verification', 'runbook', 'arc', 'recovery scripts', 'pr'],
    sections: [
      {
        heading: 'Sandboxed Git Worktree Transformation (spec §61–§62)',
        bodyHtml: `
          <p>Code changes happen exclusively in an isolated git worktree on a <code>perpetual/dr/&lt;stack&gt;/&lt;date&gt;</code> branch. Before any repository tool runs, mandatory OS/container isolation enforces:</p>
          <ul>
            <li><strong>Strict command allowlist:</strong> Only read/validate/plan tools (<code>terraform init -backend=false</code>, <code>terraform fmt</code>, <code>terraform validate</code>, <code>kubectl kustomize</code>, <code>helm template</code>) are permitted.</li>
            <li><strong>Destructive commands unreachable:</strong> <code>terraform apply|destroy|import|state</code> and <code>kubectl apply|delete</code> are blocked by policy and sandbox boundaries.</li>
            <li><strong>Companion Terraform (v0.1) &amp; In-Place Edits (v0.2):</strong> v0.1 generates deterministic companion Terraform modules and suggested edits; v0.2 adds LangGraph-driven in-place edits across Terraform, Kustomize, and Helm.</li>
          </ul>
        `,
      },
      {
        heading: '4-Stage Verification Pipeline (spec §61.1)',
        bodyHtml: `
          <ol>
            <li><strong>Stage 1 — Static Validation:</strong> Formatting, syntax, schema, and <code>terraform validate</code> / manifest rendering checks.</li>
            <li><strong>Stage 2 — Planned Snapshot Import:</strong> Imports saved-plan <code>terraform show -json</code> and rendered manifests into a planned resource snapshot, stripping obsolete live operational proof on modified/replaced resources (<code>spec §15.4</code>).</li>
            <li><strong>Stage 3 — Modeled Design Verification:</strong> Re-runs all DR rule packs and the two-pass simulator on the planned graph to verify that RTO, RPO, and budget targets are met.</li>
            <li><strong>Stage 4 — Deployment Prerequisites vs. Observed Readiness:</strong> Explicitly lists post-merge prerequisites (e.g., initial snapshot copy completion, secret population). Design verification never claims live observed <code>READY</code>; only a fresh scan after deployment establishes <code>READY</code>.</li>
          </ol>
        `,
      },
      {
        heading: 'One Recovery DAG -> Three Synchronized Artifacts (spec §63–§64)',
        bodyHtml: `
          <p>From the single approved recovery DAG—sharing the exact same digest and step numbers—Perpetual compiles three artifacts and never executes them:</p>
          <ul>
            <li><strong>Explanatory Markdown Runbook:</strong> Human-readable operator guide with preconditions, verification commands, and failback notes.</li>
            <li><strong>Laptop-Run Recovery Scripts:</strong> Idempotent, dry-runnable CLI scripts (default execution method) with step-by-step confirmation gates.</li>
            <li><strong>Optional ARC Region Switch Plan:</strong> Compiled AWS Application Recovery Controller Region switch configuration when selected in the DR Spec.</li>
          </ul>
        `,
      },
    ],
  },
  {
    slug: 'security/security-and-llm',
    category: 'security',
    categoryTitle: 'Security & LLM Guardrails',
    index: '01',
    title: 'Read-Only Security Model, Secret Redaction & LangGraph Agents',
    specRef: 'spec §65–§70',
    description:
      'How Perpetual protects your AWS account and codebase: strict read-only discovery, zero secret persistence, IaC redaction, replaceable LLM providers, and local hybrid RAG.',
    keywords: ['security', 'iam', 'secrets', 'redaction', 'llm', 'langgraph', 'rag', 'openrouter', 'bedrock', 'ollama'],
    sections: [
      {
        heading: 'Read-Only AWS Discovery & Zero Secret Persistence (spec §65–§68)',
        bodyHtml: `
          <ul>
            <li><strong>Never reads secret values:</strong> Perpetual inspects metadata and ARNs only. It never calls <code>secretsmanager:GetSecretValue</code> or reads decrypted SSM SecureStrings.</li>
            <li><strong>No invasive AWS mutations:</strong> Never enables CloudTrail trails, data events, or VPC Flow Logs on your behalf.</li>
            <li><strong>Matched facts &amp; aggregates only:</strong> From environment variables and ConfigMaps, Perpetual persists only matched resource references—never raw secret or config strings. From CloudTrail and Flow Logs, it persists only aggregated dependency counters.</li>
          </ul>
        `,
      },
      {
        heading: 'LLM Proposes, Engine Verifies (spec §2, §69)',
        bodyHtml: `
          <p>LLM features (arriving in v0.2, opt-in per project) attach at three strictly bounded points via LangGraph workflows:</p>
          <ol>
            <li><strong>Advisory Reviewer (<code>§28.2</code>):</strong> Flags subtle risks rule packs might miss (e.g., primary-Region endpoints in config). Can hold a stack from <code>READY</code> (<code>advisory_unresolved</code>), but can never upgrade a state.</li>
            <li><strong>Candidate Planner (<code>§56.1</code>):</strong> Proposes multi-resource DR designs inside the optimizer loop using AWS guidance and your runbooks; every proposal is scored by the deterministic engine.</li>
            <li><strong>Worktree Transformer (<code>§61</code>):</strong> Drafts in-place Terraform and Kubernetes manifest edits, verified by the 4-stage engine pipeline.</li>
          </ol>
          <p>Every proposal must cite its source (a resource ID, file + line, knowledge document, or versioned <code>SKILL.md</code>); uncited outputs are dropped automatically.</p>
        `,
      },
      {
        heading: 'Provider Choice, Redaction & Local Hybrid RAG (spec §69.1–§69.5)',
        bodyHtml: `
          <p>All model calls go through LangChain's <code>init_chat_model</code> interface so you can configure OpenRouter, Anthropic, AWS Bedrock, or local models via Ollama per agent role.</p>
          <p>Before any prompt leaves your machine, Perpetual strips Terraform state, secret values, environment values, and raw logs, honors <code>.perpetualignore</code>, sanitizes any <code>web_search</code> / <code>web_fetch</code> documentation queries to generic AWS/DR terms, and records the full audit trail in the local <code>llm_calls</code> SQLite table.</p>
        `,
      },
    ],
  },
  {
    slug: 'reference/cli-commands',
    category: 'reference',
    categoryTitle: 'CLI & Specification Reference',
    index: '01',
    title: 'CLI Commands, Flags & Status Vocabulary Reference',
    specRef: 'spec §30.1, §79',
    description:
      'Complete reference for planned Perpetual CLI commands (ui, scan, graph, simulate, optimize, dr-spec, transform) and canonical readiness states.',
    keywords: ['cli', 'commands', 'flags', 'scan', 'simulate', 'optimize', 'transform', 'status', 'vocabulary'],
    sections: [
      {
        heading: 'Planned CLI Commands Reference (spec §79)',
        bodyHtml: `
          <p><strong>Not available yet.</strong> These commands follow the suggested CLI in spec §79 and will land over milestones M0 to v0.2. The first to ship is the M0 demo, <code>perpetual poc fix --fixture ecs-broken</code>.</p>
          <pre><code class="language-bash"># Launch local FastAPI + React Flow UI workbench
perpetual ui [--host 127.0.0.1] [--port 8000]

# Discover AWS resources, Terraform plans/state, K8s manifests, and log evidence
perpetual scan --profile &lt;aws-profile&gt; --region &lt;primary&gt; --dr-region &lt;dr&gt; [--terraform &lt;dir&gt;] [--k8s &lt;dir&gt;]

# Inspect dependency graph and review low-confidence edges
perpetual graph --stack &lt;name&gt; [--unreviewed] [--fixture &lt;fixture-name&gt;]

# Run deterministic two-pass failure simulation and critical-path RTO/RPO
perpetual simulate &lt;stack&gt; --failure region:&lt;region&gt; [--fixture &lt;fixture-name&gt;]

# Search Pareto-optimal DR architectures within RTO, RPO, and monthly budget
perpetual optimize &lt;stack&gt; --rto 30m --rpo 5m --budget 1200

# Inspect or approve a digest-bound DR Spec
perpetual dr-spec &lt;stack&gt; [--approve]

# Generate verified Terraform/K8s changes, runbook, and recovery scripts in a git worktree
perpetual transform &lt;stack&gt; --terraform ./infra/prod --k8s ./deploy/prod [--open-pr]</code></pre>
        `,
      },
      {
        heading: 'Canonical Readiness Vocabulary (spec §30.1 & §31)',
        bodyHtml: `
          <ul>
            <li><strong><code>READY</code>:</strong> Simulation is <code>RECOVERABLE</code>, predicted RTO and RPO meet targets, high-bound cost is within budget, no required-path edge is unreviewed, and no blocking advisory is unresolved.</li>
            <li><strong><code>DEGRADED</code>:</strong> Recoverable within primary RTO/RPO targets but with non-blocking warnings or degraded redundancy margins.</li>
            <li><strong><code>NOT_READY</code>:</strong> Simulation is <code>UNAVAILABLE</code>, or a blocking rule fails, or predicted RTO/RPO/budget exceeds the stack's targets.</li>
            <li><strong><code>UNKNOWN</code>:</strong> Missing evidence, missing catalog duration, failed collector coverage, unreviewed low-confidence required-path edge (<code>graph_not_reviewed</code>), or unresolved blocking advisory (<code>advisory_unresolved</code>). Never shown as <code>READY</code>.</li>
          </ul>
        `,
      },
    ],
  },
];

export interface SearchEntry {
  title: string;
  url: string;
  badge: 'Docs' | 'Spec' | 'CLI' | 'Roadmap';
  category: string;
  description: string;
  keywords: string;
}

export const SEARCH_INDEX: SearchEntry[] = [
  ...DOC_ARTICLES.map((a) => ({
    title: a.title,
    url: `/docs/${a.slug}`,
    badge: 'Docs' as const,
    category: `${a.category} · ${a.specRef}`,
    description: a.description,
    keywords: a.keywords.join(' ') + ' ' + a.specRef,
  })),
  {
    title: 'System Architecture & Pipeline (§1–§109)',
    url: '/architecture',
    badge: 'Spec',
    category: 'architecture · pipeline & invariants',
    description:
      'End-to-end architecture pipeline from AWS/Terraform/Kubernetes evidence collectors to two-pass simulation, recovery DAG, optimizer, and 4-stage verified IaC PR delivery.',
    keywords: 'architecture pipeline diagram svg invariants import-linter layers spec index',
  },
  {
    title: 'AWS Service Scope & checkout Stack Benchmark',
    url: '/scope',
    badge: 'Spec',
    category: 'scope · 25+ aws services & rules',
    description:
      'Complete matrix of in-scope AWS services (ECS, EKS, EC2, Lambda, RDS, Aurora, DynamoDB, S3, KMS, IAM, Route 53, ARC) and illustrative checkout stack DR evaluation.',
    keywords: 'scope aws services ecs eks rds aurora dynamodb kms iam route53 arc benchmark checkout',
  },
  {
    title: 'Milestones & Release Roadmap (M0 PoC -> v1.0)',
    url: '/roadmap',
    badge: 'Roadmap',
    category: 'roadmap · pre-alpha to v1.0',
    description:
      'Engine-first development roadmap: M0 PoC, M1 Alpha, v0.1 deterministic engine, v0.2 LangGraph advisor & planner, v0.3 game days & drift, and v1.0 release.',
    keywords: 'roadmap changelog milestones m0 m1 v0.1 v0.2 v0.3 v1.0 status pre-alpha',
  },
];
