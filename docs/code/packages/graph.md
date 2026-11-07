# `graph` package: overrides

**Owns:** user corrections applied over discovered graph records, including rescan behavior and YAML import/export.
**Spec:** §23, §19.1, §24.1. **Tracker:** P0-10.
**Depends on:** `models`, `ids`, `evidence`; PyYAML and Pydantic. **Used by:** library callers and tests today; graph construction (P0-11) and CLI commands (P0-12) follow.

## In one paragraph

A scan is a record of what was discovered. A user correction is a separate instruction. `apply_overrides` copies the scan's records, replays those instructions, and returns the effective graph plus review information. It never changes the source snapshot or writes a database. The same instructions can be replayed after a new scan without losing the user's decisions.

## Concepts you need

- **Source graph:** the unmodified discovered records. Always start replay here, not from the previous effective result.
- **Effective graph:** the records after applying user corrections; consumers use its active edges.
- **Stable target:** confirmations and edits name the dependency's endpoints and relationship type, not its scan-generated edge ID. `edge_target(edge)` produces an escaped JSON string with an `edge:` prefix. Different relationship types between the same resources remain distinct.
- **Fingerprint:** a rejection names the exact material evidence claim using `evidence.edge_fingerprint(source_edge)`. It ignores timestamps, counts, and evidence IDs. [Evidence](evidence.md) explains the hash.
- **Orphan:** an override whose target is missing. The instruction is retained, with a reason, and becomes active again if its target returns.
- **Reproposal:** an edge with changed evidence linked to an earlier rejection. The old rejection does not suppress this new claim.

## Files

All implementation lives under [`graph/overrides/`](../../../apps/api/perpetual/graph/overrides/).

| File | Responsibility |
|---|---|
| `types.py` | `GraphData`, `OverrideResult`, `Reproposal`, `OverrideError` |
| `apply.py` | Replay orchestration, rejection matching, historical context, orphan statuses |
| `state.py` | Private working copies, ID lookups, reference checks, result assembly |
| `targets.py` | Stable endpoint-and-type encoding via `edge_target` |
| `validation.py` | Project ownership, duplicate IDs, canonical target checks, replay order |
| `edges.py` | User assertions, edge addition/merge, confirmation, edit |
| `nodes.py` | External nodes, AWS placeholders, stack membership, service assignment, RTO scope |
| `yaml.py` | Versioned documents, safe parsing, deterministic export, idempotent import merge |

The public entry points are exported from `graph.overrides`. The working-state helpers stay internal; they do not introduce a separate persistent graph representation.

## How application works

```text
 fresh GraphData + GraphOverride records + historical source edges (when available)
        |
        +-> validate ownership, IDs and target format
        +-> deep-copy graph records, build lookups
        +-> establish all add_node declarations
        +-> replay remaining overrides in (created_at, id) order
                 |
                 +-> target present -> apply to working records
                 +-> target absent -> keep override, record orphan reason
                 +-> rejection hash changed -> retain edge, link prior rejection
        |
        +-> check effective references and ambiguous edge identities
        v
 OverrideResult
   graph             effective resources, edges, stacks, services and scope rows
   overrides         every input override, with recomputed active/orphaned status
   rejected_edges    removed edges retained for review and group resolution
   orphan_reasons    override ID -> explanation
   reproposals       new edge ID -> earlier rejection ID and old/new fingerprints
```

Input and output records are isolated with a deep copy because Pydantic's frozen fields do not freeze nested lists. New or changed models are validated again. No partially applied result is returned on failure.

Ordering does not depend on the order rows appear in YAML. Node additions are established first so an edge can refer to a node declared later in the document. Other instructions are chronological, with override ID breaking timestamp ties. Confirming an edge after rejecting it restores it; rejecting after confirming removes it. Editing criticality or type alone does not cancel a rejection or grant confidence 1.0.

## Behavior by override kind

| Kind | Target | Result |
|---|---|---|
| `confirm_edge` | `edge_target(source_edge)` | Confidence 1.0, confirmed review, traceable user evidence |
| `reject_edge` | `edge_fingerprint(source_edge)` | Remove the matching claim from effective edges; retain a rejected record |
| `add_edge` | `edge_target(AddEdgePayload(...))` | Assert an edge with confidence 1.0; merge user evidence if discovery already contains that exact typed dependency |
| `edit_edge` | `edge_target(source_edge)` | Change relationship type or criticality, mark edited, preserve confidence and confirmation |
| `add_node` | Canonical resource ID matching the payload | Add an external node or AWS placeholder; keep discovered facts if the resource already exists |
| `edit_node` | Resource ID | Change its stack membership, service assignment, or explicit RTO scope |

User evidence has a stable `override:<id>` evidence ID, author/project provenance, and the override's original creation time. Replaying never invents a new observation timestamp. An added edge that later appears in discovery keeps its discovered edge ID and origin, with the user assertion attached.

External nodes get typed external properties; undeclared posture is `UNKNOWN`. AWS placeholders derive account, Region, type and planned identity from their canonical ID and leave configuration unknown. Conflicting node declarations are errors. If discovery later finds a placeholder, discovered facts take precedence and the user's declaration is retained as a source reference.

Membership removal clears that resource's roots, service assignments, and scope row in the selected stack. Other stacks are unchanged. Service assignment moves the resource between services within that stack. Explicit RTO scope creates a `StackResource` with `scope_source=user`; membership alone does not invent a scope default. Default classification remains P1-03.

## Rescans and historical evidence

Confirmations and edits use the original typed dependency identity, so changed scan edge IDs do not invalidate them. Edits keep targeting that source identity on each replay, even when they change its effective relationship type.

Rejections are more specific. If the source fingerprint still matches, suppress the edge. If evidence changes, a historical source edge explains what the old hash referred to. Pass those original records through `historical_edges`, including older snapshots when needed. A hash cannot be decoded back into its original evidence.

A changed claim gets a `Reproposal` containing the new edge ID, rejection ID, old fingerprint, and new fingerprint. The rejection remains active for its old claim. Any earlier confirmation superseded by that rejection is removed from the new claim, which returns as unreviewed at its source confidence; a later explicit confirmation can accept it. If history is unavailable, the override is reported as orphaned with an explicit missing-history reason; the new edge is never silently suppressed. If endpoints or the typed edge disappear, the rejection is also orphaned until they return.

## YAML and persistence boundaries

`dump_overrides(records, project_id=...)` returns a versioned YAML document:

```yaml
format: perpetual-overrides
version: 1
project_id: my-project
overrides: []
```

`parse_overrides(text, project_id=...)` reads text; `load_overrides(path, project_id=...)` reads a file. Both validate the envelope and every row's project ownership and target. Export includes orphaned records and all authorship metadata.

`merge_overrides(existing, incoming, project_id=...)` preserves existing edits and adds new ones. An identical ID/content pair is idempotent; different content under an existing ID is an error. Cached status differences are ignored because application recomputes status. Import is additive: omitting a row does not delete an existing instruction.

Persistence is explicit in the caller's transaction: save new records with `ProjectRepository.add_override`, store resulting statuses with `set_override_status`, and load source/historical records with repository reads. The override layer has no persistence dependency. See the [persistence integration test](../../../apps/api/tests/graph/test_override_persistence.py).

To withdraw a user-added edge, remove its addition with `ProjectRepository.delete_override` and replay the remaining records. The discovered snapshot stays unchanged: a user-only edge disappears; an independently discovered edge remains. Other user assertions on that dependency must also be withdrawn if the intent is to remove all user-added support. Deleting a discovered edge uses a rejection instead.

## Errors and integration limits

Malformed payloads or targets, cross-project records, duplicate IDs, conflicting declarations, and contradictory membership changes raise `OverrideError`. A typed target must identify one source edge; duplicate source edges with the same endpoints and relationship are ambiguous and refused rather than silently merged. An edit that would collide with another effective typed dependency is also refused. These checks preserve distinct relationship types and their evidence.

Groups and mechanisms remain snapshot metadata. P0-11 must combine them with the effective graph and retained rejected records; it must not silently lower a group's quorum after an edge rejection. This layer computes neither traversal nor readiness. Planned-snapshot proof invalidation remains P1b-15, and immutable evaluation manifests remain P0-15.

## Tests and worked flow

- [Replay tests](../../../apps/api/tests/graph/test_overrides.py): all six kinds, input isolation, stable ordering/targets, typed parallel edges, merge on rescan, rejection history, disappearing/reappearing targets, external posture, placeholders, membership and errors.
- [YAML tests](../../../apps/api/tests/graph/test_override_yaml.py): lossless export, deterministic ordering, repeated imports, foreign projects, malformed/unsafe YAML, invalid payloads, unsupported versions and file errors.
- [Persistence test](../../../apps/api/tests/graph/test_override_persistence.py): published snapshots stay unchanged while rejection state survives reload, rescan, orphaning and withdrawal.
- [Worked flow](../flows/graph-overrides.md): run all six kinds from `fixtures/graphs/review-overrides.yaml` and round-trip the overrides through YAML.

## Not here yet

NetworkX snapshot construction and traversal: P0-11. Graph and override CLI commands: P0-12. Readiness review gates: P1-07.
