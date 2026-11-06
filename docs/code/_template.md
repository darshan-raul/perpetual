# `<package>` package

> Copy this file to `packages/<package>.md` when a package gets real code. Relative links assume that destination. Delete these quoted lines.

**Owns:** one sentence on what this package is responsible for.
**Spec:** the sections it implements. **Tracker:** the tasks that built it.
**Depends on:** the `perpetual` packages it may import (see the import rules in [tooling.md](../tooling.md)). **Used by:** who imports it.

## In one paragraph

What the package does and where it sits in the pipeline, for someone who has not read the spec.

## Concepts you need

Define new terms in plain language, with a small example. Link to [concepts.md](../concepts.md) for shared vocabulary. Explain unfamiliar Python or library features used by this package.

## Files

| File | What it holds |
|---|---|
| `__init__.py` | Public names |

## How it works

Start with an ASCII diagram of the main path: what comes in, which functions it passes through, what comes out, and where it can fail. Then walk through the main types or functions in the order a reader should meet them, with a diagram wherever relationships or decisions matter. Show a short usage example with a concrete input and expected result. Link the actual source files and name the functions. Explain failure paths and side effects as well as the successful path. Link a flow page when the operation crosses packages.

```text
 input ──> function_a ──> function_b ──> output
               │ fails when …
               ▼
           SomeError
```

## Rules it enforces, and why

| Rule | Where | Why (spec) |
|---|---|---|

## Tests

Where the tests live and what they prove.

## Not here yet

One line per gap, pointing at the tracker task that fills it.
