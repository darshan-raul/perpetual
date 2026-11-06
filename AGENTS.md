# Working agreements

- Do not create Git commits or push changes unless the user explicitly asks for that specific commit or push.
- Read `TRACKER.md` for current status and session carry-over before implementation. `spec.md` and `docs/spec/` define behavior; `IMPL_PLAN.md` defines the implementation sequence.
- Write Python for a reader who knows variables, loops, functions, and basic classes. Follow [the readability guide](docs/code/readability.md): descriptive names, explicit control flow, focused functions, and explanations of necessary framework features. Preserve correctness, validation, typing, and performance requirements.
- Maintain [the code wiki](docs/code/README.md) in the same change as implementation. Explain new concepts, update affected package pages and flows, link new pages from the index, and update the architecture when connections change. Clearly distinguish implemented behavior from planned work.
- Before declaring an implementation task done, review the readability and wiki checklist in `docs/code/readability.md`, run appropriate checks, and update the tracker. Automated checks cannot establish whether prose or code is understandable; review that explicitly.
- Record plan changes or spec deviations in the tracker's decision log before making them. Consult `CLAUDE.md` for the detailed architecture, invariants, and tooling agreements.
