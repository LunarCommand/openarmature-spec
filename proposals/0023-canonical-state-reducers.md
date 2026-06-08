# 0023: Canonical State Reducers

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-17
- **Accepted:** 2026-06-07
- **Targets:** spec/graph-engine/spec.md (extends §2 Reducer concept)
- **Related:** 0001 (graph-engine foundation — establishes the three baseline reducers), 0006 (llm-provider — `Message` shape that motivates the chat-agent use cases), 0017 (prompt-management — composes with state-tracked message history), 0020 (sessions — declares which reducer-managed fields survive across invokes)
- **Supersedes:**

## Summary

Extend the mandatory reducer set in graph-engine §2 from three baseline
reducers (`last_write_wins`, `append`, `merge`) to a slightly larger
canonical set that solves common state-composition patterns without
forcing users to roll their own. New canonical reducers:

- **`bounded_append(max_len)`** — append-with-truncate-from-front; caps a
  list at a configured length by dropping oldest entries when the bound
  is exceeded.
- **`dedupe_append(key=None)`** — append-unique; skips items whose key
  matches an existing entry.
- **`merge_by_key(key)`** — list-of-records merge keyed by `key(item)`;
  replaces existing entries with matching keys, appends novel entries.

Three reducers, each a factory function returning a reducer closure.
Composes with the existing `Annotated[T, reducer]` declaration
mechanism without changing the reducer protocol. Motivated primarily by
chat-agent and tool-loop workflows but reducers themselves are
message-agnostic — they work over any list-typed field.

## Motivation

The current baseline (`last_write_wins`, `append`, `merge`) solves the
universal cases but leaves a handful of common idioms to each project:

- **Bounded buffers where silent drop is acceptable.** Recent-events
  caches, debug log windows, "last N errors" rings, sliding metric
  windows. Today every project writes the same closure: extend, then
  slice from the back. Trivial but repeated. `bounded_append` covers
  this. Note: this is NOT the chat-history-with-summarization case —
  that one needs unbounded `append` plus a compaction node, since
  summarization can't live in a sync pure reducer. See §2.X.1 for the
  distinction.
- **Tool-result deduplication.** Agents that re-issue equivalent tool
  calls (search retries, retry loops) accumulate duplicate
  `ToolMessage` records. Filtering duplicates at append time is a
  one-liner — but it's the same one-liner every project rewrites.
- **Streaming message updates.** Agents with token-by-token streaming
  replace the in-flight assistant message progressively. Today this
  requires either (a) custom reducer logic per project or (b)
  out-of-band state surgery via the engine's recoverable-state hooks.
  Spec'ing a keyed-merge reducer makes the streaming pattern uniform.

The framing this proposal takes: state stays as the uniform container
(per OA's design principle — no special "messages" channel like
LangGraph's `add_messages`); the canonical reducers ship as small,
composable tools the user opts into per-field. The flexibility to
manage state any way the user sees fit is preserved; the new reducers
are tools to do that more uniformly, not constraints on how state must
be shaped.

Cross-language consistency is the secondary motivation. Python and
TypeScript implementations should agree on the semantics of "bounded
append with max length 50" — whether the truncation is exclusive,
whether duplicates count against the bound, whether the key function
runs on the existing or the new value. Pinning the semantics here
prevents per-implementation drift.

This proposal is **not** about chat-specific message handling. It does
NOT introduce a built-in `messages` field, a `Message` ID convention,
or a streaming-aware reducer that depends on Message internals. The
reducers are general-purpose; the chat-agent use case is just the
concrete motivator. Any list-typed field can use them.

## Detailed design

### Extension to graph-engine §2 Reducer concept

Current text (§2):

> **Reducer.** A function that merges a node's partial update into the
> prior state for a given field. Each state field has exactly one
> reducer. The default reducer is _last-write-wins_ (the new value
> replaces the old). Implementations MUST provide at least:
> `last_write_wins`, `append` (for list-typed fields), and `merge`
> (for mapping-typed fields). Users MAY register custom reducers per
> field.

Proposed text replaces the "MUST provide at least" sentence:

> Implementations MUST provide at least the following six canonical
> reducers:
>
> - **`last_write_wins`** — replace the existing value with the new
>   value. Default reducer for fields with no `Annotated` declaration.
> - **`append`** — extend a list field with the new partial update's
>   items. Both existing and update values MUST be lists; reducer
>   raises `reducer_error` (§4) otherwise.
> - **`merge`** — dict-shallow-merge a mapping field. Keys in the
>   update override keys in the existing value; keys present only in
>   existing are preserved.
> - **`bounded_append(max_len)`** — like `append`, but caps the
>   resulting list at `max_len` entries by discarding oldest entries
>   (from the front) when the bound is exceeded. See §2.X.1.
> - **`dedupe_append(key=None)`** — like `append`, but skips entries
>   whose key already appears in the existing list. See §2.X.2.
> - **`merge_by_key(key)`** — keyed merge for list-of-records fields;
>   entries in the update with a key matching an existing entry
>   replace the existing entry; entries with novel keys are appended.
>   See §2.X.3.
>
> Users MAY register custom reducers per field.

### §2.X.1 `bounded_append(max_len)`

A factory returning a reducer that extends a list with the update's
items and truncates from the front if the total length exceeds
`max_len`.

Parameters:

| Parameter | Description |
|---|---|
| `max_len` | Positive integer. The maximum allowed list length after the reducer runs. MUST be ≥ 1. |

Behavior:

1. Concatenate existing list + update list.
2. If `len(concatenated) > max_len`, drop entries from the front
   until `len == max_len`.
3. Return the result.

Edge cases:

- **Update larger than `max_len`.** The reducer keeps only the LAST
  `max_len` items of the update; the existing list is fully evicted.
  Rationale: the bound applies to the post-merge length, not to the
  update's individual size.
- **Empty update.** Returns the existing list unchanged.
- **`max_len` ≤ 0.** Configuration-time error
  (`reducer_configuration_invalid`); reducer factory raises at field
  registration.

Cross-impl semantics:

- Truncation MUST be from the front (oldest entries dropped first).
- The bound MUST apply to the post-merge length, not the existing
  length.
- The bound MUST be inclusive — i.e., `len <= max_len` after the
  reducer.

**When to use `bounded_append` vs `append`:**

`bounded_append` is for cases where **silent drop of dropped data is
acceptable** — recent-events buffers, debug log windows, "last N
errors" caches, sliding metric windows, etc. The reducer truncates
without notification; the user cannot recover dropped entries.

For cases where **dropped data must be summarized or transformed
first** (the canonical example: chat conversation history that needs
LLM-based summarization before older messages are discarded), use
unbounded `append` plus a separate compaction step. Reducers are pure
synchronous functions per graph-engine §2; they cannot perform the
LLM call (or other IO) that real compaction requires. The compaction
step lives elsewhere in the graph:

- **Compaction node.** A graph node that runs (typically via a
  conditional edge) when `len(state.field)` crosses a user-defined
  threshold. The node calls a summarizer (LLM, callable, etc.) on the
  oldest N items, then returns a partial update replacing the field
  with `[summary, ...recent_items]`. Threshold is strictly LESS than
  the field's hard upper bound, giving the compaction node room to
  run before data would be lost.
- **Compaction middleware.** A middleware (per proposal 0004)
  wrapping content-producing nodes. Reads pre-merge state length;
  triggers summarization if the threshold is approached.
- **Post-invoke compaction.** A final node before END that summarizes
  if the field grew during the invoke. Useful for capping between
  invokes rather than within.

The patterns docs cookbook will carry the canonical "compaction
before truncation" recipe with concrete code (`append` + conditional
edge to a compactor node) for chat-history shapes. `bounded_append`
deliberately does NOT try to encompass the LLM-summarization case;
spec-level uniformity for that pattern lives in the patterns docs
plus user-supplied compactor logic.

### §2.X.2 `dedupe_append(key=None)`

A factory returning a reducer that extends a list with items from the
update that are not already present (by key) in the existing list.

Parameters:

| Parameter | Description |
|---|---|
| `key` | Optional callable. Maps an item to its dedup key. If omitted, the item itself is used as the key (requires hashable items). |

Behavior:

1. Initialize `seen_keys` with the key of every item in `existing`
   (preserving the existing list unchanged in the result).
2. Iterate through `update` in order. For each item, compute its
   key. If the key is NOT in `seen_keys`, append the item to a
   working `filtered_update` list and add the key to `seen_keys`.
   Otherwise, skip the item.
3. Return `existing + filtered_update`.

This formulation ensures both behaviors hold uniformly: items whose
key matches any item already in `existing` are filtered, and items
whose key duplicates an earlier item in the same update are also
filtered (first occurrence wins).

Edge cases:

- **Duplicates within the update.** If the update itself contains
  duplicate keys, the FIRST occurrence is kept; subsequent duplicates
  are filtered out alongside any matches against existing. Rationale:
  preserves left-to-right precedence consistent with `append`.
- **Empty update.** Returns the existing list unchanged.
- **Non-hashable items with no `key` callable.** Raises
  `reducer_error` (§4) at merge time.
- **`key` callable raises on any item.** The exception propagates as
  `reducer_error`.

Cross-impl semantics:

- Order MUST be preserved: existing items appear before update items;
  within each, original order is maintained.
- Equality is per the key function (or identity / hash for default).
- The reducer does NOT mutate existing items (no in-place dedup of
  existing); only the update is filtered.

### §2.X.3 `merge_by_key(key)`

A factory returning a reducer for list-of-records fields. Items in the
update with a key matching an existing item REPLACE the existing item
in place; items with novel keys are appended at the end.

Parameters:

| Parameter | Description |
|---|---|
| `key` | Required callable. Maps an item to its merge key. Spec does NOT default this — keyed merge without a key function is meaningless. |

Behavior:

1. Build an index `key_to_idx = {key(item): index}` for the existing
   list.
2. For each item in the update:
   - If `key(item)` is in `key_to_idx`: replace `existing[key_to_idx[k]]`
     with the update item.
   - Otherwise: append the update item to the result list and
     register its key in the index.
3. Return the result (preserving position for replaced items;
   appending for novel items).

Edge cases:

- **Duplicate keys within the update.** Last occurrence wins
  (consistent with how dict updates work for repeated keys).
- **Duplicate keys within the existing list.** When `existing`
  contains multiple items with the same key, the reducer treats
  only the LAST occurrence as the target for an update item
  sharing that key — i.e., step 1's `key_to_idx` MUST hold the
  last index for each duplicate key, consistent with the within-
  update last-wins semantics. Earlier duplicates in `existing`
  are preserved in place; the reducer does NOT in-place dedupe
  existing (parallel to `dedupe_append`'s "no in-place dedup of
  existing" rule). Implementations whose native dict/map
  construction uses first-wins semantics MUST iterate explicitly
  to enforce last-wins.
- **Empty update.** Returns the existing list unchanged.
- **`key` callable raises.** Propagates as `reducer_error`.
- **Missing `key` parameter.** Configuration-time error
  (`reducer_configuration_invalid`).

Cross-impl semantics:

- Existing entry order MUST be preserved.
- Novel entries from the update MUST be appended at the end, in the
  order they appeared in the update (modulo duplicate-key collapse).
- This reducer is NOT a substitute for `merge` — `merge` operates on
  dict-typed fields with shallow key-value semantics;
  `merge_by_key` operates on list-of-records fields with item-key
  semantics.

### Extension to graph-engine §2 compile-time error categories

Add `reducer_configuration_invalid` as a new canonical compile-time
error category in graph-engine §2 (the canonical category list at
the end of *Compiled graph*).

- **`reducer_configuration_invalid`** — a reducer factory was
  supplied invalid construction parameters (e.g.,
  `bounded_append(max_len=0)`, `merge_by_key(key=None)`). Raised at
  field registration / graph compilation time, before any node body
  runs. Distinct from `conflicting_reducers`, which fires when more
  than one reducer is declared on the same field —
  `conflicting_reducers` is about the reducer-declaration shape;
  `reducer_configuration_invalid` is about parameters supplied to a
  single reducer factory.

The new category sits alongside the v1 list (`no_declared_entry`,
`unreachable_node`, `dangling_edge`, `multiple_outgoing_edges`,
`conflicting_reducers`, `mapping_references_undeclared_field`). No
existing category is renamed or repurposed.

Errors raised at reducer invocation time (e.g., a `key` callable
that raises on a specific item, a non-list update supplied to
`bounded_append`) continue to surface as `reducer_error` (§4),
unchanged.

### Composition with existing reducer model

The new reducers compose with the existing `Annotated[T, reducer]`
declaration mechanism without changing the reducer protocol:

```python
class State(StateBase):
    history: Annotated[list[Message], bounded_append(max_len=50)] = Field(default_factory=list)
    sources: Annotated[list[str], dedupe_append()] = Field(default_factory=list)
    tool_results: Annotated[list[ToolMessage], merge_by_key(lambda m: m.tool_call_id)] = Field(default_factory=list)
```

Reducers remain pure functions; nothing in the new set requires async,
IO, or side effects. The factories run at field-registration time; the
returned closures are the reducers the engine invokes.

`conflicting_reducers` (§2 / §4) still applies — only one reducer per
field. Stacking `bounded_append(50)` on top of `append` is a
declaration error.

### What's explicitly NOT in this proposal

This proposal deliberately scopes tightly. The following are NOT
covered:

- **Summarization-on-bound reducers.** A reducer that calls a
  summarizer (LLM, callable, etc.) when a bound is hit is NOT a pure
  function; it has IO, latency, retry concerns. That's a middleware
  problem, not a reducer problem. Future work could specify a
  "bound-driven summarization middleware" alongside this proposal.
- **Message-aware semantics.** No `Message` ID convention introduced;
  no streaming-aware reducer. `merge_by_key` is keyed on a
  user-supplied callable; if you want to merge messages by
  `tool_call_id`, the callable extracts that field. The spec doesn't
  bake message-shape into the reducer.
- **Numeric / scalar reducers.** No `sum_into`, `max_into`,
  `min_into`, `running_mean`, etc. Possibly a future proposal if
  demand surfaces; out of scope here.
- **Async reducers.** Reducers remain synchronous pure functions per
  the current §2 contract. No change.

## Conformance test impact

New fixtures under `spec/graph-engine/conformance/`:

- **`022-bounded-append-basic`** — declare a field with
  `bounded_append(max_len=3)`; run a node that appends a list of 5
  items; verify final list contains the last 3.
- **`023-bounded-append-multi-step`** — multiple nodes each append 2
  items to a field with `bounded_append(max_len=4)`; verify
  cumulative bound enforcement across merges.
- **`024-bounded-append-update-larger-than-bound`** — single update
  with more items than `max_len`; verify only the LAST `max_len`
  items remain.
- **`025-dedupe-append-default-key`** — `dedupe_append()` over a
  list of strings with duplicates within the update; verify dedup
  and order preservation.
- **`026-dedupe-append-with-key-callable`** — `dedupe_append(key=lambda r: r.id)`
  over a list of records; verify key-based dedup.
- **`027-merge-by-key-replace-existing`** — `merge_by_key(lambda r: r.id)`
  with updates that share keys with existing items; verify in-place
  replacement and order preservation.
- **`028-merge-by-key-append-novel`** — `merge_by_key` with
  novel-keyed updates; verify appended at end in update order.
- **`029-merge-by-key-mixed-replace-and-append`** — updates with a
  mix of matching and novel keys; verify positional behavior.
- **`030-reducer-configuration-invalid-max-len`** — register
  `bounded_append(max_len=0)`; verify configuration-time error.
- **`031-reducer-error-non-list-update`** — register
  `bounded_append`, then run a node returning a non-list update;
  verify `reducer_error` raised.

Existing fixtures (using `append`, `merge`, `last_write_wins`)
continue to pass without modification — the new reducers add to the
required set rather than replacing any.

## Alternatives considered

**Keep the userland-closure pattern.** Every project rolls its own
`bounded_append`, `dedupe_append`, etc. as needed. Rejected for the
ecosystem-fragmentation reason: the same closure gets written ten
times with subtle semantic differences (does the bound count
exclusively? does dedupe operate on existing too? what's the order
guarantee?). Spec'ing the canonical version costs one document; the
reduced ecosystem drift more than pays for it.

**Spec a much larger reducer library.** Sum, mean, min, max,
running-stat reducers; sliding-window reducers; ID-aware nested
merge reducers; etc. Rejected as premature. The three this proposal
adds are motivated by concrete chat-agent and tool-loop patterns
with imminent implementation need. Other reducers can land as
follow-on proposals when concrete need surfaces.

**Spec a `messages` channel with built-in semantics (LangGraph
shape).** A normative `messages` field with built-in `add_messages`-
style reducer. Rejected as a departure from OA's design principle —
state is the uniform container; no special-cased field names. The
canonical reducers honor that principle by being field-name-agnostic.

**Defer until the chat harness ships.** Wait for `openarmature-chat`
to surface concrete needs before spec'ing. Rejected because the
reducers have imminent implementation need ahead of the chat harness
landing; spec'ing now lets implementations adopt them in time. The
reducers are small enough that the risk of over-specifying is low.

**Make summarization a reducer too.** Bundle
`summarize_on_bound(max_len, summarizer)` into this proposal.
Rejected because summarization is fundamentally a middleware
concern (async, retryable, IO). Reducers stay pure; summarization
gets its own future proposal.

## Open questions

None at Accept time. All six design decisions are settled in the
proposal text above:

- **Naming convention.** Operation-first / modifier-second
  (`bounded_append`, `dedupe_append`, `merge_by_key`), consistent
  with `last_write_wins`.
- **`merge_by_key` novel-key behavior.** Append at end (the more
  useful default for most workflows).
- **`bounded_append` truncation direction.** Front-drop (oldest
  evicted first). Back-drop deferred to a follow-on
  `bounded_prepend` if demand surfaces.
- **Reducer-parameter validation timing.** Parameters checkable
  without invoking callables → configuration-time
  (`reducer_configuration_invalid`); callable-dependent checks
  surface at merge time as `reducer_error`.
- **`reducer_configuration_invalid` as a distinct compile-time
  category.** Added as a new category alongside the existing six
  (`no_declared_entry`, `unreachable_node`, `dangling_edge`,
  `multiple_outgoing_edges`, `conflicting_reducers`,
  `mapping_references_undeclared_field`). Distinct from
  `conflicting_reducers` (which is about reducer-declaration shape;
  the new category is about parameters supplied to a single reducer
  factory).
- **`merge_by_key` naming.** Retained alongside `merge` (which is
  dict-shallow) despite the partial name collision; the qualifier
  `_by_key` distinguishes the list-of-records-keyed shape from the
  dict-shallow shape, and the operation-first naming convention
  applies symmetrically.
