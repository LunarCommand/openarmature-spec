# 0012: Graph Engine — Completed Event Fires After Edge Evaluation

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-09
- **Targets:** spec/graph-engine/spec.md (revises §3 step 3 and §6
  routing-error treatment)
- **Related:** 0001, 0003, 0005, 0007
- **Supersedes:**

## Summary

Move the engine's `completed` observer event dispatch from **before**
outgoing edge evaluation to **after** outgoing edge evaluation. Under
the new ordering, edge-resolution failures (`routing_error`,
`edge_exception`) land on the preceding node's `completed` event with
its `error` field populated — same mechanism as the other three §4
runtime error categories (`node_exception`, `reducer_error`,
`state_validation_error`). The §6 contract that "routing_error does
NOT produce its own node event pair" is replaced with a uniform "all
§4 runtime errors land on a node's completed event with `error`
populated."

This is a small behavioral change in graph-engine §3 (when within the
post-merge window the completed event fires) and §6 (the event-shape
treatment for routing/edge errors). No new event flow, no new error
category, no implementation-side post-end span mutation.

## Motivation

Phase 6.1 PR-C of `openarmature-python` surfaced that conformance
fixture `004-otel-routing-error-attribution` cannot be driven cleanly
under the v0.8.2 §3/§6 ordering. The fixture's contract is "routing
errors attribute to the preceding node's span" (per observability
§4.2 status mapping), but the current §3 step 3 specifies dispatch
BEFORE edge evaluation, which means the preceding node's `completed`
event has already fired and its observability span has already
closed by the time a routing error arises. The §6 text at
`spec/graph-engine/spec.md` lines 306–308 explicitly notes this and
forbids a separate event flow ("a routing error does NOT produce its
own node event pair").

Two options were considered for resolving the gap (see thread
`phase-6-1-pr-c-conformance-fixtures` rounds 02–04 in the
coordination repo):

- **Sentinel-event approach.** Engine emits a synthetic
  `routing_error` event analogous to the LLM-event sentinel namespace
  pattern. Observer applies post-end mutation to the just-closed span
  — which is implementation-defined behavior in the OTel SDK
  (`InMemorySpanExporter` tolerates it, but production exporters
  that batch-serialize at `.end()` may not). Adds a new event flow
  and a new observer code path.
- **Ordering swap.** Engine fires the `completed` event AFTER edge
  evaluation rather than before. Edge-resolution failures naturally
  land on the completed event's `error` field via the existing
  failure-capture path. No new event flow, no observer code path
  changes, no post-end mutation.

The swap is cleaner end-to-end. Five §4 error categories all land via
the same mechanism (completed event with `error`). The observer's
existing handler does the work; no special-casing for routing-error
attribution. Production OTel exporter compatibility is unaffected
because spans are still finalized exactly once at their `end()` call.

The trade-off the swap accepts: the span captured by a node's
started/completed pair now spans "node body + reducer merge + edge
resolution" rather than "node body + reducer merge." For the
overwhelming majority of nodes this is invisible — edge resolution
takes microseconds. For routing-error cases the span correctly
captures the failing transition as part of the node's lifetime,
which matches the spec's existing "the routing-error attributes to
the preceding node's span" framing.

## Detailed design

### Graph-engine §3 (Execution model — step 3 revision)

**Current text** (`spec/graph-engine/spec.md` lines 124–131):

> 3. Between the merge in step 2 and the edge evaluation in step 4,
>    the engine MUST dispatch the node event for the just-completed
>    node onto the observer delivery queue per §6. Dispatch completes
>    synchronously before step 4; observer processing happens
>    asynchronously on the delivery queue and does not affect node
>    execution timing. If step 2 fails — because the node raised, a
>    reducer raised, or state validation failed — the engine MUST
>    dispatch the node event (with `error` populated) before the
>    failure propagates to the caller.

**Replace with:**

> 3. After the merge in step 2 AND the edge evaluation in step 4 both
>    complete, the engine MUST dispatch the node event for the
>    just-completed node onto the observer delivery queue per §6.
>    Dispatch completes synchronously before the next step 2 begins;
>    observer processing happens asynchronously on the delivery queue
>    and does not affect node execution timing. The dispatched event
>    captures the node's complete transition: its body's execution,
>    the reducer merge, and the resolution of its outgoing edge. If
>    any of those steps fail — because the node raised, a reducer
>    raised, state validation failed, the edge function raised
>    (`edge_exception`), or no matching edge was returned
>    (`routing_error`) — the engine MUST dispatch the node event
>    (with `error` populated) before the failure propagates to the
>    caller.

The renumbering of steps 4–6 is unaffected; step 4 still describes
edge evaluation. The only change is the temporal pin on step 3's
dispatch (was: between 2 and 4; now: after both 2 and 4) and the
extension of the failure list to include the two edge-resolution
categories.

### Graph-engine §6 (Observer hooks — routing-error treatment revision)

**Current text** (`spec/graph-engine/spec.md` lines 306–308):

> `routing_error` from §4 is a consequence of evaluating an outgoing
> edge against a post-update state. The `completed` event for the
> preceding node has already been dispatched by the time a routing
> error arises; a routing error does NOT produce its own node event
> pair.

**Replace with:**

> `routing_error` and `edge_exception` from §4 are consequences of
> evaluating an outgoing edge against a post-update state. Per §3
> step 3 (revised), the `completed` event fires after edge evaluation
> completes — so an edge-resolution failure populates the `error`
> field of the preceding node's `completed` event. Edge-resolution
> failures do NOT produce a separate event pair; they share the
> preceding node's pair, and the observer applies its standard §4.2
> status-mapping path to surface the error category and exception
> details on that node's span (per the observability spec mapping).

### Graph-engine §4 (Error semantics — no changes)

The §4 canonical runtime category list is unchanged:
`node_exception`, `edge_exception`, `reducer_error`, `routing_error`,
`state_validation_error`. The categories themselves and their
recoverable_state semantics are preserved. The only thing the
proposal changes is how `routing_error` and `edge_exception`
propagate to the §6 event stream — they now ride on the preceding
node's completed event rather than being silent observer-side or
needing a sentinel event.

### What does NOT change

- The `started` event firing point — still before node body
  execution, per §3 step 1 (unchanged).
- The `attempt_index`, `fan_out_index`, and `phase` fields on the
  event shape (unchanged from v0.6.0).
- The observer's strict-serial delivery contract (unchanged from
  v0.3.0).
- The §4 error categories themselves and their recoverable_state
  semantics.
- The `len(parent_states) == len(namespace) - 1` invariant.
- Pipeline-utilities §6 retry middleware behavior (each attempt still
  produces its own started/completed pair; the only change is when
  within the post-merge window the completed pair's "completed" half
  fires).

### Cross-spec touchpoints

- **Observability §4.2 status mapping.** The §4.2 contract — "engine-
  raised errors per graph-engine §4 produce ERROR status with
  `exception_recorded`" — is unchanged. The observer handler that
  maps `error`-populated `completed` events to ERROR status now
  picks up `routing_error` and `edge_exception` automatically.
  Implementations of the OTel mapping (proposal 0007 / spec
  observability §4.2) need no code changes for this to take effect;
  the existing handler covers the new error categories under the
  swap.
- **Pipeline-utilities §6 middleware.** Retry middleware semantics
  unchanged; the per-attempt event pair still fires per attempt.
- **Pipeline-utilities §9 fan-out.** Fan-out internal events unchanged
  in shape; the fan-out node's own completed event now fires after
  its outgoing edge evaluates (no functional difference for fan-out's
  own contract).
- **Pipeline-utilities §10 checkpointing.** §10.3's save-on-completed
  rule unchanged; saves now fire after edge evaluation, which
  preserves the "post-merge state at completed time" semantic and
  doesn't affect resume correctness.

## Conformance test impact

### Existing fixtures — verify alignment

The following fixtures already exist and exercise paths the swap
touches. Each should continue to pass after the impl-side change;
worth a confirmation that none of them encode the BEFORE-edge-eval
ordering as an implicit assumption:

- **`graph-engine/008-routing-error.yaml`** — verifies `routing_error`
  category surfaces with recoverable_state. Under the swap, the
  routing error still propagates with the same category and
  recoverable_state. Fixture's expectations should align without
  changes.
- **`graph-engine/014-observer-error-event.yaml`** — verifies a
  failing-node event has `error` populated and `post_state` absent.
  Under the swap, this still holds for every failure mode; the
  observer event for a routing-error case now also has `error`
  populated and `post_state` absent (consistent with the existing
  contract). Fixture may need to add a `routing_error` sub-case
  explicitly; check fixture's current category coverage.
- **`observability/004-otel-routing-error-attribution.yaml`** — the
  fixture this proposal unblocks. Existing expectations should
  align: the preceding node's span carries ERROR status with
  `routing_error` category. Under the swap, the observer's existing
  `_handle_completed` path produces this naturally.

### New fixture — `graph-engine/020-observer-edge-error-events.yaml`

Add a graph-engine fixture exercising the two edge-resolution error
categories' observer-event behavior:

- **Sub-case 1: routing_error.** Two-node linear graph; node A's
  edge function returns a destination not in the graph. Expected:
  one `started` + one `completed` event for A; the `completed` event
  has `error` populated to a `RoutingError` (or implementation-
  defined `RuntimeGraphError`-shaped) with category `routing_error`
  and the recoverable_state field populated.
- **Sub-case 2: edge_exception.** Two-node linear graph; node A's
  conditional edge function raises. Expected: one `started` + one
  `completed` event for A; the `completed` event has `error`
  populated with category `edge_exception`.

This makes the new event-side contract conformance-checkable
independently of the observability backend mapping.

### Observability fixture re-enable

`observability/004-otel-routing-error-attribution.yaml` was deferred
through Phase 6.1 PR-C pending this proposal. After the proposal
accepts and the impl swap lands (PR-C.1 in `openarmature-python`),
fixture 004 drives end-to-end with no fixture YAML changes.

## Alternatives considered

### Sentinel routing_error event (rejected)

Engine emits a new event with a sentinel namespace
(e.g., `("openarmature.routing_error",)`) when `RoutingError`
propagates. Observer treats it specially: looks up the preceding
node's just-closed span and applies post-end mutation to add ERROR
status + `openarmature.error.category` attribute.

**Why rejected:**

- **Post-end span mutation is implementation-defined per OTel.** The
  SDK contract for `Span.set_attribute()` after `.end()` is "may or
  may not be reflected in exported data" — works for in-memory
  exporters used in tests, breaks unpredictably for batch-export
  pipelines used in production. Building correctness on this surface
  is fragile.
- **Larger observer code path.** A new sentinel-event handler
  analogous to the LLM-event handler. The swap reuses the existing
  `_handle_completed` path; net code reduction, not addition.
- **Less uniform spec model.** Two §4 categories (routing_error,
  edge_exception) get a separate event flow; three (node_exception,
  reducer_error, state_validation_error) ride the completed event.
  The swap puts all five on the same flow.

### Status-quo + caller-level surfacing (rejected)

Leave §3 step 3 alone. Routing errors propagate as `RuntimeGraphError`
to the `invoke()` caller; callers handle observability themselves.
Spec contract (§4.2 "the preceding node's span carries the error")
is dropped.

**Why rejected:** weakens the §4.2 contract to a per-caller
convention. Backends like the OTel mapping can no longer guarantee
that routing errors surface in the trace at all without explicit
caller-side instrumentation. Wrong direction relative to the
"transparency over abstraction" charter principle.

### Hybrid: dispatch on edge entry (rejected)

A second event pair fires AT the edge boundary: an "edge_entered"
+ "edge_completed" pair. Routing errors land on edge_completed.

**Why rejected:** introduces a new event pair shape (separate from
the existing started/completed pair for nodes), adds a new namespace
component for "edge", and doesn't simplify anything the swap
doesn't simplify more cheaply. Observer-side complexity goes up,
not down.

## Versioning

Pre-1.0 SemVer permits MINOR bumps for breaking changes per
`GOVERNANCE.md`. This proposal is a small behavioral change to §3
step 3 (timing of completed dispatch) and §6 (routing-error
treatment) that constitutes a breaking change to the v0.6.0+ §6
event contract.

Recommended bump: **MINOR (0.8.x → 0.9.0)**. Same shape as v0.6.0's
breaking pair-model bump (also MINOR pre-1.0).

The skip-ahead governance principle (`GOVERNANCE.md`) applies:
implementations that have not yet shipped against v0.8.x may target
v0.9.0 directly. `openarmature-python`'s Phase 6.1 PR-C.1 is the
canonical first implementation of this contract.

## Open questions

- **Existing fixture 014 sub-case for routing_error.** Currently
  `graph-engine/014-observer-error-event.yaml` covers the failing-
  node case. Should the routing_error coverage land in fixture 014
  as additional sub-cases, or in the new fixture 020 proposed above,
  or both? Lean: 020 alone (keeps fixtures topical — 014 is
  node-body-failure focused; 020 is edge-resolution-failure focused).
- **Edge_exception fixture coverage today.** Current spec deems
  `edge_exception` a §4 category but I'm not aware of a fixture
  driving it specifically. Phase 6.1 PR-C-side investigation may
  surface a need to update fixture coverage; tracked in the §6.1
  Phase 6.1 thread.

## Implementation guidance (informative)

For the Python implementation in PR-C.1:

- `_step_function_node`, `_step_subgraph_node`, `_step_fan_out_node`
  in `src/openarmature/graph/compiled.py` move the
  `_dispatch_completed` call from before edge evaluation to after.
  Edge-evaluation try/except wraps the existing edge logic; on
  failure the resulting `error` is passed to `_dispatch_completed`
  via the existing failure-path keyword arg.
- The observer's `_handle_completed` path requires no changes —
  the existing handler maps `error`-populated events to ERROR status
  via the existing §4.2 path.
- New unit tests: routing_error inside a node's outgoing edge
  produces a single completed event with error populated; same for
  edge_exception.
- Existing 5 driven conformance fixtures + 31 unit tests stay green
  unchanged.
