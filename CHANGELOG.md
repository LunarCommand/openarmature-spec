# Changelog

All notable changes to the OpenArmature specification are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The spec follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.0] — 2026-04-28

### Added

- **llm-provider capability (created).** Establishes the foundational LLM provider abstraction: typed `Message` (system/user/assistant/tool), `Tool`, `ToolCall`, and `Response` shapes; stateless async `complete()` operation; pre-flight `ready()` check with a strong "next call expected to succeed" contract; seven canonical error categories (`provider_authentication`, `provider_unavailable`, `provider_invalid_model`, `provider_model_not_loaded`, `provider_rate_limit`, `provider_invalid_response`, `provider_invalid_request`); a normative OpenAI-compatible wire format mapping (§8) covering vLLM, LM Studio, llama.cpp, and the OpenAI hosted API. Charter §3.1 principle 8 ("Transparency over abstraction") is realized by `Response.raw` (verbatim provider response, always populated) and by surfacing partial/malformed tool calls under `finish_reason: "error"` for application-level repair. ([proposal 0006](proposals/0006-llm-provider-core.md))
- New canonical runtime category `provider_model_not_loaded` — distinct from `provider_invalid_model`. The model is configured but not currently serving (local-server warmup pattern); marked transient (retry MAY succeed once loading completes).
- `Response.raw` field — the parsed provider response verbatim, MUST be populated on every successful `complete()` return. Provider-specific extensions (logprobs, vendor stats) surface here unchanged.
- `Tool-call id` verbatim preservation rule — implementations MUST NOT rewrite or normalize provider-supplied ids. Documents cross-provider id round-tripping behavior for applications behind LLM gateways or routers.
- Conformance fixture suite `001-008` for llm-provider, exercising basic completion, tool-call roundtrip with verbatim id preservation, pre-send message validation, error category mapping, OpenAI wire-format mapping with raw passthrough, usage accounting, the strengthened `ready()` contract, and partial/malformed tool calls under `finish_reason: "error"`.

## [0.3.1] — 2026-04-28

### Fixed

- Conformance fixture `013-observer-subgraph-namespacing-and-ordering` was syntactically invalid YAML and could not be parsed by spec-conforming loaders (PyYAML, libyaml). The four `parent_states:` values inside the flow-style event mappings used block-style sub-sequences (`- {...}`), which YAML 1.2 §8.1.2 forbids inside a flow context. Converted those four sub-sequences to flow style (`[{...}]`); the parsed semantic content is unchanged. No spec text or fixture expectations changed.

## [0.3.0] — 2026-04-27

### Added

- **graph-engine §6 Observer hooks (promoted from informative to normative).** Compiled graphs MUST expose a way to register observers (graph-attached and invocation-scoped, at minimum). Observers are async, fire-and-forget, and receive node events with `node_name`, `namespace` (ordered sequence), `step` (monotonic across the invocation including subgraph-internal nodes), `pre_state`, exactly one of `post_state` or `error`, and `parent_states` (ordered sequence of containing-graph state snapshots, outermost first; empty for outermost-graph events; `len(parent_states) == len(namespace) - 1`). `pre_state`/`post_state` carry the *node-level* state shape — outer state for outermost-graph nodes, subgraph state for inner nodes. Per-invocation delivery is strictly serial across all observers and all events; per-event order is graph-attached outermost→innermost, then invocation-scoped. Observer errors MUST NOT interrupt the graph run, prevent other observers from receiving the same event, or prevent subsequent events from being delivered. Compiled graphs MUST expose a `drain` operation. ([proposal 0003](proposals/0003-node-boundary-observer-hooks.md))
- **graph-engine §3 Execution model — observer dispatch step.** Between the reducer merge and the outgoing-edge evaluation, the engine MUST dispatch the node event onto the observer delivery queue. On a failed merge step, the event is dispatched (with `error` populated) before the failure propagates to the caller.
- Conformance fixture `012-observer-basic-firing` — linear graph with one graph-attached and one invocation-scoped observer; verifies per-node event firing, monotonic `step`, single-element `namespace`, and graph-attached-before-invocation-scoped delivery order.
- Conformance fixture `013-observer-subgraph-namespacing-and-ordering` — outer + subgraph each with an attached observer; verifies chained `namespace`, `step` monotonicity across the subgraph boundary, and outermost-first delivery for subgraph-internal events.
- Conformance fixture `014-observer-error-event` — failing-node event has `error` populated and `post_state` absent; engine still propagates the §4 `node_exception` to the caller after dispatch.
- Conformance fixture `015-observer-error-isolation` — first-registered observer raises on every event; verifies the second observer still receives every event, the graph run completes, and the raised exceptions do not propagate to `invoke()`.

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
