# Graph Engine

Canonical behavioral specification for the OpenArmature graph engine.

- **Capability:** graph-engine
- **Introduced:** spec version 0.1.0
- **History:**
  - created by [proposal 0001](../../proposals/0001-graph-engine-foundation.md)
  - §2 Subgraph extended with explicit input/output mapping by [proposal 0002](../../proposals/0002-subgraph-explicit-mapping.md)
  - §6 Observer hooks promoted from informative to normative by [proposal 0003](../../proposals/0003-node-boundary-observer-hooks.md)
  - §6 Observer hooks gained `attempt_index` field and middleware-dispatched events by [proposal 0004](../../proposals/0004-pipeline-utilities-middleware.md)
  - §3 Execution model carved out a fan-out concurrency exception; §6 Observer hooks replaced single-event-per-attempt with started/completed pairs, added per-observer phase subscription, added `fan_out_index` field, and removed the "Middleware-dispatched events" subsection by [proposal 0005](../../proposals/0005-pipeline-utilities-parallel-fan-out.md)
  - §3 Execution model concurrency exception extended to also cover parallel-branches; §6 Observer hooks gained `branch_name` field and updated event-source uniqueness invariant to include it by [proposal 0011](../../proposals/0011-pipeline-utilities-parallel-branches.md)
  - §6 Observer hooks `drain` operation gained an optional caller-supplied `timeout` parameter and now MUST return a summary (`undelivered_count`, `timeout_reached`, with implementations permitted to add richer detail); under timeout, workers MUST be cancelled and graph state MUST remain usable for subsequent invocations by [proposal 0010](../../proposals/0010-drain-timeout.md)
  - §6 Drain gained two clarifications of implicit rules: the snapshot semantic for "prior invocations" (drain covers workers active at call time; invocations started during the drain are NOT covered), and the MUST-reject rule for negative / NaN timeout inputs (with the error surface per-language idiomatic) by [proposal 0030](../../proposals/0030-drain-snapshot-and-timeout-validation.md)
  - §3 *Execution model* gained a clarifying paragraph noting that `invoke()` accepts an optional caller-supplied metadata mapping (per observability §3.4) alongside the existing `correlation_id` argument and per-language invocation surface by [proposal 0034](../../proposals/0034-caller-supplied-invocation-metadata.md)
  - §6 NodeEvent gained an optional `parallel_branches_config` field (mirroring the existing `fan_out_config` field from proposal 0013), populated on every `started` / `completed` event for a parallel-branches node and carrying the resolved `branch_names`, `branch_count`, `error_policy`, and `parent_node_name` for the observability §5.7 attribute surface by [proposal 0044](../../proposals/0044-parallel-branches-dispatch-span.md)
  - §6 observer event union extended with `LlmCompletionEvent` — the first spec-normatively-typed event variant on the union (alongside `NodeEvent` and the framework-emitted metadata-augmentation event mechanism from proposal 0040). The typed event is dispatched on every LLM call completion that produces a structured response per llm-provider §6, carries 13 typed fields (identity / scoping per the existing event-source identity tuple, outcome data mirroring observability §5.5's attribute surface, plus an OPTIONAL `caller_invocation_metadata` opt-in snapshot field), and is NOT subject to the `phases` subscription filter (matches the metadata-augmentation event's no-phase treatment). Observers filter via type discrimination rather than via sentinel-namespace string match. Failure / streaming events are out of scope for v1; the rendering / mapping concern lives in observability §5.5 by [proposal 0049](../../proposals/0049-typed-llm-completion-event.md)
  - §6 *Observer hooks* gained a per-invocation `drain_events_for(invocation_id, *, timeout)` primitive as a sibling to the existing process-wide `drain`; reuses the snapshot semantic and summary return shape (`undelivered_count`, `timeout_reached`), scopes the wait to events tagged with a single `invocation_id` (per observability §5.1), and diverges from `drain` on worker cancellation (per-invocation drain MUST NOT cancel workers on timeout because the graph remains active). Resolves the synchronization race for the queryable observer pattern (proposal 0048) when a terminal node reads accumulator state mid-invocation by [proposal 0054](../../proposals/0054-per-invocation-event-drain.md)
  - §3 *Execution model* gained an *Invocation outcomes* paragraph classifying `invoke()`'s three return categories (completed, errored, suspended); the *Invocation entry surface* paragraph's `invocation_id` clause split into two cases — fresh id on checkpoint-resume per pipeline-utilities §10.4 (existing rule); reused id on suspension-resume per suspension §7 (new rule). §6 *Node event shape* `phase` field extended with `"suspended"`; new `descriptor` field populated only on `suspended` events carrying the signal descriptor per suspension §4; per-attempt terminal-shape paragraph extended to make `completed` and `suspended` mutually exclusive at the terminal slot (each attempt produces exactly one `started` event followed by exactly one terminal `completed` OR `suspended`). The suspension capability itself defines the suspend operation, signal descriptors, suspended outcome, signal payload merge, resume API, composition with other capabilities, and error categories by [proposal 0021](../../proposals/0021-graph-suspension.md)
  - §3 *Execution model* gained a *Deployment-runtime wrapping* paragraph noting that `invoke()` is the per-call surface the harness capability wraps when an OpenArmature graph runs inside a deployment runtime (HTTP server, event bus, queue worker, CLI repl, etc.); cross-references the abstract contract for inbound dispatch classification, turn-level outcome handling, signal coordination, error categorization at the turn boundary, and the sessioned vs stateless mode distinction by [proposal 0022](../../proposals/0022-harness-contract.md)
  - §6 observer event union extended with two new typed event variants — `EmbeddingEvent` (success) and `EmbeddingFailedEvent` (failure) — paired from launch per the 0049 → 0058 success+failure pairing precedent. Both variants carry the identity / scoping / request-side field set established by `LlmCompletionEvent` post-0057 (with `input_strings` in place of `input_messages` and the embedding-specific runtime-config shape), with capability-appropriate success-side fields (`response_id`, `response_model`, `usage`, `dimensions`, `input_count`) on the success variant and the three failure-specific fields (`error_category`, `error_type`, `error_message`) on the failure variant per the 0058 pattern. Mutual exclusion + exception-flow + dispatch-timing rules mirror the LLM-side pair; the observer-side `disable_provider_payload` privacy flag (renamed by this proposal) gates the rendering boundary identically to its LLM-side counterpart. Existing LlmCompletionEvent / LlmFailedEvent privacy paragraphs updated to reference the renamed flag by [proposal 0059](../../proposals/0059-retrieval-provider-embedding.md)
  - §6 *Node event shape* `branch_name` clarified for the inline-callable parallel-branch form (pipeline-utilities §11.1.1, proposal 0075): a callable branch has no inner nodes, so the branch itself is the event-source unit — one **synthetic** `started` / `completed` pair keyed by `branch_name` (the branch name as a synthetic `node_name` / `namespace`, standing in for the registered-node `node_name`); a `when`-skipped branch (§11.10) emits no events. No new event variant; reuses the existing `branch_name` surface by [proposal 0075](../../proposals/0075-parallel-branches-lightweight-branches.md)
  - §6 observer event union: `LlmCompletionEvent` gained an `output_tool_calls` field — the assistant message's output tool calls (`[{id, name, arguments}]`, typed-event-native form), the output-side counterpart to the tool calls carried within `input_messages`; null / empty when the response had none, complementary to `output_content` (null for a tool-call-only response). Payload-bearing, gated like the other payload fields. It is the source the observability §5.5.1 `openarmature.llm.output.tool_calls` span attribute and §5.5.10 identity projections render from by [proposal 0076](../../proposals/0076-tool-call-request-observability-llm-spans.md)
  - §6 observer event union extended with two paired typed variants — `ToolCallEvent` (success) + `ToolCallFailedEvent` (failure) — for tool *execution* (the caller running a tool the model requested via `output_tool_calls`), per the 0049 → 0058 → 0059 success+failure precedent; plus an opt-in node-body **tool-call instrumentation scope** the caller wraps a single tool execution in (OA observes — emits the terminal event at outcome time and re-raises on failure — it does NOT select, run, retry, or loop tools). Events carry the identity / scoping baseline + `tool_name` / `tool_call_id` (linking to the requesting `LlmCompletionEvent.output_tool_calls` entry, the §5.5.10 `.ids` projection) / `arguments` / `result` (success) and `error_type` + `error_message` (failure — **no `error_category`**, the deliberate departure: arbitrary tool code has no closed llm-provider §7 taxonomy). Event-driven start/complete split carries the scope-entry identity; payload gated observer-side by `disable_provider_payload` (§5.5.4) by [proposal 0063](../../proposals/0063-tool-execution-observability.md)
  - §6 observer event union extended with two new typed event variants — `RerankEvent` (success) and `RerankFailedEvent` (failure) — paired from launch per the 0049 → 0058 success+failure pairing precedent, the rerank sibling to the embedding pair. Both carry the identity / scoping / request-side field set established by `EmbeddingEvent` (with `query` + `documents` in place of `input_strings` and the rerank-specific runtime-config shape), with capability-appropriate success-side fields (`response_id`, `response_model`, `usage`, `result_count`) plus `document_count` / `top_k`, and the three failure-specific fields (`error_category`, `error_type`, `error_message`) on the failure variant. Mutual exclusion + exception-flow + dispatch-timing rules mirror the embedding pair; `query` / `documents` / `request_extras` and the `ScoredDocument.document` result echoes are payload-bearing, gated observer-side by `disable_provider_payload` (§5.5.4) by [proposal 0060](../../proposals/0060-retrieval-provider-rerank.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The graph engine defines how a workflow is structured, how state flows between steps, and how execution
progresses. It is the substrate for both deterministic LLM pipelines and LLM-driven tool-calling agents.

## 2. Concepts

**State.** A typed schema describing the data flowing through a graph. State is a product type (a record with
named, typed fields). Implementations MUST validate state against the schema at graph boundaries (entry, exit)
and SHOULD validate at node boundaries.

**Node.** A named unit of work. A node receives the current state and returns a partial update — a mapping
from field names to new values. Nodes MUST be asynchronous. A node MUST NOT mutate the state object it
received; it returns a new partial update which the engine merges. In languages whose typed-state
representation is effectively immutable (notably Python with Pydantic) this is directly enforceable; in
languages without value-type enforcement (notably TypeScript) implementations SHOULD defend against
accidental mutation via freezing or immutable data structures.

**Edge.** A directed connection between nodes. Edges are one of:

- **Static edge** — always routes from source node to a fixed destination.
- **Conditional edge** — a function of current state that returns the destination node name (or the sentinel
  `END`).

Each node has exactly one outgoing edge. Branching is always expressed via a conditional edge, not by
declaring multiple static edges from the same source.

**END.** An engine-provided sentinel value used as a routing target to halt execution. `END` is a distinct
engine constant, not a reserved node name, so a user node may happen to be named `"END"` without collision.

**Reducer.** A function that merges a node's partial update into the prior state for a given field. Each state
field has exactly one reducer. The default reducer is _last-write-wins_ (the new value replaces the old).
Implementations MUST provide at least the following eight canonical reducers: `last_write_wins`, `append`
(for list-typed fields), `merge` (for mapping-typed fields), `concat_flatten` (for list-typed fields whose
updates are lists of lists — e.g., fan-out target fields collecting list-emitting per-instance values),
`merge_all` (for mapping-typed fields whose updates are lists of mappings — e.g., fan-out target fields
collecting dict-emitting per-instance values), `bounded_append(max_len)` (factory; `append` capped at
`max_len` entries with front-drop on overflow), `dedupe_append(key=None)` (factory; `append` skipping
items whose key already appears in the existing list), and `merge_by_key(key)` (factory; list-of-records
keyed merge — entries with a key matching an existing entry replace the existing entry in place; entries
with novel keys are appended). Users MAY register custom reducers per field.

**`concat_flatten` semantics.** `concat_flatten(prior, update)` returns the concatenation of `prior` with the
one-level flattening of `update`. Both `prior` and `update` MUST be lists, and every element of `update` MUST
itself be a list. Violations raise `ReducerError` per §4 (the engine MUST surface the offending field, the
reducer name, and a root-cause naming the non-list value). Empty `update` is a no-op (returns `prior`
unchanged). Empty sub-lists inside `update` contribute zero elements (the one-to-many fan-out case where an
instance legitimately produces zero records). Implementations MUST NOT auto-detect whether `update` is a list
of lists vs. a flat list — `concat_flatten` is strictly the two-level reducer; callers with mixed-shape
requirements MUST register a custom reducer rather than rely on shape-dependent behavior.

**`merge_all` semantics.** `merge_all(prior, update)` folds the sequence of mappings in `update` into `prior`,
applying the same shallow merge semantics as `merge` (later writes win on key conflict; non-conflicting keys
from `prior` are preserved). For `update = [d_1, d_2, ..., d_n]`, the result is equivalent to applying `merge`
N times sequentially: `merge(merge(...merge(merge(prior, d_1), d_2)...), d_n)`, so within `update`
last-write-wins applies across all N dicts (e.g., if `d_2` and `d_n` both set key `k`, `d_n`'s value wins).
`prior` MUST be a mapping, `update` MUST be a list, and every element of `update` MUST itself be a mapping.
Violations raise `ReducerError` per §4. Empty `update` is a no-op (returns `prior` unchanged). Empty mappings
inside `update` contribute zero keys. Implementations MUST NOT auto-detect whether `update` is a list of
mappings vs. a single mapping — `merge_all` is strictly the list-of-mappings reducer; callers needing both
behaviors on the same field MUST register a custom reducer rather than rely on shape-dependent behavior.

**`bounded_append(max_len)` semantics.** A factory returning a reducer that extends a list with the update's
items and truncates from the front (oldest entries dropped first) if the post-merge length exceeds `max_len`.
`max_len` MUST be a positive integer (≥ 1); a factory call with `max_len ≤ 0` raises
`reducer_configuration_invalid` at field registration time. Behavior: concatenate prior + update, then if
the concatenated list's length exceeds `max_len`, drop entries from the front until the length equals
`max_len`. The bound applies to the post-merge length, not to the update's individual size — an update
larger than `max_len` keeps only the last `max_len` items of the update and the prior list is fully evicted. Both `prior` and `update` MUST be lists;
violations raise `ReducerError` per §4. Empty `update` is a no-op (returns `prior` unchanged) — the bound
applies to merge-time transformations, not as a prior-validation pass; `prior` is returned as-is even if
it somehow already exceeds `max_len` (matching the established `concat_flatten` / `merge_all` empty-update
pattern). Truncation MUST be from the front (oldest-first eviction) for cross-impl consistency; back-drop
is recoverable via a
custom reducer if needed. `bounded_append` is for cases where silent drop of evicted data is acceptable
(recent-events buffers, debug log windows, sliding metric caches); for cases where dropped data must be
summarized or transformed first (the canonical chat-history-with-LLM-summarization shape), use unbounded
`append` plus a separate compaction node or middleware — reducers are pure synchronous functions per the
contract above and cannot perform the IO that real compaction requires.

**`dedupe_append(key=None)` semantics.** A factory returning a reducer that extends a list with items from
the update that are not already present (by key) in the existing list. The `key` parameter is an optional
callable mapping an item to its dedup key; if omitted, the item itself is used as the key (requires hashable
items). Behavior: initialize a seen-keys set from `prior` (preserving `prior` unchanged in the result),
iterate `update` in order, and for each item compute its key — if the key is NOT yet in seen-keys, append
the item to the result and record its key; otherwise skip. Existing items appear before update items;
within each, original order is maintained. Duplicates within the update itself are filtered alongside
matches against `prior` — first occurrence wins (preserves left-to-right precedence consistent with
`append`). The computed key (the item itself when no `key` callable is supplied, or the value returned by
the callable) MUST be hashable; a non-hashable key raises `ReducerError` per §4 at merge time. A `key`
callable that raises on any item propagates as `ReducerError`. The reducer does NOT mutate existing items
(no in-place dedup of `prior`); only the update is filtered.

**`merge_by_key(key)` semantics.** A factory returning a reducer for list-of-records fields. Items in the
update with a key matching an existing item REPLACE the existing item in place; items with novel keys are
appended at the end of the list in the order they appear in the update. The `key` parameter is a required
callable mapping an item to its merge key — the spec does NOT default this; keyed merge without a key
function is meaningless and a factory call with `key=None` raises `reducer_configuration_invalid` at field
registration time. Behavior: build a `key_to_idx` index from `prior` (when `prior` contains duplicate keys,
the index MUST hold the LAST index for each duplicate key — implementations whose native dict construction
uses first-wins semantics MUST iterate explicitly to enforce last-wins); for each item in `update`, if its
key is in the index, replace the prior entry at that index with the update item; otherwise append the
update item to the result and register its key. Existing entry order MUST be preserved (replacements are
in-place); novel entries are appended in update order. Duplicate keys within the update collapse to
last-occurrence-wins (consistent with how dict updates work for repeated keys). Earlier duplicates in
`prior` are preserved in place — the reducer does NOT in-place dedupe existing entries (parallel to
`dedupe_append`'s "no in-place dedup of existing" rule). The value returned by the `key` callable MUST
be hashable (required by the index-build step); a non-hashable return value raises `ReducerError` per §4
at merge time. The `key` callable raising on any item propagates as `ReducerError`. Empty `update` is a
no-op. `merge_by_key` is NOT a substitute for `merge` — `merge`
operates on dict-typed fields with shallow key-value semantics; `merge_by_key` operates on list-of-records
fields with item-key semantics. The qualifier `_by_key` distinguishes the two shapes.

**Subgraph.** A compiled graph used as a node inside another graph. A subgraph executes against its own state
schema and produces a partial update that is merged into the parent's state. The merge uses the same reducer
rules as ordinary nodes — parent reducers, applied to parent fields.

By default, no projection in occurs: the subgraph runs from the initial state defined by its own schema's
field defaults, independent of the parent's current state.

Projection out defaults to **field-name matching**: when the subgraph completes, the values of any subgraph
fields whose names match parent fields are merged into those parent fields via the parent's reducers.
Subgraph fields with no matching parent field are discarded.

**Explicit input/output mapping.** A subgraph-as-node MAY declare an `inputs` mapping, an `outputs` mapping,
or both:

- `inputs`: a mapping from subgraph field name → parent field name. For each entry, the parent field's
  current value is copied to the subgraph's corresponding field at entry. Subgraph fields not named in
  `inputs` receive their schema-declared default — they are NOT filled by field-name matching as a
  fallback.
- `outputs`: a mapping from parent field name → subgraph field name. For each entry, the subgraph's final
  value for the named subgraph field is merged into the corresponding parent field via the parent's
  reducer for that field. Subgraph fields not named in `outputs` are discarded — they do NOT fall through
  to field-name matching.

The two directions are independent: a subgraph-as-node MAY declare `inputs` only, `outputs` only, both, or
neither.

- When `inputs` is absent, the default above applies: no projection in. The subgraph runs from its own
  schema defaults.
- When `inputs` is present, named parent fields are copied to their mapped subgraph fields at entry; all
  other subgraph fields receive their schema-declared defaults.
- When `outputs` is absent, the default above applies: subgraph fields whose names match parent fields are
  merged back via the parent's reducers; non-matching subgraph fields are discarded.
- When `outputs` is present, it **replaces** field-name matching for projection-out: only the
  parent/subgraph field pairs named in `outputs` are merged, via the parent's reducer for the named parent
  field. All other subgraph fields are discarded.

This asymmetry — `inputs` additive, `outputs` replacement — is intentional. It reflects the asymmetry in
the defaults themselves: projection-in is off by default (so `inputs` turns it on for listed fields), while
projection-out is on by default via field-name matching (so `outputs` replaces it to avoid ambiguous mixed
rules).

Compilation MUST fail with category `mapping_references_undeclared_field` if an `inputs` mapping names a
parent field that is not declared in the parent's state schema, or a subgraph field that is not declared in
the subgraph's state schema. The same rule applies symmetrically to `outputs`. Implementations SHOULD
validate at compile time that the types of mapped parent/subgraph field pairs are compatible (per the
language's type system's notion of compatibility); this is SHOULD rather than MUST because type-system
expressiveness varies across languages.

**Compiled graph.** The result of compiling a graph definition. A compiled graph is immutable and executable.
The entry node MUST be declared explicitly by the graph author — there is no implicit "first node added"
default. Compilation MUST fail with a diagnostic error if the graph has: no declared entry node, unreachable
nodes, dangling edges (references to nonexistent nodes), a node with more than one outgoing edge, or a field
with more than one declared reducer.

When reporting a compile-time error, implementations MUST expose one of the following canonical category
identifiers (as an error class, error code, or tagged discriminant, per the language's idiom):

- `no_declared_entry` — no entry node was declared.
- `unreachable_node` — a declared node has no path from the entry.
- `dangling_edge` — an edge references a node name that is not declared.
- `multiple_outgoing_edges` — a node has more than one outgoing edge.
- `conflicting_reducers` — a state field has more than one declared reducer.
- `mapping_references_undeclared_field` — a subgraph-as-node `inputs` or `outputs` mapping names a field
  not declared in the relevant state schema.
- `reducer_configuration_invalid` — a reducer factory was supplied invalid construction parameters
  (e.g., `bounded_append(max_len=0)`, `merge_by_key(key=None)`). Raised at field registration / graph
  compilation time, before any node body runs. Distinct from `conflicting_reducers`, which is about
  the reducer-declaration shape across multiple reducers on the same field; `reducer_configuration_invalid`
  is about parameters supplied to a single reducer factory.

## 3. Execution model

1. Execution begins at the designated **entry** node with the initial state supplied by the caller.
2. The current node's async function is invoked with the current state. Its returned partial update is merged
   into state using each field's reducer.
3. After the merge in step 2 AND the edge evaluation in step 4 both complete, the engine MUST dispatch
   the node event for the just-completed node onto the observer delivery queue per §6. Dispatch
   completes synchronously before the next step 2 begins; observer processing happens asynchronously
   on the delivery queue and does not affect node execution timing. The dispatched event captures the
   node's complete transition: its body's execution, the reducer merge, and the resolution of its
   outgoing edge. If any of those steps fail — because the node raised, a reducer raised, state
   validation failed, the edge function raised (`edge_exception`), or no matching edge was returned
   (`routing_error`) — the engine MUST dispatch the node event (with `error` populated) before the
   failure propagates to the caller.
4. The engine then evaluates the outgoing edge from the current node:

- If static: route to the fixed destination.
- If conditional: invoke the edge function with the **post-update** state — i.e., the state reflecting the
  partial update merged in step 2. The returned value is the destination node name or the `END` sentinel.

5. If the destination is `END`, execution halts and the final state is returned.
6. Otherwise, repeat from step 2 with the destination node.

Execution is single-threaded per invocation **except inside a fan-out node** (pipeline-utilities §9) **or
inside a parallel-branches node** (pipeline-utilities §11): one node is active at a time within a given
graph run, with the bounded exceptions that a fan-out node may execute multiple subgraph instances
concurrently and a parallel-branches node may execute multiple heterogeneous compiled subgraphs
concurrently. After a fan-out or parallel-branches node completes, single-threaded execution resumes for
the rest of the parent run.

**Invocation entry surface.** The `invoke()` operation accepts the initial state, an optional
caller-supplied `correlation_id` (per observability §3.1), an optional caller-supplied
`invocation_id` (per observability §5.1 — used verbatim when supplied, framework-minted as a
UUIDv4 when absent; on a checkpoint-resume call per pipeline-utilities §10.4 the framework
always mints a fresh id and ignores any caller-supplied `invocation_id`; on a suspension-resume
call per suspension §7 the framework loads the suspended invocation's id from the paused record,
reuses it verbatim, and ignores any caller-supplied `invocation_id`), and an optional caller-supplied metadata mapping (per observability
§3.4). The metadata mapping carries arbitrary OTel-attribute-compatible key/value entries that
propagate to every observability backend the implementation emits to. The exact mechanism by
which callers supply these arguments at invoke time is per-language idiomatic (a keyword
argument; a field on an invocation-config record; equivalent); the graph-engine spec does not
prescribe the mechanism. The contracts for how these arguments are validated and propagated
live in the observability spec (§3.1 for `correlation_id`, §5.1 for `invocation_id`, §3.4 for
caller-supplied metadata).

**Invocation outcomes.** `invoke()` returns one of three outcome categories: **completed** (the
graph reached END; the final state is the return value), **errored** (a node raised; per §4 error
semantics), or **suspended** (a node body called `suspend()` per the suspension capability §3;
the engine persisted a paused-invocation record and returned a structured suspended outcome per
suspension §5 distinct from completion or error). The suspended outcome is observable to
attached observers via NodeEvent's new `"suspended"` phase per §6 below. Callers that do not use
the suspension primitive see only completed / errored outcomes.

**Deployment-runtime wrapping.** `invoke()` is the per-call surface that the harness capability
wraps when an OpenArmature graph runs inside a deployment runtime (HTTP server, event bus, queue
worker, CLI repl, etc.). The harness capability defines the abstract contract for inbound
dispatch classification, turn-level outcome handling, signal coordination for suspended
invocations, error categorization at the turn boundary, and the sessioned vs stateless mode
distinction. The graph engine itself stays runtime-neutral — the contract above describes what
`invoke()` does; the harness contract describes how a deployment runtime invokes it.

## 4. Error semantics

- If a node raises, execution halts and the exception propagates to the caller. The partial state at the point
  of failure MUST be recoverable (exposed on the raised error or via a documented accessor).
- If an edge function raises, behavior is identical to a node raising.
- If a reducer raises while merging a node's partial update (e.g., the `append` reducer receives a non-list
  value), the engine MUST raise a distinct `ReducerError` that names the offending field, the reducer, and
  the producing node, and that preserves the original exception as its cause (`__cause__` in Python, `cause`
  in TypeScript). Execution halts; the pre-merge state MUST be recoverable from the error.
- If a conditional edge returns a name that is not a declared node or `END`, the engine MUST raise a routing
  error before invoking any further node. The state at the point of failure MUST be recoverable from the
  error, matching the node-exception contract.
- If state validation fails at a boundary, the engine MUST raise a validation error naming the offending
  field(s).

When reporting a runtime error, implementations MUST expose one of the following canonical category
identifiers (as an error class, error code, or tagged discriminant, per the language's idiom):

- `node_exception` — a node raised. The user's exception propagates; the engine attaches recoverable state.
- `edge_exception` — an edge function raised. Behaves identically to `node_exception`.
- `reducer_error` — a reducer raised while merging. Surface class: `ReducerError` (see earlier bullet).
- `routing_error` — a conditional edge returned a destination that is neither a declared node nor `END`.
- `state_validation_error` — state failed schema validation at a graph boundary.

## 5. Determinism

Given the same initial state, the same node implementations, and the same edge functions, a graph run MUST
produce the same final state and the same observed node-execution order. Nondeterminism introduced by node
implementations (wall-clock time, randomness, external I/O) is out of scope for this guarantee.

## 6. Observer hooks

The compiled graph MUST expose a way to register one or more **observers**. An observer is a function or
callable that receives a **node event** and returns nothing of interest to the engine. Observers inspect
execution as it happens; they MUST NOT alter state, routing, or any other aspect of the graph run.

An implementation MUST support at least two registration modes:

- **Graph-attached.** Observers registered on a compiled graph fire on every invocation of that graph
  until removed.
- **Invocation-scoped.** Observers passed to a single invocation fire only for that invocation.

An implementation MAY provide additional registration modes; these two are the minimum.

Both registration modes accept an optional `phases` parameter — a set of phase strings the observer
subscribes to. See "Per-observer phase subscription" below.

Observers attached to a compiled graph fire whenever that graph runs — whether invoked directly by a
caller or as a subgraph inside a parent. A subgraph's attached observers therefore receive events for the
subgraph's internal nodes during a parent run, in addition to any observers attached to or passed to the
parent.

Observers MUST be asynchronous — the delivery queue awaits each observer to coordinate its completion. In
Python this means `async def` observers; in TypeScript, functions returning `Promise<void>`. An
implementation MAY accept synchronous observers by wrapping them internally, but this specification models
observers as async to keep delivery semantics well-defined.

**Event delivery.** Observer events are delivered asynchronously with respect to graph execution. The
graph's execution loop MUST NOT await observer processing; observer latency MUST NOT affect node execution
timing. Each invocation of the outermost graph has an observer delivery queue that runs concurrently with
graph execution.

The delivery queue MUST be strictly serial across the entire invocation. For a given invocation:

- No two observers receive the same event concurrently.
- No observer receives event e+1 until every observer has finished receiving event e.
- Observers receive each event in the following deterministic order:
  1. Graph-attached observers, outermost graph down to the graph that directly owns the node (within each
     graph, in registration order).
  2. Invocation-scoped observers passed to the outermost `invoke` call, in the order they were passed.

`invoke()` MUST return as soon as graph execution completes, regardless of the state of the observer
delivery queue. Observer processing may continue after `invoke()` returns.

An observer that raises an error MUST NOT interrupt the graph run, MUST NOT prevent other observers from
receiving the same event, and MUST NOT prevent any observer from receiving subsequent events.
Implementations SHOULD report observer errors through a language-idiomatic warning channel (e.g.,
Python's `warnings.warn`, TypeScript's `console.warn`).

**Drain.** The compiled graph MUST expose a `drain` operation that, when awaited, returns once all
observer events produced by prior invocations of this graph have been delivered to every registered
observer, OR once an optional caller-supplied timeout elapses, whichever happens first. Events
produced by subgraphs during an invocation are part of that invocation and are covered by the parent
graph's drain. Callers running in short-lived processes (scripts, serverless functions, CLIs) MUST
use drain to avoid losing observer events that were dispatched but not yet delivered.

The set of invocations covered by a `drain` call is the set whose worker(s) were active at the time
`drain` is invoked. Invocations started after `drain` is called are NOT covered by that drain;
callers needing delivery guarantees for a later invocation MUST call `drain` again after the later
invocation begins. The snapshot semantic composes cleanly with the optional `timeout`: the deadline
applies to a known finite set of workers captured at call time, rather than an open-ended set that
new invocations could extend past the deadline.

The `drain` operation MUST accept an optional **timeout** parameter (interpreted as a non-negative
duration in seconds, mapped to the host language's idiomatic wait-bound type — for example, Python's
`float` seconds). If the timeout is omitted or `None`, drain waits indefinitely (the existing v0.3.0
behavior). If a timeout is supplied:

- drain MUST return no later than `timeout` seconds after the call begins;
- any observer events still queued or in-flight when the timeout is reached are considered
  **undelivered** for the purposes of this invocation's drain;
- workers MUST be cancelled or otherwise terminated such that the compiled graph remains usable for
  subsequent invocations — partial delivery state from one drain MUST NOT leak into the next
  invocation;
- observers SHOULD be written to be cancellation-safe (idempotent writes, try/finally cleanup) so
  that interruption by drain timeout does not leave partial side effects in an inconsistent state;
- implementations MUST reject negative or `NaN` timeout inputs by raising an API-boundary error
  before any drain work begins. The error surface is per-language idiomatic (e.g., a Python
  `ValueError`, a TypeScript `RangeError`, a Go error return value); the spec mandates the
  rejection, not the error type. Non-numeric input is rejected per the language's type-error idiom
  (e.g., a Python `TypeError` from the underlying comparison or validation);

drain MUST return a summary of the drain's outcome, in a form appropriate to the host language. The
summary MUST include at least: the count of undelivered events, and a boolean or equivalent flag
indicating whether the timeout was reached. Implementations MAY provide richer detail (per-observer
counts, sampled event metadata). When called without a timeout, drain MUST still return a summary;
in that case the undelivered count is `0` and the timeout-reached flag is `false`. Callers receive
a consistent shape regardless of whether they supplied a timeout.

Implementations SHOULD document drain's worst-case duration in the presence of slow observers and
SHOULD recommend setting a timeout in short-lived process contexts (CLIs, scripts, serverless
functions).

The process-wide `drain` above is the right primitive for lifespan / shutdown coordination — drain
everything before the process exits. For per-invocation synchronization (a terminal node reading
observer-accumulated state per the observability §9.1 read-method contract before returning, or any
similar in-invocation read-after-write against an accumulator-style observer), use the
`drain_events_for(invocation_id, ...)` primitive below — it scopes the wait to a single invocation
rather than blocking on the whole graph's active invocation set.

**Per-invocation drain.** The compiled graph MUST expose a
`drain_events_for(invocation_id, *, timeout)` operation as a sibling to the process-wide `drain`
above. When awaited, `drain_events_for` returns once all observer events tagged with the supplied
`invocation_id` AND emitted up to the moment of the call have been delivered to every registered
observer, OR once the timeout elapses, whichever happens first.

Events are scoped via the `invocation_id` defined in observability §5.1; implementations MUST tag
every observer event with the `invocation_id` of the invocation that emitted it. Events tagged with
a different `invocation_id` do not affect the drain's completion. Detached subgraphs and detached
fan-outs (per observability §4.4) inherit the parent invocation's identifier (per the
*Invocation-scoped, not trace-scoped* paragraph of observability §3.4) and ARE covered by the
parent's per-invocation drain.

The set of events covered by a `drain_events_for` call is the set of events tagged with the matching
`invocation_id` AND emitted up to the moment the call begins. Events emitted with the
matching `invocation_id` AFTER the call begins are NOT covered by that drain — callers needing
delivery guarantees for events emitted after their drain call MUST issue another drain. This
snapshot rule parallels the existing `drain`'s rule (the set of invocations covered is fixed at call
time) and exists for the same reason: a caller running inside an active invocation would otherwise
spin indefinitely, because the caller's own node body emits a `completed` event AFTER the drain call
returns (the deliver loop processes that event on the same queue the drain is waiting on).

The `timeout` parameter follows the same discipline as the existing `drain`'s timeout above — a
non-negative duration in seconds, mapped to the host language's idiomatic wait-bound type;
implementations MUST reject negative or `NaN` values at the API boundary with a per-language
idiomatic error. If `timeout` is omitted or `None`, the drain waits indefinitely for the snapshotted
set to complete (the same default as `drain`); if supplied:

- the operation MUST return no later than `timeout` seconds after the call begins;
- any events still queued or in-flight when the timeout is reached are reported as **undelivered**
  for the purposes of this drain call's summary;
- workers MUST NOT be cancelled by per-invocation drain timeout (in contrast to `drain`'s timeout,
  which cancels at graph shutdown) — the deliver loop continues processing the queue after a
  per-invocation drain times out, because the graph remains active and other invocations may still
  be in flight. This is the load-bearing difference between per-invocation drain (synchronization
  barrier inside a running graph) and process-wide drain (shutdown coordination at lifespan end).

`drain_events_for` MUST return the same summary shape `drain` returns — at minimum a count of
undelivered events and a boolean flag indicating whether the timeout was reached. Implementations
MAY provide richer detail (per-observer counts, sampled event metadata) following the same MAY
allowance the existing summary contract permits.

Calling `drain_events_for` on an invocation whose events have all been delivered MUST return
immediately with `undelivered_count == 0` and `timeout_reached == false`. This is the common case in
production where the queue empties faster than the pipeline's last few nodes execute.

Per the resume-mints-fresh-id rule in §3 *Invocation entry surface*, a resumed invocation mints a
fresh `invocation_id`. A `drain_events_for(resumed_invocation_id, ...)` call scopes to the resumed
invocation's events only; events tagged with the original (pre-resume) invocation_id do not affect
this drain. This falls out naturally from the per-invocation scoping but is called out explicitly
to remove ambiguity for callers handling resume flows.

Implementations MAY provide APIs to add or remove registered observers. Any change to the set of
registered observers during a graph run MUST NOT take effect until the next invocation — the set of
observers receiving events for an in-flight invocation is fixed at the point the invocation begins.

**Node event shape.** A *node* event — the `started` / `completed` pair below, as distinct from the
framework-emitted augmentation events described under *Framework-emitted augmentation events* later in
this section, which carry no `phase` — carries the following fields:

- `phase` — required, one of `"started"`, `"completed"`, or `"suspended"`. `started` events are
  dispatched before the node executes (after middleware pre-phases; right before the wrapped function
  call). `completed` events are dispatched after the node returns or raises and the reducer merge
  runs (or after the failure is captured, on failure). `suspended` events are dispatched when the
  node body calls `suspend()` per the suspension capability §3 — the engine emits `suspended` in
  place of `completed` for that attempt and returns from `invoke()` with a suspended outcome (per
  §3 *Invocation outcomes* above). Each node attempt produces exactly one `started` event followed
  by exactly one terminal event — either `completed` OR `suspended` — in that order; the two
  terminal phases (`completed` and `suspended`) are mutually exclusive within any given attempt.
- `node_name` — the name under which this node was registered in its immediate containing graph.
- `namespace` — an ordered sequence of node names identifying the execution path from the outermost graph
  down to this node. For a node in the outermost graph, `namespace` is `[node_name]`. For a node inside a
  subgraph, `namespace` is the chain of outer subgraph-node names followed by the inner node name. Nested
  subgraphs extend the chain. Implementations MUST NOT represent the namespace as a delimiter-joined
  string at the specification boundary — the sequence form is required so that node names may contain any
  characters without parsing ambiguity.
- `step` — a monotonically increasing non-negative integer, starting at `0`, counting node executions
  within a single invocation of the outermost graph. Subgraph-internal node executions increment the same
  counter.
- `pre_state` — the state the node received, before the reducer merge. For a node in the outermost
  graph, this is the outermost state. For a node inside a subgraph, this is the subgraph's state — the
  state the inner node actually received. State shape therefore varies with `namespace`.
- `post_state` — the state after the node's partial update merged successfully via reducers. Populated
  only when the node executed to completion without raising and the merge did not raise. Same
  shape-varies-with-namespace rule as `pre_state`.
- `error` — the error category identifier from §4 (e.g., `node_exception`, `reducer_error`) together with
  the raised error instance. Populated only when the node event corresponds to a failed node execution.
- `descriptor` — the signal descriptor attached at suspend time (per suspension §4). Populated only
  on events whose `phase == "suspended"`; absent on `started` and `completed` events. Carries the
  caller-supplied `signal_id` plus the optional application-typed `metadata`. Observers consuming
  this field see what the invocation is waiting for at the moment it suspended.
- `parent_states` — an ordered sequence of state snapshots, one per containing graph, outermost first.
  For a node in the outermost graph, `parent_states` is empty. For a node inside a subgraph,
  `parent_states[0]` is the outermost graph's state, `parent_states[1]` is the next-inner containing
  graph's state, and so on; the last entry is the immediate parent's state. The invariant
  `len(parent_states) == len(namespace) - 1` MUST hold.
- `attempt_index` — non-negative integer, default `0`. The 0-based index of this attempt among any
  retries of the same node within a single invocation. `attempt_index` increments per attempt
  (`0` for the first, `1` for the second, and so on through the final attempt) for nodes whose
  execution is wrapped by retry middleware that re-attempts execution — including both **direct**
  wrapping (the node's own per-node middleware chain, per pipeline-utilities §6.1) and **transitive**
  wrapping (middleware on a containing subgraph that the node is part of, per pipeline-utilities
  §9.7 instance middleware and §11.7 branch middleware). When a wrapping retry re-invokes a
  containing subgraph, the inner nodes' events MUST emit the wrapping retry's current attempt
  index — the retry counter propagates through the wrapping chain to event emissions from anything
  re-executed as part of the retried unit. For nodes with NO re-attempting middleware anywhere in
  the wrapping chain, `attempt_index` MUST be `0`. When multiple retry middlewares apply to the
  same node — whether by stacking on the per-node middleware chain or by composing direct with
  transitive wrapping — `attempt_index` reflects the **innermost** retry's counter (the retry
  closest to the node in the wrapping chain). Outer retries' attempt counters do NOT propagate
  through inner retry middleware to events below it; the outer counter is internal to the outer
  retry's runtime state and is not surfaced on §6 events from the shadowed node. (Observability
  layers MAY expose outer-retry context via span attributes on synthesized spans for containing
  subgraph / branch / fan-out instance constructs per observability §4's mapping; that is an
  observability-layer concern outside the §6 event shape.) This matches the natural semantics
  of ContextVar-style propagation (innermost set shadows outer); implementations using
  explicit-threading mechanisms SHOULD preserve the same precedence. `attempt_index` is part of
  the **event-source identification tuple** alongside `namespace`, `branch_name`, `fan_out_index`,
  and `phase` — see the `branch_name` and `fan_out_index` entries below for how this tuple
  distinguishes events from the same node name appearing in different fan-out instances or
  branches. Within a single source, `step` orders individual events emitted across multiple
  invocations (e.g., agent-loop iterations of the same node). The §6 invariant
  `len(parent_states) == len(namespace) - 1` is unaffected; `attempt_index` is independent of the
  namespace chain and parent-state list.
- `fan_out_index` — optional non-negative integer. Populated only for events from nodes that execute
  inside a fan-out instance (pipeline-utilities §9). The 0-based index of this fan-out instance among
  its siblings (in `items_field` mode, matching the position of the corresponding item; in `count`
  mode, `0..count-1`). When the same node name appears in multiple fan-out instances, the
  combination of `namespace`, `branch_name`, `fan_out_index`, `attempt_index`, and `phase` uniquely
  identifies the event source. Absent for events from nodes that are not inside any fan-out instance.
- `branch_name` — optional non-empty string. Populated only for events from nodes that execute inside
  a parallel-branches branch (pipeline-utilities §11). Carries the branch's name as declared in the
  parallel-branches node's `branches` mapping. When the same node name appears in multiple branches'
  subgraphs, the combination of `namespace`, `branch_name`, `fan_out_index`, `attempt_index`, and
  `phase` uniquely identifies the event source. `branch_name` and `fan_out_index` are independent and
  MAY both be present simultaneously when a fan-out node executes inside a parallel-branches branch
  (or a parallel-branches node executes inside a fan-out instance). Absent for events from nodes that
  are not inside any parallel-branches branch. In the uniqueness tuple, an absent field participates
  as a distinct slot: `branch_name = absent` and `branch_name = "alpha"` identify different events;
  the same applies to `fan_out_index`. This matches the convention `fan_out_index` followed
  pre-amendment. For an **inline-callable** parallel branch (pipeline-utilities §11.1.1), which has
  no inner nodes and is not a registered node, the branch itself is the event-source unit: the
  engine emits one **synthetic** `started` / `completed` pair for it, with `node_name` and
  `namespace` set to the branch's name (the `branches`-mapping key) — a synthetic identity standing
  in for the registered-node `node_name` defined above — and `branch_name` carrying the same value.
  A `when`-skipped branch (§11.10) emits no events.
- `fan_out_config` — optional structured value, populated on EVERY `started` and `completed`
  event for a fan-out node (i.e., events whose `node_name` resolves to a fan-out node per
  pipeline-utilities §9), including retried attempts of the fan-out node itself
  (`attempt_index > 0`). Carries the resolved values for the observability §5.4 fan-out
  attributes. Absent (null / None / equivalent) on all events from non-fan-out nodes —
  inner-node events from inside a fan-out instance (those carry `fan_out_index` instead),
  subgraph wrapper events, function-node events whether retried or not, and so on. The value
  carries four fields:
  - `item_count` — non-negative integer. The resolved instance count for this fan-out invocation.
    Equal to `len(items_field_value)` in `items_field` mode and to the resolved `count` in `count`
    mode (per pipeline-utilities §9). Available at fan-out entry, so populated on both `started`
    and `completed` events of the fan-out node.
  - `concurrency` — positive integer or null (unbounded). The resolved concurrency bound for
    this fan-out invocation, after evaluating the int-or-callable from pipeline-utilities §9.
    Matches §9.2's resolved type — zero or negative values are invalid at the configuration
    boundary (raised as `fan_out_invalid_concurrency` per §9.2) and therefore never appear here;
    null indicates unbounded. The `0` sentinel in observability §5.4's
    `openarmature.fan_out.concurrency` attribute is an OTel-attribute-mapping pragmatism (OTel
    primitives can't carry null) and does NOT appear on this canonical field. Available at
    fan-out entry, so populated on both `started` and `completed` events.
  - `error_policy` — string, exactly one of `"fail_fast"` or `"collect"` (per pipeline-utilities
    §9, `error_policy`). Populated on both `started` and `completed` events.
  - `parent_node_name` — string. The fan-out node's own name in the parent graph (i.e., equal to
    `node_name` on this event). Surfaced explicitly so observers and downstream consumers do not
    need to rederive it from `namespace`. Populated on both `started` and `completed` events.

  Implementations MUST present all four keys of `fan_out_config` whenever the field itself is
  populated on a fan-out node event — `item_count`, `concurrency`, `error_policy`, and
  `parent_node_name`. Keys are never individually omitted on the basis of an implementation's
  representation; observers can rely on key presence. Of the four, only `concurrency` is
  nullable (null indicates unbounded per pipeline-utilities §9.2); `item_count`, `error_policy`,
  and `parent_node_name` are always non-null when `fan_out_config` is populated.

  `fan_out_config` MUST be populated on a fan-out node's `completed` event regardless of whether
  the event carries `post_state` or `error` — i.e., even when the fan-out itself raised
  (`fan_out_empty`, `fan_out_invalid_count`, `fan_out_field_not_list`, etc.) at runtime after
  config resolution succeeded, the resolved configuration that was visible at fan-out entry MUST
  appear on the completed event with all four keys populated.

  Behavior in the rare case where engine configuration resolution itself fails (e.g., a
  `concurrency` or `count` callable raises) is implementation-defined for v0.10.0 — whether the
  engine dispatches a fan-out node event pair at all in that case, and if so what shape
  `fan_out_config` takes for partially-resolved configurations, is left to a future proposal.
  Conformance does not depend on this corner: existing fixtures exercise the success path and
  the post-config-resolution runtime-failure paths only.

- `parallel_branches_config` — optional structured value, populated on EVERY `started` and
  `completed` event for a parallel-branches node (i.e., events whose `node_name` resolves to a
  parallel-branches node per pipeline-utilities §11), including retried attempts of the
  parallel-branches node itself (`attempt_index > 0`). Carries the resolved values for the
  observability §5.7 parallel-branches attributes. Absent (null / None / equivalent) on all
  events from non-parallel-branches nodes — inner-node events from inside a parallel-branches
  branch (those carry `branch_name` instead), subgraph wrapper events, fan-out events,
  function-node events, and so on. The value carries four fields:
  - `branch_names` — non-empty ordered sequence of strings. The branch identifiers in
    declaration / dispatch order, as configured on the parallel-branches node (pipeline-
    utilities §11.1). Available at parallel-branches entry, so populated on both `started` and
    `completed` events.
  - `branch_count` — positive integer. The number of branches dispatched. Equals
    `len(branch_names)`; surfaced explicitly so observers and downstream consumers do not need
    to derive it. Populated on both `started` and `completed` events.
  - `error_policy` — string, exactly one of `"fail_fast"` or `"collect"` (per pipeline-utilities
    §11.5). Populated on both `started` and `completed` events.
  - `parent_node_name` — string. The parallel-branches node's own name in the parent graph
    (i.e., equal to `node_name` on this event). Surfaced explicitly so observers and downstream
    consumers do not need to rederive it from `namespace`. Populated on both `started` and
    `completed` events.

  Implementations MUST present all four keys of `parallel_branches_config` whenever the field
  itself is populated on a parallel-branches node event. Keys are never individually omitted on
  the basis of an implementation's representation; observers can rely on key presence.

  `parallel_branches_config` MUST be populated on a parallel-branches node's `completed` event
  regardless of whether the event carries `post_state` or `error` — even when the
  parallel-branches itself raised (e.g., a per-branch error escaping under `fail_fast` per
  §11.5) at runtime after config resolution succeeded, the resolved configuration visible at
  parallel-branches entry MUST appear on the completed event with all four keys populated.

`pre_state` is populated on `started`, `completed`, and `suspended` events (it is the state the node
received, identical across all events of one attempt). `post_state` and `error` are populated only
on `completed` events; exactly one of them MUST be populated on a `completed` event. `started` events
MUST have `post_state`, `error`, and `descriptor` absent. `descriptor` is populated only on
`suspended` events; `post_state` and `error` MUST be absent on `suspended` events. The three
terminal-event shapes (`completed` with `post_state`, `completed` with `error`, `suspended` with
`descriptor`) are mutually exclusive for any given node attempt.

**Parent-state snapshot semantics.** Each entry of `parent_states` is the corresponding containing graph's
state **at the moment that graph entered the subgraph-as-node leading down to this event**. The parent is
not stepping while the subgraph runs, so all node events emitted from a single subgraph run share the
same `parent_states` snapshots. The shape of each entry is the corresponding graph's own state schema —
it is NOT projected, mapped, or otherwise transformed.

**Event dispatch.** Each node attempt produces a started/completed event pair. The engine dispatches
the `started` event before invoking the wrapped node function (after all middleware pre-phases run
per pipeline-utilities §2); the engine dispatches the `completed` event after the reducer merge
succeeds (with `post_state` populated) or after the node, reducer, or state validation fails (with
`error` populated per §4). Both dispatches happen synchronously before the engine proceeds to the
next graph step; neither awaits observer processing.

For a given attempt, the `started` event is delivered to subscribed observers strictly before the
`completed` event for that same attempt.

For nodes wrapped by middleware that re-attempts (e.g., pipeline-utilities §6.1 retry), each attempt
invokes the wrapped node function, which triggers a fresh started/completed pair from the engine. A
3-attempt retry produces 6 events: pairs at `attempt_index` 0, 1, 2 in order. The engine dispatches
all events; middleware does NOT dispatch directly.

`routing_error` and `edge_exception` from §4 are consequences of evaluating an outgoing edge against
a post-update state. Per §3 step 3, the `completed` event fires after edge evaluation completes — so
an edge-resolution failure populates the `error` field of the preceding node's `completed` event.
Edge-resolution failures do NOT produce a separate event pair; they share the preceding node's pair,
and the observer applies its standard §4.2 status-mapping path to surface the error category and
exception details on that node's span (per the observability spec mapping).

**Per-observer phase subscription.** Observer registration (graph-attached or invocation-scoped)
accepts an optional `phases` parameter — a set of phase strings the observer subscribes to.
Accepted values:

- `{"started", "completed"}` — both phases. **Default if `phases` is not specified.**
- `{"completed"}` — only `completed` events. Useful for metrics aggregators, completion-only
  loggers, retry-classification observers.
- `{"started"}` — only `started` events. Useful for stuck-node detectors and "node entered"
  alerting.

Empty phase sets are not permitted; implementations SHOULD raise at registration time.

When delivering events, the engine MUST check the receiving observer's `phases` set before dispatch
to that observer; it MUST NOT deliver an event whose phase is not in the subscribed set. This rule
governs node-boundary events, which carry a `phase`; framework-emitted augmentation events (see
*Framework-emitted augmentation events* below) carry no `phase` and are not subject to the `phases`
filter — they are delivered to every registered observer, which ignores them if it does not handle
augmentation events. Observers
with different phase subscriptions on the same graph or invocation are permitted and common — for
example, an OpenTelemetry observer subscribes to both for span boundaries while a metrics observer
subscribes to `completed` only.

The phase filter applies at delivery, not dispatch — the engine still produces both events for every
attempt; observers that don't subscribe simply don't receive them. This keeps the delivery-queue
invariants and §5 determinism intact regardless of observer mix.

**State immutability.** `pre_state`, `post_state`, and every entry of `parent_states` MUST present the
same immutability contract as state instances flowing through the graph (§2 Node). Attempts by an
observer to mutate any of them MUST fail per the implementation's state-immutability strategy (e.g.,
Python: frozen-instance error).

**Determinism.** Given the same initial state, same node implementations, same edge functions, and same
registered observers, the sequence of events passed to observers MUST be identical across runs. This
extends the §5 determinism guarantee to observer delivery order. Observer side effects (logging, IO)
remain out of scope for this guarantee.

**Framework-emitted augmentation events.** Beyond node-boundary `started` / `completed` pairs, the
observer delivery queue MAY also carry framework-emitted observability events that are not node-boundary
events — specifically the metadata-augmentation event defined in observability §3.4 / §6, emitted when
`set_invocation_metadata` adds entries mid-invocation. An augmentation event is a **distinct event
kind**, delivered to observers via a per-language-idiomatic representation (a discriminated union
carrying an explicit `kind` discriminator, a separate observer callback, equivalent). It carries no
`phase` — the `phase` field and its `started` / `completed` enumeration (per *Node event shape* above)
are properties of node-boundary events only — and none of the node-only fields (`pre_state`,
`post_state`, `error`); it carries the added metadata entries plus the lineage-identity fields it reuses
from the node event (`namespace`, `attempt_index`, `fan_out_index`, `branch_name`). Augmentation events
are delivered in the same strict-serial order as node-boundary events, at the point the augmentation
occurs. Because the `phases` subscription filter governs node-boundary phases, augmentation events are
not subject to it: they are delivered to every registered observer, which ignores them if it does not
handle augmentation events. graph-engine does not define the augmentation event's full semantics beyond
this representation and its delivery ordering; the semantics live in observability §3.4 / §6.

**Typed LLM completion event.** The observer delivery queue also carries a typed `LlmCompletionEvent`
on every LLM call completion that produces a structured response (per llm-provider §6's `Response`
shape). This is the first spec-normatively-typed event variant on the observer event union — observers
filter via type discrimination (`isinstance(event, LlmCompletionEvent)` or per-language idiomatic
equivalent) rather than via a sentinel-namespace string match on `NodeEvent.node_name`. The class name
`LlmCompletionEvent` is normative as an identifier shape; implementations MAY use a per-language
idiomatic name (e.g., adjusted casing or symbol conventions per the language's naming idioms) provided
the field set + dispatch contract are preserved.

The event carries the following typed fields:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. Part of the event-source identity tuple; required for disambiguating sibling fan-out instances. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11, with the resolved `branch_names` per proposal 0044 governing the value space). Null otherwise. Part of the event-source identity tuple; required for disambiguating sibling parallel branches. |
| `provider` | string | The LLM provider identifier (matches `gen_ai.system` per observability §5.5.3). |
| `model` | string | The model identifier the request was made against (matches `gen_ai.request.model` / `openarmature.llm.model` per observability §5.5 / §5.5.3). The provider-returned model identifier — which MAY be more specific — is carried separately on `response_model` below. |
| `response_model` | string \| null | The model identifier the provider returned in the response (matches `gen_ai.response.model` per observability §5.5.3). Distinct from `model` because providers MAY return a more specific identifier than the one requested (e.g., requested `gpt-4o`, response carries `gpt-4o-2024-08-06`). Null when the provider does not return a response model. |
| `response_id` | string \| null | The provider-returned response identifier, when present (matches `gen_ai.response.id` per observability §5.5.3). |
| `usage` | record \| null | Token usage record per llm-provider §6 `Response.usage` shape (including the prefix-cache fields `cached_tokens` and `cache_creation_tokens` per proposal 0047 when populated). May be null when the provider does not report usage. |
| `latency_ms` | float \| null | Wall-clock latency of the LLM call measured at the adapter boundary, in milliseconds. May be null when latency is not measured. Implementations MAY use a provider-reported latency value when the provider surfaces one, documenting which source is in use. |
| `finish_reason` | string \| null | The LLM call's finish reason per llm-provider §6 `Response.finish_reason`. May be null when the call did not complete normally. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field — a snapshot of the caller-supplied invocation metadata (per observability §3.4) at the time of the LLM call, populated only when the observer is configured to include it (per-language opt-in mechanism). Default absent / null; off by default to avoid bloating every event with potentially-large metadata. Consumers wanting a fresh metadata view rather than a snapshot use the `get_invocation_metadata()` read API per observability §3.4. |
| `input_messages` | list of message records | The §3 message list of llm-provider that the call was made with, in the typed-event-native form of the spec's message shape (NOT the JSON-encoded string form observability §5.5.1 emits on the OTel span). Each record carries `{role, content, tool_calls?, tool_call_id?}` per llm-provider §3, including content-block sequences for multimodal messages. Inline image bytes follow the observability §5.5.5 redaction rule (replaced with the redacted placeholder) before population. Populated by the implementation on every typed event; the empty-history case is represented as an empty list, not null. Observer-side privacy gating applies at the rendering boundary per *Privacy and observer-side gating* below. |
| `output_content` | string \| null | The assistant's response content verbatim per llm-provider §6 `Response.message.content`. Null when the response was a tool-call-only assistant message with empty content (the structured-response and tool-call paths are mutually exclusive at the response level, matching observability §5.5.1's framing for `openarmature.llm.output.content`); the output tool calls themselves are carried in `output_tool_calls` below. Same privacy-gating posture as `input_messages`. |
| `output_tool_calls` | list of tool-call records \| null | The assistant message's output `tool_calls` (llm-provider §3 `ToolCall`), in typed-event-native form — each record `{id, name, arguments}` with `arguments` the parsed argument mapping. The output-side counterpart to the tool calls carried per-message within `input_messages`. Null when the response carried no tool calls (the canonical "no tool calls" representation — not an empty list) — complementary to `output_content` (null for a tool-call-only response): together they represent the full assistant output (text and/or tool calls). Carries argument values (payload) — same privacy-gating posture as `input_messages` / `output_content`. The observability §5.5.1 `openarmature.llm.output.tool_calls` span attribute (gated) and the §5.5.10 identity projections render from this field. |
| `request_params` | mapping | The observability §5.5.2 GenAI request-parameter family — `temperature`, `max_tokens`, `top_p`, `seed`, `frequency_penalty`, `presence_penalty`, `stop_sequences`. Keys are the GenAI semconv attribute names without the `gen_ai.request.` prefix (e.g., `temperature`, not `gen_ai.request.temperature`). Values are the per-parameter types observability §5.5.2 specifies (double for `temperature` / `top_p` / `frequency_penalty` / `presence_penalty`, int for `max_tokens` / `seed`, list-of-string for `stop_sequences`). **Absence is meaningful**: the mapping carries only parameters the caller actually supplied — a parameter not in the mapping means "not supplied on this call," distinct from "supplied with a zero value." Empty mapping when no observability §5.5.2 parameters were supplied. |
| `request_extras` | mapping | The `RuntimeConfig` extras pass-through bag per llm-provider §6 — vendor-specific sampling parameters callers supplied as un-declared fields. Values are opaque to the spec; the bag carries whatever the caller supplied, in the typed-event-native mapping form rather than the JSON-encoded string form observability §5.5.1 emits on the OTel span. Same privacy-gating posture as `input_messages`. Empty mapping when no extras were supplied. |
| `active_prompt` | record \| null | A snapshot of the active `Prompt` identity at LLM-call time, sourced from the implementation's prompt-context binding mechanism (the mechanism that drives the `openarmature.prompt.*` span attributes per prompt-management §12 / observability §8.4.4; specific mechanism per-language idiomatic). Fields: `{name, version, label, template_hash, rendered_hash}` matching the prompt-identity attribute family one-for-one. Null when the LLM call ran outside any prompt-context binding (no `openarmature.prompt.*` attributes would have been emitted on the span). |
| `active_prompt_group` | record \| null | A snapshot of the active `PromptGroup` identity at LLM-call time, sourced from the same prompt-context binding mechanism. Fields: `{group_name}` matching the prompt-group attribute family per prompt-management §12 / observability §8.4.4. Null when no group was active. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); implementations MUST mint a fresh identifier per `provider.complete()` call. The value MUST be stable for the call's lifetime and unique within the implementation's run. Wire shape unconstrained — any stable string format works. Distinct from `response_id` (which is the provider-returned identifier and MAY be absent or duplicated across providers); `call_id` is the implementation's own correlation token. |

The event MUST be dispatched on the observer delivery queue at the point of LLM call completion (after
the adapter receives a successful response and before the call returns to the caller). Delivery
semantics follow the *Event delivery* rules above — strict-serial across the invocation,
async-delivered concurrently with graph execution, not blocking the engine's execution loop.

The event is dispatched ONLY for LLM call completions that produce a structured response per
llm-provider §6. Failure cases (provider exceptions, malformed responses) do NOT emit this event
variant; a future `LlmCallFailedEvent` typed variant MAY be added if downstream demand surfaces. The
llm-provider §7 error categories — `provider_invalid_response`, `provider_unavailable`,
`provider_authentication`, etc. — cover failure surfaces through the exception path, not the observer
event surface.

Like the metadata-augmentation event above, `LlmCompletionEvent` carries no `phase` discriminator and
is NOT subject to the `phases` subscription filter. Observers with a `phases={"started"}` or
`phases={"completed"}` subscription still receive `LlmCompletionEvent`; the phases filter applies only
to phase-bearing `NodeEvent` variants. Observers that want to selectively consume the typed event
filter via type discrimination rather than via phase subscription. graph-engine does not define the
event's emission timing semantics beyond this representation and delivery ordering; the rendering /
mapping concern lives in observability §5.5.

**Privacy and observer-side gating.** The `input_messages`, `output_content`, `output_tool_calls`,
and `request_extras` fields carry potentially sensitive payload data. Implementations MUST populate these fields on the
typed event by default; observer-side privacy gating applies at the rendering boundary, matching the
observability §5.5.4 `disable_provider_payload` opt-out flag semantics for the equivalent observability
§5.5.1 span attributes. The OTel observer (per observability §5.5) and the Langfuse observer (per
observability §8) honor their existing `disable_provider_payload` flag on the typed-event rendering path
identically to the §5.5.1 span attribute path.

Custom queryable observers (per observability §9) consuming the typed event are responsible for
their own redaction posture — the §5.5.4 `disable_provider_payload` flag gates OTel + Langfuse
rendering; the typed-event field surface is uniform across observer types. Accumulator authors with
payload-redaction requirements MUST gate at their own rendering / persistence boundary.

Inline image bytes in `input_messages` MUST be redacted per the observability §5.5.5 inline-image
redaction rule before the field is populated, identically to how the observability §5.5.1
`openarmature.llm.input.messages` attribute treats inline images. The hard-rule prohibition on
emitting inline image bytes applies to the typed event field identically.

**Typed LLM failure event.** The observer delivery queue also carries a typed `LlmFailedEvent`
on every LLM provider call that raises one of the llm-provider §7 error categories. A second
spec-normatively-typed event variant on the observer event union, alongside `LlmCompletionEvent` —
observers filter via type discrimination (`isinstance(event, LlmFailedEvent)` or per-language
idiomatic equivalent) rather than via a sentinel-namespace string match. The class name
`LlmFailedEvent` is normative as an identifier shape; implementations MAY use a per-language
idiomatic name provided the field set + dispatch contract are preserved.

The event mirrors `LlmCompletionEvent`'s identity / scoping / request-side field set 1:1, carries
failure-specific fields in place of the success-only response-side fields:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. Part of the event-source identity tuple; required for disambiguating sibling fan-out instances. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11, with the resolved `branch_names` per proposal 0044 governing the value space). Null otherwise. Part of the event-source identity tuple; required for disambiguating sibling parallel branches. |
| `provider` | string | The LLM provider identifier (matches `gen_ai.system` per observability §5.5.3). |
| `model` | string | The model identifier the request was made against (matches `gen_ai.request.model` / `openarmature.llm.model` per observability §5.5 / §5.5.3). |
| `latency_ms` | float \| null | Wall-clock latency from `provider.complete()` entry to the point the failure was raised, in milliseconds. May be null when latency is not measured. Per-attempt under call-level retry. Provider-reported latency rarely applies on failure (no full response received); implementations MAY use a provider-surfaced latency value on the rare error response that includes one, documenting which source is in use. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field — same opt-in semantics as on `LlmCompletionEvent` (per observability §3.4). Default absent / null. |
| `input_messages` | list of message records | The §3 message list of llm-provider that the call was made with, in the typed-event-native form. Populated unconditionally on every typed event; the empty-history case is represented as an empty list, not null. Inline image bytes follow the observability §5.5.5 redaction rule before population. Same observer-side privacy-gating posture as the equivalent field on `LlmCompletionEvent`. |
| `request_params` | mapping | The observability §5.5.2 GenAI request-parameter family. Keys are the GenAI semconv attribute names without the `gen_ai.request.` prefix. Absence-is-meaningful semantics per the equivalent field on `LlmCompletionEvent`. Empty mapping when no observability §5.5.2 parameters were supplied. |
| `request_extras` | mapping | The `RuntimeConfig` extras pass-through bag per llm-provider §6. Same shape and privacy posture as on `LlmCompletionEvent`. Empty mapping when no extras were supplied. |
| `active_prompt` | record \| null | A snapshot of the active `Prompt` identity at LLM-call time, sourced from the implementation's prompt-context binding mechanism. Same fields and nullability as on `LlmCompletionEvent`. |
| `active_prompt_group` | record \| null | A snapshot of the active `PromptGroup` identity at LLM-call time. Same fields and nullability as on `LlmCompletionEvent`. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); freshly minted per `provider.complete()` call. Same contract as on `LlmCompletionEvent` — a failed call gets its own `call_id`, distinct from any retry-attempt sibling. |
| `error_category` | string | The llm-provider §7 normative error category the provider call raised. One of `provider_authentication`, `provider_unavailable`, `provider_invalid_model`, `provider_model_not_loaded`, `provider_rate_limit`, `provider_invalid_response`, `provider_invalid_request`, `provider_unsupported_content_block`, `structured_output_invalid` per the §7 enumeration; new categories added by future llm-provider proposals extend the enum naturally. Always present. |
| `error_type` | string \| null | OPTIONAL impl-level / vendor-specific error type or code (e.g., the upstream exception class name, or a vendor error code like OpenAI's `rate_limit_exceeded` before normalization to `provider_rate_limit`). Provides per-error-source detail beyond the normative category. Null when no impl-side type is available. |
| `error_message` | string | The human-readable error message from the raised exception. Always present (the empty string when the exception carried no message). |

The event MUST be dispatched on the observer delivery queue at the point of LLM call failure (after
the §7 category exception is raised — whether by the provider or by the implementation's pre-send
validation layer per llm-provider §7 — and before the exception propagates to the caller). Delivery
semantics follow the *Event delivery* rules above — strict-serial across the invocation,
async-delivered concurrently with graph execution, not blocking the engine's execution loop.

The event is dispatched ONLY for LLM call failures that raise one of the llm-provider §7 error
categories above. Successful completions emit `LlmCompletionEvent` per the contract above; the two
variants are mutually exclusive on a given `provider.complete()` call. Implementations MUST NOT
emit both `LlmCompletionEvent` and `LlmFailedEvent` for the same call.

**Exception-flow contract preserved.** The §7 category exception still raises out of
`provider.complete()` per llm-provider §7 — whether the category was raised by the provider or by
the implementation's pre-send validation layer; the typed event is dispatched alongside the
exception, not in place of it. Callers handling exceptions see the exception path unchanged;
observers consuming typed events see the failure event on the observer delivery queue. The two
surfaces compose without conflict.

Like the other typed event variants, `LlmFailedEvent` carries no `phase` discriminator and is NOT
subject to the `phases` subscription filter. Observers filter via type discrimination
(`isinstance` or per-language idiomatic equivalent).

The privacy posture for `input_messages` / `request_extras` is identical to
`LlmCompletionEvent`'s — observer-side gating at the rendering boundary per observability §5.5.4
(implementations populate the fields unconditionally; observers honor `disable_provider_payload`).
Inline image bytes in `input_messages` MUST be redacted per the observability §5.5.5 inline-image
redaction rule before population. Custom queryable observers (per observability §9) consuming the
failure variant are responsible for their own redaction posture, identical to the
`LlmCompletionEvent` posture.

**Typed embedding event.** The observer delivery queue also carries a typed `EmbeddingEvent` on
every successful `EmbeddingProvider.embed()` call per the retrieval-provider §3 contract. A third spec-normatively-typed event variant on the observer event union — observers
filter via type discrimination (`isinstance(event, EmbeddingEvent)` or per-language idiomatic
equivalent) rather than via a sentinel-namespace string match. The class name `EmbeddingEvent` is
normative as an identifier shape; implementations MAY use a per-language idiomatic name provided
the field set + dispatch contract are preserved.

The event mirrors `LlmCompletionEvent`'s identity / scoping / request-side field set with
capability-appropriate substitutions (`input_strings` in place of `input_messages`; the
embedding-specific runtime-config in place of the LLM `RuntimeConfig`):

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11, with the resolved `branch_names` per proposal 0044 governing the value space). Null otherwise. |
| `provider` | string | The embedding provider identifier (matches `gen_ai.system` per observability §5.5.3). |
| `model` | string | The model identifier the request was made against. |
| `response_model` | string \| null | The model identifier the provider returned in the response (matches `gen_ai.response.model`). May be more specific than requested; null when the provider doesn't return a response model. |
| `response_id` | string \| null | The provider-returned response identifier when present. |
| `usage` | record \| null | `EmbeddingUsage` record per retrieval-provider §4. May be null when the provider does not report usage. |
| `latency_ms` | float \| null | Wall-clock latency of the embedding call measured at the adapter boundary, in milliseconds. May be null when latency is not measured. Implementations MAY use a provider-reported latency value when the provider surfaces one, documenting which source is in use. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `LlmCompletionEvent` (per observability §3.4). Default absent / null. |
| `input_strings` | list of string | The input strings the embedding call was made with, in the typed-event-native form. Populated unconditionally on every typed event; observer-side privacy gating applies at the rendering boundary per the privacy paragraph below. |
| `request_params` | mapping | Embedding-specific runtime-config fields the caller supplied (initially `dimensions` per retrieval-provider §2). Absence-is-meaningful semantics per the equivalent field on `LlmCompletionEvent`. Empty mapping when no parameters were supplied. |
| `request_extras` | mapping | The embedding runtime config's extras pass-through bag — vendor-specific knobs. Same shape and privacy posture as on `LlmCompletionEvent`. Empty mapping when no extras were supplied. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at embedding-call time (RAG pipelines often render a prompt template before embedding for chat-shaped search). Same field set and nullability as on `LlmCompletionEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape as on `LlmCompletionEvent`. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); freshly minted per `embed()` call. |
| `input_count` | int | The number of input strings the call was made with (equals `len(input_strings)`). Derivable but kept for ergonomics + cross-vendor consistency. |
| `dimensions` | int \| null | The dimensionality of the returned vectors (equals the inner-vector length from the response). May be null when the response does not surface a determinate dimensionality. |

The event MUST be dispatched on the observer delivery queue at the point of `embed()` completion
(after the response is parsed and validated per retrieval-provider §4, before `embed()` returns
to the caller). Delivery semantics follow the *Event delivery* rules above — strict-serial across
the invocation, async-delivered concurrently with graph execution, not blocking the engine's
execution loop. Like the other typed event variants, `EmbeddingEvent` carries no `phase`
discriminator and is NOT subject to the `phases` subscription filter.

**Typed embedding failure event.** The observer delivery queue also carries a typed
`EmbeddingFailedEvent` on every `embed()` call that raises one of the llm-provider §7 error
categories (per retrieval-provider §7's embedding-applicable subset). A fourth spec-normatively-
typed event variant on the observer event union, paired with `EmbeddingEvent` per the 0049 → 0058
success+failure pairing precedent — observers filter via type discrimination
(`isinstance(event, EmbeddingFailedEvent)` or per-language idiomatic equivalent) rather than via
a sentinel-namespace string match.

The event mirrors `EmbeddingEvent`'s identity / scoping / request-side field set 1:1, carries
failure-specific fields in place of the success-only response-side fields:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11). Null otherwise. |
| `provider` | string | The embedding provider identifier. |
| `model` | string | The model identifier the request was made against. |
| `latency_ms` | float \| null | Wall-clock latency from `embed()` entry to the point the failure was raised, in milliseconds. May be null when latency is not measured. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `EmbeddingEvent`. |
| `input_strings` | list of string | The input strings the embedding call was made with. Populated unconditionally on every typed event; same observer-side privacy-gating posture as on `EmbeddingEvent`. |
| `request_params` | mapping | Embedding-specific config fields the caller supplied. Same shape as on `EmbeddingEvent`. |
| `request_extras` | mapping | The embedding runtime config's extras pass-through bag. Same shape and privacy posture as on `EmbeddingEvent`. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at embedding-call time. Same shape as on `EmbeddingEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape as on `EmbeddingEvent`. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present**; freshly minted per `embed()` call. A failed call gets its own `call_id`, distinct from any retry-attempt sibling. |
| `error_category` | string | One of the llm-provider §7 normative categories applicable to embedding (per retrieval-provider §7). Always present. |
| `error_type` | string \| null | OPTIONAL impl-level / vendor-specific error type or code. Two acceptable styles (vendor error code, upstream exception class name). Null when no impl-side type is available. |
| `error_message` | string | Human-readable message from the raised exception. Always present (empty string when the exception carried no message). |

The event MUST be dispatched on the observer delivery queue at the point of `embed()` failure
(after the §7 category exception is raised — whether by the provider or by the implementation's
pre-send validation layer per llm-provider §7 — and before the exception propagates to the
caller). The §7 category exception still raises out of `embed()`; the typed event is dispatched
alongside the exception, not in place of it.

`EmbeddingEvent` and `EmbeddingFailedEvent` are mutually exclusive on a given `embed()` call.
Implementations MUST NOT emit both for the same call. The privacy posture for `input_strings` /
`request_extras` is identical to `EmbeddingEvent`'s — observer-side gating at the rendering
boundary per observability §5.5.4 (implementations populate the fields unconditionally; observers
honor `disable_provider_payload`). Custom queryable observers (per observability §9) consuming
either embedding-variant are responsible for their own redaction posture, identical to the
`LlmCompletionEvent` / `LlmFailedEvent` posture.

**Typed rerank event.** The observer delivery queue also carries a typed `RerankEvent` on every
successful `RerankProvider.rerank()` call per the retrieval-provider §5 contract — a spec-normatively-
typed variant on the observer event union, filtered via type discrimination
(`isinstance(event, RerankEvent)` or per-language idiomatic equivalent) rather than via a
sentinel-namespace string match. The class name `RerankEvent` is normative as an identifier shape;
implementations MAY use a per-language idiomatic name provided the field set + dispatch contract are
preserved. It mirrors `EmbeddingEvent`'s identity / scoping / request-side field set with
rerank-specific substitutions (`query` + `documents` in place of `input_strings`):

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11). Null otherwise. |
| `provider` | string | The rerank provider identifier (matches `gen_ai.system` per observability §5.5.3). |
| `model` | string | The model identifier the request was made against. |
| `response_model` | string \| null | The model identifier the provider returned in the response (matches `gen_ai.response.model`). May be more specific than requested; null when the provider doesn't return a response model. |
| `response_id` | string \| null | The provider-returned response identifier when present. |
| `usage` | record \| null | `RerankUsage` record per retrieval-provider §6. May be null when the provider does not report usage. |
| `latency_ms` | float \| null | Wall-clock latency of the rerank call measured at the adapter boundary, in milliseconds. May be null when latency is not measured. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `EmbeddingEvent` (per observability §3.4). Default absent / null. |
| `query` | string | The query string the rerank call was made with. Populated unconditionally on every typed event; observer-side privacy gating applies at the rendering boundary per the privacy paragraph below. |
| `documents` | list of string | The input documents list. Populated unconditionally; same privacy posture as `query`. |
| `request_params` | mapping | Rerank-specific runtime-config fields the caller supplied (initially `return_documents` per retrieval-provider §2). Absence-is-meaningful semantics per the equivalent field on `EmbeddingEvent`. Empty mapping when no parameters were supplied. |
| `request_extras` | mapping | The rerank runtime config's extras pass-through bag — vendor-specific knobs. Same shape and privacy posture as on `EmbeddingEvent`. Empty mapping when no extras were supplied. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at rerank-call time. Same field set and nullability as on `EmbeddingEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape as on `EmbeddingEvent`. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); freshly minted per `rerank()` call. |
| `document_count` | int | The number of input documents the call was made with (equals `len(documents)`). Derivable but kept for ergonomics + cross-vendor consistency. |
| `top_k` | int \| null | The caller-supplied `top_k` value (or null when the caller passed `None`). |
| `result_count` | int | The number of `ScoredDocument` entries the provider returned (equals `len(response.results)`). |

The event MUST be dispatched on the observer delivery queue at the point of `rerank()` completion
(after the response is parsed and validated per retrieval-provider §6, before `rerank()` returns to
the caller). Delivery semantics follow the *Event delivery* rules above — strict-serial across the
invocation, async-delivered concurrently with graph execution, not blocking the engine's execution
loop. Like the other typed event variants, `RerankEvent` carries no `phase` discriminator and is NOT
subject to the `phases` subscription filter.

**Typed rerank failure event.** The observer delivery queue also carries a typed `RerankFailedEvent`
on every `rerank()` call that raises one of the llm-provider §7 error categories (per
retrieval-provider §7's rerank-applicable subset). Paired with `RerankEvent` per the 0049 → 0058
success+failure pairing precedent — filtered via type discrimination
(`isinstance(event, RerankFailedEvent)` or per-language idiomatic equivalent) rather than via a
sentinel-namespace string match.

The event mirrors `RerankEvent`'s identity / scoping / request-side field set 1:1, carries
failure-specific fields in place of the success-only response-side fields (`response_id`,
`response_model`, `usage`, `result_count` absent):

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name (per pipeline-utilities §11). Null otherwise. |
| `provider` | string | The rerank provider identifier. |
| `model` | string | The model identifier the request was made against. |
| `latency_ms` | float \| null | Wall-clock latency from `rerank()` entry to the point the failure was raised, in milliseconds. May be null when latency is not measured. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `RerankEvent`. |
| `query` | string | The query string. Populated unconditionally; same observer-side privacy-gating posture as on `RerankEvent`. |
| `documents` | list of string | The input documents list. Populated unconditionally; same privacy posture. |
| `request_params` | mapping | Rerank-specific config fields the caller supplied. Same shape as on `RerankEvent`. |
| `request_extras` | mapping | The rerank runtime config's extras pass-through bag. Same shape and privacy posture as on `RerankEvent`. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at rerank-call time. Same shape as on `RerankEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present**; freshly minted per `rerank()` call. A failed call gets its own `call_id`, distinct from any retry-attempt sibling. |
| `document_count` | int | The number of input documents the call was made with (equals `len(documents)`). |
| `top_k` | int \| null | The caller-supplied `top_k` value (or null when the caller passed `None`). |
| `error_category` | string | One of the llm-provider §7 normative categories applicable to rerank (per retrieval-provider §7). Always present. |
| `error_type` | string \| null | OPTIONAL impl-level / vendor-specific error type or code. Two acceptable styles (vendor error code, upstream exception class name). Null when no impl-side type is available. |
| `error_message` | string | Human-readable message from the raised exception. Always present (empty string when the exception carried no message). |

The event MUST be dispatched on the observer delivery queue at the point of `rerank()` failure
(after the §7 category exception is raised — whether by the provider or by the implementation's
pre-send validation layer per retrieval-provider §7 — and before the exception propagates to the
caller). The §7 category exception still raises out of `rerank()`; the typed event is dispatched
alongside the exception, not in place of it.

`RerankEvent` and `RerankFailedEvent` are mutually exclusive on a given `rerank()` call.
Implementations MUST NOT emit both for the same call. The privacy posture for `query` / `documents` /
`request_extras` is identical to `EmbeddingEvent`'s — observer-side gating at the rendering boundary
per observability §5.5.4 (implementations populate the fields unconditionally; observers honor
`disable_provider_payload`). The `ScoredDocument.document` echoes in the response are payload-bearing
on the same footing. Custom queryable observers (per observability §9) consuming either rerank-variant
are responsible for their own redaction posture, identical to the embedding-variant posture.

**Tool-call instrumentation scope.** Tool *execution* — the caller running a tool the model requested
via `LlmCompletionEvent.output_tool_calls` (the output-side tool-call requests, per observability
§5.5.10) — happens in user node-body code; llm-provider §1 is explicit that the caller, not OA,
executes tools. To make that execution observable without owning it, the graph engine provides an
opt-in **tool-call instrumentation scope**: a node-body primitive the caller enters around a single
tool execution. Behaviorally (language-agnostic; e.g. an async context manager, or a helper wrapping
the call):

- The caller provides the `tool_name`, the `arguments` the tool is invoked with, and OPTIONALLY a
  `tool_call_id` (the `ToolCall.id` of the `LlmCompletionEvent.output_tool_calls` entry this execution
  satisfies, per llm-provider §3).
- The caller executes the tool **within** the scope. OA does not execute it.
- On the execution returning a result, OA emits a `ToolCallEvent` carrying the result.
- On the execution raising, OA emits a `ToolCallFailedEvent` carrying the exception's type + message,
  and **re-raises** — the scope observes, it does not swallow. The caller's node body decides what to
  do with the exception (feed it back to the model as a `tool` message, abort, etc. — orchestration,
  out of scope).

**OA observes; the caller runs.** The scope MUST NOT select which tool to call, retry it, loop, or
feed the result back to the model — those are tool-dispatch orchestration, separate from this
observability layer. It instruments a single caller-initiated execution and obtains the outcome as the value the execution
**yields to the scope**: in the inline-wrapping form, the return value of the caller-supplied call the
scope wraps (the wrapping invocation is instrumentation — capturing timing and the return value — not
tool ownership); in the start/complete form, a result the caller reports at completion (the outcome
arrives in a later turn, so there is nothing to wrap). The result is **opaque** to OA — the
pre-serialization, language-idiomatic value as the tool produced it; OA has no tool schema and does not
parse, validate, or transform it, it records it (the observability mappings JSON-encode it for
rendering). A failure is symmetric: the wrapped call raises, or the caller reports a failure, surfaced
as `error_type` + `error_message`.

**Event-driven composition.** The scope MUST NOT assume synchronous inline execution. In an
event-driven runtime a tool call may dispatch as a separate step and return in a later invocation /
turn. The contract is that the terminal event is **emitted when the tool's outcome is known** (result
or failure), not necessarily synchronously within one function call. Implementations MAY offer an
inline-wrapping form (the common case) and a start/complete split (for deferred execution),
correlating the completion to its start via `call_id` / `tool_call_id`. The spec defines the event
contract (one terminal `ToolCallEvent` XOR `ToolCallFailedEvent` per execution, at outcome time); the
surface shape is per-language / per-runtime.

**Identity under deferred execution.** When the start and the outcome fall in different invocations /
turns, the emitted event carries the **scope-entry identity** — the `node_name`, `namespace`,
`invocation_id`, `correlation_id`, `attempt_index`, `fan_out_index`, and `branch_name` captured when
the scope was *entered* (the node that initiated the execution), NOT the ambient identity of the later
turn where the outcome landed. The tool execution belongs to the node that requested it; attributing
it to a downstream turn's context would mislocate it in the trace. This mirrors suspension §7's
`invocation_id`-reuse correlation across the suspend/resume boundary. (The inline case is the trivial
instance — start and outcome share one context.)

**"Tool" is any instrumented function.** The scope is general — it observes any function the caller
records as a tool call, not only model-requested ones. `tool_call_id` is populated when the execution
satisfies an `output_tool_calls` entry, and null otherwise (a node-body utility the caller chooses to
instrument as a tool).

**Typed tool-call event.** On a tool execution returning a result, the observer delivery queue carries
a typed `ToolCallEvent` — a spec-normatively-typed variant on the observer event union, filtered via
type discrimination (`isinstance(event, ToolCallEvent)` or per-language idiomatic equivalent) rather
than via a sentinel-namespace string match. The class name `ToolCallEvent` is normative as an
identifier shape; implementations MAY use a per-language idiomatic name provided the field set +
dispatch contract are preserved. It mirrors `LlmCompletionEvent`'s identity / scoping baseline plus
tool-specific fields:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that executed the tool. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The node-level retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name (per pipeline-utilities §11). Null otherwise. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `LlmCompletionEvent` (per observability §3.4). Default absent / null. |
| `call_id` | string | A per-execution disambiguator minted by the implementation when the scope is entered. **Always present**; freshly minted per tool execution. Distinct from `tool_call_id` — `call_id` is OA's own correlation token for this execution, `tool_call_id` is the provider's id from the model's request. |
| `tool_name` | string | The name of the tool / function executed. Matches the `Tool.name` (llm-provider §4) when the execution satisfies a model request. |
| `tool_call_id` | string \| null | The `ToolCall.id` (llm-provider §3) of the `LlmCompletionEvent.output_tool_calls` entry this execution satisfies — the linkage back to the requesting LLM call (the §5.5.10 `openarmature.llm.output.tool_calls.ids` projection surfaces these request-side ids). Null when the instrumented function did not originate from an LLM tool request. |
| `arguments` | mapping \| null | The arguments the tool was invoked with. For an LLM-originated call, the parsed `ToolCall.arguments` mapping (llm-provider §3/§4); for a standalone instrumented function, the caller-supplied argument shape. Null when the tool takes no arguments. Payload-bearing — observer-side gating per the privacy paragraph below. |
| `result` | (language-idiomatic value) | The tool's return value **as the tool produced it** (pre-serialization — a mapping, string, or any language-idiomatic value). OA observes the return value; it does not build the `tool` message (the caller serializes the result into the `tool` message content, a string per llm-provider §3; the observability mappings JSON-encode it for rendering). Payload-bearing. |
| `latency_ms` | float \| null | Wall-clock latency of the tool execution measured at the scope boundary, in milliseconds. May be null when not measured. |

**Typed tool-call failure event.** On a tool execution raising, the observer delivery queue carries a
typed `ToolCallFailedEvent` (paired with `ToolCallEvent` per the 0049 → 0058 → 0059 success+failure
precedent; filtered via type discrimination). It mirrors `ToolCallEvent`'s identity / scoping /
request-side fields (`tool_name`, `tool_call_id`, `arguments`, `latency_ms`, `call_id`), with the
success-only `result` absent and two failure-specific fields:

| Field | Type | Description |
|---|---|---|
| (identity / scoping / `tool_name` / `tool_call_id` / `arguments` / `latency_ms` / `call_id`) | | Same definitions as on `ToolCallEvent`. |
| `error_type` | string \| null | The impl-level / language-level exception type — the exception class name (e.g. `"TimeoutError"`, `"ValueError"`) or a tool-defined error code. Null when no type is available. |
| `error_message` | string | The human-readable message from the raised exception. Always present (empty string when the exception carried no message). |

**No `error_category`.** This is the deliberate departure from `LlmFailedEvent` / `EmbeddingFailedEvent`.
Those carry an `error_category` from the llm-provider §7 normative enumeration because provider calls
have a closed, spec-defined failure taxonomy. Tool execution is arbitrary user / third-party code that
can raise anything — there is no normative category to assign, and inventing one would be a fiction.
`error_type` (the actual exception class) + `error_message` carry the failure faithfully.

**Mutual exclusion, exception flow, and dispatch.** `ToolCallEvent` and `ToolCallFailedEvent` are
mutually exclusive per tool execution — implementations MUST NOT emit both for the same execution. The
exception still propagates out of the scope (the re-raise rule above); the typed event is dispatched
alongside the exception, not in place of it — caller code handling the exception sees the exception
path unchanged, observers see the failure event. Both events MUST be dispatched on the observer
delivery queue at the point the outcome is known (after the result is in hand / after the exception is
raised; before the result or exception flows back to the caller), strict-serial across the invocation
and async-delivered per the §6 contract. Like the other typed variants, they carry no `phase`
discriminator and are not subject to the `phases` filter; observers filter via type discrimination.

**Privacy posture (tool events).** `arguments` and `result` carry potentially sensitive payload (the
tool's inputs and outputs — often user content or external-API data). The posture matches
`LlmCompletionEvent`'s — implementations populate the fields unconditionally; observer-side gating
applies at the rendering boundary per observability §5.5.4. The `disable_provider_payload` flag (renamed
from `disable_llm_payload` by proposal 0059) gates tool payload: its framing covers payload from any
instrumented external operation, and a tool call is exactly that. The flag gates observability
*rendering* only — it does NOT affect the `result` the caller serializes into the `tool` message (the
model needs the tool's output to continue), nor the event-field population. Custom queryable observers
(per observability §9) consuming the tool events own their own redaction posture, identical to the
`LlmCompletionEvent` posture.

## 7. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Middleware** — wrapping nodes with cross-cutting concerns (retry, timing, logging).
- **Checkpointing and resume** — pipeline utility, not a graph-engine primitive.
- **Parallel fan-out / fan-in** — batch execution of a single node over many inputs.
- **Streaming outputs** — per-node streaming of partial state updates.
- **Persistent state backends** — durable state stores beyond in-memory execution.
- **Human-in-the-loop interrupts** — pause, inspect, resume semantics.
