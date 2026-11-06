# Readability audit — 2026-11-07

Scope: the implemented Python foundation through P0-09, focusing on executable paths in models and validators, IDs, config, fixtures, evidence, persistence, and CLI. The review used the [readability checklist](readability.md). Stub packages have no implementation to refactor. The Astro site and a full rewrite of test helpers were outside this Python audit.

## Findings and changes

| Area | Reading difficulty | Resolution |
|---|---|---|
| Fixture defaults | Nested helper calls concealed the separate project and timestamp defaults | Named intermediate values in `expand`; preserve explicit values and invalid nulls |
| Fixture errors | A nested conditional built dotted/indexed paths in one line | Explicit branches in `_issue`, with an example of the Pydantic input |
| Fixture cross-references | Abbreviations obscured observations, mechanisms, and group membership | Descriptive local names and an explanation of the `(scope, edge)` lookup |
| Evidence combination | Formula, grouping, and output construction were compressed | Named intermediate probabilities, group maps, and contribution-building loop |
| Evidence fingerprints | A nested lambda hid the null-versus-string ordering contract | Named `_fact_sort_key`; retain the exact ordering and JSON bytes |
| Database edge round trips | Nested collection and model reconstruction hid where evidence is attached | Explicit evidence gathering and copied payload reconstruction; keep batch queries |
| Model helpers | Cost totals used a filtered sum after a null check; severity lookup used a special method directly | Explicit known-value collection before summing; readable severity lookup |
| Framework concepts | Readers needed to know generators, sort keys, dynamic access, and transactions | Expanded concepts and added a runnable snapshot round trip |

## What remains intentionally explicit or framework-specific

- Most model validators already state one rule at a time with explanatory comments. Keep these near their fields rather than introduce a generic validation framework.
- The typed-properties union is long because it enumerates the supported resource models. Its discriminator chooses the correct model; replacing it with a custom loader would add indirection.
- Config merging uses recursion because mappings can nest. Each recursive call handles one smaller mapping. Existing package documentation explains replacement versus merging.
- SQLAlchemy declarations and Alembic migrations use their libraries' normal syntax. Keep the database schema visible; do not rewrite an existing migration for style.
- The repository is long, but its methods map directly to storage operations. Keep it in one module for now; splitting it across mixins or generic writers would make its validation and project scope harder to follow. `_load` remains the small shared read helper, with its generic type explained.
- Simple comprehensions, enums, type hints, and validators remain. Basic Python knowledge plus the linked concepts should be enough to follow the local logic; understanding the domain still requires reading its rules.

## Compatibility and validation

Public signatures, error messages, model fields, serialized schema, database schema, and import boundaries are unchanged. No new runtime dependency or product capability was introduced.

Added regressions lock a pre-refactor fingerprint containing nulls, empty strings, Unicode, and a string beginning with `=`; they also check authored override defaults, input preservation, and explicit null rejection. Existing tests cover unknown cost totals, state ordering, fixture issue paths, evidence correlation, database round trips, and batch statement counts.

`mise run check` passed after the refactor: 369 tests, strict typing on 96 files, all nine import contracts, lint, and formatting. Both library walkthroughs ran successfully; local file links and code fences passed across 19 wiki pages. The snapshot walkthrough and fixture-to-evidence walkthrough are runnable documentation examples. This is a readability review, not a security audit or proof that every reader will understand every line. Future implementation still needs the same review checklist.
