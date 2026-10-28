# `models.properties`: typed resource properties

Part of the [`models` package](models.md).

**Owns:** one typed configuration model per AWS resource type, which rule packs read instead of the raw property dict.
**Spec:** §5–§8.1, §15.3, §15.4, §28.1, §42, §67. **Tracker:** P0-04b (compute), P0-04c (data and storage), P0-04d (messaging, network, edge, supporting, ARC, Identity Center, and the planned-resource fixes from review), P0-04e (external, generic, CodePipeline).
**Code:** `apps/api/perpetual/models/properties/`.

## In one paragraph

A `ResourceNode` keeps whatever a source reported in `properties`, a raw dict that rules never read (§15.3). Normalizers also fill `typed_properties`: a model with exactly the fields the rules need for that resource type, validated. Pydantic chooses the model from its `type_key`, so a plain dict from a fixture or importer becomes the right class, and anything malformed fails when it is loaded.

## How a dict becomes the right model

Each model has a `type_key` equal to the `SERVICE/TYPE` part of the canonical resource ID. `ResourceProperties` (in `properties/__init__.py`) is a union of all models, discriminated by `type_key`:

```text
 ResourceNode dict
   id: aws://…/ecs/service/checkout          service="ecs", resource_type="service"
   typed_properties: {type_key: "ecs/service", …}
                          │
                          ▼  Pydantic reads type_key, picks one model from the union
        ┌──────────────────────────────────────────────────────────┐
        │ ResourceProperties = ECSServiceProperties | RDSInstance… │ (57 keys)
        └──────────────────────────────────────────────────────────┘
                          │  validates the fields of ECSServiceProperties only
                          ▼
        ResourceNode._typed_properties_match_type
          type_key == "service/resource_type" of the node?   "ecs/service" == "ecs/service" ✓
            external/dependency -> allowed only when provider == "external"
            generic/resource    -> allowed only when the type has no model
          mismatch -> error (RDS fields on an ECS node would make every rule read nonsense)
```

```python
node = ResourceNode.model_validate({
    "id": "aws://123456789012/ap-south-1/ecs/service/checkout",
    "provider": "aws", "service": "ecs", "resource_type": "service",
    "typed_properties": {"type_key": "ecs/service", "service_name": "checkout",
                         "cluster_arn": "...", "task_definition_arn": "...", "desired_count": 3},
    "discovered_at": "2026-10-28T12:00:00Z",
})
type(node.typed_properties)  # ECSServiceProperties
```

`ResourceNode` checks that `type_key` matches its own `service/resource_type`, with two exceptions (see [External, generic and out of scope](#external-generic-and-out-of-scope)). `type_key` follows the service name in the resource's ARN, so EBS uses `ec2/…`, EFS `elasticfilesystem/…`, routing controls `route53-recovery-control/…`.

## Three kinds of missing

The engine treats these differently, so the models keep them apart:

| Case | How it looks | Meaning for rules |
|---|---|---|
| Absent or null | field is `None` | the source says there is no value |
| Unknown | field name listed in `unknown_fields` | e.g. a Terraform plan value known only after apply; treat as UNKNOWN, never as absent or as the old live value (§15.4) |
| Known empty | empty list | known to have none |

`unknown_fields` may only name real fields of the model, may not repeat one, and is stored sorted, so the same state always hashes the same (§56.3).

Two helpers read these cases:

- `is_missing(field)`: empty *and* not marked unknown. "Empty" means None or an empty string or collection; `0` and `False` are values, never missing. Validators use it, so a value known only after apply never fails a check such as "an Image function needs `image_uri`".
- `is_unknown(field)`: the field is marked unknown.

### Planned resources: required fields

A resource that a Terraform plan will create has no ARN or ID until apply, and the importer must never invent one (§15.4). So values that AWS assigns (IDs, ARNs, URIs, computed numbers such as a task definition's revision) are declared in a model's `required_fields`. They are typed `... | None`, and the base class enforces that each one is **present, or listed in `unknown_fields`**: never just absent.

```text
 for each name in required_fields:

     value present? ──yes──> ok
          │no
          ▼
     name in unknown_fields? ──yes──> ok, rules treat it as UNKNOWN
          │no
          ▼
     error: "<name> is required; if it is only known after apply, list it in unknown_fields"

 nested part (e.g. one container):  a missing required value inside it
     -> the PARENT lists the whole field: unknown_fields=["containers"]
```

```python
ECSServiceProperties.model_validate({"service_name": "checkout", "desired_count": 2})
# error: cluster_arn is required; if it is only known after apply, list it in unknown_fields

ECSServiceProperties.model_validate({"service_name": "checkout", "desired_count": 2,
    "unknown_fields": ["cluster_arn", "task_definition_arn"]})   # loads; both are UNKNOWN
```

Names you choose in code (bucket name, function name, service name) stay plainly required, because Terraform knows them at plan time.

Nested parts, such as a container definition, a replication rule or a CloudFront origin, inherit `PropertyPart` and declare their own `required_fields`. A part can't hold `unknown_fields` itself. If one of its required values is unknown, the parent field is listed instead (e.g. `unknown_fields=["containers"]`), and rules treat that whole field as UNKNOWN. The check goes one level deep. Checks that pair two fields ("set together or not at all") skip when either side is unknown. For lists of plain strings with some unknown items (a security group rule naming a group the plan creates), the importer keeps the known items and marks the field unknown.

## What is never stored

There is no field for these values, so a collector that tried to store one would fail validation (§67):

- secret and SSM parameter values (secrets appear only as `SecretReference.value_from`, an ARN);
- environment variable values (only names: `environment_names`);
- launch-template user data (only `has_user_data`);
- SNS endpoints that point at people or URLs (email, SMS, HTTP/S); only AWS-resource endpoints such as an SQS queue ARN are kept.

IAM policies *are* stored, as structured `PolicyStatement`s (effect, actions, resources), because rules must find DR roles that grant only primary-Region ARNs (XREG-IAM-002). Policies aren't secrets.

## Resource types

**Compute and containers** (`ecs.py`, `ec2.py`, `awslambda.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `ecs/cluster` | `ECSClusterProperties` | capacity providers |
| `ecs/service` | `ECSServiceProperties` | task definition, launch type, desired count, subnets, security groups, target groups, Cloud Map, scaling |
| `ecs/task-definition` | `ECSTaskDefinitionProperties` | roles, containers: images, secret references, env var names, health checks |
| `ec2/instance` | `EC2InstanceProperties` | AMI, instance type, subnet, profile, volumes |
| `autoscaling/group` | `AutoScalingGroupProperties` | sizes, launch template, instance types, subnets, target groups |
| `ec2/launch-template` | `LaunchTemplateProperties` | AMI (or SSM parameter), profile, block devices and their KMS keys |
| `ec2/image` | `AMIProperties` | owner, state, backing snapshots and KMS keys |
| `lambda/function` | `LambdaFunctionProperties` | package type, S3 code or ECR image, layers, role, VPC, env var names, destinations, concurrency |
| `lambda/event-source-mapping` | `LambdaEventSourceMappingProperties` | source queue/stream, target function, state, failure destination |

**Data and storage** (`rds.py`, `dynamodb.py`, `s3.py`, `ebs.py`, `efs.py`, `backup.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `rds/db` | `RDSInstanceProperties` | engine, size, Multi-AZ (AZ only), backups and latest restorable time, cross-Region backup Regions, replicas, subnet group, KMS |
| `rds/cluster` | `AuroraClusterProperties` | members, writer, Global Database role (primary/secondary), replication source, backups, KMS |
| `rds/snapshot`, `rds/cluster-snapshot` | `RDSSnapshotProperties` | one model for both: source, type, age, source Region of a copy, KMS |
| `dynamodb/table` | `DynamoDBTableProperties` | PITR, Global Tables version, replicas (Region, status, KMS key, table class), streams, encryption, size |
| `dynamodb/backup` | `DynamoDBBackupProperties` | table, type, age, size |
| `s3/bucket` | `S3BucketProperties` | versioning, replication rules (destination, KMS replication, RTC), encryption, size |
| `ec2/volume` | `EBSVolumeProperties` | size, type, encryption and KMS, source snapshot, attachments |
| `ec2/snapshot` | `EBSSnapshotProperties` | source volume, age, encryption and KMS |
| `elasticfilesystem/file-system` | `EFSFileSystemProperties` | mount targets, KMS, replication destinations and last sync time, replica flag, backups |
| `backup/backup-vault` | `BackupVaultProperties` | KMS, Vault Lock |
| `backup/recovery-point` | `BackupRecoveryPointProperties` | protected resource, vault, status, age, cross-Region copy source, KMS |

Volumetric fields (storage size, IOPS, item counts, bucket size) are here because they drive recovery time (data gravity, §42). Fast-changing metrics such as replication lag are separate measurements with freshness rules (P0-04e).

**Messaging** (`messaging.py`): SQS endpoint recovery (RTO) and in-flight message durability (RPO) are separate questions (§7.1).

| `type_key` | Model | What rules use it for |
|---|---|---|
| `sqs/queue` | `SQSQueueProperties` | FIFO, retention, DLQ and redrive, encryption |
| `sns/topic` | `SNSTopicProperties` | FIFO, encryption, delivery logging |
| `sns/subscription` | `SNSSubscriptionProperties` | topic, protocol, target ARN (AWS resources only) |

**Network** (`network.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `ec2/vpc` | `VPCProperties` | CIDR blocks |
| `ec2/subnet` | `SubnetProperties` | VPC, CIDR, route table |
| `ec2/security-group` | `SecurityGroupProperties` | ingress/egress rules; peers by group ID are "permitted" evidence (§14.1) |
| `ec2/route-table` | `RouteTableProperties` | routes and their targets, subnet associations |
| `ec2/natgateway` | `NATGatewayProperties` | subnet, connectivity |
| `ec2/internet-gateway` | `InternetGatewayProperties` | attached VPCs |
| `ec2/vpc-endpoint` | `VPCEndpointProperties` | service name (contains the Region), type, subnets, private DNS |
| `ec2/transit-gateway-attachment` | `TransitGatewayAttachmentProperties` | transit gateway, attached resource |

**Load balancing** (`elb.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `elasticloadbalancing/loadbalancer` | `LoadBalancerProperties` | ALB/NLB, scheme, DNS name (matched to Route 53 aliases), subnets, Web ACL |
| `elasticloadbalancing/listener` | `ListenerProperties` | protocol, port, ACM certificates, default target groups |
| `elasticloadbalancing/targetgroup` | `TargetGroupProperties` | target type, health check, registered targets |

**Edge: DNS, CDN, certificates, WAF** (`edge.py`). Route 53 and CloudFront control planes live in us-east-1 (§8.1).

| `type_key` | Model | What rules use it for |
|---|---|---|
| `route53/hostedzone` | `HostedZoneProperties` | public/private, VPCs, Accelerated Recovery (public zones only) |
| `route53/recordset` | `RecordSetProperties` | routing policy, failover role, health check, alias target or values |
| `route53/healthcheck` | `HealthCheckProperties` | type, target, inversion, routing control (for ARC-backed checks) |
| `cloudfront/distribution` | `CloudFrontDistributionProperties` | origins, origin-group failover, us-east-1 certificate, Web ACL |
| `acm/certificate` | `ACMCertificateProperties` | domains, type, expiry, what uses it |
| `wafv2/webacl` | `WebACLProperties` | scope, default action, rules and managed groups (DR parity), associations |

**Supporting services** (`supporting.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `ecr/repository` | `ECRRepositoryProperties` | URI (contains the Region), encryption |
| `ecr/registry` | `ECRRegistryProperties` | replication rules: once per registry, so a PR may conflict with other owners |
| `ecr/image` | `ECRImageProperties` | digest, tags: an image must exist in the DR registry |
| `secretsmanager/secret` | `SecretProperties` | KMS, rotation, replicas per Region and their status (metadata only) |
| `ssm/parameter` | `SSMParameterProperties` | type, KMS, version and last-modified for parity checks (no value) |
| `kms/key` | `KMSKeyProperties` | multi-Region role, primary key, replica Regions, aliases |
| `iam/role` | `IAMRoleProperties` | trusted principals, attached policies, inline statements |
| `iam/policy` | `IAMPolicyProperties` | default-version statements |
| `logs/log-group` | `LogGroupProperties` | retention, KMS, subscriptions (out of RTO scope by default) |

**Recovery control and operator access** (`recovery_control.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `route53-recovery-control/routingcontrol` | `RoutingControlProperties` | control panel, On/Off state |
| `arc-region-switch/plan` | `RegionSwitchPlanProperties` | Regions, RTO, workflows and steps with their targets and ungraceful behaviour, health alarms, evaluation status (ARC-RS-001) |
| `route53-recovery-readiness/readiness-check` | `ReadinessCheckProperties` | legacy: collected, never recommended |
| `sso/instance` | `IdentityCenterInstanceProperties` | home Region and replica Regions (OPS-ACCESS-001) |

**External, generic and out of scope** (`other.py`)

| `type_key` | Model | What rules use it for |
|---|---|---|
| `external/dependency` | `ExternalResourceProperties` | declared DR posture (`unknown` until the user says otherwise), description, matching hostnames |
| `generic/resource` | `GenericResourceProperties` | nothing: it keeps unmodelled AWS types (e.g. ElastiCache in v0.1) visible in the graph; Terraform or CloudFormation type for reference |
| `codepipeline/pipeline` | `CodePipelineProperties` | what it deploys and to which Regions: a pipeline the recovery plan uses comes back into RTO scope (§24.1) |

### External, generic and out of scope

These two are the exceptions to "`type_key` matches the node's `service/type`":

- `external/dependency` is allowed on any node with `provider="external"`, whatever its user-chosen service name (§15.2), and only on such nodes.
- `generic/resource` is allowed on any AWS node whose `service/type` has **no** typed model. `SPECIFIC_TYPE_KEYS` lists the ones that do, so the fallback can never be used to skip a type's validation.

## Rules they enforce, and why

| Rule | Where | Why (spec) |
|---|---|---|
| `unknown_fields` names only real configuration fields, without repeats; stored sorted | `TypedProperties` | Unknown must stay distinct from absent (§15.4); stable hashes (§56.3) |
| Required (AWS-assigned) fields are present or unknown, including inside nested parts | `TypedProperties`, `PropertyPart` | Planned resources have no ARN yet; never invent one (§15.4) |
| Secret values, env values, user data and personal SNS endpoints have no field | `ecs.py`, `awslambda.py`, `ec2.py`, `supporting.py`, `messaging.py` | §67 |
| Auto Scaling sizes satisfy min ≤ desired ≤ max | `AutoScalingGroupProperties` | AWS rejects anything else |
| A launch template has one image source: AMI ID or SSM parameter | `LaunchTemplateProperties` | §5.3 |
| An Image function has an image and no S3 package or layers; a Zip function has no image | `LambdaFunctionProperties` | §5.4 |
| A task definition has at least one container | `ECSTaskDefinitionProperties` | §5.1 |
| An Aurora instance belongs to a cluster | `RDSInstanceProperties` | Data and recovery settings live on the cluster (§6.2) |
| A Global Database member has both its global cluster ID and its role (unless one is unknown) | `AuroraClusterProperties` | The secondary is the promotion path (§6.2) |
| Aurora keeps at least one day of backups | `AuroraClusterProperties` | AWS minimum |
| A DynamoDB table with replicas names its global-table version; one replica per Region | `DynamoDBTableProperties` | §6.3 |
| S3 replication needs versioning Enabled (unless unknown) and a replication role; rule IDs are distinct | `S3BucketProperties` | AWS prerequisites (§7); versioning is often a separate Terraform resource |
| A recovery point can't complete before it was created | `BackupRecoveryPointProperties` | Its age bounds RPO (§51) |
| An SQS redrive names both the DLQ and the receive count (unless one is unknown) | `SQSQueueProperties` | §7.1; a plan creating queue and DLQ together knows only the count |
| Security group port ranges are ordered | `SecurityGroupRule` | Broken import otherwise |
| HTTPS and TLS listeners have a certificate | `ListenerProperties` | ACM is Regional; DR needs its own (§8) |
| A private zone has a VPC and no Accelerated Recovery | `HostedZoneProperties` | Accelerated Recovery is public-only (§8.1) |
| A record is an alias or has values; non-simple routing has a set identifier; failover role ↔ failover routing | `RecordSetProperties` | Route 53 requirements |
| CloudFront origin groups use two distinct, known origins | `CloudFrontDistributionProperties` | Origin failover (§8) |
| Only SecureString parameters use KMS | `SSMParameterProperties` | SSM behaviour |
| A secret has at most one replica per Region | `SecretProperties` | Secrets Manager behaviour |
| Multi-Region key fields agree (unless the role is unknown); a replica names its primary | `KMSKeyProperties` | XREG-KMS-003 depends on them |
| A policy statement has actions | `PolicyStatement` | IAM requirement |
| A Region switch plan has two distinct Regions; primary and workflow targets are among them; parallel steps nest one level | `RegionSwitchPlanProperties`, `RegionSwitchStep` | ARC constraints (§63.3) |
| Identity Center replicas are other Regions than home | `IdentityCenterInstanceProperties` | OPS-ACCESS-001 (§28.1) |
| External properties only on `provider="external"` nodes; generic only for types without a model | `ResourceNode` | §15.2; no validation bypass |

## Tests

In `apps/api/tests/models/`:

- `test_model_properties_compute.py`: union selection, type mismatch, `unknown_fields`, no secret/env/user-data values, ECS/EC2/Lambda rules.
- `test_model_properties_data.py`: both RDS snapshot keys, Multi-AZ default, Aurora and Global Database rules, DynamoDB replicas, S3 replication prerequisites, recovery-point times.
- `test_model_properties_planned.py`: required-or-unknown fields, nested parts, sorted `unknown_fields`, `0`/`False` vs empty, planned Aurora and S3 cases.
- `test_model_facts_and_fallbacks.py`: external, generic and CodePipeline properties and their node checks (facts are covered in [models.md](models.md#tests)).
- `test_model_properties_supporting.py`: every properties model is registered in the union and `type_key`s are unique; messaging, network, edge, supporting, ARC and Identity Center rules.

## Adding a resource type

1. Write the model in the file for its service, inheriting `TypedProperties`, with `type_key: Literal["service/type"] = "service/type"` using the service name from its ARN. Declare AWS-assigned values in `required_fields` and type them `... | None`. Nested parts inherit `PropertyPart`.
2. Import it in `properties/__init__.py` and add it to `ResourceProperties`. A test fails if you forget.
3. Add its rules and tests here and in the matching test file.
