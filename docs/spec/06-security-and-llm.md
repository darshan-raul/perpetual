> **Perpetual Engineering Specification (Revision 4)** — Part VI — Security Model & LLM Architecture (§65–§70)  
> [↑ Spec Overview & Index](../../spec.md) · [← 05-iac-and-runbooks.md](05-iac-and-runbooks.md) · [07-platform-ui-and-testing.md →](07-platform-ui-and-testing.md)

---

# 65. Security Model

Perpetual handles extremely sensitive infrastructure metadata.

Security principles:

```text
Read-only by default.
Do not retrieve secret values.
Do not retrieve application data.
Never send Terraform state, secret values, env values or raw logs to an LLM (section 69.5).
Redact credentials.
Minimize persisted sensitive metadata.
Never enable logging, trails or flow logs in customer accounts; read what exists.
Persist only aggregates of CloudTrail and flow-log data (section 14.1).
Change code, never infrastructure: no apply, no kubectl apply, no merges (section 62).
LLM features are opt-in per project.
```

---

# 66. AWS Access

Development can initially support standard AWS SDK credential resolution.

Examples:

```text
AWS_PROFILE
environment credentials
assumed role
IAM role when deployed
```

Commercial/SaaS design should eventually use a customer-created read-only IAM role with external ID.

Do not require write permissions for assessments.

Reading CloudTrail and flow logs needs read access to where they are delivered: `s3:GetObject` and `s3:ListBucket` on the log buckets (plus `kms:Decrypt` if they are encrypted), `logs:FilterLogEvents` or Logs Insights queries for CloudWatch Logs destinations, or read-only Athena and CloudTrail Lake queries. These permissions are optional. Without them, Perpetual reports that observed evidence is unavailable.

The DR target may be a separate AWS account. This is a common best practice, for example a dedicated DR or backup account.

The MVP MUST support one primary account plus one DR account per stack, with separate credentials or role per account. Every resource ID already carries `account_id`, so cross-account counterparts need no model change.

Organization-wide multi-account orchestration remains a non-goal (section 101).

---

# 67. Secret Handling

Do NOT call:

```text
GetSecretValue
```

for dependency discovery unless a future explicit opt-in feature is designed.

Use metadata and resource references.

Similarly, do not store Kubernetes Secret values.

ECS task-definition environment variables, Lambda environment variables and Kubernetes ConfigMaps frequently contain plaintext secrets.

Collectors may read them in memory to match endpoints, ARNs and Region strings. They MUST persist only:

- the variable name;
- the matched fact (e.g. "matches RDS endpoint of aws://.../rds/db/prod-mysql", "contains Region string ap-south-1").

They MUST NOT persist the value. Unmatched values are discarded.

Generated scripts (63.1, 63.2) may read secret values when an operator runs them, on the operator's machine with the operator's credentials. Perpetual never runs these scripts, never receives their output and never embeds values in them.

---

# 68. Terraform State

Terraform state may contain sensitive material.

Requirements:

- mark uploaded state as sensitive;
- minimize persistence;
- redact known sensitive fields;
- do not send raw state to an LLM;
- allow local-only analysis.

---

# 69. LLM Architecture

Discovery, the graph, assessment, simulation, the deterministic optimizer and companion Terraform work without an LLM. Advisory review (28.2), the candidate planner (56.1), DR spec rationale (56.2), IaC transformation (61) and the explainer (70) need one.

## 69.1 Provider Abstraction

The provider is replaceable. Perpetual depends on LangChain's chat-model interface, not on a vendor SDK.

```yaml
# perpetual.yaml (project) or user config
llm:
  default:
    provider: openai_compatible      # openai_compatible | anthropic | bedrock | ollama | ...
    model: anthropic/claude-sonnet-4.5
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
  roles:                             # optional per-role overrides
    planner:     { model: ... }
    advisor:     { model: ... }
    transformer: { model: ... }
    explainer:   { model: ... }
  embeddings:
    provider: local                  # local (fastembed) | openai_compatible | bedrock | ...
    model: BAAI/bge-small-en-v1.5
```

- Models are built with LangChain's `init_chat_model`; OpenRouter and any OpenAI-compatible endpoint use the OpenAI integration with `base_url`.
- API keys come from environment variables or the OS keyring. They are never written to the database or logs.
- On configuration, Perpetual probes each role's model for tool calling and structured output, and refuses roles that lack them.
- Example model names in this spec are illustrative.

## 69.2 Agents

Agents are LangGraph graphs:

```text
advisor       section 28.2   proposes findings, edges, mechanisms, questions
planner       section 56.1   proposes candidate architectures, writes DR spec rationale
transformer   section 61     edits IaC, runs checks, responds to verification failures
explainer     section 70     answers questions over deterministic tool results
```

- Tools give agents read access to Perpetual's own data (stack context, findings, simulations, plans), to the local knowledge base and skills, and to controlled `web_search` and `web_fetch` tools for researching unmodeled/out-of-scope resources and enriching the local knowledge base (section 69.3). Agents never call AWS.
- State is checkpointed with LangGraph's SQLite checkpointer in the project data directory, so runs can resume and be audited.
- Human-in-the-loop interrupts: DR spec approval before transformation; confirmation before opening a pull request.
- All structured outputs are validated with Pydantic. Invalid output is retried once with the validation error, then the step fails closed.

## 69.3 Knowledge Base (RAG)

A local knowledge base grounds the agents.

Sources:

- **Shipped domain knowledge (`knowledge/domain/`).** Curated Markdown reference documents shipped in the repository and indexed automatically into the local knowledge base. They hold DR domain knowledge for every in-scope AWS service (ECS, EKS, EC2/Auto Scaling, Lambda, RDS/Aurora, DynamoDB, S3, EBS, EFS, SQS, SNS, ECR, Secrets Manager, SSM Parameter Store, KMS, IAM, Route 53, ALB/NLB, WAF, CloudWatch Logs, VPC networking): replication and backup mechanisms, RTO/RPO characteristics, control-plane vs data-plane failover behaviour, service quotas, common DR failure modes, and Terraform/Kubernetes implementation patterns.
- **Public references (`knowledge/sources.yaml`).** Perpetual ships a list of official reference URLs (the AWS DR whitepaper, service guides on replication, backup, quotas and failover, EKS DR guidance) and the code to ingest them. `perpetual kb sync` fetches and indexes them locally.
- **Perpetual's own material.** Rule documentation, duration-catalog basis notes, skills.
- **The user's documents.** Runbooks, ADRs, postmortems, internal standards: `perpetual kb add ./docs`.
- **Dynamic agent research (`web_search` and `web_fetch`).** When a stack includes an out-of-scope or unmodeled resource type, or an AWS capability not yet covered in the local knowledge base, agents (`advisor`, `planner`, `transformer`, `explainer`) can invoke `web_search` and `web_fetch` to retrieve official documentation (prioritizing AWS and Terraform provider docs). Fetched pages are sanitized, chunked, embedded and persisted into `kb_documents` and `kb_chunks` (with `origin = "agent_web_fetch"`, source URL, title and fetch timestamp). This continuously improves the local doc store so subsequent runs already have that domain knowledge locally without re-fetching, and every agent claim using web-fetched knowledge must cite the stored `kb_chunk` ID.

Storage is local: a SQLite database with `sqlite-vec` for vectors and FTS5 for keywords, combined as hybrid retrieval. Every chunk keeps its source (URL or path), origin, title and fetch date, and every retrieval is cited by chunk ID.

## 69.4 Skills

Skills are versioned, reviewable know-how for implementing DR mechanisms, loaded by agents only when relevant.

```text
skills/
  rds-cross-region-replica/
    SKILL.md            # frontmatter + procedure
    terraform.md        # patterns and pitfalls
    verify.md           # what verification must see
  aurora-global-database/
  ecr-replication/
  secrets-manager-replication/
  kms-multi-region-keys/
  s3-cross-region-replication/
  route53-failover/
  ecs-dr-service/
  ec2-asg-ami-dr/
  lambda-multi-region/
  sqs-sns-dr/
  waf-web-acl-dr/
  eks-dr-cluster-gitops/
  ebs-snapshot-copy/
```

`SKILL.md` frontmatter:

```yaml
name: rds-cross-region-replica
description: Add a cross-Region read replica for an RDS MySQL/PostgreSQL instance.
applies_to:
  resource_types: [rds/db]
  mechanisms: [live_counterpart]
  strategies: [pilot_light, warm_standby, hot_standby]
version: 1
```

- Agents see the index (name and description) and load a full skill with the `load_skill` tool. This keeps prompts small.
- Shipped skills live in the repository and are reviewed like code. Users and organizations can add or override skills in `<project>/.perpetual/skills/`.
- A skill's IaC patterns are examples, not templates to paste; the agent adapts them to the user's code.

## 69.5 Data Sent and Guardrails

LLM features are off until the user configures a provider and accepts, per project, a notice that lists what will be sent.

Sent: stack subgraph metadata (IDs, types, non-secret properties), findings, plans, simulation results, the IaC files in scope, knowledge-base excerpts, skills.

Never sent: Terraform state, secret values, environment-variable and ConfigMap values, raw CloudTrail or flow-log data, credentials.

Before sending IaC files, a redaction pass removes secret-like values (known key patterns, high-entropy strings, `sensitive` variables' defaults). A `.perpetualignore` file excludes paths entirely.

For `web_search` and `web_fetch`, queries are sanitized before execution so they contain only generic AWS service, resource-type, DR and Terraform terms—never account IDs, ARNs, resource names, internal hostnames, tags or code snippets. Fetched web content is stripped of scripts, hidden text and instruction-like prompt-injection patterns and wrapped as untrusted reference text before indexing into `kb_chunks` or passing to a model. Web research can be disabled per project (`allow_web_research: false` or `--offline`).

Every LLM call (and every `web_search` / `web_fetch` invocation) is recorded locally in `llm_calls`: time, role, provider, model, token counts, which files, documents and web URLs were included, redactions applied, and a hash of the prompt. The UI and `perpetual llm log` show it. For no data egress, use a local model (`ollama`) with web research disabled.

## 69.6 Testing and Evaluation

- Unit and integration tests use a fake chat model and a recorded `web_search` / `web_fetch` harness (including hostile and prompt-injection web-page fixtures). CI never needs an API key or live internet access.
- An evaluation suite in `evals/` runs against real providers on demand: the canonical fixtures (sections 85–89) must yield DR specs that meet their targets, and transformations of `examples/` repositories must pass verification.
- Tracked per model: verification pass rate, retries per change, share of claims with valid citations, accepted vs dismissed advisory items.

---

# 70. LLM Example

User:

```text
Why can't I achieve a 15-minute RTO?
```

The LLM should call deterministic systems.

Result:

```text
Three blockers dominate your current recovery path:

1. RDS restore
   expected 35-65 minutes.

2. ECS environment provisioning
   expected 8-15 minutes.

3. Traffic recovery
   expected 3-7 minutes.

The database path alone exceeds your target.
```

The numbers MUST originate from Perpetual's recovery engine. The explainer calls the same read-only tools as the other agents and cites the results it uses.

---

---

> [↑ Spec Overview & Index](../../spec.md) · [← 05-iac-and-runbooks.md](05-iac-and-runbooks.md) · [07-platform-ui-and-testing.md →](07-platform-ui-and-testing.md)
