# Changelog

All notable changes to the OpenArmature specification are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The spec follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-04-16

### Added

- Initial **graph-engine** capability: typed state, async nodes, static and conditional edges, reducers
  (`last_write_wins`, `append`, `merge`), subgraph composition, and the baseline execution model.
  ([proposal 0001](proposals/0001-graph-engine-foundation.md))
- Conformance fixtures for graph-engine under `spec/graph-engine/conformance/` (10 fixture pairs covering
  linear flow, conditional routing, each reducer, subgraph composition, compile-time errors, routing errors,
  node exception propagation, and determinism).

### Notes

- The spec text tightens proposal 0001's language in two small ways beyond the proposal's literal wording.
  Both are applied pragmatically during the initial implementation PR since no spec version has been
  released yet; from 0.1.0 onward, comparable changes will require a follow-on proposal.
  - **Mandated error-category identifiers.** §2 fixes the canonical compile-time categories
    (`no_declared_entry`, `unreachable_node`, `dangling_edge`, `multiple_outgoing_edges`,
    `conflicting_reducers`), and §4 fixes the canonical runtime categories (`node_exception`,
    `edge_exception`, `reducer_error`, `routing_error`, `state_validation_error`). Proposal 0001 described
    these cases but did not mandate identifier strings.
  - **Routing error recoverable state.** §4 now requires that routing errors carry recoverable state,
    matching the node-exception contract. Proposal 0001 required recoverable state for node exceptions
    only.
- Subgraph projection defaults to field-name matching, as clarified in §2. Alternative projection
  strategies (e.g., explicit input/output mapping) are deferred to proposal 0002 (Draft).
