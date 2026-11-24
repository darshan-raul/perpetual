"""Normalization from raw source payloads into canonical `ResourceNode`s and identity resolution."""

from perpetual.normalization.aws import (
    AwsFixtureError,
    AwsFixtureImportResult,
    import_aws_fixture_dict,
    import_aws_fixture_file,
    resolve_aws_fixture_path,
)
from perpetual.normalization.identity import (
    AttributeConflict,
    IdentityResolutionResult,
    resolve_identities,
)

__all__ = [
    "AttributeConflict",
    "AwsFixtureError",
    "AwsFixtureImportResult",
    "IdentityResolutionResult",
    "import_aws_fixture_dict",
    "import_aws_fixture_file",
    "resolve_aws_fixture_path",
    "resolve_identities",
]
