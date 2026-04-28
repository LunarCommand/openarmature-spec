# Changelog

All notable changes to the OpenArmature specification are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The spec follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] — 2026-04-27

### Added

- **graph-engine §2 Subgraph — explicit input/output mapping.** A subgraph-as-node MAY declare optional `inputs` (subgraph field name → parent field name) and/or `outputs` (parent field name → subgraph field name) mappings. `inputs` is additive over the §2 default of no projection in; `outputs` *replaces* (does not extend) the §2 default of field-name matching for projection out. ([proposal 0002](proposals/0002-subgraph-explicit-mapping.md))
- New canonical compile-error category `mapping_references_undeclared_field` — added to the §2 Compiled graph mandated identifier list. Compilation MUST fail with this category when an `inputs` or `outputs` mapping names a field that is not declared in the relevant state schema.
- Conformance fixture `011-subgraph-explicit-mapping` — composes the same subgraph at three sites with different mapping configurations (both / inputs-only / outputs-only) and verifies projection-in copies, projection-out replacement vs. fallback, and per-site mapping independence.
- Conformance fixture `007-compile-errors` adds case `mapping_references_undeclared_field`.

## [0.1.1] — 2026-04-18

### Changed

- **graph-engine §2 Subgraph (clarification, non-behavioral).** Rewrote the Subgraph section to align with conformance fixture `006-subgraph-composition`, which already encoded the intended behavior. The corrected defaults: **projection in** is off (a subgraph runs from its own schema's field defaults, independent of the parent), and **projection out** uses field-name matching (subgraph fields whose names match parent fields merge back via the parent's reducers; non-matching subgraph fields are discarded). The previous wording said parent fields were copied into the subgraph's initial state by field-name matching at entry, which contradicted fixture 006. No fixtures change.
- **proposal 0002 (Draft) — Summary, Motivation, and Detailed design.** Reworded so `inputs` is additive over the clarified "no projection in" default, while `outputs` continues to replace the default field-name matching for projection out. Added an asymmetry note explaining the design choice; tightened the Precedence rationale to outputs-only.

## [0.1.0] — 2026-04-16

### Added

- Initial **graph-engine** capability: typed state, async nodes, static and conditional edges, reducers (`last_write_wins`, `append`, `merge`), subgraph composition, and the baseline execution model. ([proposal 0001](proposals/0001-graph-engine-foundation.md))
- Conformance fixtures for graph-engine under `spec/graph-engine/conformance/` (10 fixture pairs covering linear flow, conditional routing, each reducer, subgraph composition, compile-time errors, routing errors, node exception propagation, and determinism).

### Notes

- **Mandated error-category identifiers (proposal 0001 supplement).** §2 fixes the canonical compile-time categories (`no_declared_entry`, `unreachable_node`, `dangling_edge`, `multiple_outgoing_edges`, `conflicting_reducers`), and §4 fixes the canonical runtime categories (`node_exception`, `edge_exception`, `reducer_error`, `routing_error`, `state_validation_error`). Proposal 0001 described these cases but did not mandate identifier strings. Applied pragmatically during the initial implementation PR since no spec version had been released; from 0.1.0 onward, comparable changes require a follow-on proposal.
- **Routing error recoverable state (proposal 0001 supplement).** §4 now requires that routing errors carry recoverable state, matching the node-exception contract. Proposal 0001 required recoverable state for node exceptions only. Same pragmatic-pre-release rationale as above.
- **Subgraph projection.** Defaults to field-name matching for projection out, as clarified in §2. Alternative projection strategies (e.g., explicit input/output mapping) are deferred to proposal 0002 (Draft).
