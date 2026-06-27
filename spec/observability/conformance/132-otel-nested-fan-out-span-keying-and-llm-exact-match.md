# 132 — OTel Nested Fan-Out Span Keying and Nested-LLM Exact-Match

Verifies the lineage-chain-aware span keying and the nested-LLM exact-match parent rule added by
[proposal 0084](../../../proposals/0084-nested-fan-out-span-lineage.md) for an inner fan-out nested
inside an outer fan-out instance, run under **concurrent** outer execution. One `span_tree` carries
both assertions.

**Spec sections exercised:**

- §4.1 / §6 — the driving-span key is `(namespace, attempt_index, fan_out_index_chain,
  branch_name_chain)`; the chains replace the innermost scalar so the inner spans of two concurrent
  outer instances that share an inner `fan_out_index` no longer collide and drop.
- §4.3 — node / fan-out-instance spans are parented by the lineage chain when the innermost scalar
  can coincide across concurrent enclosing instances.
- §5.5 *Lineage-resolved parent* — an LLM provider span parents under its own lineage-disambiguated
  calling-node span (the calling-node span IS open here, the common case), not a sibling sharing the
  innermost scalar.
- §5.4 / §4.5 — fan-out NODE spans carry `item_count` / `error_policy`; instance spans carry the
  scalar `openarmature.node.fan_out_index` (the innermost value) + `parent_node_name`, and share the
  fan-out node's name.

## Topology

Standard nested fan-out (cf. fixtures 006 and 076), with an LLM-calling leaf:

```
outer_fan_out  -- fan-out over outer_seeds (2 lists), concurrent --> subgraph `mid`
  inner_fan_out -- fan-out over inner_seeds (2 ints) --> subgraph `leaf_sg`
    ask         -- calls_llm, stores_response_in score
```

`outer_seeds = [[0, 1], [2, 3]]` → 2 outer instances × 2 inner instances = four LLM calls. The leaf
ignores the projected `seed` (it issues a fixed LLM call); the projection only fixes the instance
counts.

## Span lineage and the collision

The lineage is encoded by the **tree shape**, not a new span attribute. Each inner instance's
innermost scalar `fan_out_index` repeats across the two outer instances:

| outer instance | inner instance | lineage chain | inner-instance span `fan_out_index` |
| -------------- | -------------- | ------------- | ----------------------------------- |
| 0              | 0              | `[0, 0]`      | `0`                                 |
| 0              | 1              | `[0, 1]`      | `1`                                 |
| 1              | 0              | `[1, 0]`      | `0`                                 |
| 1              | 1              | `[1, 1]`      | `1`                                 |

Under **concurrent** outer execution both outer instances' inner subtrees are in-flight on the
serial event queue at once. Keying the observer's span stack by the innermost scalar
`(namespace, attempt_index, fan_out_index, branch_name)` produces only two distinct keys for the
four inner instances (`fan_out_index` 0 and 1), so the second outer instance's `started`/`completed`
events overwrite the first — its inner subtree (inner instances, `ask` spans, `llm.complete` spans)
silently drops. Keying by `fan_out_index_chain` keeps all four distinct.

`concurrent_mode: concurrent` on the outer fan-out forces the concurrency; under serial execution
the innermost-scalar key never overlaps and the fixture would not discriminate the bug. This is the
same fan-out directive pipeline-utilities 076 uses for nested concurrent outer execution. (It is
established in the pipeline-utilities fixtures but is the first observability fixture to use it; it
is a shared `fan_out` config directive, parsed identically by the shared conformance adapter.)

## Fixture-specific invariant predicates

Per conformance-adapter §5.9, documented here.

- `no_inner_spans_dropped_under_concurrent_nesting` — all four inner-instance subtrees are present;
  none collided away under the concurrent shared-innermost-`fan_out_index` keying.
- `inner_node_span_count` — exactly four `ask` spans.
- `llm_provider_span_count` — exactly four `openarmature.llm.complete` spans.
- `llm_span_parents_under_own_lineage_calling_node` — each `llm.complete` is a direct child of the
  `ask` span in its own lineage (`[0,0]`/`[0,1]`/`[1,0]`/`[1,1]`), never the `ask` span of the
  other outer instance's inner instance with the same innermost `fan_out_index`.
- `unique_fan_out_indices_per_node_span_under` / `fan_out_index_range` — instance indices are unique
  within EACH `inner_fan_out` node span (there are two — one per outer instance — so the check is
  per-parent-span, not global: globally the indices are `{0,1,0,1}`) and cover `0..1` (cf. 006).

**What passes:**

- The span tree contains both outer instances, each with both inner instances, each inner instance
  with its `ask` span and that `ask`'s single `openarmature.llm.complete` child — eight inner-level
  spans plus four LLM spans.
- Each fan-out NODE span carries `item_count = 2`, `error_policy = "collect"`; each instance span
  carries its scalar `fan_out_index` and `parent_node_name`.

**What fails:**

- The second outer instance's inner subtree is missing (innermost-scalar keying collided it away) —
  the pre-0084 drop.
- An `llm.complete` parents under the wrong `ask` span (the sibling sharing the innermost
  `fan_out_index`), or under a fan-out node span / the invocation span.
- Inner instances collapsed so `fan_out_index` is duplicated or the tree is flattened.
