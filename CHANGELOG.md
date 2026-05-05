# Changelog

All notable changes to the OpenArmature specification are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The spec follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.8.1] — 2026-05-05

### Added

- Conformance fixture `019-subgraph-two-level-nesting` (graph-engine). Regression coverage at depth 3 — existing subgraph fixtures (006, 011, 013) only exercised depth 1, leaving the §6 `len(parent_states) == len(namespace) - 1` invariant and the §2 default-projection chain untested at namespace length 3 / parent_states length 2. First graph-engine fixture using the plural `subgraphs:` form (already in use in observability and pipeline-utilities). No spec text or contract changes. ([PR #28](https://github.com/LunarCommand/openarmature-spec/pull/28))

## [0.8.0] — 2026-05-04

### Added

- **pipeline-utilities §10 Checkpointing (created).** A normative `Checkpointer` protocol — `save` / `load` / `list` / `delete` keyed by `invocation_id` — that lets a graph invocation persist state at well-defined save points and resume from a prior `invocation_id` without restarting from scratch. The protocol is backend-agnostic: §10 defines the contract; reference implementations (`InMemoryCheckpointer`, `SQLiteCheckpointer`) ship in core; durable-execution adapters (Temporal, DBOS, Restate, Redis) plug in as sibling packages. The engine fires a save at every graph-engine §6 `completed` event for outermost-graph nodes, subgraph-internal nodes, and the fan-out node itself (when the fan-out has fully completed). Fan-out instance internals do NOT save in v1, since v1 fan-out resume is atomic-restart and saving inner-instance state the engine cannot resume from would be dead weight. ([proposal 0008](proposals/0008-pipeline-utilities-checkpointing.md))
- **§10.1.1 Registration and default behavior.** Checkpointing is opt-in via Checkpointer registration at graph build time. Without a registered Checkpointer the engine never calls `save()` and `invoke(resume_invocation=...)` raises `checkpoint_not_found`. Mirrors the §6 observer-registration pattern; matches OA's broader "contract is normative; activation is an explicit choice" pattern.
- **§10.4 Resume model.** `invoke(resume_invocation=invocation_id)` loads the prior record, restores state, mints a new `invocation_id` for the resumed run, preserves the original `correlation_id` as the cross-attempt join key, and resumes from the first node in graph topological order whose position is not in `completed_positions`. Subgraph re-entry uses `parent_states`. State-restore (not event-replay) — sufficient because graph-engine §5's determinism contract makes state at any boundary equivalent to "all prior nodes' merged contributions."
- **§10.5 Idempotency contract.** Nodes MUST be idempotent under re-execution; mid-node crashes restart the node from its entry on resume. Three explicit escape hatches for nodes that cannot be made idempotent: application-level idempotency (idempotency keys, conditional writes — recommended); a sentinel-based skip middleware on top of pipeline-utilities §6; or skip checkpoint registration entirely.
- **§10.6 Retry on resume.** `attempt_index` resets to `0` on resume; retry budgets restart fresh. Consistent with "resume is a new execution attempt" framing (§10.4 step 4).
- **§10.7 Fan-out resume — atomic in v1.** A crash mid-fan-out causes the entire fan-out to re-run on resume. Couples directly to §10.3's "no fan-out internal saves" rule. A follow-on proposal will add per-instance fan-out resume with configurable backend batching for fan-out internal saves.
- **§10.8 Composition with §6 observer hooks.** `Checkpointer.save` calls SHOULD emit a §6-style observer event so the observability mapping can surface saves as spans (`openarmature.checkpoint.save` recommended). SHOULD-level to allow high-throughput backends to suppress event emission.
- **§10.9 Composition with detached trace mode.** Detached trace mode (observability §4.4) and checkpoint scope are independent. Detached trace mode is purely about trace UI organization; checkpoint scope is about execution recovery. One `invoke()` call produces one Checkpointer record set keyed by one `invocation_id`, regardless of how many detached traces it produced.
- **§10.10 New canonical runtime error categories.** `checkpoint_not_found` (non-transient — raised when `Checkpointer.load` returns `None`); `checkpoint_save_failed` (engine behavior implementation-defined — transient via middleware OR raise to caller; implementation MUST document its choice); `checkpoint_record_invalid` (non-transient — raised when a loaded record's schema is incompatible with the current graph).
- **§10.11 Reference implementations and backend layering.** Core ships `InMemoryCheckpointer` (not durable; tests, short-lived runs) and `SQLiteCheckpointer` (durable on a single host, WAL-mode, accepts pickleable or JSON-native state). Sibling-package adapters for Temporal, DBOS, Restate, and Redis are informative — not specified normatively.
- 8 conformance fixtures `024-031`: save-on-every-completed-event, resume-from-completed-position, record-shape, attempt-index-resets-on-resume, fan-out-atomic-restart, subgraph-resume, checkpoint-not-found, correlation-id-preserved-across-resume.

## [0.7.0] — 2026-04-29

### Added

- **observability capability (created).** Establishes the observability surface; the first backend mapping is OpenTelemetry. Defines a span hierarchy rooted at an `openarmature.invocation` span with node, subgraph, fan-out instance, retry attempt, and LLM-provider child spans (§4); span status mapping (§4.2) where engine-raised errors per graph-engine §4 produce ERROR status with `exception_recorded`; the `openarmature.*` attribute namespace covering invocation, node, subgraph, fan-out, LLM-provider, and cross-cutting attributes (§5); opt-in **detached trace mode** per subgraph or per fan-out node (§4.4) for very large fan-outs and long-running subgraphs, where the dispatch span carries an OTel `Link` to a new `trace_id`; canonical span-name table (§4.5); a normative §6 **TracerProvider isolation** rule — openarmature MUST emit through its own private `TracerProvider`, never the OTel global one, preventing duplicate signals when callers run their own auto-instrumentation; a §5.5 **LLM-provider span MUST emit** rule with a `disable_llm_spans` opt-out for callers who prefer external instrumentation; OTel **Logs Bridge** integration so log records emitted during an invocation carry the active `trace_id`/`span_id` (§7); and a §8 determinism contract that asserts deterministic span content (hierarchy, names, attributes minus timing, status) while carving out IDs and timestamps. ([proposal 0007](proposals/0007-observability-otel-span-mapping.md))
- **§3 Cross-backend correlation ID — first-class architectural concept.** A per-invocation `correlation_id` propagated across every backend the implementation emits to: caller-supplied verbatim or auto-generated UUIDv4 when absent; propagated via the language's idiomatic context primitive (Python `ContextVar`, TypeScript `AsyncLocalStorage`); reset between invocations; flows unchanged across detached subgraphs/fan-outs (invocation-scoped, not trace-scoped). For the OTel mapping it surfaces as `openarmature.correlation_id` on every span (§5.6) and every log record (§7); future backend mappings (Langfuse, etc.) follow the same per-backend "correlation ID realization" pattern.
- **§5.1 `openarmature.invocation_id` MUST UUIDv4.** Framework-generated, canonical 36-character UUIDv4. Distinct from `correlation_id`: `invocation_id` ties spans of one invocation together within one backend; `correlation_id` is the cross-backend join key. Backends MUST NOT conflate them.
- Conformance fixture suite `001-011` for observability: basic trace shape, subgraph hierarchy, error status, routing-error attribution to the preceding node span, LLM-provider span nested under the calling node (with `disable_llm_spans` and external-auto-instrumentation isolation sub-cases), fan-out instance attribution via `fan_out_index`, retry attempt spans (sibling-level), detached trace mode for both subgraph and fan-out, correlation_id cross-cutting + UUIDv4 + context-reset, log correlation including the detached-trace interaction, and determinism over the deterministic portion of span content.

## [0.6.0] — 2026-04-28

### Added

- **pipeline-utilities §9 Parallel fan-out (created).** A `fan_out` node type that executes a compiled subgraph (or async callable) once per item in a parent state field, with bounded concurrency, and collects per-instance results back into a parent collection field. Two modes: `items_field` (data-driven; instance count = `len(items_field_value)`, items projected per-instance via `item_field`) and `count` (count-driven; literal int OR callable `(state) -> int`; no per-item data). Mutually exclusive. Default `concurrency: 10` (also int-or-callable). Default `error_policy: "fail_fast"` (cancel siblings on first failure); alternative `"collect"` (run all, omit failed slots, record errors in `errors_field`). New `instance_middleware` config wraps each instance's invocation as a unit (the seam for whole-instance retry vs. per-inner-node retry). Empty fan-out (`items_field == []` or `count == 0`) raises `fan_out_empty` by default (`on_empty: "raise"`); user opts in to silent no-op via `on_empty: "noop"`. Optional `count_field` writes the resolved instance count to a parent state field for programmatic inspection. New compile error categories `fan_out_field_not_list`, `fan_out_count_mode_ambiguous`. New runtime error categories `fan_out_invalid_count`, `fan_out_invalid_concurrency`, `fan_out_empty` (non-transient — does not auto-resolve via retry). ([proposal 0005](proposals/0005-pipeline-utilities-parallel-fan-out.md))
- **graph-engine §3 Execution model — fan-out concurrency exception.** Single-threaded execution rule carved out so a fan-out node may execute multiple subgraph instances concurrently. Single-threaded execution resumes for the parent run after the fan-out completes.
- **graph-engine §6 — `fan_out_index` field on the node event shape.** Optional non-negative integer; populated only on events from nodes inside a fan-out instance. The combination of `namespace`, `fan_out_index`, `attempt_index`, and `phase` uniquely identifies an event source.
- **graph-engine §6 — per-observer phase subscription.** Optional `phases` parameter on observer registration. Accepted values: `{"started", "completed"}` (default), `{"completed"}` (v0.5.0-style; useful for metrics/log aggregators), `{"started"}` (useful for stuck-node alerting). Empty phase sets raise at registration. Engine filters delivery; phase filter applies at delivery, not dispatch.
- Conformance fixtures for pipeline-utilities `017-023` (fan-out basic, fail-fast, collect, retry-middleware, instance-middleware-retry, count-and-concurrency-modes, empty-input) and for graph-engine `017-018` (fan-out index, phase subscription).

### Changed

- **graph-engine §6 Event dispatch — replaced single-event-per-attempt with started/completed pairs (BREAKING, but pre-1.0).** Each node attempt now produces TWO events: a `started` event before the node executes, and a `completed` event after the reducer merge (or after a failure is captured). Both events share `node_name`, `namespace`, `step`, `attempt_index`, `fan_out_index`, `pre_state`, `parent_states`. `started` events have `post_state` and `error` absent; `completed` events have exactly one of `post_state` or `error` populated. Required new `phase` field on the event shape. The pair model makes span boundaries cleaner for OpenTelemetry mapping and other observability backends; doubled event volume is mitigated by per-observer phase subscription.
- **graph-engine §6 — removed the v0.5.0 "Middleware-dispatched events" subsection.** Under the pair model, the engine instruments at the inner-node-call level: each invocation of the wrapped node function produces a started/completed pair from the engine. Retry middleware no longer dispatches its own events — engine handles per-attempt events naturally. The "Middleware-dispatched events" mechanism added in v0.5.0 is no longer needed and is removed.
- **pipeline-utilities §6.1 Retry middleware — manual dispatch removed.** Pseudocode simplified: no more `dispatch_failed_attempt_event(...)` calls. Each call to `next(state)` triggers a fresh started/completed pair from the engine. The "Per-attempt observer events" subsection rewritten to reflect engine-handled events.
- pipeline-utilities §8 Out of scope — removed "Parallel fan-out / fan-in" (now in §9).
- Existing v0.5.0 conformance fixtures updated for the pair model: `graph-engine/conformance/012-016` (5 fixtures) and `pipeline-utilities/conformance/011`, `015` — every event in `expected.observer_events` split into a started/completed pair; `delivery_order` updated to include `phase` field.

### Notes

- **Breaking change to v0.5.0 §6 contract permitted by pre-1.0 SemVer** (per `GOVERNANCE.md`). Per the new "Skip-ahead implementation" governance principle, implementations that have not yet shipped against v0.5.0 may target v0.6.0 directly without implementing the v0.5.0 contract first.

## [0.5.0] — 2026-04-28

### Added

- **pipeline-utilities capability (created).** Establishes the foundational pipeline-utilities surface. §2 specifies the **middleware** primitive: an async wrapper around node execution with the shape `(state, next) -> partial_update`, supporting pre-node and post-node phases, short-circuit, exception recovery, and reentrant `next` calls. §3 mandates per-node and per-graph registration with per-graph-outside-per-node composition. §4 mandates strict bidirectional subgraph-boundary locality (parent middleware sees the subgraph as a single dispatch; subgraph middleware never sees parent state). §6 specifies two **canonical middleware** implementations MUST ship: **retry** (§6.1) with default classifier aligned to llm-provider §7 transient categories, exponential-with-full-jitter backoff, explicit cancellation propagation, and per-attempt observer event dispatch; **timing** (§6.2) with monotonic-clock duration record, `on_complete` callback, and per-node `node_name` capture. ([proposal 0004](proposals/0004-pipeline-utilities-middleware.md))
- New `RetryMiddleware.classifier` signature `(exception, state) -> bool`. Default classifier ignores `state` and matches purely on §7 transient categories; user-supplied classifiers MAY consult pre-merge state for context-dependent retry policies.
- Conformance fixture suite `001-016` for pipeline-utilities, exercising basic firing, composition ordering, per-graph-vs-per-node nesting, short-circuit, error propagation, error recovery, retry success/exhaustion/passthrough/determinism, subgraph isolation, timing basic firing/failure path, timing+retry composition, retry per-attempt observer events, and retry state-aware classifier.

### Changed

- **graph-engine §6 Observer hooks — `attempt_index` field added to node event shape.** Non-negative integer, default `0`. For nodes wrapped by retry middleware (pipeline-utilities §6.1) that re-attempts execution, `attempt_index` increments per attempt; combined with `node_name` and `namespace` it uniquely identifies events from a retried node. The `len(parent_states) == len(namespace) - 1` invariant is unaffected. ([proposal 0004](proposals/0004-pipeline-utilities-middleware.md))
- **graph-engine §6 Event dispatch — events fire per attempt, not per node execution.** For nodes not wrapped by re-attempting middleware, this is exactly once per node execution (unchanged from v0.4.0). For nodes wrapped by retry middleware, one event fires per attempt: the engine dispatches the final attempt's event; the retry middleware dispatches events for any preceding failed attempts via the new "Middleware-dispatched events" subsection.
- **graph-engine §6 — new "Middleware-dispatched events" subsection.** Middleware MAY dispatch additional node events through the engine's delivery queue. Pipeline-utilities canonical retry middleware MUST do so for non-final attempts. Implementation-defined dispatch mechanism; same delivery-queue rules and observer-error isolation as engine-dispatched events; same §5 determinism contract.
- Graph-engine conformance fixture `016-observer-attempt-index-default` — verifies the new `attempt_index` field defaults correctly to `0` for non-retry workflows.

### Notes

- Open question deferred from proposal 0004: per-conditional-branch middleware. Documented as an Out-of-scope item in pipeline-utilities §8 with workarounds (state markers + per-node middleware).

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
