# Flow: inspect evidence from a fixture

This is a manual library walkthrough using existing functions. No CLI command currently performs this composition, and it does not simulate recovery or establish readiness.

```text
 fixtures/graphs/minimal.yaml
          |
 fixtures.load_fixture(path) -> validated Fixture
          |
 fixture.edges[0] -> DependencyEdge with Terraform evidence
          |                              |
 config.load_config().evidence           |
          |                              |
 evidence.combine(edge.evidence, config) evidence.edge_fingerprint(edge)
          |                              |
 CombinedConfidence                 sha256:<digest>
 (score and group breakdown)         stable identity for this claim
```

From the repository root, run:

```bash
mise exec -- uv run python - <<'PY'
from pathlib import Path

from perpetual.config import load_config
from perpetual.evidence import combine, edge_fingerprint
from perpetual.fixtures import load_fixture

fixture = load_fixture(Path("fixtures/graphs/minimal.yaml"))
edge = fixture.edges[0]
evidence_config = load_config().evidence
result = combine(edge.evidence, evidence_config)

print("Dependency:", edge.from_resource_id, "->", edge.to_resource_id)
print("Confidence:", result.confidence)
for group in result.groups:
    print("Group:", group.group, "confidence:", group.confidence)
print("Fingerprint:", edge_fingerprint(edge))
PY
```

With the current defaults, the score is `1.0`, the group is `terraform`, and the fingerprint is `sha256:4fddabe17a1599357186057af04125547254090097ee92476a905f5c9fcd29f9`. These are evidence results, not a DR readiness verdict.

1. [The loader](../../../apps/api/perpetual/fixtures/loader.py) reads YAML, fills fields derived from IDs, validates models, and checks references. Invalid input raises `FixtureError`.
2. [The config loader](../../../apps/api/perpetual/config/loader.py) supplies the versioned evidence weights. The fixture's evidence has kind `terraform_reference`; its configured weight determines its contribution.
3. [combine](../../../apps/api/perpetual/evidence/combination.py) takes the strongest contribution within each correlation group, then combines independent groups. Unrecognized kinds raise `UnknownEvidenceKindError`. Empty evidence produces confidence 0.0.
4. [edge_fingerprint](../../../apps/api/perpetual/evidence/fingerprint.py) hashes the endpoints, relationship type, and material evidence facts. IDs of individual evidence records, timestamps, and confidence values do not affect this fingerprint.

Changing a configured weight can change the score without changing the fingerprint. Changing a dependency's endpoint or relationship changes the claim and therefore its fingerprint. The planned override layer will use fingerprints to decide whether rejected claims have materially changed.

For the exact rules and regression tests, see [the evidence package](../packages/evidence.md). The loader and scoring tests cover their respective functions; this walkthrough is not a new CLI feature.
