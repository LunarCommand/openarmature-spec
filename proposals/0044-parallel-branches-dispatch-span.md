# 0044: Parallel-Branches Dispatch Span Synthesis

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-29
- **Accepted:** 2026-05-29
- **Targets:** spec/graph-engine/spec.md (§6 NodeEvent — adds `parallel_branches_config` field, mirroring `fan_out_config` from proposal 0013); spec/observability/spec.md (§5 — adds an `openarmature.node.branch_name` per-branch span attribute paralleling `openarmature.node.fan_out_index`; new §5.7 *Parallel-branches span attributes* paralleling §5.4 *Fan-out span attributes*; §4 / §6 driving-span lifecycle — defines per-branch dispatch span synthesis behavior); new conformance fixture exercising the OTel parallel-branches dispatch span shape.
- **Related:** 0011 (parallel branches — established the §6 NodeEvent `branch_name` field), 0013 (fan-out config on NodeEvent — the template this proposal mirrors), 0042 (reserved-keys extension — included `branch_name` in §8.4.2 Langfuse mapping; this proposal completes the §5 / §6 OTel side)
- **Supersedes:**

## Summary

Align the OTel mapping (observability §5 / §6) with the Langfuse mapping
(§8) for parallel-branches: synthesize a per-branch dispatch span between
the parallel-branches NODE span and the inner-node spans, so the OTel
trace tree carries the same shape as the Langfuse Observation tree
(per fixture 030's expectations).

Two structural changes enable this:

1. **graph-engine §6 NodeEvent** gains a `parallel_branches_config` field
   (optional structured value, populated on every `started` / `completed`
   event for a parallel-branches NODE, including retried attempts; absent
   otherwise). Carries `branch_names` (ordered sequence of branch
   identifiers in dispatch order), `branch_count` (derived), `error_policy`
   (from pipeline-utilities §11.5), and `parent_node_name` (the
   parallel-branches NODE's name). Mirrors `fan_out_config` from proposal
   0013, minus the fan-out-specific `item_count` / `concurrency` and
   plus the parallel-branches-specific `branch_names`.
2. **observability §5** gains an `openarmature.node.branch_name`
   per-branch span attribute (paralleling `openarmature.node.fan_out_index`)
   and a new §5.7 *Parallel-branches span attributes* subsection
   (paralleling §5.4 *Fan-out span attributes*). The §4 / §6 driving-span
   lifecycle gains per-branch dispatch span synthesis behavior: the OTel
   observer caches the parallel-branches NODE's namespace on `started`,
   synthesizes a per-branch dispatch span on the first inner event of each
   branch, and closes the per-branch dispatch span on the parallel-branches
   NODE's `completed` event (children-before-parents).

## Motivation

The Langfuse mapping (§8) already emits a per-branch dispatch span
between the parallel-branches NODE observation and the inner-node
observations (per Langfuse fixture 030's expected shape):

```
dispatcher (parallel-branches NODE observation)
├── fraud_check dispatch span (branch_name = "fraud_check")
│   └── ask (inner observation)
└── policy_audit dispatch span (branch_name = "policy_audit")
    └── ask (inner observation)
```

The OTel mapping currently does NOT synthesize the per-branch dispatch
span; inner-branch spans parent directly under the parallel-branches
NODE span, with no spec-defined OTel span attribute disambiguating which
branch they belong to. (The §6 NodeEvent's `branch_name` field is
observer-readable, and 0042 added an `observation.metadata.branch_name`
row to §8.4.2's Langfuse mapping, but observability §5 does not currently
define an `openarmature.*` span attribute carrying the value — this
proposal also introduces `openarmature.node.branch_name` to fill that
gap.) The OTel trace tree is "works but doesn't match the Langfuse
shape," and the two mappings diverge structurally on the same graph
topology.

Two consequences:

- Operators consuming both backends see different tree shapes for the
  same invocation — Langfuse observations nest one level deeper than the
  corresponding OTel spans.
- Implementations have to handle parallel-branches specially in their
  OTel observer: the `_StackKey` (`(namespace, attempt_index,
  fan_out_index)`) collides when two concurrent branches share an
  identically-named inner node (e.g. `dispatcher → ask` in both
  `fraud_check` and `policy_audit`). Implementations have been widening
  `_StackKey` with `branch_name` internally as a workaround. Adding a
  per-branch dispatch span at the structural level removes the
  `_StackKey` collision entirely — each branch's inner spans key off
  their distinct dispatch-span parent, and the disambiguation is part of
  the span tree rather than an observer-private detail.

Proposal 0013 solved the analogous problem for fan-out by adding
`fan_out_config` to NodeEvent + §5.4 fan-out span attributes + the
§4 / §6 synthesis behavior. This proposal applies the same shape to
parallel-branches.

## Detailed design

The proposed normative changes are below. Anticipated bump: **MINOR**
(pre-1.0). The concrete spec version is assigned at acceptance.

### graph-engine §6 NodeEvent — `parallel_branches_config` field

A new optional field is added to the §6 NodeEvent definition (paralleling
the existing `fan_out_config` field per proposal 0013):

> **`parallel_branches_config`** — optional structured value, populated on
> EVERY `started` and `completed` event for a parallel-branches NODE
> (i.e., events whose `node_name` resolves to a parallel-branches node per
> pipeline-utilities §11), including retried attempts of the
> parallel-branches node itself (`attempt_index > 0`). Carries the
> resolved values for the observability §5.7 parallel-branches attributes.
> Absent (null / None / equivalent) on all events from non-parallel-
> branches nodes — inner-node events from inside a parallel-branches
> branch (those carry `branch_name` instead), subgraph wrapper events,
> function-node events whether retried or not, and so on. The value
> carries four fields:
>
> - **`branch_names`** — non-empty ordered sequence of strings. The
>   branch identifiers in declaration / dispatch order, as configured on
>   the parallel-branches node (pipeline-utilities §11.1). Available at
>   parallel-branches entry, so populated on both `started` and
>   `completed` events.
> - **`branch_count`** — positive integer. The number of branches
>   dispatched. Equals `len(branch_names)`; surfaced explicitly so
>   observers and downstream consumers do not need to derive it. Populated
>   on both `started` and `completed` events.
> - **`error_policy`** — string, exactly one of `"fail_fast"` or
>   `"collect"` (per pipeline-utilities §11.5). Populated on both
>   `started` and `completed` events.
> - **`parent_node_name`** — string. The parallel-branches node's own
>   name in the parent graph (i.e., equal to `node_name` on this event).
>   Surfaced explicitly so observers and downstream consumers do not need
>   to rederive it from `namespace`. Populated on both `started` and
>   `completed` events.
>
> Implementations MUST present all four keys of `parallel_branches_config`
> whenever the field itself is populated. Keys are never individually
> omitted on the basis of an implementation's representation; observers
> can rely on key presence.
>
> `parallel_branches_config` MUST be populated on a parallel-branches
> node's `completed` event regardless of whether the event carries
> `post_state` or `error` — the resolved configuration visible at
> parallel-branches entry MUST appear on the completed event with all
> four keys populated, matching the corresponding `fan_out_config` rule
> in proposal 0013.

### observability §5 — `openarmature.node.branch_name` per-branch span attribute

A new attribute is added to the per-span attribute set, paralleling
§5.2's `openarmature.node.fan_out_index`:

> **`openarmature.node.branch_name`** — string. Populated on every span
> emitted from a node inside a parallel-branches branch (per the §6
> NodeEvent `branch_name` field, when present). Absent on observations
> from nodes outside any parallel-branches subgraph. Mirrors the
> per-instance role `openarmature.node.fan_out_index` plays for fan-out
> instance spans: same uniqueness-disambiguator role within the OTel
> attribute namespace.

### observability §5.7 — *Parallel-branches span attributes* (new subsection)

A new subsection is added after §5.6, paralleling §5.4 *Fan-out span
attributes*:

> ### 5.7 Parallel-branches span attributes
>
> The following attributes MUST appear on per-branch dispatch spans
> (synthesized by the OTel observer per §4.3 and §6):
>
> - `openarmature.node.branch_name` — string. The branch's identifier,
>   sourced from the §6 NodeEvent `branch_name` field. Also appears on
>   every inner-node span beneath the per-branch dispatch span —
>   consistent with how `openarmature.node.fan_out_index` propagates onto
>   inner nodes from §5.4. (Newly introduced by this proposal; prior spec
>   versions did not define an OTel span attribute carrying `branch_name`.)
> - `openarmature.parallel_branches.parent_node_name` — string. The
>   parallel-branches NODE's name in the parent graph, cached by the
>   observer from the parallel-branches NODE's `started` event.
>
> Parallel-branches node spans (the parent of the per-branch dispatch
> spans) carry:
>
> - `openarmature.parallel_branches.branch_count` — int. The number of
>   branches dispatched.
> - `openarmature.parallel_branches.error_policy` — string. One of
>   `"fail_fast"` or `"collect"` (per pipeline-utilities §11.5). Useful
>   for filtering traces by policy.
>
> Implementations source these attributes from the corresponding
> graph-engine §6 NodeEvent fields, preserving the two-span-category
> distinction above:
>
> - **Parallel-branches node span attributes.**
>   `openarmature.parallel_branches.branch_count` and
>   `openarmature.parallel_branches.error_policy` go on the
>   parallel-branches node span. Sourced from
>   `event.parallel_branches_config` on the parallel-branches node's own
>   `started` / `completed` events.
> - **Per-branch dispatch span attributes.** `openarmature.node.branch_name`
>   and `openarmature.parallel_branches.parent_node_name` go on the
>   synthesized per-branch dispatch span. The observer caches the
>   `parent_node_name` from the parallel-branches node's `started` event
>   (via `parallel_branches_config.parent_node_name`) and applies it on
>   each synthesized dispatch span. The branch's `branch_name` is sourced
>   from the first inner event of that branch (`event.branch_name`).
>
> **Per-branch dispatch span name.** The OTel observer MUST set the
> per-branch dispatch span's `name` attribute to the branch's
> `branch_name` value (e.g., `"fraud_check"`, `"policy_audit"`). This
> matches the Langfuse mapping's per-branch Span observation naming and
> gives operators a directly meaningful span name in the trace tree.

### observability §4 / §6 — driving-span lifecycle: per-branch dispatch span synthesis

The §6 driving-span-lifecycle text gains a new rule for parallel-branches
synthesis, paralleling the existing fan-out synthesis rule:

> **Parallel-branches dispatch span synthesis.** On a parallel-branches
> node's `started` event, the OTel observer:
>
> 1. Opens the parallel-branches NODE span (per the observer-driven model
>    above) and attaches the §5.7 node-level attributes from
>    `parallel_branches_config`.
> 2. Caches the resolved `parallel_branches_config` (carrying
>    `parent_node_name` for the dispatch-span attribute and `branch_names`
>    for step 5's close ordering) under the parallel-branches NODE's full
>    §6 event-source identity `(namespace, attempt_index, fan_out_index,
>    branch_name)`. The NODE's `branch_name` is null when the NODE itself
>    runs outside any parallel-branches branch (the common case — the
>    NODE is the dispatcher, not a node inside a branch); it is non-null
>    when the NODE executes inside an outer parallel-branches branch
>    (nested parallel-branches), where per §6 the NODE's event carries
>    the outer branch's `branch_name`. Including `branch_name` in the
>    cache key disambiguates such nested executions; `attempt_index` and
>    `fan_out_index` similarly disambiguate retried attempts and fan-out-
>    instance contexts.
>
> On the **first inner `started` event** received whose containing
> parallel-branches NODE matches a cached entry (matched by the inner
> event's `attempt_index` and `fan_out_index` — which propagate from the
> parallel-branches NODE per §6's nested-retry / nested-fan-out rules —
> and a namespace prefix that matches the cached NODE's namespace), and
> whose `branch_name` value hasn't yet been seen for that cached entry,
> the observer:
>
> 3. Synthesizes a per-branch dispatch span as a child of the
>    parallel-branches NODE span, attaches the §5.7 dispatch-span
>    attributes (`branch_name`, `parent_node_name` from the cache), and
>    pushes it onto the span-stack keyed by the parallel-branches NODE's
>    full event-source identity plus the inner branch:
>    `(parallel_branches_node_namespace, parallel_branches_node_attempt_index,
>    parallel_branches_node_fan_out_index, branch_name)`. The dispatch
>    span's start time is the moment the inner `started` event fires.
> 4. The inner event itself opens its span as a child of the synthesized
>    per-branch dispatch span (not a direct child of the parallel-branches
>    NODE span).
>
> On the parallel-branches NODE's `completed` event, the observer:
>
> 5. Looks up the cache entry by the completing parallel-branches NODE's
>    full §6 event-source identity `(namespace, attempt_index,
>    fan_out_index, branch_name)`, then closes the per-branch dispatch
>    spans associated with that cache entry in declaration order per the
>    cached `parallel_branches_config.branch_names`. Dispatch spans
>    associated with other NODE executions (other fan-out instances,
>    other retry attempts, other outer-branch contexts) remain open until
>    their respective NODEs' `completed` events fire. Each dispatch span's
>    end-time is the moment the parallel-branches NODE's `completed`
>    event fires.
> 6. Closes the parallel-branches NODE span itself (children-before-parents
>    — this is the standard close order for nested-span emission).
>
> The synthesis is **lazy**: the dispatch span is created on the first
> inner `started` event for each branch, not eagerly at the parallel-
> branches NODE's `started`. This keeps the synthesis observable from
> existing NodeEvents without requiring the engine to emit per-branch
> lifecycle events.

The §4 OTel span-tree definition gains a corresponding bullet documenting
the per-branch dispatch span as a child of the parallel-branches NODE
span and a parent of each branch's inner-node spans.

## Conformance test impact

### New fixture

A new fixture under `observability/conformance/` (number assigned at
acceptance) exercises the OTel parallel-branches dispatch span synthesis,
paralleling the existing Langfuse-side fixture 030 shape on the OTel
side. The fixture asserts:

- Per-branch dispatch spans exist between the parallel-branches NODE
  span and the inner-node spans (one dispatch span per declared branch).
- Each per-branch dispatch span carries `openarmature.node.branch_name`
  and `openarmature.parallel_branches.parent_node_name` attributes with
  the expected values.
- The parallel-branches NODE span carries
  `openarmature.parallel_branches.branch_count` and
  `openarmature.parallel_branches.error_policy` attributes sourced from
  `parallel_branches_config`.
- Inner-node spans inside each branch carry
  `openarmature.node.branch_name` matching the branch they belong to and
  are children of the corresponding per-branch dispatch span (not direct
  children of the parallel-branches NODE span).
- Lifecycle invariants: per-branch dispatch spans close before the
  parallel-branches NODE span (children-before-parents); dispatch spans
  in declared order on close.

### Extended

Existing parallel-branches fixtures (`030-caller-metadata-parallel-branches-per-branch`
on the Langfuse side) are unaffected — Langfuse already synthesizes the
per-branch dispatch span, and this proposal aligns the OTel side without
changing the Langfuse-side shape.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments
(concrete version assigned at acceptance):

- graph-engine §6 NodeEvent gains the `parallel_branches_config` optional
  field (additive — `None` on existing non-parallel-branches events).
- observability §5 gains the `openarmature.node.branch_name` per-span
  attribute.
- observability §5.7 *Parallel-branches span attributes* added (new
  subsection paralleling §5.4).
- §4 / §6 driving-span lifecycle text extended with per-branch dispatch
  span synthesis behavior.
- New conformance fixture.

The OTel trace tree for invocations using parallel-branches changes
shape: inner-branch spans previously parented directly under the
parallel-branches NODE span now parent under a per-branch dispatch span.
Downstream consumers that hard-code the previous "inner spans are direct
children of the parallel-branches NODE span" assumption need to update
to the new nesting. The proposal also introduces
`openarmature.node.branch_name` as a new OTel span attribute on
inner-branch spans (paralleling `openarmature.node.fan_out_index`),
surfacing the §6 NodeEvent `branch_name` field into §5's attribute
namespace for the first time — this is a new attribute, not a rename of
a pre-existing one.

## Out of scope

- **Per-branch resource limits.** Parallel-branches doesn't have a
  fan-out-style concurrency cap (it dispatches all branches concurrently
  per pipeline-utilities §11.3). No new attribute for concurrency.
- **Synthesis at the engine level.** The engine does NOT emit per-branch
  lifecycle events; the dispatch span is purely an OTel-observer-side
  synthesis from existing NodeEvents (the `branch_name` field on inner
  events plus `parallel_branches_config` on the NODE's events provides
  enough signal). This keeps the engine's event surface small.
- **Langfuse mapping updates.** Langfuse already synthesizes per-branch
  dispatch spans (per fixture 030); this proposal aligns the OTel side
  rather than touching the Langfuse mapping.

## Alternatives considered

- **Keep the current OTel shape** (inner-branch spans direct children
  of the parallel-branches NODE span, with no spec-defined OTel
  disambiguator at the attribute level). Rejected: structural divergence
  between OTel and Langfuse mappings on the same graph topology, and the
  observer-internal `_StackKey` collision when two branches share an
  identically-named inner node forces implementations into a workaround
  (widening the key with `branch_name`) that this proposal eliminates
  at the structural level.
- **Engine emits per-branch lifecycle events** (e.g., a `branch_started`
  / `branch_completed` event pair around each branch's inner spans).
  Rejected: expands the engine's event surface for a concern that's
  observable from existing NodeEvents (the inner event's `branch_name`
  + the parallel-branches NODE's `parallel_branches_config` is enough
  signal for the observer to synthesize the dispatch span). The fan-out
  side (proposal 0013) settled on the same observer-side synthesis
  approach for the same reason.
- **`ParallelBranchesEventConfig` with a smaller field set** (just
  `branch_names` + `parent_node_name`, mirroring the coord-thread
  sketch). Rejected: `branch_count` and `error_policy` are surfaced
  explicitly so observers don't have to derive them from
  `branch_names` length or look up the policy elsewhere; matches
  `fan_out_config`'s four-key shape from proposal 0013.
- **Do nothing.** Leaves the OTel trace tree structurally different
  from the Langfuse Observation tree for parallel-branches invocations,
  and leaves the `_StackKey` collision as an observer-internal
  workaround. Rejected: parity between the two mappings is part of
  §8's framing as a "sibling §-section to OTel."
