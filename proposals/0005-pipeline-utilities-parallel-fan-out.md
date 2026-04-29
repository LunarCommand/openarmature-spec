# 0005: Pipeline Utilities — Parallel Fan-Out

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-28
- **Accepted:**
- **Targets:**
  - spec/pipeline-utilities/spec.md (depends on proposal 0004; adds new §X "Parallel fan-out")
  - spec/graph-engine/spec.md (modifies §3 Execution model — fan-out concurrency exception; modifies §6 Observer hooks — adds optional `fan_out_index` to node events)
- **Related:** 0001, 0003, 0004
- **Supersedes:**

## Summary

Add a parallel fan-out primitive to pipeline-utilities: a `FanOutNode` that runs a compiled subgraph
(or async callable) once per item in a parent state field, executing instances concurrently up to a
configurable bound, and merging results back into a parent collection field. Default error policy is
fail-fast (cancel siblings on first error); a `partial_failures` mode collects per-item failures
without raising. Updates graph-engine §3 to acknowledge fan-out as the single intentional
concurrency exception, and §6 to attribute observer events to a specific fan-out instance via an
optional `fan_out_index` field.

## Motivation

Concurrent batch processing of N items through the same logic is one of the two most common LLM
pipeline shapes — the other being deterministic single-pass pipelines (already covered by graph-
engine). Examples in the openarmature charter's case studies and the work projects that drive this
proposal:

- Score 200 retrieved documents through the same LLM-grading subgraph; collect all scores.
- Generate per-item summaries for a batch of input rows.
- Run the same agent loop across many user prompts in an evaluation harness.

Today, none of this is expressible inside a graph: graph-engine §3 mandates single-threaded
execution per invocation, and the user's only options are (a) write a synchronous loop that runs
each item serially (correct, but throws away per-item concurrency), (b) hand-roll an `asyncio.gather`
inside a node body (loses the engine's observability, retry, and projection facilities for the
inner work), or (c) use a graph-engine-external batch runner like `asyncio.gather(graph.invoke(s)
for s in inputs)` (works, but loses the parent's surrounding graph context and fan-in semantics).

A first-class fan-out primitive captures the pattern once and lets the rest of the framework see
into it:

- Each fan-out instance gets its own observer events with `namespace` chained through the fan-out
  node name and disambiguated by a per-instance index.
- Per-instance retry middleware (proposal 0004) wraps each instance independently.
- The fan-out node itself can carry middleware (e.g., concurrency limiting via a semaphore-style
  middleware, OTel instrumentation).
- Fan-in is structured: results are merged into a parent collection field via the parent's reducer,
  matching the existing subgraph projection contract.

## Detailed design

This proposal updates two specs. The pipeline-utilities update adds a new `Parallel fan-out`
section to that capability; the graph-engine updates carve out §3's concurrency rule and extend the
§6 event shape.

The spec versions under which these changes land are determined at acceptance time and recorded in
`CHANGELOG.md`.

---

### Pipeline-utilities §X: Parallel fan-out

Append the following section to `spec/pipeline-utilities/spec.md` after the current sections. The
section number is the next available section in the capability spec.

#### X. Parallel fan-out

A **fan-out node** is a special node type that executes a compiled subgraph (or async callable) once
per item in a designated parent state field, with instances running concurrently up to a
configurable bound, and collects per-instance results back into a parent collection field.

Fan-out nodes are the single place in the engine where multiple subgraph executions overlap in time
within a single invocation; everywhere else (graph-engine §3) execution is single-threaded.

##### Configuration

A fan-out node is registered with the following fields:

| Field | Description |
|---|---|
| `name` | The fan-out node's name in the parent graph. |
| `subgraph` | A compiled subgraph or async callable executed once per item. |
| `items_field` | A field name on the parent state. Its value at fan-out entry MUST be a list-typed value. |
| `item_field` | A field name on the subgraph state to which each item is assigned at instance entry. |
| `collect_field` | A field name on the subgraph state whose final value is collected from each instance. |
| `target_field` | A field name on the parent state into which the collected list is merged. |
| `concurrency` | Int, optional. Upper bound on concurrently-running instances. `None` = unbounded; default: `10`. |
| `error_policy` | One of `"fail_fast"` (default) or `"collect"`. See §X.5 below. |
| `inputs` | Optional `Mapping[str, str]` (subgraph_field → parent_field) to copy additional non-per-item parent fields into each instance. Same semantics as graph-engine §2 explicit input mapping. |
| `extra_outputs` | Optional `Mapping[str, str]` (parent_field → subgraph_field) to merge additional non-collected fields back from each instance via the parent's reducer. |

The four mandatory `*_field` references and any `inputs`/`extra_outputs` entries MUST refer to
declared fields on the relevant state schema; compilation MUST fail with category
`mapping_references_undeclared_field` (graph-engine §2) otherwise. The `items_field` MUST be
declared as a list-typed field; otherwise compilation MUST fail with a new category
`fan_out_field_not_list`.

##### X.1 Per-instance projection

At fan-out entry, the engine snapshots the parent state. For each item in the snapshot's
`items_field`, an instance is constructed with:

- `item_field` ← the item value
- For each `(subgraph_field, parent_field)` in `inputs`: subgraph field ← parent field's value at the
  snapshot
- All other subgraph fields ← schema defaults

The instance receives a fresh subgraph state instance, NOT a shared one. Mutations within an
instance do not affect siblings.

Per-item items are assigned in input list order. Each instance is also tagged internally with its
0-based index in the input list (`fan_out_index`); see §6 below.

##### X.2 Concurrent execution

Up to `concurrency` instances execute concurrently. The order in which instances *start* MUST match
input list order; the order in which they *complete* depends on per-instance work. Implementations
MUST use the language's idiomatic async concurrency primitive (Python: `asyncio.TaskGroup` or
`asyncio.Semaphore` + `asyncio.gather`; TypeScript: `Promise.all` with a semaphore wrapper) and MUST
NOT block one instance's progress on another's.

##### X.3 Per-instance fan-in

When an instance completes, the engine extracts:

- `collect_field`'s final value → contributed to the parent's `target_field`
- For each `(parent_field, subgraph_field)` in `extra_outputs`: subgraph field's final value →
  contributed to the parent's named field

Instance contributions are NOT merged into the parent state until ALL instances complete. The fan-
in step then merges all per-instance contributions into the parent state in input list order via
the parent's reducer for the named field. The reducer for `target_field` MUST be a list-extending
reducer (`append` or a user-defined equivalent that concatenates list values); the reducer for any
field named in `extra_outputs` MUST accept the value type the subgraph produces.

The collected list at `target_field` preserves input order (instance 0's value, then instance 1's,
…), independent of completion order.

##### X.4 Item ordering and fan-in determinism

A fan-out node MUST produce the same final state on identical input regardless of per-instance
completion order, given deterministic instance work. The collected `target_field` value is in
input order; `extra_outputs` merges happen via the parent's reducer in input order. This preserves
graph-engine §5 determinism end to end.

##### X.5 Error policy

`error_policy: "fail_fast"` (default):

- The first instance that raises causes the engine to cancel all sibling instances and propagate
  the original exception. Cancellation MUST be cooperative (the language's idiomatic cancellation
  signal: Python `CancelledError`, TypeScript `AbortSignal`); instances MUST be given the opportunity
  to clean up.
- The propagated exception is the offending instance's, wrapped in a `node_exception` per graph-
  engine §4. Recoverable state is the parent state at fan-out entry (the snapshot).
- Sibling cancellations DO NOT produce additional `node_exception` per cancelled instance;
  cancellations are infrastructure, not user-visible errors. Observers MAY see partial events from
  cancelled instances (whatever fired before cancellation propagated).

`error_policy: "collect"`:

- All instances run to completion (whether success or error).
- A successful instance contributes to fan-in normally.
- A failed instance contributes nothing to `target_field` (its slot is OMITTED — input order is
  preserved among successes).
- After all instances complete, fan-in merges successes; the engine then proceeds to the outgoing
  edge.
- Per-instance errors are recorded in a parent state field named by an additional config field
  `errors_field` (default: omitted, meaning errors are silently dropped after their per-instance
  events fire). `errors_field` MUST refer to a declared list-typed field with an extending reducer.

The `collect` policy never raises from the fan-out node itself; no exception is propagated even if
ALL instances fail. Users who need failure thresholds compose this with downstream conditional
edges over the `errors_field`.

##### X.6 Composition with middleware

Per-graph and per-node middleware (proposal 0004) compose with fan-out as follows:

- **Per-graph middleware** wraps the fan-out node *as a single dispatch* — sees the input parent
  state, sees the merged-fan-in partial update on completion. Per-graph middleware does NOT see
  per-instance state.
- **Per-node middleware on the fan-out node itself** wraps the same dispatch; same scope as per-
  graph but applied only to this fan-out.
- **Per-node middleware on the inner subgraph's nodes** wraps each per-instance node call. Retry
  middleware on an inner node retries within that instance only; sibling instances are not
  retried.

This locality matches §6 observer hook composition (graph-engine spec §6, proposal 0003) and §4
middleware subgraph composition (this spec).

---

### Graph-engine §3: Execution model (fan-out concurrency exception)

Replace the current paragraph in graph-engine §3 (after step 5):

> Execution is single-threaded per invocation: one node is active at a time within a given graph
> run. Parallel fan-out is a separate concern addressed by pipeline utilities (future capability),
> not by the base execution model.

with:

> Execution is single-threaded per invocation **except inside a fan-out node** (pipeline-utilities
> §X): one node is active at a time within a given graph run, with the bounded exception that a
> fan-out node may execute multiple subgraph instances concurrently. After a fan-out node
> completes, single-threaded execution resumes for the rest of the parent run.

### Graph-engine §6: Observer hooks (fan-out index attribution)

Add the following field to the §6 Node event shape:

> - `fan_out_index` — optional non-negative integer. Populated only for events from nodes that
>   execute inside a fan-out instance. The 0-based index of this fan-out instance among its
>   siblings (matching the position of the corresponding item in the fan-out's `items_field`).
>   When the same node name appears in multiple fan-out instances, the combination of `namespace`
>   and `fan_out_index` uniquely identifies the executing instance. Absent for events from nodes
>   that are not inside any fan-out instance.

A fan-out node itself produces a single event (when the fan-out completes), with `fan_out_index`
absent. Per-instance events have `fan_out_index` populated.

The §6 invariant `len(parent_states) == len(namespace) - 1` is preserved; fan-out does not extend
`namespace` beyond what subgraph composition already produces. Implementations MUST emit per-
instance events under a deterministic namespace based on the inner subgraph's node structure.

---

## Conformance test impact

Add four new fixtures under `spec/pipeline-utilities/conformance/`. Number ranges are placeholders;
final numbers depend on the order this proposal is accepted relative to 0004.

1. **`Y01-fan-out-basic`** — parent state has `items: list[int] = [1, 2, 3]` and
   `results: Annotated[list[int], append] = []`. Fan-out node runs an inner subgraph that doubles
   the item. Verifies:
   - Three instances run.
   - Final `results == [2, 4, 6]` (input order preserved despite concurrent completion).
   - Observer events for inner-subgraph nodes carry `fan_out_index` 0, 1, 2.
   - Outer execution order shows the fan-out node treated as a single step.

2. **`Y02-fan-out-fail-fast`** — fan-out where instance index 1 raises. Verifies:
   - The fan-out node propagates the exception as `node_exception` per graph-engine §4.
   - Recoverable state matches the pre-fan-out snapshot.
   - Sibling instances are cancelled (their final-state events do NOT fire as
     `post_state`-populated; the events that DO fire from cancelled instances carry the language's
     cancellation marker — Python `CancelledError`).

3. **`Y03-fan-out-collect`** — fan-out with `error_policy: "collect"` and `errors_field`. Two
   instances succeed, one raises. Verifies:
   - Final `target_field` carries the two successful values, in input order, with the failed
     instance's slot omitted.
   - `errors_field` carries the recorded failure.
   - The fan-out node itself does NOT raise; downstream nodes execute normally.

4. **`Y04-fan-out-with-retry-middleware`** — fan-out where each instance has a retry middleware
   wrapping a flaky inner node. Verifies:
   - Each instance retries independently.
   - Sibling instances are not delayed by another instance's retries beyond the concurrency budget.
   - Final state reflects all instances eventually succeeding.

The conformance harness supplies a deterministic mock-flaky-node adapter for fixture Y04;
real-time-dependent jitter is swapped for a fixed sequence.

Add one new fixture to `spec/graph-engine/conformance/` for the §6 update:

5. **`016-observer-fan-out-index`** — graph with a fan-out node; verifies:
   - Per-instance events carry `fan_out_index` matching their input list index.
   - The fan-out node's own completion event has `fan_out_index` absent.
   - Events from nodes outside the fan-out have `fan_out_index` absent.

---

## Alternatives considered

**Do nothing — let users write `asyncio.gather` inside a node body.** Works for ad-hoc cases but
loses the engine's observability, projection, and middleware integration for the inner work.
Per-item events don't appear in the observer stream. Per-instance retry has to be re-coded inside
the node. Rejected because the use case is too central to LLM pipelines (every batch-processing
shape lands here).

**Multiple parallel `add_edge` outputs from a single node.** A node could fan out by declaring
multiple successors; each runs concurrently. Rejected: this conflicts with graph-engine §2's
"each node has exactly one outgoing edge" rule (a deliberate choice to make routing logic
inspectable). Re-litigating that rule is outside scope. Fan-out is a different shape — same logic
N times — and deserves a different primitive.

**Treat fan-out as a higher-order subgraph (a subgraph whose entry node is implicitly a parallel
loop).** Cleaner conceptually but requires a new entry-node concept and changes the graph-engine
§2 model in a non-additive way. Rejected as too invasive for what amounts to a pipeline-utilities
concern.

**Heterogeneous fan-out (different subgraphs per item).** Useful for A/B routing inside a fan-out.
Deferred — uncommon; users can express it today by switching on the item inside a uniform
subgraph.

**Streaming fan-in (downstream nodes see partial results as instances complete).** Useful for
"first N results, cancel rest" patterns. Deferred to a follow-on streaming proposal. The current
fan-in waits for all instances before merging.

**Implicit fan-out via list-typed projections.** A subgraph node whose `inputs` mapping receives a
list-typed parent field could implicitly fan out. Rejected because it conflates explicit-mapping
semantics (graph-engine §2 / proposal 0002) with concurrency semantics, making the user-facing
contract harder to reason about. Explicit `FanOutNode` keeps the two concerns separate.

**Default `concurrency: None` (unbounded).** Rejected — unbounded fan-out hits provider rate limits
hard and tends to OOM on large item lists. The default `10` is a sensible starting bound that
covers most cases without adversarial concurrency. Users who need higher throughput compose with
the rate-limiting capability (future) or override.

**Default `error_policy: "collect"`.** Rejected because silent partial failures are a debugging
nightmare in pipelines; users who want partial-failure semantics opt in explicitly. The default
fail-fast surfaces problems immediately.

**Per-instance independent state including parent-snapshot views.** Currently the parent snapshot
is taken once at fan-out entry and shared. An alternative would let each instance see a "current"
parent state (which would require synchronization). Rejected — instances are independent by
design; shared mutable parent state would require locks and break determinism.

**Bake fan-out into the subgraph projection.** A subgraph could declare itself "fan-outable" and
then `add_subgraph_node` would handle fan-out implicitly. Rejected for the same reasons as the
list-typed-projection alternative: conflates two contracts.

## Open questions

1. **Should `concurrency` accept a function `(state) -> int`?** Useful for dynamic concurrency
   based on parent state (e.g., scale with available API budget). Currently a static int. Defer
   until needed.

2. **Should `error_policy: "collect"` preserve input list slots for failures (with a sentinel) or
   omit them?** Currently spec'd to omit. An alternative is `target_field[i] = None` (or a tagged
   union) for failed instances. Omitting is simpler and matches the "successes only" semantics; the
   `errors_field` carries the failure record with the index. Revisit if implementation feedback
   shows the slot-preservation semantics are needed.

3. **Should fan-out events emit a `fan_out_started` and `fan_out_completed` pair?** Currently the
   fan-out node produces a single observer event (per the graph-engine §6 single-event-per-node
   contract). A pair would make span boundaries cleaner for OTel (proposal 0007). Could be added
   without breaking the §6 contract by emitting both events with `pre_state` only on `started` and
   `post_state` only on `completed`. Defer to 0007's design.

4. **What happens when `items_field` is empty?** The fan-out node executes zero instances; the
   merge step contributes an empty list to `target_field` (the field's prior value is unchanged
   under the `append` reducer). The node still produces a §6 event for itself. Currently spec'd
   implicitly — confirm if this needs an explicit clause.

5. **Should `inputs` on fan-out nodes support the same default-elision rules as graph-engine §2
   ExplicitMapping?** Currently fan-out's `inputs` is described as "same semantics as graph-engine
   §2 explicit input mapping" — meaning subgraph fields not named in `inputs` (other than
   `item_field`) receive their schema defaults, NOT field-name fallback. Confirm this is the
   intended pairing.
