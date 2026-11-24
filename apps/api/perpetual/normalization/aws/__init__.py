"""AWS API response normalizers and recorded-fixture importer (`P1b-03`)."""

from perpetual.normalization.aws.ecs import (
    normalize_ecs_cluster,
    normalize_ecs_service,
    normalize_ecs_task_definition,
)
from perpetual.normalization.aws.importer import (
    AwsFixtureError,
    AwsFixtureImportResult,
    import_aws_fixture_dict,
    import_aws_fixture_file,
    resolve_aws_fixture_path,
)
from perpetual.normalization.aws.network import (
    normalize_acm_certificate,
    normalize_hosted_zone,
    normalize_listener,
    normalize_load_balancer,
    normalize_record_set,
    normalize_security_group,
    normalize_subnet,
    normalize_target_group,
    normalize_vpc,
)
from perpetual.normalization.aws.rds import (
    normalize_aurora_cluster,
    normalize_rds_instance,
    normalize_rds_snapshot,
)
from perpetual.normalization.aws.s3 import normalize_s3_bucket
from perpetual.normalization.aws.supporting import (
    normalize_ecr_registry,
    normalize_ecr_repository,
    normalize_iam_policy,
    normalize_iam_role,
    normalize_kms_key,
    normalize_log_group,
    normalize_secretsmanager_secret,
    normalize_ssm_parameter,
)

__all__ = [
    "AwsFixtureError",
    "AwsFixtureImportResult",
    "import_aws_fixture_dict",
    "import_aws_fixture_file",
    "normalize_acm_certificate",
    "normalize_aurora_cluster",
    "normalize_ecr_registry",
    "normalize_ecr_repository",
    "normalize_ecs_cluster",
    "normalize_ecs_service",
    "normalize_ecs_task_definition",
    "normalize_hosted_zone",
    "normalize_iam_policy",
    "normalize_iam_role",
    "normalize_kms_key",
    "normalize_listener",
    "normalize_load_balancer",
    "normalize_log_group",
    "normalize_rds_instance",
    "normalize_rds_snapshot",
    "normalize_record_set",
    "normalize_s3_bucket",
    "normalize_secretsmanager_secret",
    "normalize_security_group",
    "normalize_ssm_parameter",
    "normalize_subnet",
    "normalize_target_group",
    "normalize_vpc",
    "resolve_aws_fixture_path",
]
