# 0048: Read-Symmetric Invocation Metadata + Queryable Observer Pattern

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-01
- **Accepted:**
- **Targets:** spec/observability/spec.md (§3.4 — extends *Caller-supplied invocation metadata* with a `get_invocation_metadata()` read API symmetric to the existing `set_invocation_metadata()` write API, scoped per-async-context per §3.4's copy-on-write semantics; new §9 *Queryable observer pattern* blessing the convention of observers exposing read methods on the concrete type with explicit lifecycle / async-safety contracts; *Three-channel data-access guidance* sub-section in §9 distinguishing State / invocation-metadata / queryable observer as three distinct read surfaces with different use cases); plus new conformance fixtures covering the read API + per-async-context scoping + queryable observer pattern.
- **Related:** 0034 (caller-supplied invocation metadata — established `set_invocation_metadata()` write API this proposal makes read-symmetric), 0040 (mid-invocation augmentation open-span update — established the §3.4 augmentation mechanism this proposal's reads access), 0045 (nested-lineage augmentation — established the per-depth lineage scoping the read API inherits)
- **Supersedes:**

## Summary

OpenArmature's `set_invocation_metadata()` write API (per observability §3.4,
proposal 0034) lets nodes annotate the in-flight invocation with cross-cutting
attribution data (request IDs, user identifiers, audit-context values). That
data flows to observability backends — Langfuse trace metadata, OTel span
attributes — but **nothing inside the invocation can read it back**. A
downstream "persist" or "summary" node that wants to consume facts an
earlier node wrote has to either round-trip the data through the typed
state schema (often forcing schema pollution for cross-cutting concerns
that don't belong there) or duplicate the write at every consumer site.

Separately, observers attached to a graph today are framed as **write-only
sinks** — they consume events; they don't expose data back to the
pipeline. But the physical pattern of "observer maintains queryable state
+ pipeline node reads it" is widely used in practice (per-node usage
rollup for LLM workloads, per-node latency summaries, per-node error
rates) — implemented as custom observer subclasses with bespoke
`get_X()` methods. The pattern works, but lives in unspecified territory:
downstream is rightly nervous about building on something the spec doesn't
sanction, and no shared convention exists for lifecycle, async-safety, or
when the pattern should be reached for vs. State.

This proposal addresses both gaps with one cross-cutting change:

1. **`get_invocation_metadata()` read API** — extends §3.4 with a
   symmetric read primitive. Returns an immutable mapping snapshot of the
   metadata in the current async context's view, scoped per-async-context
   per §3.4's existing copy-on-write rule (NOT global-flat across the
   invocation). Per-attempt scoping under retry. Silent no-op outside an
   invocation. Reads do NOT emit a `MetadataAugmentationEvent`.

2. **Queryable observer pattern blessing** — new §9 normatively
   sanctions observers exposing read methods on the concrete type
   that pipeline nodes consume at runtime. Read methods MUST be
   query-only (no graph state mutation, no emission to other observers,
   no I/O that could deadlock the event loop). Async-safety contract:
   loose (reads MAY race with concurrent event emission; impls MUST
   ensure read-consistency / no torn views; consumers needing
   post-completion stability gate reads on completion signals
   themselves). Lifecycle: explicit `drop()` only (auto-drop on
   `InvocationCompletedEvent` races with end-of-invocation reads).

3. **Three-channel data-access guidance** — explicit table comparing
   State (canonical typed channel), invocation-metadata (cross-cutting
   key/value attribution), and queryable observer accumulator
   (per-node summary derived from event emissions). Default: prefer
   State. Each channel's narrow carve-out is documented.

The two extensions compose: a downstream node's `persist` step reaches
`get_invocation_metadata()` for cross-cutting attribution AND queries an
attached `LlmUsageAccumulator` (or other queryable observer) for per-node
summary data. State handles everything pipeline-computational. Three
distinct surfaces, three distinct use cases.

The change is backwards-compatible: existing applications see no
behavioral change; applications opting into the new read surfaces get
predictable in-band data flow for cross-cutting concerns that don't
warrant State schema fields.

## Motivation

Two pressures converge:

**Read symmetry on invocation metadata.** 0034 established the write side
of the cross-cutting attribution channel; downstream pipelines have since
discovered they want to read it back from later nodes in the same
invocation. Today's workarounds are State schema pollution (adding fields
for "current node path", "audit kind", "user attribution" that the
pipeline computation itself doesn't need but the persist node does) or
duplicate writes (every node that needs the data computes it again from
its own inputs). Both have real costs — schema pollution makes the typed
state harder to reason about; duplicate writes spread attribution logic
across nodes that shouldn't own it.

The natural answer is read symmetry: if `set_invocation_metadata()` writes
to a per-invocation channel, `get_invocation_metadata()` should read from
the same channel. The implementation cost is small (the contextvar
mechanism is already in place from 0034); the spec cost is the surface
addition + the scoping rule (per-async-context, not global-flat).

**Queryable observer pattern is widespread but unsanctioned.** Observers
maintaining queryable state is the canonical pattern for
per-node-summary rollups (token usage per node, latency per node, error
rate per node). The current observer spec treats observers as write-only
sinks; the pattern is physically possible but lives outside the spec's
sanctioned surface. Three signals say it deserves blessing:

- **Recurring pattern shape.** Per-node-summary use cases — LLM token
  rollup, latency rollup, retry-count rollup — share the same shape
  (custom observer + read method + pipeline-node consumer). Without
  spec sanction, each downstream re-derives the shape independently;
  with sanction, the convention is shared.
- **State schema friction.** The pattern's main alternative is State
  fields with custom reducers; the reducer shape for per-node-summary
  data is awkward (a `dict[node_name, stats]` accumulator wants
  merge-by-key semantics across fan-out, which today requires
  per-pipeline reducer code rather than a built-in primitive).
- **Read-augmenting framing closes a real door.** Without the spec
  blessing, downstream maintainers worry the pattern might be retroactively
  forbidden in a future spec edit. The blessing + the read-augmenting
  framing ("NOT a replacement for State") settle the question.

The proposal bundles both because they share the data-access narrative —
each is read-side; each documents a narrow carve-out from "prefer
State"; each gives downstream a load-bearing tool that didn't exist
before. The 3-channel guidance lives in this proposal as the canonical
home (the State-vs-metadata text is incomplete without the queryable
observer column, and vice versa).

## Proposed change

### §3.4 *Caller-supplied invocation metadata* — add `get_invocation_metadata()` read API

Extend §3.4 with a new paragraph after the existing *Mid-invocation
augmentation* section:

> **Read access.** The framework MUST expose a per-language symmetric
> read primitive — `get_invocation_metadata()` (Python idiomatic name;
> per-language equivalents follow the same naming convention as
> `set_invocation_metadata()`). The read returns an **immutable mapping
> snapshot** of the metadata visible in the current async context at
> the time of the call.
>
> **Scoping.** Reads are scoped to the current async context's view of
> the metadata mapping — i.e., the contextvar's current value. This
> includes:
>
> - All entries set via `set_invocation_metadata()` in the current
>   async context.
> - All entries set via `set_invocation_metadata()` in any ancestor
>   context that propagated to the current context through dispatch.
> - The original caller-supplied metadata mapping from `invoke()`.
>
> Reads do NOT see entries set in sibling async contexts. Per §3.4's
> *Per-async-context scoping* paragraph, fan-out instance #1's writes
> are isolated to instance #1's copy of the mapping — instance #2's
> reads do not see them. A node reading at the outermost serial
> context (e.g., after fan-out joins) sees only the outermost context's
> view; fan-out instance writes are not visible after the join.
>
> This scoping is the natural consequence of the contextvar's
> copy-on-write semantics from §3.4. Implementations MUST NOT layer a
> separate global aggregator structure to make sibling-instance writes
> visible across the join — the read surface mirrors the write
> surface's scoping exactly.
>
> **Per-attempt scoping.** Under retry middleware (pipeline-utilities
> §6.1), each attempt sees only the metadata set during that attempt
> plus the ancestor / pre-attempt baseline. Writes from a prior attempt
> that subsequently failed do NOT carry over — consistent with
> `set_invocation_metadata()`'s per-attempt scoping in 0040.
>
> **Outside invocation.** Calling `get_invocation_metadata()` outside
> an active invocation returns an empty mapping (silent no-op,
> mirroring `set_invocation_metadata()`'s silent-no-op-outside-scope
> behavior). Implementations MUST NOT raise.
>
> **No observer emission.** Reads do NOT emit a
> `MetadataAugmentationEvent` or any other observer notification — that
> event variant signals mutations to backends, not consumer reads.
>
> **Return type.** The read returns an immutable mapping shape (Python
> `MappingProxyType` or equivalent; TypeScript `Readonly<Record<...>>`
> or equivalent) carrying string keys and `AttributeValue`-typed values
> per §3.4's existing value-type contract. Typed wrappers (e.g., a
> caller-supplied accessor class with strongly-typed field access)
> are out of scope for v1; the snapshot is the spec-normative shape.

### New §9 — *Queryable observer pattern*

Insert a new §9 between §8 (Langfuse mapping) and the existing §9
*Determinism*. The current §9 *Determinism* shifts to §10; the
current §10 *Out of scope* shifts to §11.

```markdown
## 9. Queryable observer pattern

The `Observer` protocol (per graph-engine §6) is intentionally minimal —
a single async callable receiving the event union. **Concrete observer
types MAY expose additional read methods** on the instance attached to
the graph; pipeline nodes MAY hold a reference to the observer they
attached and consume those methods at runtime.

This section describes the pattern's normative constraints. It does NOT
add new abstract surface to the `Observer` protocol itself — the
protocol's single async-callable shape is unchanged. The pattern is a
convention for how concrete observer implementations expose
read-augmenting state to the pipeline.

### 9.1 Read-method contract

Read methods on a queryable observer MUST be:

- **Query-only.** No graph state mutation (the pipeline state is
  managed exclusively by the graph engine; observers MUST NOT modify
  it).
- **No routing side effects.** The observer's read MUST NOT influence
  edge resolution, conditional branching, or node dispatch.
- **No observer-side emission.** Read methods MUST NOT emit events to
  other observers, directly or indirectly. The observer's role in the
  event stream is event consumption (via the `Observer.__call__`
  surface); cross-observer notification would create ordering
  dependencies the spec does not establish.
- **Non-blocking from the event-loop perspective.** Read methods
  SHOULD be local-state accesses (synchronous reads against in-memory
  data the observer accumulated). If a method must perform I/O
  (e.g., a cached remote lookup), it SHOULD use the event loop's
  non-blocking primitives and document the latency expectations so
  callers can decide whether to call from within a node handler.
  The spec does not forbid I/O outright — implementations that
  expose I/O-backed reads accept responsibility for the latency
  envelope.

Queryable observers are a **read-augmenting** convenience for patterns
where pipeline computation depends on cross-cutting data derived from
event emissions (per-node usage summaries, per-node latency rollups,
per-node error counts). They are NOT a replacement for State — see
*Three-channel data-access guidance* (§9.3 below).

### 9.2 Async-safety contract

Read methods on a queryable observer MAY race with concurrent event
emission to the same observer. Implementations MUST ensure the
observer's internal state is **read-consistent** — a read MUST NOT
return a torn or partially-mutated view (no half-updated dictionaries,
no inconsistent counter pairs) — but they MUST NOT guarantee that a
read sees all events emitted up to a particular point in wall-clock
time.

A consumer that needs **post-completion stability** (e.g., a
final-summary node that wants to read after every event for the
invocation has been delivered) MUST gate the read on observing the
invocation's `InvocationCompletedEvent` (per the graph-engine event
contract). Implementations MAY offer stricter guarantees as
concrete-observer features (e.g., a `get_stable_total()` accessor
that blocks until completion); the spec defines the floor.

### 9.3 Three-channel data-access guidance

Pipelines have three distinct read surfaces for data accumulated
across an invocation. Use the right one for the use case:

| Channel | Shape | Use when |
|---|---|---|
| **State** | Typed schema with declared reducers; participates in graph routing; survives checkpoint / resume; canonical mutable data plane | Pipeline computation data; data the next node's behavior depends on; data that needs to round-trip through reducers; data that needs to survive a crash |
| **Invocation metadata** (§3.4) | Untyped per-invocation key/value channel; cross-cutting attribution; per-async-context scoped | Span / trace attributes; user / request IDs; audit context; values that don't belong in the typed schema; cross-cutting attribution consumed by one end-of-invocation node |
| **Queryable observer accumulator** (this section) | Derived summary state on a concrete observer instance; queried via read methods at runtime | Per-node summaries derived from event emissions (usage tokens per node, latency per node, retry count per node); when adding the summary as a State field would force reducer-shape pollution |

**Default: prefer State.** State is the canonical mutable data channel
for pipeline computation. Invocation metadata and queryable observer
accumulators are narrow carve-outs.

**Invocation metadata** is the right answer when:

- The data is cross-cutting attribution (user, request, audit context),
- Adding the data as a State field would be schema pollution AND
- The data doesn't need reducer semantics AND
- The data doesn't survive across invocations.

**Queryable observer accumulator** is the right answer when:

- The data is a derived summary (counts, sums, ratios) over event
  emissions, not raw input,
- Adding the summary as a State field would force schema pollution
  (incompatible reducer shapes, fan-out vs non-fan-out asymmetry, etc.),
  AND
- The consuming node is downstream of the event emissions it needs to
  read.

The three channels are independent — a real pipeline may use all
three. A "persist" node at the end of an invocation might read its
canonical computation results from State, its user attribution from
invocation metadata, and its per-LLM-call token rollup from a
queryable accumulator. The shapes are different; the data lifetimes
are different; the spec carves out each lane explicitly to keep them
from blurring.

### 9.4 Lifecycle

This subsection's rules apply only to queryable observers that
accumulate per-invocation state (e.g., per-node-summary accumulators).
Observers that expose query methods over non-accumulated data
(e.g., a pass-through inspector that returns the latest event seen)
are not subject to the lifecycle rules below.

Accumulating queryable observers MUST NOT auto-drop accumulated state
on `InvocationCompletedEvent` — an end-of-invocation reader (typically
a "persist" or "summary" node running as the final invocation step)
legitimately needs to read the bucket BEFORE the invocation completes,
and `InvocationCompletedEvent` fires at invocation exit. Auto-drop
would race against the read.

Concrete accumulating observers MUST provide an **explicit drop /
cleanup mechanism** — a method that releases the accumulated state
for a given invocation (e.g., `drop(invocation_id)` in Python; per-
language idiomatic equivalents). The consuming node calls drop after
reading. Implementations SHOULD document the cleanup discipline in
the observer's API documentation.

Long-lived accumulators (an observer that survives across many
invocations) accumulate buckets per `invocation_id` until explicitly
dropped — this is a feature (session-scoped accumulators surviving
across resumes) and a cost (memory pressure if drops are missed). The
spec does NOT mandate a maximum retention policy; concrete observers
MAY offer ergonomic safety features (e.g., LRU eviction, TTL-based
cleanup) on top of the spec contract.
```

### Reference implementation note (informative)

This proposal does not specify a concrete queryable observer in spec
terms. Per-language implementations ship reference accumulators (e.g.,
a per-node LLM-usage rollup, a latency rollup) in their observability
packages following this section's contract. The spec defines the
pattern; impls ship the primitives.

## Conformance test impact

### New fixtures

Five new fixtures under `observability/conformance/` (numbers assigned
at acceptance):

1. **`get_invocation_metadata()` reads writes from the same context.**
   A node calls `set_invocation_metadata({"audit_kind": "fraud"})`
   followed by `get_invocation_metadata()`; asserts the returned
   mapping contains `audit_kind: "fraud"`. Verifies the basic write →
   read round-trip in a single async context.

2. **Per-async-context scoping under fan-out.** Fan-out over two
   instances. Instance #0 calls
   `set_invocation_metadata({"item_id": "A"})`; instance #1 calls
   `set_invocation_metadata({"item_id": "B"})` then
   `get_invocation_metadata()`. Asserts instance #1's read shows
   `item_id: "B"` only — NOT `"A"` (sibling-instance writes invisible
   per the COW boundary). Outermost-serial node after the fan-out
   joins reads `get_invocation_metadata()`; asserts neither
   instance's `item_id` write is visible at the outermost context
   (fan-out instance writes are scoped to their instances).

3. **Per-attempt scoping under retry.** A node configured with
   retry middleware writes
   `set_invocation_metadata({"attempt_marker": "first"})` on attempt
   0, then raises a transient error to trigger a retry; on attempt
   1, the node first reads `get_invocation_metadata()` and asserts
   `attempt_marker` is NOT present (per-attempt scoping per 0040),
   then writes `{"attempt_marker": "second"}` and succeeds. Final
   downstream node reads and asserts `attempt_marker: "second"`.

4. **Empty mapping outside invocation.** Calling
   `get_invocation_metadata()` outside an active invocation (e.g.,
   in code that doesn't run inside a graph) returns an empty mapping;
   asserts no exception raised.

5. **Queryable observer pattern.** A custom observer subclass with
   a `get_count()` read method maintains a counter incremented on
   every `NodeEvent` it receives. A downstream node calls
   `get_count()` mid-invocation and reads the value; asserts the
   count matches the expected number of events emitted by that point.
   Verifies the queryable-observer pattern is exercised end-to-end
   (attach → emit → consume) under the §9 contract.

A sixth informative fixture exercises the §9.2 async-safety contract
by triggering a concurrent read + write (a node reads while a
parallel-branch sibling is emitting events to the same observer);
asserts the read returns a consistent (non-torn) view without
guaranteeing event-count completeness. This is an
implementation-defined boundary; the fixture documents the contract
behavior rather than enforcing a strict ordering.

### Unaffected fixtures

All existing observability fixtures (029, 030, 034, etc. — the §3.4
caller-metadata and mid-invocation augmentation fixtures) remain
valid unchanged. The proposal's normative additions are additive: the
write-side mechanism from 0034 / 0040 is preserved; this proposal
adds the read surface and the queryable-observer convention without
modifying existing write semantics.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- New `get_invocation_metadata()` read primitive in §3.4 (additive —
  existing `set_invocation_metadata()` write contract unchanged).
- New §9 *Queryable observer pattern* section (informative-clarifying;
  blesses an existing widely-used pattern without changing the
  Observer protocol surface).
- New three-channel data-access guidance (§9.3) — informative;
  documents the State / invocation-metadata / queryable observer
  carve-outs.
- New conformance fixtures (five required, one informative). Existing
  fixtures unchanged.

The change is backwards-compatible. Existing applications see no
behavioral change; applications opting in get the new read surface
and the queryable observer pattern with documented constraints.

## Alternatives considered

1. **Global-flat read aggregation.** Make
   `get_invocation_metadata()` return every key written anywhere in
   the invocation, including sibling fan-out instance writes that
   would otherwise be isolated by the contextvar's copy-on-write
   semantics. Rejected: the contextvar isolation is load-bearing for
   per-fan-out-instance attribution (the common case "each instance
   adds its own `productId`" works because writes don't leak to
   siblings); breaking that isolation on the read side creates an
   asymmetric "writes are scoped, reads are global" semantic that's
   hard to reason about, AND forces a separate aggregator data
   structure parallel to the contextvar with per-async-context locking
   discipline. The natural impl (contextvar read) gives the
   per-async-context view; consumers that need "every key in the
   invocation" build that on top via observer aggregation or State.

2. **Typed wrapper return type.** Return a strongly-typed accessor
   class instead of a plain mapping. Rejected for v1: typed wrappers
   warrant their own proposal if the use case becomes "I want
   strongly-typed metadata reads" — the demand hasn't surfaced.
   `Mapping[str, AttributeValue]` is the minimal contract; impls MAY
   offer typed conveniences on top (e.g., a `pydantic`-based
   accessor in Python) without binding the spec.

3. **Auto-drop on `InvocationCompletedEvent` for queryable observers.**
   Have the framework automatically clear an accumulator's bucket
   when the invocation completes. Rejected: the race against
   end-of-invocation reads is real — a "persist" node running as the
   last invocation step would lose access to the bucket when the
   invocation completes. Explicit `drop()` puts cleanup responsibility
   on the consumer (who knows when they're done reading), with the
   cost that long-lived accumulators need cleanup discipline.

4. **New abstract `QueryableObserver` Protocol.** Add a typed Protocol
   to graph-engine §6 with abstract read-method requirements
   (`get_state()`, `query(...)`). Rejected: the pattern is too varied
   to constrain to a fixed Protocol shape — different accumulators
   want different read APIs (`get_by_node()`, `get_total()`,
   `get_history()`, etc.). The pattern blessing in §9 is a
   convention; concrete observers ship the specific read methods.

5. **Read methods MAY emit to other observers (cross-observer
   notification).** Allow a queryable observer's read to fire an
   event that another observer consumes (e.g., a "metric finalized"
   event when an accumulator is queried). Rejected: this creates a
   sub-network of observer-to-observer events with ordering
   dependencies the spec doesn't establish. Cross-observer
   notification is the kind of feature that ships as a separate
   capability if ever needed, not as a hidden mode of the queryable
   observer pattern.

6. **Bundle with a typed `LlmCompletionEvent` proposal.** Combine
   this proposal with the typed-LLM-completion-event work to land a
   single observability data-flow refresh. Rejected: the typed
   event surface is conceptually distinct (carving out a specific
   event variant vs. blessing a general pattern); bundling would
   triple the proposal's review burden and entangle two disjoint
   concerns. The typed event lands as a sibling proposal that
   sequences before or after this one (independent of which order
   gets accepted first).

## Open questions

None at draft time. The design choices are settled in the proposal
text above:

- **Read scoping** — per-async-context (mirrors the write-side
  copy-on-write isolation); global-flat aggregation deferred (see
  alternative 1).
- **Return type shape** — immutable `Mapping[str, AttributeValue]`;
  typed wrappers out of scope for v1 (alternative 2).
- **Lifecycle for accumulating observers** — explicit `drop()`
  required; auto-drop on completion rejected (alternative 3).
- **Read-method emission to other observers** — forbidden per §9.1
  (alternative 5).
- **3-channel guidance home** — lives in §9.3 of this proposal as
  the canonical location; the State-vs-metadata and queryable-
  observer columns are mutually-defining.

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **Typed wrapper return type** (alternative 2). `Mapping[str, AttributeValue]`
  is the v1 shape.
- **Global-flat read aggregation** (alternative 1). The per-async-context
  scoping is normative; "every key globally" use cases route to observer
  aggregation or State.
- **Auto-drop on completion** (alternative 3). Explicit `drop()` only.
- **`QueryableObserver` Protocol** (alternative 4). Pattern blessing
  only; no Protocol surface added.
- **Read-side emission to other observers** (alternative 5). MUST NOT
  per §9.1.
- **Specific accumulator implementations.** The proposal blesses the
  pattern; concrete accumulators (e.g., `LlmUsageAccumulator`,
  `LatencyAccumulator`) ship in per-language packages with the
  reference impl in `openarmature-python` per its own roadmap.
- **Cross-observer ordering or dependency rules.** Observers are
  independent consumers of the event stream; this proposal does not
  introduce ordering or dependency semantics between them.
- **Persistent / cross-invocation accumulator state.** A queryable
  observer that retains data across multiple invocations is permitted
  but its persistence model is concrete-observer scope, not spec
  scope.
