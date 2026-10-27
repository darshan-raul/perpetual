"""Typed properties for VPC networking (spec §8).

A DR Region needs its own network path: subnets in usable AZs, security groups
that allow the same flows, and a route out (NAT, internet gateway) or to AWS
services (VPC endpoints). Security group rules are also dependency evidence with
basis "permitted" (spec §14.1).
"""

from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from perpetual.models.common import NonEmptyStr
from perpetual.models.properties.base import PropertyPart, TypedProperties


class VPCProperties(TypedProperties):
    type_key: Literal["ec2/vpc"] = "ec2/vpc"
    required_fields: ClassVar[frozenset[str]] = frozenset({"cidr_blocks", "vpc_id"})
    vpc_id: NonEmptyStr | None = None
    cidr_blocks: list[NonEmptyStr] = Field(default_factory=list)
    is_default: bool = False


class SubnetProperties(TypedProperties):
    type_key: Literal["ec2/subnet"] = "ec2/subnet"
    required_fields: ClassVar[frozenset[str]] = frozenset({"cidr_block", "subnet_id", "vpc_id"})
    subnet_id: NonEmptyStr | None = None
    vpc_id: NonEmptyStr | None = None
    cidr_block: NonEmptyStr | None = None
    map_public_ip_on_launch: bool = False
    route_table_id: str | None = None
    """None means the VPC's main route table."""


class SecurityGroupRule(PropertyPart):
    protocol: NonEmptyStr
    """tcp, udp, icmp or -1 (all)."""
    from_port: int | None = Field(default=None, ge=-1, le=65535)
    to_port: int | None = Field(default=None, ge=-1, le=65535)
    cidr_blocks: list[NonEmptyStr] = Field(default_factory=list)
    ipv6_cidr_blocks: list[NonEmptyStr] = Field(default_factory=list)
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    """Peers referenced by security group ID: the strongest network evidence."""
    prefix_list_ids: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ports_ordered(self) -> Self:
        if (
            self.from_port is not None
            and self.to_port is not None
            and self.from_port > self.to_port
        ):
            raise ValueError("from_port must not exceed to_port")
        return self


class SecurityGroupProperties(TypedProperties):
    type_key: Literal["ec2/security-group"] = "ec2/security-group"
    required_fields: ClassVar[frozenset[str]] = frozenset({"group_id", "vpc_id"})
    group_id: NonEmptyStr | None = None
    group_name: NonEmptyStr
    vpc_id: NonEmptyStr | None = None
    ingress: list[SecurityGroupRule] = Field(default_factory=list)
    egress: list[SecurityGroupRule] = Field(default_factory=list)


class Route(PropertyPart):
    destination: NonEmptyStr
    """CIDR or prefix list ID."""
    target_type: Literal[
        "local",
        "internet-gateway",
        "nat-gateway",
        "transit-gateway",
        "vpc-endpoint",
        "vpc-peering",
        "network-interface",
        "other",
    ]
    target_id: str | None = None


class RouteTableProperties(TypedProperties):
    type_key: Literal["ec2/route-table"] = "ec2/route-table"
    required_fields: ClassVar[frozenset[str]] = frozenset({"route_table_id", "vpc_id"})
    route_table_id: NonEmptyStr | None = None
    vpc_id: NonEmptyStr | None = None
    main: bool = False
    subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)


class NATGatewayProperties(TypedProperties):
    type_key: Literal["ec2/natgateway"] = "ec2/natgateway"
    required_fields: ClassVar[frozenset[str]] = frozenset({"nat_gateway_id", "subnet_id"})
    nat_gateway_id: NonEmptyStr | None = None
    subnet_id: NonEmptyStr | None = None
    connectivity: Literal["public", "private"] = "public"
    state: Literal["pending", "available", "deleting", "deleted", "failed"] | None = None


class InternetGatewayProperties(TypedProperties):
    type_key: Literal["ec2/internet-gateway"] = "ec2/internet-gateway"
    required_fields: ClassVar[frozenset[str]] = frozenset({"internet_gateway_id"})
    internet_gateway_id: NonEmptyStr | None = None
    vpc_ids: list[NonEmptyStr] = Field(default_factory=list)


class VPCEndpointProperties(TypedProperties):
    type_key: Literal["ec2/vpc-endpoint"] = "ec2/vpc-endpoint"
    required_fields: ClassVar[frozenset[str]] = frozenset({"vpc_endpoint_id", "vpc_id"})
    vpc_endpoint_id: NonEmptyStr | None = None
    vpc_id: NonEmptyStr | None = None
    service_name: NonEmptyStr
    """e.g. com.amazonaws.ap-south-1.secretsmanager. The Region inside it matters."""
    endpoint_type: Literal[
        "Interface", "Gateway", "GatewayLoadBalancer", "Resource", "ServiceNetwork"
    ]
    subnet_ids: list[NonEmptyStr] = Field(default_factory=list)
    security_group_ids: list[NonEmptyStr] = Field(default_factory=list)
    route_table_ids: list[NonEmptyStr] = Field(default_factory=list)
    private_dns_enabled: bool = False


class TransitGatewayAttachmentProperties(TypedProperties):
    type_key: Literal["ec2/transit-gateway-attachment"] = "ec2/transit-gateway-attachment"
    required_fields: ClassVar[frozenset[str]] = frozenset({"attachment_id", "transit_gateway_id"})
    attachment_id: NonEmptyStr | None = None
    transit_gateway_id: NonEmptyStr | None = None
    resource_type: Literal["vpc", "vpn", "direct-connect-gateway", "peering", "connect", "other"]
    resource_id: str | None = None
    state: str | None = None
