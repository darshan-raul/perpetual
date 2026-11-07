"""User-declared nodes and stack/service membership edits (spec §23, §24.1)."""

from perpetual.graph.overrides.state import WorkingGraph
from perpetual.graph.overrides.types import OverrideError
from perpetual.ids import AwsResourceId, parse
from perpetual.models import (
    GraphOverride,
    ResourceNode,
    ScopeSource,
    SourceReference,
    SourceType,
    Stack,
    StackResource,
    StackService,
)
from perpetual.models.override import AddNodePayload, DrPosture, EditNodePayload, NodeKind
from perpetual.models.properties import ExternalResourceProperties


def add_node(state: WorkingGraph, override: GraphOverride) -> None:
    payload = AddNodePayload.model_validate(override.payload)
    if override.target != payload.resource_id:
        raise OverrideError(f"override {override.id!r}: target does not match resource_id")
    identity = parse(payload.resource_id)
    account_id: str | None
    region: str | None
    properties = None
    planned = False
    terraform_address = None
    if isinstance(identity, AwsResourceId):
        if payload.node_kind is not NodeKind.PLACEHOLDER or payload.provider != "aws":
            raise OverrideError("AWS node additions must be aws placeholders")
        if payload.service != identity.service or payload.resource_type != identity.resource_type:
            raise OverrideError("placeholder service/type contradicts its canonical ID")
        if payload.account_id is not None and payload.account_id != identity.account_id:
            raise OverrideError("placeholder account contradicts its canonical ID")
        if payload.region is not None and payload.region != identity.region:
            raise OverrideError("placeholder Region contradicts its canonical ID")
        account_id = identity.account_id
        region = identity.region
        planned = identity.is_planned
        if identity.planned_address is not None:
            terraform_address = identity.planned_address.address
    else:
        if payload.node_kind is not NodeKind.EXTERNAL or payload.provider != "external":
            raise OverrideError("external IDs require external nodes")
        if payload.service != identity.service:
            raise OverrideError("external service contradicts its canonical ID")
        account_id = payload.account_id
        region = payload.region
        properties = ExternalResourceProperties(dr_posture=payload.dr_posture or DrPosture.UNKNOWN)

    reference = SourceReference(
        source_type=SourceType.USER_CONFIRMATION,
        locator=f"override:{override.project_id}:{override.id}:{override.author}",
        collected_at=override.created_at,
    )
    existing = state.resources.get(payload.resource_id)
    if existing is not None:
        # A scan now knows this resource: keep its facts, attach the declaration.
        references = list(existing.source_refs)
        if reference not in references:
            references.append(reference)
        state.resources[existing.id] = ResourceNode.model_validate(
            existing.model_dump() | {"source_refs": references}
        )
        return
    state.resources[payload.resource_id] = ResourceNode(
        id=payload.resource_id,
        provider=payload.provider,
        service=payload.service,
        resource_type=payload.resource_type,
        account_id=account_id,
        region=region,
        name=payload.name,
        typed_properties=properties,
        source_refs=[reference],
        planned=planned,
        terraform_address=terraform_address,
        discovered_at=override.created_at,
    )


def edit_node(state: WorkingGraph, override: GraphOverride) -> str | None:
    """Apply membership and explicit scope; missing referenced objects are orphans."""
    payload = EditNodePayload.model_validate(override.payload)
    resource_id = override.target
    if resource_id not in state.resources:
        return "the resource is absent"
    stack = state.stacks.get(payload.stack_id)
    if stack is None:
        return "the stack is absent"
    if payload.member is False and (
        payload.service_id is not None or payload.rto_scope is not None
    ):
        raise OverrideError("removing a stack member cannot also assign its service or RTO scope")
    if payload.service_id is not None:
        service = state.services.get(payload.service_id)
        if service is None:
            return "the service is absent"
        if service.stack_id != stack.id:
            raise OverrideError("the selected service belongs to another stack")
    if payload.member is None and resource_id not in stack.resource_ids:
        return "the resource is not a member of this stack"

    resource_ids = set(stack.resource_ids)
    root_ids = set(stack.root_resource_ids)
    service_ids = set(stack.service_ids)
    if payload.member is False:
        resource_ids.discard(resource_id)
        root_ids.discard(resource_id)
        state.members.pop((stack.id, resource_id), None)
    elif payload.member is True:
        resource_ids.add(resource_id)

    # A resource is assigned to at most one service within this stack. Removing
    # membership also removes its service references, but leaves other stacks alone.
    if payload.member is False or payload.service_id is not None:
        _assign_service(state, stack.id, resource_id, payload.service_id)
        if payload.service_id is not None:
            service_ids.add(payload.service_id)
    if payload.rto_scope is not None:
        state.members[(stack.id, resource_id)] = StackResource(
            stack_id=stack.id,
            resource_id=resource_id,
            rto_scope=payload.rto_scope,
            scope_source=ScopeSource.USER,
        )
    state.stacks[stack.id] = Stack.model_validate(
        stack.model_dump()
        | {
            "resource_ids": sorted(resource_ids),
            "root_resource_ids": sorted(root_ids),
            "service_ids": sorted(service_ids),
        }
    )
    return None


def _assign_service(
    state: WorkingGraph, stack_id: str, resource_id: str, service_id: str | None
) -> None:
    """Move a resource between services in one stack, or unassign it when None."""
    for service in list(state.services.values()):
        if service.stack_id != stack_id:
            continue
        members = set(service.resource_ids)
        members.discard(resource_id)
        if service.id == service_id:
            members.add(resource_id)
        state.services[service.id] = StackService.model_validate(
            service.model_dump() | {"resource_ids": sorted(members)}
        )
