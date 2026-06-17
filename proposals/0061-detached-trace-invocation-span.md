# 0061: Detached-Trace Invocation Span

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-09
- **Accepted:** 2026-06-17
- **Targets:** spec/observability/spec.md (§4.4 *Detached trace mode* — normative update: a detached subgraph or fan-out roots its separate trace in an `openarmature.invocation` span carrying the **same** `invocation_id` as the parent invocation, with the detached unit's spans nested under it, replacing the current "spans use the new `trace_id` as their root" shape; §4.1 *Span timing* + §4.2 *Status mapping* — the detached invocation span opens at the detached unit's entry and closes at its completion (the detached-unit window, not the whole `invoke()`) and carries the detached unit's outcome status, distinct from the parent invocation span's `invoke()`-wide window and whole-run status; §4.3 *Parent-child rules* — new *Detached-dispatch invocation spans* paragraph pinning the shared-`invocation_id` correlation across the trace boundary, parallel to the existing *Suspended-resume invocation spans* paragraph; §5.1 *Invocation span attributes* — clarifying note that one invocation MAY produce multiple invocation spans across traces (parent + detached), all carrying the same `invocation_id`, and that the always-emit attribution invariant applies to each; §4.5 *Span names* — note that multiple `openarmature.invocation`-named spans MAY coexist across the traces of a single invocation; §8 *Langfuse mapping* — clarifying note that the detached Langfuse Trace's `trace.metadata.implementation_name` / `implementation_version` rows source from the now-present detached invocation span's §5.1 attributes, and that `trace.metadata.detached_from_invocation_id` (proposal 0042) points to the shared `invocation_id`); plus updates to two existing conformance fixtures (`008-otel-detached-trace-mode`, `058-implementation-attribution-otel`) whose expected span trees currently contradict each other.
- **Related:** 0042 (reserved `detached` / `detached_from_invocation_id` keys + the §8.4.1 detached-child back-pointer row this proposal cross-references), 0052 (implementation attribution attributes + the §5.1 *Always-emit invariant*; its fixture 058 case 2 surfaced the contradiction this proposal resolves), 0021 (suspension — established the *Suspended-resume invocation spans* shared-`invocation_id` correlation pattern this proposal mirrors for detached dispatch), 0053 (precedent: an ambiguity-resolution proposal that reconciled spec text against fixture behavior through the full lifecycle rather than as an editorial edit), 0054 (per-invocation event drain — `drain_events_for(invocation_id)` scoping, relevant to the shared-`invocation_id` consequence discussed below)
- **Supersedes:**

## Summary

Resolves a contradiction between two Accepted-proposal conformance fixtures over the
OTel span shape of a detached trace (per observability §4.4), and pins the underlying
invocation-identity model that the contradiction exposed.

`008-otel-detached-trace-mode` (case 1) asserts a detached subgraph's separate trace
roots in the **subgraph-named span** — no invocation span. `058-implementation-attribution-otel`
(case 2, added by proposal 0052) asserts the detached trace roots in an
**`openarmature.invocation` span** carrying the §5.1 implementation-attribution
attributes. The two cannot both be normative: either a detached trace opens an
invocation span at its root or it does not.

This proposal resolves toward **the detached trace roots in an `openarmature.invocation`
span**, carrying the **same `invocation_id`** as the parent invocation (detached mode
is an observer-side trace-rendering choice, not an engine-level sub-invocation — the
run's identity does not change). The detached unit's spans nest under that invocation
span. This:

1. Lets the §5.1 always-emit attribution invariant apply to detached traces with no
   per-context caveat (the detached trace has an invocation span for the attributes
   to land on).
2. Requires no graph-engine change — the OTel observer synthesizes the detached
   invocation span at the new trace's root, using the `invocation_id` it already sees
   on every event.
3. Reuses the existing *Suspended-resume invocation spans* correlation pattern
   (§4.3): one invocation, multiple invocation spans, correlated by shared
   `invocation_id`.

The key clarification the proposal pins: **`trace_id` is the per-backend rendering
identity (distinct per detached trace); `invocation_id` is the engine-level run
identity (shared across the parent and all detached traces of one `invoke()` call).**

## Motivation

### The contradiction

Detached trace mode (§4.4) lets a subgraph or fan-out render its spans into a separate
trace, opt-in per observer, for two documented reasons: very large fan-outs would bury
the parent trace under thousands of sibling spans, and long-running subgraphs need
real-time visibility before the parent trace closes.

Two fixtures describe the OTel span tree of a detached subgraph's separate trace, and
they disagree at the root:

**`008-otel-detached-trace-mode` case 1** (`detached_subgraph_two_traces_one_link`):

```
<trace_id_detached>
  long_running_workflow        ← subgraph-named span at the root; no invocation span
    step
```

**`058-implementation-attribution-otel` case 2**
(`detached_subgraph_attribution_propagates_to_child_trace_invocation_span`):

```
<trace_id_detached_child>
  openarmature.invocation      ← invocation span at the root, carrying §5.1 attribution
    step                        ← (note: no subgraph-wrapper span between them)
```

These can't both be the contract. 058 case 2 was added by proposal 0052 alongside the
§5.1 *Always-emit invariant* ("`openarmature.implementation.name` and
`openarmature.implementation.version` MUST be emitted on every invocation span") — the
fixture presupposes a detached trace *has* an invocation span. 008 case 1 (older,
reflecting §4.4's "all spans inside the detached subgraph … use the new `trace_id` as
their root") presupposes it does not.

A second, smaller inconsistency: 058 case 2 puts the inner node (`step`) directly under
the invocation span with **no subgraph-wrapper span** — which contradicts the normal
nesting rule (a subgraph's inner node sits under the subgraph span).

The conformance manifest in the reference implementation currently defers 058 case 2's
runtime activation pending this resolution; the cross-capability impact (an
implementation passes 008 today, can't pass 058 case 2) is real, not hypothetical.

### Why the resolution is a normative decision, not an editorial fix

Reconciling the two fixtures requires choosing what an observer MUST emit for a detached
trace — a behavioral contract change to the observability capability, plus a change to
conformance-test expectations established by Accepted proposals. That is squarely
proposal-governed territory, not an editorial correction. The direct precedent is
proposal 0053, which reconciled §3.4 spec text against fixture behavior through the full
lifecycle.

### The identity model the contradiction exposed

Underneath the fixture disagreement is an unpinned question: **when a subgraph detaches,
is it a new invocation?** The answer is **no** — and pinning that is the load-bearing
part of this proposal.

Detached trace mode is configured **per observer** (§4.4: "a parameter on the OTel
observer's constructor"), and §8 specifies the Langfuse observer applies detachment
**independently**. A per-observer rendering choice cannot create an engine-level
invocation: if it could, two observers (OTel + Langfuse) detaching the same subgraph
would each mint a *different* fresh `invocation_id`, and "the detached subgraph's
invocation_id" would not be a stable property of the run. It is one `invoke()` call
(§4.4: "every span produced during a single `invoke()` call"), rendered across multiple
traces. The run's `invocation_id` does not change.

This is corroborated by the existing Langfuse mapping: fixture
`033-langfuse-detached-trace-mode` has the detached child Trace carry
`metadata.detached_from_invocation_id = <parent invocation_id>` (proposal 0042). That
back-pointer references the parent invocation's id as the stable engine-level identity
the detached trace was split from — exactly the shared-`invocation_id` model. The
detached trace's *distinct* identity is its `trace_id` (a per-backend rendering
identifier), not a fresh `invocation_id`.

## Proposed change

### §4.4 *Detached trace mode* — root the detached trace in an invocation span

The current §4.4 bullet "All spans inside the detached subgraph or fan-out … use the new
`trace_id` as their root. They are NOT children of the parent's invocation span" is
replaced with the invocation-span-rooted shape:

- When a subgraph or fan-out is detached, the observer creates a new `trace_id` and opens
  an `openarmature.invocation` span as the **root span of the new trace**.
- The detached invocation span carries the §5.1 invocation-span attribute set:
  `openarmature.invocation_id` set to the **same value** as the parent invocation
  (it is the same `invoke()` call); `openarmature.graph.entry_node` set to the detached
  unit's entry node (the subgraph's entry node, or the fan-out instance subgraph's entry
  node) — §5.1's "entry node name of the outermost graph" resolves **per trace** under
  detached mode, and the outermost graph of a detached trace is the detached subgraph
  itself (the alternative, echoing the parent graph's entry, would name a node that
  does not appear anywhere in the detached trace); `openarmature.graph.spec_version`,
  `openarmature.implementation.name`, and
  `openarmature.implementation.version` per §5.1, identical to the parent's (they are
  runtime-identity constants for the same run).
- The detached unit's spans (the subgraph span, its inner-node spans, nested subgraph
  spans, retry-attempt spans, LLM provider spans) nest **under** the detached invocation
  span, following the normal §4.3 parent-child rules within the detached trace.
- The parent's subgraph-dispatch span (or fan-out node span) stays in the parent trace
  and carries the OTel `Link` to the detached trace, unchanged from current §4.4. The
  Link's target is the detached trace (whose root is now the detached invocation span).

For detached **fan-out**, each instance trace roots in its own detached invocation span
(one per instance trace), each carrying the same shared `invocation_id` and the instance
subgraph's entry node. The fan-out instance span (named after the fan-out node, carrying
`openarmature.node.fan_out_index` per §4.5 / §5.4) nests directly under the per-instance
detached invocation span; the instance's inner-node spans nest under that. The fan-out
node's span in the parent trace carries one Link per instance trace, unchanged. The
per-instance trace shape:

```
<instance trace i>
  openarmature.invocation          ← detached root; shared invocation_id; entry = instance subgraph entry
    per_document_scoring           ← fan-out instance span; openarmature.node.fan_out_index = i
      score
```

The motivating rationale (§4.4 intro) is preserved and strengthened: a detached trace
now renders as a **self-contained invocation** in the backend UI — proper root, full
identity attribution at the top — which is exactly what the "watch a long-running
subgraph live" use case wants, rather than a headless subtree whose producing
library/version is only discoverable by pivoting to the parent trace.

### §4.1 *Span timing* + §4.2 *Status mapping* — the detached invocation span's window and status

The existing §4.1 rule — "the invocation span's start time is the entry of `invoke()`;
its end time is the return" — describes the **parent** invocation span and MUST NOT be
read as applying to the detached invocation span. §4.1 gains a paragraph specifying the
detached invocation span's window:

> A detached invocation span (per §4.4) opens when its detached subgraph or fan-out
> instance is entered and closes when that unit completes — the detached-unit window,
> coterminous with the detached subgraph span nested directly beneath it, NOT the
> outer `invoke()` window. (It opens and closes in the same window as the parent's
> subgraph-dispatch span that carries the Link to the detached trace.)

§4.2 gains a *Detached invocation span status* note:

> A detached invocation span carries the **detached unit's** outcome status per the
> §4.2 table — `OK` when the detached subgraph / fan-out instance completes
> successfully, `ERROR` (with the §4 category and an OTel exception event) when it
> raises. This is distinct from the parent invocation span's status, which reflects the
> whole `invoke()` outcome.

When a detached subgraph raises, the failure surfaces on **two** spans — the parent's
subgraph-dispatch span (per the existing §4.4 "reflects the subgraph's outcome via §4.2"
rule) and the detached invocation span (per the note above). This is correct, not
double-attribution noise: the two spans live in different traces and each is the
authoritative status carrier for its own trace's view of the dispatch (the parent trace
records "the dispatch failed"; the detached trace records "this invocation errored").

### §4.3 *Parent-child rules* — new *Detached-dispatch invocation spans* paragraph

A new paragraph parallel to the existing *Suspended-resume invocation spans* paragraph:

> **Detached-dispatch invocation spans.** A detached subgraph or fan-out (per §4.4)
> renders its spans into a separate trace rooted in its own `openarmature.invocation`
> span. That detached invocation span carries the **same** `openarmature.invocation_id`
> as the parent invocation — detached mode is an observer-side trace-rendering choice,
> not an engine-level invocation boundary, so the run's identity is unchanged. The
> parent and detached invocation spans are correlated by shared
> `openarmature.invocation_id` (per §5.1), the same correlation mechanism as
> *Suspended-resume invocation spans* above; they additionally carry the OTel `Link`
> from the parent's dispatch span to the detached trace (per §4.4). The detached
> trace's **distinct** identity is its `trace_id` (a per-backend rendering identifier
> — a fresh OTel `trace_id`, a distinct Langfuse `trace.id`); the `invocation_id` is the
> shared engine-level run identity. This distinguishes detached dispatch from
> checkpoint-resume (pipeline-utilities §10.4), which mints a fresh `invocation_id`
> because it is a genuinely separate `invoke()` call.

### §5.1 *Invocation span attributes* — multiple-invocation-spans-per-run note

A clarifying note (the always-emit invariant text itself is unchanged):

> A single invocation MAY produce more than one `openarmature.invocation` span when
> detached trace mode (§4.4) is in use — one in the parent trace and one at the root of
> each detached trace — all carrying the same `openarmature.invocation_id`. The
> always-emit attribution invariant applies to **each** invocation span: every
> invocation span, in the parent trace or a detached trace, carries the §5.1
> attribute set (`openarmature.implementation.name` / `.version`,
> `openarmature.graph.spec_version`, `openarmature.invocation_id`,
> `openarmature.graph.entry_node`). `openarmature.correlation_id` also appears on every
> detached invocation span, but as a §5.6 cross-cutting attribute (on every span of the
> invocation per §3.1 / §5.6), not as a member of the §5.1 set. No per-context caveat is
> needed on the §5.1 invariant because a detached trace always has an invocation span at
> its root.

### §4.5 *Span names* — note on multiple invocation spans

A note that the constant span name `openarmature.invocation` applies to every invocation
span including detached-trace roots; multiple `openarmature.invocation`-named spans MAY
coexist across the traces of a single invocation, disambiguated by `trace_id`.

### §8 *Langfuse mapping* — clarifying note (no normative change)

The Langfuse side is already largely consistent and needs only a clarifying note:

- The detached Langfuse Trace already carries `trace.metadata.implementation_name` /
  `implementation_version` (proposal 0052 §8.4.1, sourced from the §5.1 attributes). The
  note records that the source is the detached invocation span's §5.1 attributes — now
  normatively present per this proposal — so the OTel and Langfuse sides share one
  canonical attribution source.
- `trace.metadata.detached_from_invocation_id` (proposal 0042) points to the shared
  `invocation_id` — the engine-level run identity, the same value carried on both the
  parent and detached invocation spans. The note clarifies this is not a pointer from a
  fresh child id to a distinct parent id; it is the back-pointer recording which
  invocation the separately-rendered trace belongs to.

Langfuse has no per-trace "invocation span" concept (the Trace entity is the invocation-
level container), so the OTel invocation-span-at-root change has no direct Langfuse
analog — the Langfuse Trace already plays that role.

## Conformance test impact

### `008-otel-detached-trace-mode` — updated

Case 1 (`detached_subgraph_two_traces_one_link`) detached-trace expected span tree gains
the invocation-span root with the subgraph span nested under it:

```
<trace_id_detached>
  openarmature.invocation      ← NEW root; same invocation_id as parent
    long_running_workflow
      step
```

A new invariant asserts the detached invocation span's `openarmature.invocation_id`
equals the parent invocation span's (`detached_invocation_id_equals_parent: true`).

Case 2 (`detached_fan_out_one_trace_per_instance`): the per-instance trace internals are
not asserted as span trees today (the case asserts `detached_trace_count: 3` + parent
structure + invariants), so the expected block needs only an added invariant that each
instance trace roots in an invocation span sharing the parent `invocation_id`. The
parent-trace assertions are unchanged.

A new case 3 (`detached_subgraph_raises_error_status_on_both_spans`) covers the §4.2
status rule added by this proposal: a detached subgraph whose inner node raises produces
`ERROR` status on **both** the parent's dispatch span (parent trace) and the detached
invocation span (detached trace), each with the §4 category + an OTel exception event;
asserts the two spans carry the same `invocation_id` and live in distinct traces. Pins
the dual-trace status behavior so an implementation can't drop the detached-trace-side
ERROR.

### `058-implementation-attribution-otel` — updated

Case 2 (`detached_subgraph_attribution_propagates_to_child_trace_invocation_span`)
detached-trace expected span tree gains the missing subgraph-wrapper span between the
invocation span and the inner node:

```
<trace_id_detached_child>
  openarmature.invocation      ← carries §5.1 attribution (unchanged)
    detached_workflow          ← NEW subgraph-wrapper span
      step
```

The attribution-attribute assertions on the detached invocation span are unchanged; the
`always_emit_invariant_applies_to_every_invocation_span` invariant continues to hold.
Case 1 (the non-detached attribution case) is unchanged.

### `033-langfuse-detached-trace-mode` — no expected-output change; clarifying comment

Fixture 033 is the Langfuse detached-mode fixture, and Langfuse has no per-trace
invocation span (the Trace entity is the invocation-level container), so the OTel
invocation-span-at-root change does not touch it. Its detached-trace assertions
(`detached_from_invocation_id`, `detached_child_trace_ids`, shared `correlation_id`,
distinct `trace_id`s) all hold unchanged under the shared-`invocation_id` framing pinned
here — none of them are affected. The only edit is a one-line YAML comment clarifying
that the `detached_from_invocation_id: <invocation_id_parent>` value references the
**shared run `invocation_id`** (the run the detached trace was split from), not a
distinct child `invocation_id` — the placeholder name should not be read as implying the
detached trace has its own `invocation_id`. No assertion or expected-value change.

## Versioning

**MINOR bump** (pre-1.0). This is a normative observer-rendering change (detached OTel
traces gain an invocation-span root) plus two fixture expected-output changes — **not a
textual-only proposal**. The reference implementation's OTel observer needs a real change
(synthesize the detached invocation span at each detached trace root), so the conformance
manifest entry will be `implemented` on the observer change landing, not `textual-only`.

Tentative spec version target deferred to Accept (next available MINOR after any in-flight
acceptances). No public type or interface changes; no graph-engine change. The CHANGELOG
entry calls out the detached-trace span-shape change under **Changed** for observer-
operator awareness — any downstream snapshotting detached-trace OTel output sees a new
invocation-span layer at the detached trace root after upgrade.

## Alternatives considered

1. **Fresh `invocation_id` for the detached trace (the original framing).** Reject —
   incoherent under per-observer detachment. Detached mode is configured per observer and
   applied independently by OTel and Langfuse (§4.4 / §8); a fresh id would mean two
   observers mint two different ids for the same detached subgraph, so "the detached
   invocation_id" would not be a stable property of the run. It would also require a
   graph-engine change (engine-level sub-invocation identity) for what §4.4 frames as an
   observer-side rendering feature, and would contradict proposal 0042's
   `detached_from_invocation_id` back-pointer (which references the parent invocation's
   stable id). Checkpoint-resume mints a fresh `invocation_id` because it is a genuinely
   separate `invoke()` call; detached dispatch is not.

2. **No invocation span on the detached trace; drop the attribution there (Path B1).**
   Reject — the detached trace, viewed in isolation in a backend UI, would carry no
   `openarmature.implementation.*` identity; an operator would have to pivot to the
   parent trace via `correlation_id` to learn what produced it. It also forces a
   per-context caveat onto the §5.1 always-emit invariant ("every invocation span — and
   detached traces don't open one"), which every future §5.1 attribute would inherit.
   Breaks the "paste any trace into the registry search" operator flow that motivated the
   attribution attributes in the first place (proposal 0052).

3. **No invocation span; put the attribution on the subgraph-root span as a special case
   (Path B2).** Reject — the §5.1 invariant stops being cleanly invocation-span-scoped and
   picks up a "…and on detached-trace root spans" caveat that every future §5.1 attribute
   inherits. The mechanism becomes "trace-root attribution" rather than "invocation-span
   attribution," a more complex contract for marginal benefit over rooting the trace in a
   real invocation span.

4. **Leave the contradiction; let implementations pick.** Reject — two Accepted-proposal
   fixtures assert mutually exclusive span trees; an implementation cannot pass both. The
   reference implementation already defers 058 case 2's runtime activation pending this
   resolution. Leaving it unresolved leaves a permanent conformance gap and an ambiguous
   contract.

## Open questions

None remaining at draft time. The two questions surfaced during drafting are resolved in
the proposal text above (collected here for retrieval).

**Resolved at Draft:**

- **Detached invocation span's `graph.entry_node` value** — decided: the **detached
  unit's own entry node** (the subgraph's entry, or the fan-out instance subgraph's
  entry). This is the reading consistent with §5.1's existing definition ("the entry
  node name of the outermost graph"), which resolves per-trace under detached mode — the
  outermost graph of a detached trace is the detached subgraph itself. Echoing the
  parent graph's outermost entry was the alternative, rejected because it would name a
  node absent from the detached trace and defeat the self-contained-view purpose of
  detached mode. Stated normatively in the §4.4 touchpoint above.

- **Fixture 033 (Langfuse) touch** — decided: **no expected-output change.** Langfuse
  has no per-trace invocation span, so the OTel invocation-span change doesn't reach it;
  033's assertions all hold unchanged under shared-`invocation_id`. The only edit is a
  one-line clarifying comment on the `detached_from_invocation_id` placeholder (per the
  *Conformance test impact* section above).

## Out of scope

- **Engine-level sub-invocations for detached subgraphs.** Detached mode stays an
  observer-side rendering feature; this proposal does not give detached subgraphs their
  own engine `invocation_id`, lifecycle, or `invoke()` boundary.
- **Changing the detached-mode opt-in mechanism.** The per-observer configuration surface
  (§4.4) is unchanged.
- **Non-detached span shapes.** The default single-trace nesting (§4.1–§4.3) is unchanged.
- **`drain_events_for` semantics under detached mode.** The shared-`invocation_id` model
  means a detached subgraph's events carry the parent's `invocation_id`, so
  `drain_events_for(invocation_id)` (proposal 0054) covers them as part of the same
  invocation — consistent with detached mode being one `invoke()`. No change to the drain
  contract is proposed; this proposal only pins the OTel span shape and the identity
  model that makes the drain behavior unambiguous.
- **The `trace_id` derivation for detached Langfuse Traces.** How a backend derives a
  distinct `trace.id` for a detached child from the shared `invocation_id` is an
  existing implementation-defined concern (the parent and child Traces already carry
  distinct `trace.id`s today per fixture 033); this proposal does not constrain it.
