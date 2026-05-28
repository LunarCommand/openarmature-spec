# 0040: Observability — Mid-Invocation Metadata Augmentation MUST Reach Open Spans in the Augmenting Context

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-28
- **Targets:** spec/observability/spec.md (tightens the §3.4 *Mid-invocation augmentation* open-span clause from SHOULD to MUST and adds precise per-async-context scoping; adds a §6 subsection describing how an observer-driven lifecycle reflects augmentation onto already-open spans); spec/graph-engine/spec.md (small §6 clarifying touch: the observer delivery queue MAY carry a framework-emitted metadata-augmentation event in addition to node-boundary `started` / `completed` pairs)
- **Related:** 0034 (caller-supplied invocation metadata — defines §3.4), 0003 (node-boundary observer hooks — the §6 event model), 0007 (observability OTel span mapping), 0031 (observability Langfuse mapping), 0035 (Langfuse graph-topology fixtures — inner-leaf tree precedent)
- **Supersedes:**

## Summary

Proposal 0034 added §3.4 *caller-supplied invocation metadata*, including a
**mid-invocation augmentation** helper (`set_invocation_metadata(**entries)`).
Today §3.4 says open spans MAY pick up augmented entries — implementations
SHOULD update them "where the backend SDK supports it." This proposal tightens
that to a **MUST**, scoped precisely to the **augmenting async context's own
open spans**, and blesses the mechanism by which an observer-driven lifecycle
(the RECOMMENDED §6 driver) reflects the augmentation onto spans that are
already open.

Three coupled changes:

1. **§3.4 SHOULD → MUST.** Spans that are still open at the time of a
   `set_invocation_metadata` call AND were opened from the augmenting async
   context MUST be updated in place (where the backend SDK supports in-place
   attribute / metadata update). The closed-span boundary is unchanged (closed
   spans are NOT retroactively updated).

2. **Precise per-async-context scoping.** The update is scoped to the
   augmenting context's **own** open spans (and open descendants that share the
   mutated mapping copy) — NOT ancestor spans (the shared invocation span, a
   parent fan-out-node span) and NOT sibling spans (other fan-out instances,
   other parallel branches). This scoping is load-bearing: it is exactly the
   per-async-context copy-on-write isolation §3.4 already mandates, applied to
   in-place open-span updates. A naive "update every open span in the
   invocation" would re-introduce the cross-context leakage §3.4 forbids.

3. **Mechanism (§6 + a graph-engine §6 touch).** An observer runs on the §6
   serial delivery queue, not in the node body's call stack, so it does not
   observe the `set_invocation_metadata` call directly. The RECOMMENDED
   mechanism is a framework-emitted **metadata-augmentation event** delivered
   on the same serial observer queue, carrying the added entries plus the
   originating lineage identity (`namespace`, `attempt_index`, `fan_out_index`,
   `branch_name`). The open-span-update *behavior* is the MUST; the event is the
   recommended *mechanism*, mirroring §6's existing observer-driven /
   middleware-driven framing ("the contract is the emitted spans, not the
   driver mechanism").

Two existing conformance fixtures (029 fan-out per-instance, 030
parallel-branches per-branch) already encode the open-span update as a hard
expectation but cannot pass while §3.4 only SHOULDs it; this proposal makes
them normatively required and corrects their expected trees. One new fixture
(034) covers the outermost-context half of the rule.

## Motivation

§3.4's mid-invocation augmentation exists so that code inside a node body,
middleware, or observer can attach an identifier discovered at runtime
(`productId`, `documentId`, `branchName`, per-request `requestId`) and have it
appear on that work's observability output — the canonical example being a
fan-out where each instance tags its own subtree with its item's id.

For that to be useful end-to-end, the augmented entry has to land on the spans
that represent the augmenting work — including the spans that are **already
open** when the call is made. In the fan-out example, the instance's dispatch
span and the inner node span are opened *before* the body calls
`set_invocation_metadata` (their attribute snapshot is taken at the node's
`started` event, which fires before the body runs). Only spans opened *after*
the call — typically the LLM generation — see the new entry under the current
SHOULD. The result is a split: the generation carries `productId`, but the
dispatch span and inner node span that contain it do not. An operator
filtering the backend UI by `productId` finds the generation but not the
surrounding instance span, so the per-item view is incomplete.

The fix is to update the open spans in place. The SDKs support it (OTel
`set_attribute` on an open span; Langfuse observation / trace `update`), and
the per-async-context COW model already gives a clean isolation boundary — each
fan-out instance / parallel branch has its own mapping copy, so updating "this
context's own open spans" is well-defined and leak-free. Leaving it a SHOULD
means a conformant implementation can legitimately decline (the v0.10.0 Python
implementation did), which in turn blocks fixtures 029 / 030 — they assert the
open-span update, but a conformant impl need not perform it, so they are not
universally passable. Tightening to MUST closes that gap.

### Why a MUST and not a stronger SHOULD

The open-span update is universally implementable on the backends the spec
currently maps: OTel exposes `set_attribute` on a live span, and the Langfuse
SDK exposes observation- and trace-level `update`. The conditioning clause
("where the backend SDK supports in-place update") preserves correctness for a
hypothetical future backend whose SDK cannot mutate an open observation — such
a backend is not forced to do the impossible — but for every backend specified
today, in-place update is available, so the practical effect of the MUST is
universal. A SHOULD that every mapped backend can satisfy, yet which a
conformance fixture depends on, is the worst of both: the behavior is expected
in tests but optional in prose.

## Design

The proposed normative text is reproduced below.

Anticipated bump: **MINOR**. The change tightens a SHOULD to a MUST (a behavior
that an implementation relying on the SHOULD was free to omit becomes required)
and adds a delivery-queue event kind; pre-1.0 this lands in a MINOR. The
concrete spec version is assigned at acceptance.

### observability §3.4 — *Mid-invocation augmentation* (revised open-span clause)

The §3.4 subsection's "**Mid-invocation augmentation**" paragraph ends with a
three-part bullet describing the helper's effect on spans. The final sub-bullet
(currently the SHOULD) is replaced. The first two effects (forward flow,
closed-span boundary) are restated unchanged for context; the open-span effect
is split into the MUST and an explicit boundary.

The helper:

- Performs an additive merge into the current async context's metadata.
  Existing keys with the same name are overwritten; other keys are preserved.
  *(unchanged)*
- Validates added keys against the reserved-namespace rule (`openarmature.*`,
  `gen_ai.*`) and the value-type contract above. Violations MUST raise at the
  call site, before any downstream span emission picks up the partially-applied
  state. *(unchanged)*
- **Forward flow.** Spans emitted after the call returns carry the additions
  via normal propagation through the async context. *(unchanged)*
- **Closed spans.** Spans already closed are NOT retroactively updated.
  *(unchanged)*
- **Open spans in the augmenting context (MUST).** Spans that are still open at
  the time of the call AND were opened from the augmenting async context (or
  from an open descendant context that shares the mutated mapping copy) MUST be
  updated in place, where the backend SDK supports in-place attribute /
  metadata update (OTel `set_attribute`; Langfuse observation / trace
  `update`). The *augmenting async context* is the copy-on-write context (per
  the *Per-async-context scoping* paragraph below) in which
  `set_invocation_metadata` executed:
    - For a call in the **outermost serial flow**, the augmenting context's own
      open spans include the **invocation span** and the **calling node's
      span**.
    - For a call **inside a fan-out instance or parallel branch**, they include
      that instance's / branch's **dispatch span** and any **inner node span**
      open beneath it — but NOT the shared parent or invocation span (see the
      boundary below).
  The augmented metadata is thereby visible end-to-end across the spans that
  represent the augmenting work, not only on spans opened afterward.
- **Ancestor / sibling boundary (MUST NOT).** Spans opened in an **ancestor**
  async context (e.g., relative to a fan-out instance's augmentation: the
  invocation span and the shared fan-out-node span) or in a **sibling** context
  (another fan-out instance, another parallel branch) MUST NOT be updated by
  that augmentation. Updating them would re-introduce the cross-context
  metadata leakage the per-async-context COW scoping forbids — the whole point
  of the per-instance isolation is that instance A's `productId` reaches A's own
  spans and nothing else.

The existing **Per-async-context scoping** paragraph is unchanged; this clause
makes explicit that in-place open-span updates honor the same boundary as
copy-on-write forward propagation.

### observability §6 — *Reflecting mid-invocation augmentation on open spans* (new subsection)

Added after the existing §6 lifecycle-driver subsections (observer-driven /
middleware-driven), before *Log correlation* (§7):

> §3.4 requires (MUST) that open spans in the augmenting async context pick up
> entries added mid-invocation by `set_invocation_metadata`. For the
> observer-driven lifecycle (the RECOMMENDED driver above) this needs a
> notification path: observers run on the §6 serial delivery queue, not in the
> node body's call stack, so they do not observe the `set_invocation_metadata`
> call directly and cannot read the node context's mapping copy.
>
> **Recommended mechanism — augmentation event on the delivery queue.** When
> `set_invocation_metadata` adds entries mid-invocation, the framework SHOULD
> enqueue a framework-emitted **metadata-augmentation event** onto the same
> strictly-serial observer delivery queue that carries node-boundary `started`
> / `completed` events (graph-engine §6). The event carries:
>
> - the added `(key, value)` entries (post-validation), and
> - the originating lineage identity — `namespace`, `attempt_index`,
>   `fan_out_index`, `branch_name` — sufficient for an observer to scope the
>   update to the augmenting async context's own open spans.
>
> Routing the augmentation through the serial queue, rather than mutating
> observer state directly from the node-body task, preserves the strict-serial
> invariant the lifecycle driver relies on (no interleaved mutation of the
> in-flight span stack). Ordering follows naturally: augmentation happens inside
> a node body, so the event is delivered after that node's `started` event
> (the inner span is open) and before its `completed` event (the inner span has
> not yet closed) — the target spans are open when the event arrives.
>
> **Observer behavior.** On a metadata-augmentation event, an observer
> maintaining the in-flight span stack updates, in place, every open span whose
> lineage is within the augmenting context's subtree (its dispatch span and any
> open inner-node spans beneath it), applying the added entries as span
> attributes (OTel) / observation and trace metadata (Langfuse). It MUST NOT
> touch open spans in ancestor or sibling lineages (§3.4). Observers that do not
> maintain metadata-sensitive spans ignore the event.
>
> **Alternative drivers.** As with the `started` / `completed` lifecycle,
> implementations MAY use a different mechanism (e.g., a middleware-driven
> driver that reads the live context when it closes each span, or a backend
> SDK's own context-update hook) provided the resulting spans satisfy §3.4's
> open-span-update contract. The contract is the emitted spans, not the driver
> mechanism.

### graph-engine §6 — observer delivery queue carries augmentation events (clarifying touch)

§6's observer event model defines node-boundary events with a closed `phase`
enumeration (`started` / `completed`). This proposal adds a short note:

> The observer delivery queue MAY also carry **framework-emitted observability
> events that are not node-boundary events** — specifically the
> metadata-augmentation event defined in observability §3.4 / §6, emitted when
> `set_invocation_metadata` adds entries mid-invocation. Such events:
>
> - are delivered in the same strict-serial order as node-boundary events, at
>   the point the augmentation occurs;
> - are distinguished from node-boundary events by **event kind** — an
>   augmentation event is not a node `started` / `completed` and carries no
>   `pre_state` / `post_state` / `error`; the closed `phase` enumeration
>   continues to apply to node-boundary events only;
> - are delivered to every registered observer irrespective of its node-phase
>   subscription (the `phases` filter governs node-boundary phases); observers
>   that do not handle augmentation events ignore them.
>
> graph-engine does not define the augmentation event's semantics or full field
> set beyond delivery ordering and the lineage-identity fields it reuses
> (`namespace`, `attempt_index`, `fan_out_index`, `branch_name`); the semantics
> live in observability §3.4 / §6. This touch only makes explicit that the
> cross-language observer delivery surface carries the event.

## Conformance fixtures

### Existing fixtures corrected (activated by the MUST)

Both fixtures already exist under `spec/observability/conformance/` and are
deferred in implementations pending this proposal. Correcting their expected
trees and the §3.4 SHOULD → MUST tightening is a conformance-expectation
change, which is why it requires a proposal.

- **029-caller-metadata-fan-out-per-instance** — the expected tree currently
  shows, per instance, `instance dispatch span → generation`, omitting the
  inner LLM node's own span. The real span tree (and fixture 032's passing
  precedent, which shows the inner `compute` leaf under each per-instance
  observation) has an inner-node level. Corrected expected tree per instance:

  ```
  fan_out_node span            { tenantId }                 # ancestor context — baseline only
    └─ instance dispatch span  { tenantId, productId }      # augmenting context's own span
         └─ ask inner node span { tenantId, productId }     # augmenting context's own span  [ADDED LEVEL]
              └─ generation     { tenantId, productId }     # opened after augmentation
  ```

  Both the dispatch span and the inner `ask` node span are open at augmentation
  time and live in the instance's own async context, so under the MUST both
  carry the augmented `productId`. The shared `fan_out_node` span (ancestor
  context) continues to carry only the baseline `tenantId`. No sibling
  instance's `productId` appears on any of A's spans (unchanged isolation
  assertion).

- **030-caller-metadata-parallel-branches-per-branch** — same correction:
  insert the inner `ask` node span between each branch's subgraph dispatch span
  and its generation. The inner `ask` span carries the branch's `branchName`;
  the `dispatcher` span (ancestor context) keeps only the baseline `tenantId`.

### New fixture

- **034-caller-metadata-open-span-update-serial** — the outermost-context
  complement to 029 / 030. A single serial graph: one node's body calls
  `set_invocation_metadata(requestId=<value>)` before its LLM call. The harness
  asserts that the **invocation span** AND the **calling node's span** — both
  open at the time of the call, both in the outermost async context — pick up
  `requestId` in place, and that the LLM generation (opened after the call)
  also carries it. This isolates the "augmenting context's own open spans,
  including the invocation span, ARE updated" half of the §3.4 MUST that 029 /
  030 do not exercise (029 / 030 test the complementary "ancestor / sibling
  spans are NOT updated" half).

### Harness conventions

No new top-level harness primitive is required. 029 / 030 already encode the
augmentation point via `augment_metadata_from_field` (fan-out) and
`augment_metadata` (parallel-branches); 034 reuses `augment_metadata` on a
serial node. The harness models the recommended augmentation-event path by
surfacing the augmentation to the observer in serial order at the point it
occurs (between the augmenting node's `started` and `completed` events).

## Versioning

MINOR bump. On acceptance the whole-spec SemVer increments (concrete version
assigned at acceptance):

- Tightens observability §3.4's mid-invocation-augmentation open-span clause
  from SHOULD to MUST, with explicit per-async-context scoping (own context's
  open spans updated; ancestor / sibling spans not).
- Adds an observability §6 subsection describing the recommended
  augmentation-event mechanism and the observer's open-span-update behavior.
- Adds a graph-engine §6 clarifying note that the observer delivery queue
  carries the framework-emitted augmentation event.
- Corrects conformance fixtures 029 and 030 (adds the inner-node span level
  carrying the augmented key) and adds fixture 034.
- No breaking change to caller-facing surfaces: callers that do not call
  `set_invocation_metadata`, and callers whose backend already updated open
  spans, see no behavior change. An implementation that previously declined the
  open-span update (relying on the SHOULD) must now perform it for backends
  whose SDK supports in-place update.

CHANGELOG entry references this proposal.

## Out of scope

- **Retroactive update of closed spans.** The closed-span boundary is
  preserved: a span that has already ended is never re-opened or mutated. The
  augmentation reaches only spans that are still open (in the augmenting
  context) plus spans opened afterward. Backends differ on whether a closed
  observation can be amended; rather than condition on that, the spec keeps the
  clean "open spans only" boundary.
- **Backends without in-place open-span update.** The MUST is conditioned on
  "where the backend SDK supports in-place attribute / metadata update." A
  hypothetical backend whose SDK cannot mutate an open observation is not
  required to perform the update; the augmented entries still reach
  later-opened spans via forward propagation. Every observability backend the
  spec maps today (OTel-attribute backends; Langfuse) supports in-place update.
- **Per-LLM-call metadata override.** Unchanged from 0034's out-of-scope:
  attaching metadata to a single LLM call within a node (rather than to the
  node / instance / branch context) is not addressed; mid-invocation
  augmentation operates at async-context granularity.
- **Exact open-span matching algorithm.** How an observer identifies "the open
  spans in the augmenting context's subtree" (namespace-prefix matching against
  the in-flight span stack, fork-point identification by `fan_out_index` /
  `branch_name`, etc.) is an implementation concern. The spec mandates the
  resulting span attributes, not the matching mechanism.
- **Global ordering of concurrent augmentations.** Concurrent augmentations in
  sibling contexts are isolated by COW and need no cross-context ordering
  guarantee beyond the per-context serial delivery the §6 queue already
  provides. The spec defines no global ordering across instances.

## Open questions

The design decisions are settled in the text above:

- **MUST vs SHOULD** — MUST, conditioned on backend SDK support for in-place
  update (universal across mapped backends today).
- **Scope of "open spans"** — the augmenting async context's own open spans
  (and open descendants sharing the mutated copy); never ancestor or sibling
  spans. This is the per-async-context COW boundary applied to in-place
  updates.
- **Mechanism** — a framework-emitted augmentation event on the serial observer
  delivery queue is the RECOMMENDED mechanism; the open-span-update behavior is
  the MUST. Alternatives that produce the same spans are permitted (mirrors
  §6's observer- vs middleware-driven framing).
- **Event kind vs new phase** — the augmentation event is a distinct event
  kind, not a new node `phase`; it carries no `pre_state` / `post_state` /
  `error` and is not subject to the `phases` subscription filter.
- **029 / 030 tree shape** — the inner LLM node's own span is a real node
  execution (one span per node execution, §4) and must appear; the fixtures
  gain the inner-node level, which carries the augmented key. This matches
  fixture 032's passing inner-leaf precedent.

One verification step belongs at acceptance rather than as an open design
question: diff the corrected 029 / 030 expected trees against the span tree an
observer-driven implementation actually emits for the fan-out / parallel-branch
patterns, to confirm the inner-node level and its child structure match what
the lifecycle driver produces (one span per node execution, generation
parented under the inner LLM node).
