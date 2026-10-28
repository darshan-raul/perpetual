"""Build and parse canonical resource IDs (spec §15, §15.1, §15.2).

```text
live       aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER
global     aws://ACCOUNT/global/SERVICE/TYPE/IDENTIFIER
planned    aws://ACCOUNT/REGION/SERVICE/TYPE/tf:<root_id>:<workspace>:<terraform_address>
external   external://SERVICE/NAME
```

IDs must be stable: the same resource always gets the same string, because
overrides, evidence and digests are keyed on it. So building is strict (a bad
part raises instead of producing an ID that would never match), and
`str(parse(x)) == x` holds for every valid ID.

SERVICE/TYPE is the resource's type key, following its ARN (`rds/db`,
`elasticfilesystem/file-system`). IDENTIFIER is the last part and may contain
`/` (log group names do), so parsing splits only the first four segments.
"""

import re
from dataclasses import dataclass

AWS_SCHEME = "aws://"
EXTERNAL_SCHEME = "external://"
GLOBAL_REGION = "global"
PLANNED_PREFIX = "tf:"

_ACCOUNT = re.compile(r"^\d{12}$")
# Covers commercial, GovCloud, China and ISO partitions (us-gov-west-1, cn-north-1).
_REGION = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d+$")
_NAME_PART = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class InvalidResourceIdError(ValueError):
    """A resource ID, or a part of one, does not follow the canonical format."""


@dataclass(frozen=True)
class PlannedAddress:
    """Where a not-yet-created resource comes from: one address in one root and workspace."""

    root_id: str
    workspace: str
    address: str
    """The Terraform address, e.g. module.db.aws_db_instance.this. May contain `:` in
    for_each keys, so it is always the last part."""

    def __post_init__(self) -> None:
        for label, value in (("root_id", self.root_id), ("workspace", self.workspace)):
            _check_text(label, value)
            if ":" in value:
                raise InvalidResourceIdError(f"{label} must not contain ':': {value!r}")
        _check_text("terraform address", self.address)

    def __str__(self) -> str:
        return f"{PLANNED_PREFIX}{self.root_id}:{self.workspace}:{self.address}"


@dataclass(frozen=True)
class AwsResourceId:
    account_id: str
    region: str
    """An AWS Region, or "global"."""
    service: str
    resource_type: str
    identifier: str
    """The resource's own identifier; for a planned resource, its `tf:` address."""

    def __post_init__(self) -> None:
        if not _ACCOUNT.match(self.account_id):
            raise InvalidResourceIdError(f"account must be 12 digits: {self.account_id!r}")
        if self.region != GLOBAL_REGION and not _REGION.match(self.region):
            raise InvalidResourceIdError(f"not an AWS Region or 'global': {self.region!r}")
        _check_name("service", self.service)
        _check_name("resource type", self.resource_type)
        _check_text("identifier", self.identifier)
        if self.identifier.startswith(PLANNED_PREFIX):
            # Validates the planned form, so a malformed tf: ID fails here.
            _parse_planned(self.identifier)

    @property
    def is_global(self) -> bool:
        return self.region == GLOBAL_REGION

    @property
    def is_planned(self) -> bool:
        """True for a resource that exists only in a Terraform plan (spec §15.1)."""
        return self.identifier.startswith(PLANNED_PREFIX)

    @property
    def planned_address(self) -> PlannedAddress | None:
        return _parse_planned(self.identifier) if self.is_planned else None

    @property
    def type_key(self) -> str:
        """`SERVICE/TYPE`, the key that picks the typed properties model."""
        return f"{self.service}/{self.resource_type}"

    def __str__(self) -> str:
        return (
            f"{AWS_SCHEME}{self.account_id}/{self.region}/"
            f"{self.service}/{self.resource_type}/{self.identifier}"
        )


@dataclass(frozen=True)
class ExternalResourceId:
    """A user-declared dependency Perpetual cannot discover (spec §15.2)."""

    service: str
    """User-chosen, e.g. payments-gateway."""
    name: str

    def __post_init__(self) -> None:
        _check_name("service", self.service)
        _check_text("name", self.name)

    def __str__(self) -> str:
        return f"{EXTERNAL_SCHEME}{self.service}/{self.name}"


ResourceId = AwsResourceId | ExternalResourceId


def aws_id(account_id: str, region: str, service: str, resource_type: str, identifier: str) -> str:
    """A live AWS resource ID. Use `global_id` for global resources."""
    if identifier.startswith(PLANNED_PREFIX):
        raise InvalidResourceIdError("a live identifier must not start with 'tf:'; use planned_id")
    return str(AwsResourceId(account_id, region, service, resource_type, identifier))


def global_id(account_id: str, service: str, resource_type: str, identifier: str) -> str:
    """An ID for a resource with no Region, e.g. a Route 53 hosted zone or an IAM role."""
    return aws_id(account_id, GLOBAL_REGION, service, resource_type, identifier)


def planned_id(
    account_id: str,
    region: str,
    service: str,
    resource_type: str,
    *,
    root_id: str,
    workspace: str,
    address: str,
) -> str:
    """An ID for a resource that exists only in a plan. It has no ARN yet (spec §15.1)."""
    planned = PlannedAddress(root_id, workspace, address)
    return str(AwsResourceId(account_id, region, service, resource_type, str(planned)))


def external_id(service: str, name: str) -> str:
    return str(ExternalResourceId(service, name))


def parse(resource_id: str) -> ResourceId:
    """Parse any canonical ID. Raises InvalidResourceIdError if it is not one."""
    if resource_id.startswith(AWS_SCHEME):
        parts = resource_id.removeprefix(AWS_SCHEME).split("/", 4)
        if len(parts) != 5:
            raise InvalidResourceIdError(
                f"expected aws://ACCOUNT/REGION/SERVICE/TYPE/IDENTIFIER: {resource_id!r}"
            )
        return AwsResourceId(*parts)
    if resource_id.startswith(EXTERNAL_SCHEME):
        parts = resource_id.removeprefix(EXTERNAL_SCHEME).split("/", 1)
        if len(parts) != 2:
            raise InvalidResourceIdError(f"expected external://SERVICE/NAME: {resource_id!r}")
        return ExternalResourceId(*parts)
    raise InvalidResourceIdError(f"unknown ID scheme: {resource_id!r}")


def parse_aws(resource_id: str) -> AwsResourceId:
    parsed = parse(resource_id)
    if not isinstance(parsed, AwsResourceId):
        raise InvalidResourceIdError(f"not an AWS resource ID: {resource_id!r}")
    return parsed


def is_valid(resource_id: str) -> bool:
    try:
        parse(resource_id)
    except InvalidResourceIdError:
        return False
    return True


def _parse_planned(identifier: str) -> PlannedAddress:
    parts = identifier.removeprefix(PLANNED_PREFIX).split(":", 2)
    if len(parts) != 3:
        raise InvalidResourceIdError(
            f"expected tf:<root_id>:<workspace>:<terraform_address>: {identifier!r}"
        )
    return PlannedAddress(*parts)


def _check_name(label: str, value: str) -> None:
    if not _NAME_PART.match(value):
        raise InvalidResourceIdError(
            f"{label} must be lowercase letters, digits and '-': {value!r}"
        )


def _check_text(label: str, value: str) -> None:
    if not value:
        raise InvalidResourceIdError(f"{label} must not be empty")
    if _CONTROL.search(value):
        raise InvalidResourceIdError(f"{label} must not contain control characters")
