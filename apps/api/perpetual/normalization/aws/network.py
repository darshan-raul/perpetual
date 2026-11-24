"""AWS API response normalizers for VPC networking, ELB, Route 53, and ACM."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, cast

from perpetual.ids import aws_id, global_id
from perpetual.models.properties.edge import (
    ACMCertificateProperties,
    AliasTarget,
    HostedZoneProperties,
    RecordSetProperties,
)
from perpetual.models.properties.elb import (
    ListenerProperties,
    LoadBalancerProperties,
    TargetGroupProperties,
)
from perpetual.models.properties.network import (
    SecurityGroupProperties,
    SecurityGroupRule,
    SubnetProperties,
    VPCProperties,
)
from perpetual.models.resource import ResourceNode
from perpetual.normalization.aws._common import (
    aws_source_ref,
    ensure_aware_utc,
    parse_aws_datetime,
    tags_from_list,
)

_LbType = Literal["application", "network", "gateway"]
_LbScheme = Literal["internet-facing", "internal"]
_ListenerProtocol = Literal["HTTP", "HTTPS", "TCP", "TLS", "UDP", "TCP_UDP", "GENEVE"]
_TargetType = Literal["instance", "ip", "lambda", "alb"]
_CertType = Literal["AMAZON_ISSUED", "IMPORTED", "PRIVATE"]
_RoutingPolicy = Literal[
    "simple",
    "failover",
    "weighted",
    "latency",
    "geolocation",
    "geoproximity",
    "multivalue",
    "cidr",
]


def normalize_vpc(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one VPC object from `ec2:DescribeVpcs`."""
    ts = ensure_aware_utc(collected_at)
    vpc_id = str(raw["VpcId"])
    tags = tags_from_list(raw.get("Tags"))

    cidrs: list[str] = []
    if raw.get("CidrBlock"):
        cidrs.append(str(raw["CidrBlock"]))
    for assoc in raw.get("CidrBlockAssociationSet", []):
        cidr = assoc.get("CidrBlock")
        if cidr and str(cidr) not in cidrs:
            cidrs.append(str(cidr))

    typed = VPCProperties(
        vpc_id=vpc_id,
        cidr_blocks=cidrs,
        is_default=bool(raw.get("IsDefault", False)),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ec2", "vpc", vpc_id),
        provider="aws",
        service="ec2",
        resource_type="vpc",
        account_id=account_id,
        region=region,
        name=tags.get("Name", vpc_id),
        arn=f"arn:aws:ec2:{region}:{account_id}:vpc/{vpc_id}",
        tags=tags,
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ec2:DescribeVpcs",
                identifier=vpc_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_subnet(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    route_table_id: str | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one Subnet object from `ec2:DescribeSubnets`."""
    ts = ensure_aware_utc(collected_at)
    subnet_id = str(raw["SubnetId"])
    tags = tags_from_list(raw.get("Tags"))

    typed = SubnetProperties(
        subnet_id=subnet_id,
        vpc_id=str(raw["VpcId"]),
        cidr_block=str(raw["CidrBlock"]),
        map_public_ip_on_launch=bool(raw.get("MapPublicIpOnLaunch", False)),
        route_table_id=route_table_id,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ec2", "subnet", subnet_id),
        provider="aws",
        service="ec2",
        resource_type="subnet",
        account_id=account_id,
        region=region,
        availability_zone=raw.get("AvailabilityZone"),
        name=tags.get("Name", subnet_id),
        arn=raw.get("SubnetArn") or f"arn:aws:ec2:{region}:{account_id}:subnet/{subnet_id}",
        tags=tags,
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ec2:DescribeSubnets",
                identifier=subnet_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_security_group(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one SecurityGroup object from `ec2:DescribeSecurityGroups`."""
    ts = ensure_aware_utc(collected_at)
    group_id = str(raw["GroupId"])
    group_name = str(raw["GroupName"])
    tags = tags_from_list(raw.get("Tags"))

    typed = SecurityGroupProperties(
        group_id=group_id,
        group_name=group_name,
        vpc_id=str(raw["VpcId"]),
        ingress=[_parse_sg_rule(p) for p in raw.get("IpPermissions", [])],
        egress=[_parse_sg_rule(p) for p in raw.get("IpPermissionsEgress", [])],
    )
    return ResourceNode(
        id=aws_id(account_id, region, "ec2", "security-group", group_id),
        provider="aws",
        service="ec2",
        resource_type="security-group",
        account_id=account_id,
        region=region,
        name=tags.get("Name", group_name),
        arn=f"arn:aws:ec2:{region}:{account_id}:security-group/{group_id}",
        tags=tags,
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="ec2:DescribeSecurityGroups",
                identifier=group_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_load_balancer(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    tags: Sequence[Mapping[str, Any]] | None = None,
    web_acl_arn: str | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one LoadBalancer object from `elbv2:DescribeLoadBalancers`."""
    ts = ensure_aware_utc(collected_at)
    name = str(raw["LoadBalancerName"])
    arn = str(raw["LoadBalancerArn"])
    identifier = arn.split(":loadbalancer/", 1)[-1]

    lb_type_raw = str(raw.get("Type", "application"))
    lb_type: _LbType = (
        cast(_LbType, lb_type_raw)
        if lb_type_raw in {"application", "network", "gateway"}
        else "application"
    )
    scheme_raw = str(raw.get("Scheme", "internet-facing"))
    scheme: _LbScheme = (
        cast(_LbScheme, scheme_raw)
        if scheme_raw in {"internet-facing", "internal"}
        else "internet-facing"
    )
    subnet_ids = [
        str(az["SubnetId"]) for az in raw.get("AvailabilityZones", []) if az.get("SubnetId")
    ]
    state = raw.get("State", {}).get("Code") if isinstance(raw.get("State"), Mapping) else None

    typed = LoadBalancerProperties(
        name=name,
        lb_type=lb_type,
        scheme=scheme,
        dns_name=raw.get("DNSName"),
        vpc_id=raw.get("VpcId"),
        subnet_ids=subnet_ids,
        security_group_ids=[str(sg) for sg in raw.get("SecurityGroups", [])],
        web_acl_arn=web_acl_arn,
        state=state,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "elasticloadbalancing", "loadbalancer", identifier),
        provider="aws",
        service="elasticloadbalancing",
        resource_type="loadbalancer",
        account_id=account_id,
        region=region,
        name=name,
        arn=arn,
        tags=tags_from_list(tags),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="elbv2:DescribeLoadBalancers",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_listener(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one Listener object from `elbv2:DescribeListeners`."""
    ts = ensure_aware_utc(collected_at)
    arn = str(raw["ListenerArn"])
    identifier = arn.split(":listener/", 1)[-1]
    proto_raw = str(raw["Protocol"])
    if proto_raw not in {"HTTP", "HTTPS", "TCP", "TLS", "UDP", "TCP_UDP", "GENEVE"}:
        raise ValueError(f"unsupported listener protocol: {proto_raw!r}")
    protocol = cast(_ListenerProtocol, proto_raw)

    cert_arns = [
        str(c["CertificateArn"]) for c in raw.get("Certificates", []) if c.get("CertificateArn")
    ]
    tg_arns: list[str] = []
    for action in raw.get("DefaultActions", []):
        if action.get("TargetGroupArn"):
            tg_arns.append(str(action["TargetGroupArn"]))
        fwd = action.get("ForwardConfig", {})
        for tg in fwd.get("TargetGroups", []):
            if tg.get("TargetGroupArn"):
                tg_arns.append(str(tg["TargetGroupArn"]))

    typed = ListenerProperties(
        load_balancer_arn=str(raw["LoadBalancerArn"]),
        protocol=protocol,
        port=int(raw["Port"]),
        certificate_arns=cert_arns,
        default_target_group_arns=tg_arns,
    )
    return ResourceNode(
        id=aws_id(account_id, region, "elasticloadbalancing", "listener", identifier),
        provider="aws",
        service="elasticloadbalancing",
        resource_type="listener",
        account_id=account_id,
        region=region,
        name=f"{protocol}:{raw['Port']}",
        arn=arn,
        tags={},
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="elbv2:DescribeListeners",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_target_group(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    registered_target_ids: Sequence[str] = (),
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one TargetGroup object from `elbv2:DescribeTargetGroups`."""
    ts = ensure_aware_utc(collected_at)
    name = str(raw["TargetGroupName"])
    arn = str(raw["TargetGroupArn"])
    identifier = arn.split(":targetgroup/", 1)[-1]

    tt_raw = str(raw.get("TargetType", "instance"))
    target_type: _TargetType = (
        cast(_TargetType, tt_raw) if tt_raw in {"instance", "ip", "lambda", "alb"} else "instance"
    )
    typed = TargetGroupProperties(
        name=name,
        target_type=target_type,
        protocol=raw.get("Protocol"),
        port=raw.get("Port"),
        vpc_id=raw.get("VpcId"),
        health_check_protocol=raw.get("HealthCheckProtocol"),
        health_check_path=raw.get("HealthCheckPath"),
        load_balancer_arns=[str(lb) for lb in raw.get("LoadBalancerArns", [])],
        registered_target_ids=list(registered_target_ids),
    )
    return ResourceNode(
        id=aws_id(account_id, region, "elasticloadbalancing", "targetgroup", identifier),
        provider="aws",
        service="elasticloadbalancing",
        resource_type="targetgroup",
        account_id=account_id,
        region=region,
        name=name,
        arn=arn,
        tags=tags_from_list(tags),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="elbv2:DescribeTargetGroups",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_hosted_zone(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    collected_at: datetime,
    vpc_ids: Sequence[str] = (),
    accelerated_recovery_enabled: bool | None = None,
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one HostedZone object from `route53:ListHostedZones` / `GetHostedZone`."""
    ts = ensure_aware_utc(collected_at)
    zone_id = str(raw["Id"]).removeprefix("/hostedzone/")
    name = str(raw["Name"])
    private = bool(raw.get("Config", {}).get("PrivateZone", False))

    typed = HostedZoneProperties(
        zone_id=zone_id,
        name=name,
        private=private,
        vpc_ids=list(vpc_ids),
        record_count=raw.get("ResourceRecordSetCount"),
        accelerated_recovery_enabled=None if private else accelerated_recovery_enabled,
    )
    return ResourceNode(
        id=global_id(account_id, "route53", "hostedzone", zone_id),
        provider="aws",
        service="route53",
        resource_type="hostedzone",
        account_id=account_id,
        region="global",
        name=name,
        arn=f"arn:aws:route53:::hostedzone/{zone_id}",
        tags=tags_from_list(tags),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="route53:GetHostedZone",
                identifier=zone_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_record_set(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    hosted_zone_id: str,
    collected_at: datetime,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize one ResourceRecordSet from `route53:ListResourceRecordSets`."""
    ts = ensure_aware_utc(collected_at)
    clean_zone = hosted_zone_id.removeprefix("/hostedzone/")
    name = str(raw["Name"])
    record_type = str(raw["Type"])
    set_id = raw.get("SetIdentifier")

    routing_policy: _RoutingPolicy = "simple"
    failover_role: Literal["PRIMARY", "SECONDARY"] | None = None
    if raw.get("Failover") in {"PRIMARY", "SECONDARY"}:
        routing_policy = "failover"
        failover_role = "PRIMARY" if raw["Failover"] == "PRIMARY" else "SECONDARY"
    elif raw.get("Weight") is not None:
        routing_policy = "weighted"
    elif raw.get("Region"):
        routing_policy = "latency"
    elif raw.get("GeoLocation"):
        routing_policy = "geolocation"
    elif raw.get("GeoProximityLocation"):
        routing_policy = "geoproximity"
    elif raw.get("MultiValueAnswer"):
        routing_policy = "multivalue"
    elif raw.get("CidrRoutingConfig"):
        routing_policy = "cidr"

    alias_raw = raw.get("AliasTarget")
    alias_target = (
        AliasTarget(
            dns_name=str(alias_raw["DNSName"]),
            hosted_zone_id=str(alias_raw["HostedZoneId"]),
            evaluate_target_health=bool(alias_raw.get("EvaluateTargetHealth", False)),
        )
        if isinstance(alias_raw, Mapping)
        else None
    )
    values = (
        []
        if alias_target is not None
        else [str(r["Value"]) for r in raw.get("ResourceRecords", []) if r.get("Value")]
    )

    identifier = f"{clean_zone}/{name.rstrip('.')}/{record_type}"
    if set_id:
        identifier = f"{identifier}/{set_id}"

    typed = RecordSetProperties(
        hosted_zone_id=clean_zone,
        name=name,
        record_type=record_type,
        set_identifier=str(set_id) if set_id else None,
        routing_policy=routing_policy,
        failover_role=failover_role,
        weight=raw.get("Weight"),
        region=raw.get("Region"),
        health_check_id=raw.get("HealthCheckId"),
        alias_target=alias_target,
        values=values,
        ttl_seconds=raw.get("TTL"),
    )
    return ResourceNode(
        id=global_id(account_id, "route53", "recordset", identifier),
        provider="aws",
        service="route53",
        resource_type="recordset",
        account_id=account_id,
        region="global",
        name=f"{name} ({record_type})",
        arn=None,
        tags={},
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="route53:ListResourceRecordSets",
                identifier=identifier,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def normalize_acm_certificate(
    raw: Mapping[str, Any],
    *,
    account_id: str,
    region: str,
    collected_at: datetime,
    tags: Sequence[Mapping[str, Any]] | None = None,
    scan_id: str | None = None,
) -> ResourceNode:
    """Normalize a CertificateDetail object from `acm:DescribeCertificate`."""
    ts = ensure_aware_utc(collected_at)
    cert = raw.get("Certificate", raw)
    arn = str(cert["CertificateArn"])
    cert_id = arn.rsplit("/", 1)[-1]
    domain_name = str(cert["DomainName"])

    cert_type_raw = cert.get("Type")
    cert_type: _CertType | None = (
        cast(_CertType, str(cert_type_raw))
        if cert_type_raw in {"AMAZON_ISSUED", "IMPORTED", "PRIVATE"}
        else None
    )

    typed = ACMCertificateProperties(
        domain_name=domain_name,
        subject_alternative_names=[str(s) for s in cert.get("SubjectAlternativeNames", [])],
        status=cert.get("Status"),
        certificate_type=cert_type,
        not_after=parse_aws_datetime(cert.get("NotAfter")),
        in_use_by=[str(a) for a in cert.get("InUseBy", [])],
    )
    return ResourceNode(
        id=aws_id(account_id, region, "acm", "certificate", cert_id),
        provider="aws",
        service="acm",
        resource_type="certificate",
        account_id=account_id,
        region=region,
        name=domain_name,
        arn=arn,
        tags=tags_from_list(tags),
        properties={},
        typed_properties=typed,
        source_refs=[
            aws_source_ref(
                operation="acm:DescribeCertificate",
                identifier=cert_id,
                collected_at=ts,
                scan_id=scan_id,
            )
        ],
        discovered_at=ts,
    )


def _parse_sg_rule(raw: Mapping[str, Any]) -> SecurityGroupRule:
    return SecurityGroupRule(
        protocol=str(raw.get("IpProtocol", "-1")),
        from_port=raw.get("FromPort"),
        to_port=raw.get("ToPort"),
        cidr_blocks=[str(r["CidrIp"]) for r in raw.get("IpRanges", []) if r.get("CidrIp")],
        ipv6_cidr_blocks=[
            str(r["CidrIpv6"]) for r in raw.get("Ipv6Ranges", []) if r.get("CidrIpv6")
        ],
        security_group_ids=[
            str(pair["GroupId"]) for pair in raw.get("UserIdGroupPairs", []) if pair.get("GroupId")
        ],
        prefix_list_ids=[
            str(pl["PrefixListId"]) for pl in raw.get("PrefixListIds", []) if pl.get("PrefixListId")
        ],
    )
