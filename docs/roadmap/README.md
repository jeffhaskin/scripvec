# docs/roadmap/

Orientation for the scripvec roadmap.

> Orientation only. If a `domain_policies/` subfolder is added here later, read it before editing the roadmap.

## What lives here

- `roadmap.md` — the project roadmap. **This is where you plan out the project's direction and which systems are going to be built in which order.** High-level sequencing and intent; not a CR tracker and not a spec.

The roadmap is a living document. It names the systems, milestones, or initiatives the project is aiming at, and the order they are expected to be tackled. It does **not** replace change requests (`../specs/change_requests/`) — CRs are the unit of discrete, auditable work; the roadmap is the narrative that ties CRs together.

## How roadmap entries relate to other docs

- A **roadmap entry** is a named direction — e.g., *"Q&A layer on top of retrieval"* or *"Bible corpus."* It is not yet a proposal; it is an intent.
- When a roadmap entry becomes concrete enough to implement against, it is proposed as one or more **change requests** (`../specs/change_requests/`).
- The roadmap must remain consistent with every **accepted ADR** (`../specs/adrs/`). See the top of `roadmap.md` for the editing rule.
- The **vision tree** (`../specs/vision_tree/`) is the long-range aspiration the roadmap serves. The vision is steadier; the roadmap is the path.

## Neighbors

- `../specs/change_requests/` — discrete proposed changes, status-tracked. A roadmap entry typically spawns one or more CRs when the work becomes concrete enough to propose.
- `../specs/adrs/` — architectural decisions. The roadmap must stay consistent with every accepted ADR.
- `../specs/vision_tree/` — long-range vision. The roadmap speaks in terms of what the system *will become next*; the vision tree speaks in terms of what it is ultimately for.
- `../principles/` — philosophies that inform decisions. Roadmap sequencing should not contradict them.
- `../policies/` — enforceable rules. Roadmap edits must comply with them (naming conventions, etc.).
