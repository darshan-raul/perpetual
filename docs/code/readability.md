# Writing code people can follow

Our reader knows basic Python: variables, lists and dictionaries, loops, functions, and simple classes. They should be able to follow a function's decisions without already knowing AWS, Pydantic, or SQLAlchemy. Explain those concepts in the [wiki](README.md) when they become necessary.

## Everyday choices

- Use names that describe the domain: `evidence`, `resource_id`, `snapshot`, and `confidence`. Avoid names such as `x` or `res` when the meaning matters.
- Prefer explicit loops and intermediate variables when an expression combines several decisions. Short, single-purpose comprehensions are fine.
- Give each function one clear job. Split it when separate responsibilities become hard to follow, not to satisfy an arbitrary line limit. Avoid tiny wrappers that only make readers jump between files.
- Use early returns or clear errors to keep the main path visible. Handle expected exceptions specifically; never silently turn invalid or missing data into a successful result.
- Introduce helpers, base classes, registries, or generic types when they solve an existing need. Explain that need. Avoid frameworks for hypothetical future cases.
- Keep useful type hints and validation. Explain unfamiliar syntax and framework behavior in the relevant wiki page; do not weaken contracts to make code shorter.
- Comment decisions, assumptions, units, and surprising behavior. Explain why a check exists, with its spec section where relevant. Do not narrate obvious assignments.
- Give public operations a short docstring covering purpose and any non-obvious inputs, result, side effects, or failure modes. Tests should read as a concrete setup, action, and expected outcome.
- Preserve efficient batching and established algorithms. Simple code can still use a library algorithm; explain its inputs and result rather than replacing it with fragile custom logic.

For example, when several steps matter, write them separately:

```python
# Illustration: collect the strongest confidence in each correlation group.
best_by_group = {}
for item in evidence:
    group, confidence = group_of(item, config)
    previous_best = best_by_group.get(group, 0.0)
    best_by_group[group] = max(previous_best, confidence)
```

The key idea is that related evidence counts once. The [evidence page](packages/evidence.md) explains why and connects this idea to the actual implementation.

## Review before completing a task

- Can a reader identify the inputs, result, decisions, and possible errors without decoding a dense expression or following unnecessary indirection?
- Are new domain terms and unfamiliar Python/library features explained with a small example?
- Does the affected package page explain the implementation, its rules, and its tests?
- Does a new or changed cross-package flow show its entry point, concrete input, function calls, result, and failure path? For library-only paths, label the example as manual composition.
- Are new pages linked from the wiki index, and are architecture and status descriptions current?
- Were relevant existing explanations corrected as well as new material added?
- Have appropriate lint, type, and behavior checks passed, with limitations recorded?

This is a human review requirement. Lint and typing help, but cannot prove that code is understandable. Apply it to new and changed code, and improve surrounding explanations as needed. The [2026-11-07 audit](readability-audit.md) records the review and refactors of the implemented foundation. It does not certify every line as universally understandable; broader refactors should remain scoped and verified.
