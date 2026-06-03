# 0054: Per-Invocation Observer Event Drain

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-02
- **Accepted:**
- **Targets:** spec/graph-engine/spec.md (§6 *Observer hooks* — new `drain_events_for(invocation_id)` primitive as a sibling to the existing process-wide `drain()`, scoping the wait to events tagged with a single invocation; snapshot semantic at call time, reuses the existing `DrainSummary` return shape and timeout discipline); plus new conformance fixtures covering the basic synchronization case, the snapshot semantic (events emitted after the call do not block), the timeout path, and the resume-mints-fresh-invocation-id case from proposal 0039.
- **Related:** 0010 (drain timeout — established the existing `drain()` timeout parameter and `DrainSummary` return shape this proposal extends), 0030 (drain snapshot semantic and timeout-input validation — established the snapshot-at-call-time rule this proposal generalizes to per-invocation scope), 0034 (caller-supplied invocation metadata / `invocation_id` propagation via the contextvar mechanism this proposal scopes against), 0039 (caller-supplied `invocation_id` — established the per-invocation identifier this primitive accepts as scope filter), 0048 (queryable observer pattern — established the accumulator-style observer convention that motivates this primitive by exposing the synchronization race)
- **Supersedes:**

## Summary

Proposal 0048 (queryable observer pattern) blessed the convention of
concrete observers exposing read methods on the instance — pipeline
nodes hold a reference and consume accumulated data at runtime.
The §9.4 lifecycle text mandates explicit `drop()` discipline, but
it does NOT address the synchronization race between observer event
dispatch (asynchronous, runs on a background queue per graph-engine
§6's *Event delivery* contract) and node reads of the accumulator
inside the same invocation.

Concretely: an observer accumulating per-`(invocation_id, node_name)`
data (LLM token totals, retry counts, per-call latency rollups —
the canonical use cases §9.3's *Three-channel data-access guidance*
table names) can have its terminal-node reader (a "persist" or
"summary" node running as the last invocation step) call
`accumulator.pop(invocation_id)` BEFORE the deliver loop has
dispatched the previous LLM call's `completed` event. The
accumulator returns a bucket missing the last record. The persist
node writes incomplete data. The orphaned event lands in a fresh
bucket no consumer ever reads. Silent under-count.

The existing process-wide `graph.drain()` primitive (graph-engine
§6 *Drain*) has the right semantics — wait until observer events
have been delivered — but the wrong scope: it waits on every active
invocation across the whole graph, blocking on sibling invocations
the caller doesn't care about. Inside a node body, the caller
needs to synchronize on just THIS invocation's events.

This proposal adds **`drain_events_for(invocation_id, *, timeout)`**
as a sibling primitive under graph-engine §6 *Observer hooks*. The
function scopes the wait to events tagged with a single
`invocation_id`, snapshots the pending set at call time (so events
emitted after the call do not block return), and returns the same
`DrainSummary` shape the existing `drain()` returns.

The change is additive at the spec level. Existing applications
see no behavioral change; consumers opting into the accumulator
pattern get a normative synchronization primitive that closes the
race.

## Motivation

Three forces converge:

**Proposal 0048 blessed the accumulator pattern at the spec level,
surfacing the race as a normative concern that needs a
synchronization primitive to resolve.** §9 *Queryable observer
pattern* normatively sanctions accumulator-style observers. §9.4 mandates explicit-drop cleanup
discipline. §9.3 names per-node token rollup, latency rollup, and
retry-count rollup as the canonical use cases. None of these can
treat their accumulated data as authoritative without some way to
synchronize on event dispatch — but §9.2's async-safety contract
explicitly says "MUST NOT guarantee that a read sees all events
emitted up to a particular point in wall-clock time." That's the
right floor for the general case (post-completion stability gates
on the invocation's completion signal); but for the
terminal-node-reads-mid-invocation case it leaves an unresolved
gap. This proposal fills the gap with a normative synchronization
primitive callable from inside an active invocation.

**Existing primitives don't fit.** `graph.drain()` (§6 *Drain*)
waits on every active invocation across the graph, which is the
wrong scope for in-invocation synchronization. `asyncio.sleep` /
spin-wait approaches are probabilistic, not synchronous, and
unbounded in the worst case. Per-node primitives like
`drain_until_node_completed(node_name)` don't generalize across
fan-out (a consumer wanting end-of-fan-out usage data needs the
drain to scope to the fan-out parent, not a single inner node).
Side-channel counters wrap the dispatch primitive in user-space
and inherit the same race the primitive has. Tolerating the race
is acceptable when accumulator data is decorative (debug telemetry)
but not when it's load-bearing (anything billing-adjacent,
audit-grade, or persisted as part of the canonical invocation
record).

**Symmetric with the existing §6 *Drain* primitive.** The new
primitive reuses the snapshot semantic (events emitted before the
call vs after, established by proposal 0030 for the existing
`drain()`), reuses the `DrainSummary` return shape (established by
proposal 0010), and reuses the timeout discipline. The only design
choice is the scope filter (process-wide vs per-`invocation_id`).
A reader who understands the existing `drain()` reads the new
primitive's contract correctly with one parameter substitution.

The cost is small (one new public method on the compiled graph
surface; an implementation that already tags every event with its
`invocation_id` per the contextvar propagation from proposal 0034
can derive the per-invocation pending count from existing
plumbing). The operator-UX improvement is the load-bearing payoff
— accumulator-style observers become safe to treat as
authoritative when callers synchronize at the right points.

## Proposed change

### graph-engine §6 — new `drain_events_for` primitive

Add a new sub-paragraph to graph-engine §6 *Observer hooks* (after
the existing *Drain* paragraph block, within §6):

> **Per-invocation drain.** The compiled graph MUST expose a
> `drain_events_for(invocation_id, *, timeout)` operation as a
> sibling to the process-wide `drain()` above. When awaited,
> `drain_events_for` returns once all observer events tagged with
> the supplied `invocation_id` AND emitted up to the moment of the
> call have been delivered to every registered observer, OR once
> the timeout elapses, whichever happens first.
>
> **Scope.** Events are scoped via the `invocation_id` propagated
> through the §3.4 / proposal 0034 contextvar mechanism; the
> framework tags every observer event with the invocation it
> originated under. Events tagged with a different `invocation_id`
> do not affect the drain's completion. Detached subgraphs and
> detached fan-outs (per observability §4.4) inherit the parent
> invocation's identifier (per the *Invocation-scoped, not
> trace-scoped* paragraph of §3.4) and ARE covered by the parent's
> per-invocation drain.
>
> **Snapshot semantic.** The set of events covered by a
> `drain_events_for` call is the set whose events were emitted
> with the matching `invocation_id` AND emitted up to the moment
> the call begins. Events emitted with the matching
> `invocation_id` AFTER the call begins are NOT covered by that
> drain — callers needing delivery guarantees for events emitted
> after their drain call MUST issue another drain. This snapshot
> rule parallels the existing `drain()`'s rule (the set of
> invocations covered is fixed at call time) and exists for the
> same reason: a caller running inside an active invocation
> would otherwise spin indefinitely, because the caller's own
> node body emits a `completed` event AFTER the drain call returns
> (the deliver loop processes that event on the same queue the
> drain is waiting on).
>
> **Timeout.** The `timeout` parameter follows the same discipline
> as the existing `drain()`'s timeout per §6 *Drain* — a
> non-negative duration in seconds, mapped to the host language's
> idiomatic wait-bound type; implementations MUST reject negative
> or `NaN` values at the API boundary with a per-language
> idiomatic error. If `timeout` is omitted or `None`, the drain
> waits indefinitely for the snapshotted set to complete (the same
> existing-behavior default as `drain()`); if supplied:
>
> - the operation MUST return no later than `timeout` seconds
>   after the call begins;
> - any events still queued or in-flight when the timeout is
>   reached are reported as **undelivered** for the purposes of
>   this drain call's summary;
> - workers MUST NOT be cancelled by per-invocation drain timeout
>   (in contrast to `drain()`'s timeout, which cancels at graph
>   shutdown) — the deliver loop continues processing the queue
>   after a per-invocation drain times out, because the graph
>   remains active and other invocations may still be in flight.
>   This is the load-bearing difference between per-invocation
>   drain (synchronization barrier inside a running graph) and
>   process-wide drain (shutdown coordination at lifespan end).
>
> **Return shape.** The operation MUST return the same summary
> shape `drain()` returns — at minimum a count of undelivered
> events and a boolean flag indicating whether the timeout was
> reached, per §6 *Drain*. Implementations MAY provide richer
> detail (per-observer counts, sampled event metadata) following
> the same MAY allowance the existing summary contract permits.
>
> **Idempotent / cheap on already-drained scopes.** Calling
> `drain_events_for` on an invocation whose events have all been
> delivered MUST return immediately with `undelivered = 0` and
> `timeout_reached = False`. This is the common case in
> production where the queue empties faster than the pipeline's
> last few nodes execute.
>
> **Composition with resume.** Per proposal 0039, a resumed
> invocation mints a fresh `invocation_id`. A
> `drain_events_for(resumed_invocation_id, ...)` call scopes to
> the resumed invocation's events only; events tagged with the
> original (pre-resume) invocation_id do not affect this drain.
> This falls out naturally from the per-invocation scoping but
> is called out explicitly to remove ambiguity for callers
> handling resume flows.

### graph-engine §6 *Drain* — cross-reference paragraph

Append a short cross-reference to the existing §6 *Drain* paragraph
block (after the current paragraph defining the process-wide drain
discipline) pointing at the new primitive:

> The process-wide `drain()` above is the right primitive for
> lifespan / shutdown coordination — drain everything before the
> process exits. For per-invocation synchronization (a terminal
> node reading observer-accumulated state per observability §9.4
> before returning, or any similar in-invocation read-after-write
> against an accumulator-style observer), use the
> `drain_events_for(invocation_id, ...)` primitive below — it
> scopes the wait to a single invocation rather than blocking on
> the whole graph's active invocation set.

## Conformance test impact

### New fixtures

Five new fixtures under `graph-engine/conformance/` (numbers assigned
at acceptance):

1. **Basic synchronization.** A graph with one LLM-calling node
   followed by a terminal node. A custom accumulating observer
   records each `openarmature.llm.complete` event into a per-
   invocation bucket. The terminal node calls
   `drain_events_for(invocation_id, timeout=2.0)` then reads the
   accumulator's bucket. Asserts the bucket contains the LLM
   call's record after the drain returns (no race; the drain
   blocked until the event was delivered).

2. **Snapshot semantic.** A graph with multiple LLM calls and a
   terminal node. The terminal node calls `drain_events_for` and
   then emits its own `started` / `completed` events (per
   graph-engine §6's per-node event-pair model). Asserts the
   drain returns without blocking on the terminal node's own
   events — only events emitted before the drain call are covered.
   The terminal node's `completed` event is delivered AFTER the
   drain returns, on the deliver loop's normal schedule.

3. **Timeout path.** A graph configured with a deliberately slow
   observer (sleeps before processing each event, parameterized
   by the harness). The terminal node calls `drain_events_for`
   with a timeout shorter than the observer's processing time.
   Asserts the returned `DrainSummary` has `timeout_reached =
   True` and `undelivered` non-zero; the graph remains usable for
   subsequent invocations (the deliver loop continues processing
   after the timeout; no worker cancellation).

4. **Resume with fresh `invocation_id`.** A graph that suspends
   and resumes (per pipeline-utilities §10.4). The resumed
   invocation mints a fresh `invocation_id` per proposal 0039.
   The terminal node in the resumed invocation calls
   `drain_events_for(state.invocation_id, ...)`. Asserts the
   drain scopes to the resumed invocation's events only — events
   tagged with the original (pre-resume) invocation_id do not
   affect the drain's completion.

5. **Fan-out interaction.** A graph with a fan-out node over
   multiple instances, each running an LLM-calling inner subgraph,
   followed by a downstream persist node at the outermost-serial
   context after the fan-out joins. The accumulating observer
   records each instance's LLM call. The downstream persist node
   calls `drain_events_for(state.invocation_id, ...)` then reads
   the accumulator. Asserts the drain covers events from EVERY
   fan-out instance (not just the most recent one) because all
   instances share the same `invocation_id`; the accumulator's
   bucket after drain contains records from every instance. Locks
   down the per-invocation scope rationale that rejected the
   per-node-scope alternative (per the *Alternatives considered*
   §3 above) — the consumer at the outermost-serial context needs
   the drain to scope to the fan-out parent's invocation, which
   per-invocation scoping handles correctly without the consumer
   having to enumerate inner node names.

### Unaffected fixtures

All existing fixtures continue to pass unchanged. The new
primitive is purely additive at the spec level — existing
applications that don't call `drain_events_for` see no behavioral
change.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- New `drain_events_for(invocation_id, *, timeout)` method on the
  compiled graph surface (additive — existing `drain()` surface
  unchanged).
- Cross-reference paragraph in §6 *Drain* pointing at the new
  primitive (documentary; no behavior change to the existing
  primitive).
- New conformance fixtures (four required). Existing fixtures
  unchanged.

The change is backwards-compatible. Existing pipelines see no
behavioral change; pipelines opting into the accumulator pattern
get a synchronization primitive that closes the race their
terminal-node-reads-mid-invocation case had.

## Alternatives considered

1. **Ambient scope (no `invocation_id` parameter).** Have
   `drain_events_for()` (or whatever the name) read the current
   `invocation_id` from the contextvar implicitly instead of
   accepting it as a parameter. Rejected: while the canonical
   use case (terminal node syncs on accumulator) does have the
   invocation_id in ambient context and would benefit from the
   shorter call site, edge cases exist where a caller outside the
   active invocation's context wants to drain a specific
   invocation's events (test harnesses, monitoring tools holding
   a graph reference). The explicit parameter handles both cases;
   an ambient-scope helper can be added later as a sibling if the
   shorter ergonomics become important.

2. **Different verb than "drain".** The new primitive is more
   accurately a synchronization barrier than a drain — it doesn't
   empty the queue (the queue keeps receiving events from other
   concurrent invocations), it just waits for the snapshotted set
   to be delivered. More accurate verbs include `await_event_delivery`,
   `await_observer_dispatch`, `flush_observers`. Rejected:
   "drain" preserves the vocabulary symmetry with the existing
   process-wide `drain()` primitive. Spec readers who understand
   `drain()` read `drain_events_for` correctly with one
   parameter substitution; introducing a different verb for an
   essentially-symmetric operation costs more in readability than
   the verb-accuracy gains. The existing `drain()` also has the
   wait-for-delivery (not destructive) semantic, so the verb has
   always been used in this sense in OA's vocabulary.

3. **Single-node scope (`drain_until_node_completed(node_name)`).**
   A primitive that drains events emitted by a specific node
   rather than scoped to an entire invocation. Rejected: doesn't
   generalize across fan-out — a consumer that wants
   end-of-fan-out usage data (sum across all instances before a
   downstream persist node runs) needs the drain to scope to the
   fan-out parent's invocation, not a single inner node.
   Per-invocation scope sidesteps the granularity question
   entirely; the consumer always drains the invocation it's
   reading state for.

4. **Tolerate the race (no new primitive).** Document the race
   as a known limitation of the accumulator pattern and tell
   consumers to either accept it (for non-load-bearing telemetry)
   or use State (per §9.3's *Three-channel data-access guidance*
   default-prefer-State recommendation). Rejected: §9 explicitly
   blesses the accumulator pattern for use cases where State is
   the wrong shape (incompatible reducer semantics, fan-out vs
   non-fan-out asymmetry). The pattern needs a synchronization
   primitive to be usable for load-bearing data; without one, the
   §9 blessing is partial.

5. **`asyncio.sleep(N)` or polling.** Probabilistic, not
   synchronous, unbounded worst case. Wrapping a polling loop in
   user-space inherits the same race the underlying primitive
   has. Rejected as a non-solution.

6. **Side-channel "events delivered" counter on the accumulator
   observer.** The observer tracks how many events it has
   received; the consumer polls until the count matches an
   expected value. Rejected: wraps the dispatch primitive in
   user-space without addressing the synchronization gap.
   Doesn't generalize across multiple observers (a graph attaches
   N observers; each has its own counter; the consumer would
   need to drain all of them with consistent semantics).
   Implementing this correctly is essentially re-implementing the
   primitive this proposal adds, in user-space, less reliably.

7. **Wait-until-quiet** (observer tracks event-arrival timestamps;
   consumer waits until N ms have passed since the last event).
   Rejected: adds latency to every drain call (the quiet
   threshold), still probabilistic (a slow observer might trigger
   a false-quiet false-positive), no upper bound on tail-latency
   races.

8. **Spec the snapshot as "events emitted before the timestamp of
   the call" instead of "events emitted before the call begins."**
   Use a wall-clock timestamp as the cut. Rejected: timestamps
   are not the right ordering primitive on an async-dispatched
   event queue — events emitted simultaneously by concurrent node
   bodies could land before or after the timestamp depending on
   scheduling. The "moment of the call" framing is implementation-
   defined as the moment the deliver loop's per-invocation
   pending counter is sampled; events not yet enqueued at sample
   time are simply not in the count. This is the simplest correct
   shape.

## Open questions

None at draft time. The design choices are settled in the proposal
text above:

- **Name** (alternative 2) — `drain_events_for` for vocabulary
  symmetry with the existing process-wide `drain()`.
- **Parameter shape** (alternative 1) — explicit `invocation_id`
  for flexibility; ambient-scope helper can land later if
  ergonomics warrant.
- **Scope granularity** (alternative 3) — per-invocation, not
  per-node; sidesteps fan-out granularity questions.
- **Snapshot semantic** (alternative 8) — events emitted up to
  the moment the call begins, implementation-defined as the
  pending-counter sample point.
- **Worker cancellation behavior** — diverges from `drain()`'s
  shutdown-cancel rule because the graph remains active after a
  per-invocation drain; the deliver loop continues processing
  the queue.
- **Return type** — reuses the existing `DrainSummary` shape; no
  new per-invocation variant.

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **Cross-invocation aggregation.** A primitive that drains
  events across multiple specific invocations (e.g., "drain
  invocations A, B, C"). Out of scope; callers needing multi-
  invocation coordination call `drain_events_for` once per id.
  The simpler shape ships first; a batched variant lands later
  if a use case surfaces.
- **Observer-side acknowledgment.** A mechanism for individual
  observers to explicitly acknowledge per-event delivery (rather
  than the deliver loop's implicit "I dispatched it" rule). Out
  of scope; the existing deliver-loop dispatch contract is the
  delivery boundary. Per-observer ack would be a separate
  capability if downstream demand surfaces.
- **Sync primitives at sub-event granularity** (e.g., wait until
  a specific event field has a specific value). Out of scope;
  this proposal scopes to per-invocation event-set completion,
  not per-event content semantics.
- **Worker cancellation on per-invocation timeout.** The
  process-wide `drain()` cancels workers on timeout to allow
  clean shutdown. The per-invocation drain explicitly does NOT
  cancel workers — the graph remains active and other
  invocations continue. A future proposal MAY add a stricter
  variant if a use case for in-flight cancellation surfaces.
- **Replacing the existing `drain()`.** The process-wide drain
  remains the correct primitive for lifespan / shutdown
  coordination. This proposal adds a per-invocation sibling, not
  a replacement.
