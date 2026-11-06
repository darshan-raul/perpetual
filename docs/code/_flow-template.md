# Flow: <operation>

> Copy to `flows/<name>.md`, remove this note, and link it from the wiki index.

## Purpose and starting point

Explain the user or developer goal in plain language. State whether this is an existing command, an automatic internal path, or a manual composition of library calls. Link prerequisite concepts.

## Concrete input and result

Use a small existing fixture or self-contained example. Give a runnable command from the repository root and its expected result. Explain any variable values, such as digests or timestamps.

## The path through the code

Use a text diagram showing data in, calls, decisions, output, and errors. Link source files and name the functions at each step. Explain why each layer exists and any unfamiliar library behavior.

## Failure paths and side effects

Describe invalid and missing input, error propagation, and any filesystem, database, or network effects. State what the result does and does not establish.

## Tests and related pages

Link tests that exercise the path and explain what they prove. Link package pages for detail; avoid duplicating their full implementation explanation.
