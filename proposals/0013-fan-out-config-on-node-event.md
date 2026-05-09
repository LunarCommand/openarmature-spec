# 0013: Graph Engine — Fan-Out Config on Node Event

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-09
- **Accepted:** 2026-05-09
- **Targets:** spec/graph-engine/spec.md (extends §6 NodeEvent shape);
  spec/observability/spec.md (small editorial cross-reference in §5.4)
- **Related:** 0001, 0005, 0007, 0011
- **Supersedes:**

## Summary

Extend graph-engine §6's `NodeEvent` shape with an optional
`fan_out_config` field carrying the resolved values for the four
observability §5.4 fan-out attributes (`item_count`, `concurrency`,
`error_policy`, `parent_node_name`). The engine MUST populate the
field on a fan-out node's own `started` and `completed` events; the
field MUST be null on all other events.

The motivating concrete need: observability §5.4 normatively
requires these four attributes on fan-out spans, but the canonical
`NodeEvent` shape provides no path for the engine to surface them
to the observer. The reference Python implementation surfaced an
architectural finding during Phase 6.1 PR-C.2 scoping: an
implementation-private ContextVar pattern (the route initially
recommended by the spec maintainer in coordination thread
`phase-6-1-pr-c-conformance-fixtures` round 06) does not survive
the observer's worker-task boundary, because asyncio's
`Context.copy()` semantics freeze the worker's context at task
creation. ContextVar values written by the engine after worker
creation are not visible on the worker side. The data must flow
through the canonical event payload to cross the queue.

A small editorial cross-reference is added in observability §5.4
noting that the per-instance fan-out instance span layout in §4
applies to both detached and non-detached fan-outs. This is
already the case in §4's prose ("each fan-out instance produces
its own subgraph span as a child"); the cross-reference makes the
connection explicit for readers landing in §5.4 first.

No new error categories. No new event flow. No conformance-test
additions — fixture `006-otel-fan-out-instance-attribution`
already exercises both the fan-out node attributes and the
per-instance span layout.

## Motivation

### The cross-task ContextVar problem

The graph-engine's observer hook delivery model (§6, lines
206–214) puts every observer's event handlers on a delivery queue
that runs concurrently with graph execution. In the reference
Python implementation, this is realised as an asyncio task
distinct from the engine task: `CompiledGraph.invoke()` calls
`asyncio.create_task(deliver_loop(queue))`, and that
`create_task` call captures the engine's ContextVar context at
the moment of task creation per Python's `Context.copy()`
semantics. Subsequent ContextVar mutations on the engine side
do NOT propagate to the worker.

The architectural consequence: implementation-private ContextVars
written by the engine inside `_step_fan_out_node`'s scope are
read as `None` on the worker side, because the worker captured a
snapshot before any fan-out scope was entered. Any surfacing
mechanism that relies on the observer reading ambient context
inside its handler is broken by the queue.

This isn't a Python-specific quirk; it's the natural shape of
async-runtime context isolation. TypeScript implementations using
`AsyncLocalStorage` would face the same boundary; the spec
shouldn't lean on a mechanism that any conformant implementation
must work around.

The right shape is the one PR-A established for the LLM-hook
calling-node identity fields: the engine reads engine-side
state at dispatch time and stuffs it onto the event payload; the
observer reads from the event, not from ambient context. This
proposal extends that pattern to the four observability §5.4
fan-out attributes.

### Why this matters for spec parity

§6's `NodeEvent` field list is canonical: implementations across
languages observe the same event shape so that observers
authored against the spec port across implementations. If the
Python implementation surfaces fan-out config via a private
`pre_state` subclass (Option B below) and the TypeScript
implementation invents its own equivalent, observers are no
longer language-portable for fan-out attribute access. Putting
the field on the canonical `NodeEvent` shape is the
language-agnostic answer.

### Why now (not in proposal 0007)

Proposal 0007 (observability OTel mapping) introduced the four
§5.4 attributes as normative requirements on fan-out spans, but
left "how the engine gets the values to the observer" as
implementation-defined. The reference Python implementation
deferred fan-out attribute support to Phase 6.1 PR-C.2; scoping
that PR surfaced the cross-task issue. Pre-1.0 we have headroom
to refine §6 to support the §5.4 contract cleanly rather than
relying on each implementation to invent its own mechanism.

## Detailed design

### Graph-engine §6 (Observer hooks — Node event shape extension)

**Current text** (`spec/graph-engine/spec.md` lines 276–281):

> - `fan_out_index` — optional non-negative integer. Populated
>   only for events from nodes that execute inside a fan-out
>   instance (pipeline-utilities §9). The 0-based index of this
>   fan-out instance among its siblings (in `items_field` mode,
>   matching the position of the corresponding item; in `count`
>   mode, `0..count-1`). When the same node name appears in
>   multiple fan-out instances, the combination of `namespace`,
>   `fan_out_index`, `attempt_index`, and `phase` uniquely
>   identifies the event source. Absent for events from nodes
>   that are not inside any fan-out instance.

**Add immediately after** (between the `fan_out_index` bullet and
the closing paragraph at line 283):

> - `fan_out_config` — optional structured value, populated on
>   EVERY `started` and `completed` event for a fan-out node
>   (i.e., events whose `node_name` resolves to a fan-out node
>   per pipeline-utilities §9), including retried attempts of
>   the fan-out node itself (`attempt_index > 0`). Carries the
>   resolved values for the observability §5.4 fan-out
>   attributes. Absent (null / None / equivalent) on all events
>   from non-fan-out nodes — inner-node events from inside a
>   fan-out instance (those carry `fan_out_index` instead),
>   subgraph wrapper events, function-node events whether
>   retried or not, and so on.
>
>   The `fan_out_config` value carries four fields:
>
>   - `item_count` — non-negative integer. The resolved instance
>     count for this fan-out invocation. Equal to
>     `len(items_field_value)` in `items_field` mode and to the
>     resolved `count` in `count` mode (per pipeline-utilities
>     §9). Available at fan-out entry, so populated on both
>     `started` and `completed` events of the fan-out node.
>   - `concurrency` — positive integer or null (unbounded).
>     The resolved concurrency bound for this fan-out
>     invocation, after evaluating the int-or-callable from
>     pipeline-utilities §9. Matches §9.2's resolved type —
>     zero or negative values are invalid at the configuration
>     boundary (raised as `fan_out_invalid_concurrency` per
>     §9.2) and therefore never appear here; null indicates
>     unbounded. The `0` sentinel in observability §5.4's
>     `openarmature.fan_out.concurrency` attribute is an
>     OTel-attribute-mapping pragmatism (OTel primitives can't
>     carry null) and does NOT appear on this canonical field.
>     Available at fan-out entry, so populated on both
>     `started` and `completed` events.
>   - `error_policy` — string, exactly one of `"fail_fast"` or
>     `"collect"` (per pipeline-utilities §9, `error_policy`).
>     Populated on both `started` and `completed` events.
>   - `parent_node_name` — string. The fan-out node's own name
>     in the parent graph (i.e., equal to `node_name` on this
>     event). Surfaced explicitly so observers and downstream
>     consumers do not need to rederive it from `namespace`.
>     Populated on both `started` and `completed` events.
>
>   Implementations MUST present all four keys of
>   `fan_out_config` whenever the field itself is populated on
>   a fan-out node event — `item_count`, `concurrency`,
>   `error_policy`, and `parent_node_name`. Keys are never
>   individually omitted on the basis of an implementation's
>   representation; observers can rely on key presence. Of the
>   four, only `concurrency` is nullable (null indicates
>   unbounded per pipeline-utilities §9.2); `item_count`,
>   `error_policy`, and `parent_node_name` are always non-null
>   when `fan_out_config` is populated.
>
>   `fan_out_config` MUST be populated on a fan-out node's
>   `completed` event regardless of whether the event carries
>   `post_state` or `error` — i.e., even when the fan-out
>   itself raised (`fan_out_empty`, `fan_out_invalid_count`,
>   `fan_out_field_not_list`, etc.) at runtime after config
>   resolution succeeded, the resolved configuration that was
>   visible at fan-out entry MUST appear on the completed event
>   with all four keys populated.
>
>   Behavior in the rare case where engine configuration
>   resolution itself fails (e.g., a `concurrency` or `count`
>   callable raises) is implementation-defined for v0.10.0 —
>   whether the engine dispatches a fan-out node event pair at
>   all in that case, and if so what shape `fan_out_config`
>   takes for partially-resolved configurations, is left to a
>   future proposal. Conformance does not depend on this
>   corner: existing fixtures exercise the success path and the
>   post-config-resolution runtime-failure paths only.

The closing paragraph at lines 283–286 (which currently reads
"`pre_state` is populated on both `started` and `completed`
events..." through "`started` events MUST have both `post_state`
and `error` absent") is unchanged.

### Observability §5.4 (Fan-out span attributes — editorial cross-reference)

**Current text** (`spec/observability/spec.md` lines 363–377):

> ### 5.4 Fan-out span attributes
>
> The following attributes MUST appear on fan-out instance spans
> (per pipeline-utilities §9):
>
> - `openarmature.node.fan_out_index` — int. The §6 `fan_out_index`
>   for this instance.
> - `openarmature.fan_out.parent_node_name` — string. The fan-out
>   node's name in the parent graph.
>
> Fan-out node spans (the parent of the per-instance subgraph
> spans) carry:
>
> - `openarmature.fan_out.item_count` — int. The resolved instance
>   count (matches the `count_field` value when configured;
>   matches `len(items_field)` in items_field mode).
> - `openarmature.fan_out.concurrency` — int. The resolved
>   concurrency bound (or a sentinel int for unbounded; `0` is
>   RECOMMENDED).
> - `openarmature.fan_out.error_policy` — string. One of
>   `"fail_fast"` or `"collect"`. Useful for filtering traces by
>   policy.

**Add a paragraph** at the end of §5.4 (after the existing
attribute lists, before §5.5):

> Implementations source these attributes from the corresponding
> graph-engine §6 `NodeEvent` fields, preserving the two-span-
> category distinction above:
>
> - **Fan-out node span attributes.**
>   `openarmature.fan_out.item_count`,
>   `openarmature.fan_out.concurrency`, and
>   `openarmature.fan_out.error_policy` go on the fan-out node
>   span. Sourced from `event.fan_out_config` on the fan-out
>   node's own `started`/`completed` events.
> - **Fan-out instance span attributes.**
>   `openarmature.fan_out.parent_node_name` goes on the
>   per-instance fan-out instance spans (not on the fan-out
>   node span). It is also surfaced via `event.fan_out_config`
>   on the fan-out node's `started` event, but per-instance
>   events don't themselves carry `fan_out_config` — the
>   observer caches the value from the fan-out node's started
>   event and applies it when synthesizing each per-instance
>   instance span. `openarmature.node.fan_out_index` also goes
>   on per-instance instance spans (and on inner-node spans
>   nested below); it is sourced directly from
>   `event.fan_out_index` on those inner-node events.
>
> The per-instance span layout (one per-instance subgraph span
> as a child of the fan-out node span, with inner-node spans
> nested below) is required by §4 for both detached and
> non-detached fan-out modes — the only behavioral difference
> between detached and non-detached is the trace-id treatment
> per §4.4, not the per-instance layout.

This addition is editorial: it cross-references the existing §6
field (newly extended by this proposal) and the existing §4
per-instance layout requirement, which already applies regardless
of detached mode. No new normative behavior is introduced in §5.4.

## Conformance impact

Conformance fixture `observability/006-otel-fan-out-instance-attribution`
already exercises both pieces of the proposal:

- The fan-out node span's `item_count` / `concurrency` /
  `error_policy` attributes (sourced from the new
  `fan_out_config` field).
- The per-instance subgraph span layout (one span per
  `fan_out_index`, nested between the fan-out node span and
  inner-node spans).
- The per-instance `parent_node_name` and `fan_out_index`
  attributes.

No fixture additions are required. Implementations that drive
fixture 006 today against the v0.9.0 spec already comply with
both the existing §5.4 attributes and the existing §4 per-instance
layout. This proposal makes the surfacing mechanism canonical so
that implementations don't each invent their own non-portable
mechanism.

## Migration / compatibility

- **Spec version:** v0.10.0 (pre-1.0 MINOR bump).
- **Field addition is additive at the event-shape level.** Existing
  observers that ignore `fan_out_config` continue to function
  unchanged. The field is null on all events that aren't
  fan-out-node events, which is the same observed shape they see
  today.
- **§5.4 cross-reference is editorial.** No new normative behavior
  in observability; existing implementations passing fixture 006
  already comply.
- **Per the "Skip-ahead implementation" governance principle**
  (`GOVERNANCE.md`), implementations that have not yet shipped
  v0.9.0 MAY target v0.10.0 directly without implementing v0.9.0
  first.
- **No change to error categories**, no change to the
  started/completed event pair contract, no change to the §6
  delivery queue semantics.

## Alternatives considered

### A. ContextVar surfacing (initially recommended; rejected)

Initial recommendation in coordination thread
`phase-6-1-pr-c-conformance-fixtures/06-spec-006-architectural-decisions.md`:
expose a private `current_fan_out_config: ContextVar` (mirroring
the engine's `current_namespace_prefix` / `current_fan_out_index`
ContextVars established in PR-A); engine sets it on entry to
`_step_fan_out_node` and resets on exit; observer's `_node_attrs`
reads it when constructing the fan-out node span's attributes.

Rejected on architectural grounds: as documented in the Motivation
section, asyncio's `Context.copy()` at observer-worker-task
creation time freezes the worker's ContextVar context. Engine-side
mutations after worker creation are invisible to the worker. The
observer's `_node_attrs` runs in the worker, so
`current_fan_out_config()` would read `None`. Same constraint
applies in any async runtime with copy-on-task-creation context
semantics (Python asyncio, TypeScript `AsyncLocalStorage`).

### B. Typed `pre_state` subclass mirroring `_LlmEventState` (rejected)

Mirror the implementation pattern PR-A used for the LLM hook:
construct a private Pydantic subclass of `State` that adds the
fan-out fields, set it as the event's `pre_state`, and have the
observer `isinstance`-check on dispatch.

Rejected on two grounds:

1. **Pre_state semantic bend.** §6 specifies `pre_state` as "the
   state the node received." For LLM events this was tolerable
   because the event's `pre_state` was always synthetic (LLM
   provider calls don't run inside a node's body the same way
   normal nodes do; the event's pre_state had no other consumer).
   For fan-out node events, `pre_state` is the parent graph's
   actual state at fan-out entry, with real consumers (state
   inspection, debugging, downstream observers). Overloading
   pre_state with config attributes muddies a contract that's
   currently clean.
2. **Dynamic Pydantic subclass per graph.** Each graph has its own
   parent state schema. The Python pattern would require
   constructing `_FanOutEventState` as a runtime subclass of the
   user's parent state class for every graph that contains a
   fan-out node. This is fragile under generics, future Pydantic
   versions, and IDE-time inference; the LLM hook avoided this
   because its synthetic pre_state had a fixed shape.

### C. Sidecar event payload (rejected)

Add an `extra` mapping to `NodeEvent` carrying
implementation-defined key-value pairs. Engine populates fan-out
config under a known key; observer reads from that key.

Rejected: an untyped `extra` mapping invites every implementation
to invent its own keys for every cross-cutting metadata need,
fragmenting the canonical event shape worse than language-private
mechanisms. The whole point of putting fan-out config on the
canonical `NodeEvent` is that the field is normatively defined,
typed, and language-portable.

## References

- **Phase 6.1 PR-C.2 architectural finding** (motivating thread):
  `openarmature-coord/threads/phase-6-1-pr-c2-fan-out-per-instance/01-python-contextvar-finding.md`
- **PR-C scoping with the original ContextVar recommendation**
  (superseded by this proposal):
  `openarmature-coord/threads/phase-6-1-pr-c-conformance-fixtures/06-spec-006-architectural-decisions.md`
- **Observability §5.4** — the four fan-out attributes whose
  surfacing mechanism this proposal canonicalizes.
- **Observability §4 (line 145–147)** — the per-instance subgraph
  span layout requirement, already normative for both detached
  and non-detached fan-outs.
- **Pipeline-utilities §9** — fan-out node configuration shape
  (source of `concurrency`, `error_policy`, `count` /
  `items_field`).
- **Proposal 0007** — observability OTel mapping; introduced the
  §5.4 attributes without specifying the surfacing mechanism this
  proposal addresses.
- **Proposal 0005** — pipeline-utilities parallel fan-out;
  established the §6 `fan_out_index` field this proposal extends
  with `fan_out_config`.
- **PR-A pattern** (reference): the LLM-hook calling-node identity
  fields surfaced via event-payload state established by
  `openarmature-python` Phase 6.1 PR-A; this proposal extends the
  same pattern to fan-out config attributes.
