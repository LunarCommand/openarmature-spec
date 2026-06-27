# 039 — Nested Fan-Out Event Lineage Chain

Verifies the `fan_out_index_chain` and `branch_name_chain` fields added to `NodeEvent` by
[proposal 0084](../../../proposals/0084-nested-fan-out-span-lineage.md). For a node nested inside a
fan-out that is itself nested inside an outer fan-out instance, the scalar `fan_out_index` is the
**innermost** instance index — identical across the two outer instances — so the scalars alone do
not uniquely identify the event source. The chains carry the full enclosing-instance lineage
(outermost→innermost, aligned to the `namespace` path) that disambiguates them, while the retained
scalar carries the innermost value.

**Spec sections exercised:**

- §6 `fan_out_index_chain` — the enclosing fan-out instance lineage, one entry per namespace
  segment / dispatch boundary, each entry the `fan_out_index` of the fan-out instance entered at
  that boundary (or null when that boundary is not a fan-out instance); empty for a top-level event.
- §6 `branch_name_chain` — the same shape for the enclosing parallel-branch lineage; null at every
  position here because neither boundary is a parallel branch.
- §6 scalar retention — `fan_out_index` is retained as the innermost (deepest non-null) chain value;
  for a node nested inside multiple fan-out instances the scalar alone does not identify the source,
  the chain does.
- pipeline-utilities §9 — fan-out node projection / collection across two nesting levels.

## Topology and arithmetic

Standard nested fan-out (cf. graph-engine fixture 017 and pipeline-utilities 076):

```
outer_fan_out  -- fan-out over outer_items (2 lists) --> subgraph `mid`
  inner_fan_out -- fan-out over inner_items (2 ints) --> subgraph `leaf_sg`
    leaf        -- out = input
```

- Outer item 0 `[10, 11]` → inner instances 0, 1 → `out` 10, 11 → `inner_results` `[10, 11]`.
- Outer item 1 `[20, 21]` → inner instances 0, 1 → `out` 20, 21 → `inner_results` `[20, 21]`.
- `all_results` (append reducer; merged in instance-index order at the outer fan-in per
  pipeline-utilities §9.3) = `[[10, 11], [20, 21]]`.

## Per-instance lineage (the load-bearing assertion)

The leaf node runs two fan-out boundaries deep. Each `(outer, inner)` pair yields a distinct chain;
the scalar repeats across outer instances:

| outer instance | inner instance | `fan_out_index_chain` | `branch_name_chain` | scalar `fan_out_index` |
| -------------- | -------------- | --------------------- | ------------------- | ---------------------- |
| 0              | 0              | `[0, 0]`              | `[null, null]`      | `0`                    |
| 0              | 1              | `[0, 1]`              | `[null, null]`      | `1`                    |
| 1              | 0              | `[1, 0]`              | `[null, null]`      | `0`                    |
| 1              | 1              | `[1, 1]`              | `[null, null]`      | `1`                    |

Scalar `fan_out_index` `0` and `1` each occur under **both** outer instances — the scalar tuple
`(namespace, fan_out_index, branch_name, attempt_index, phase)` collides across outer instances. The
chain disambiguates: `[0, 0]` ≠ `[1, 0]` and `[0, 1]` ≠ `[1, 1]`.

The two enclosing nodes anchor the chain's two endpoints:

- `outer_fan_out` (the outer fork point) is at the outermost graph — **empty** chains, scalar
  `fan_out_index` absent.
- `inner_fan_out` recurs once per outer instance and runs *inside* the outer instance — a length-1
  chain `[outer_index]`, scalar `fan_out_index` = the outer index.

## Fixture-specific invariant predicates

Per conformance-adapter §5.9 these are documented here; the adapter implements each against the
recorded event stream. (`*_chains_seen` is the **set** of distinct chains observed, mirroring the
set-valued `inner_fan_out_indices_seen` convention from fixture 017.)

- `outer_fan_out_node_events_count` / `inner_fan_out_node_events_count` / `leaf_node_events_count` —
  the started+completed pair counts (2 / 4 / 8).
- `outer_fan_out_node_fan_out_index_chain_empty` — the outer fan-out node's `fan_out_index_chain` is
  empty (`[]`).
- `outer_fan_out_node_fan_out_index_absent` — the outer fan-out node's scalar `fan_out_index` is
  absent (it is the fork point, not inside any instance).
- `inner_fan_out_node_fan_out_index_chains_seen` — the set of inner-fan-out-node chains is
  `{[0], [1]}` (one length-1 chain per outer instance).
- `inner_fan_out_node_branch_name_chains_seen` — every inner-fan-out-node `branch_name_chain` is
  `[null]` (the one enclosing boundary is a fan-out, not a branch).
- `inner_fan_out_node_scalar_fan_out_index_equals_innermost_chain_element` — every inner-fan-out-node
  event's scalar `fan_out_index` equals the deepest non-null chain element (the outer index it runs in).
- `inner_fan_out_node_scalar_branch_name_absent` — every inner-fan-out-node event's scalar
  `branch_name` is absent (no enclosing branch).
- `leaf_fan_out_index_chains_seen` — the set of leaf chains is exactly
  `{[0,0], [0,1], [1,0], [1,1]}`.
- `leaf_branch_name_chains_seen` — every leaf `branch_name_chain` is `[null, null]`.
- `leaf_scalar_fan_out_index_equals_innermost_chain_element` — for every leaf event, the scalar
  `fan_out_index` equals the deepest non-null chain element.
- `leaf_scalar_branch_name_absent` — every leaf event's scalar `branch_name` is absent.
- `leaf_event_identities_unique_by_chain` — the four leaf instances are uniquely identified once the
  chains are included in the identity tuple.
- `leaf_scalar_fan_out_index_not_unique_across_outer_instances` — without the chain (scalar
  `fan_out_index` only), the four leaf instances collapse to two identities — the collision the
  chain resolves.

**What passes:**

- The leaf events carry exactly the four chains above, each with `branch_name_chain = [null, null]`
  and scalar `fan_out_index` equal to the innermost chain element.
- The inner fan-out node events carry length-1 chains `[0]` / `[1]`; the outer fan-out node events
  carry empty chains with the scalar `fan_out_index` absent.
- `final_state.all_results == [[10, 11], [20, 21]]`.

**What fails:**

- Leaf chains truncated to the scalar (`fan_out_index` only) — outer instances 0 and 1 become
  indistinguishable (`leaf_event_identities_unique_by_chain` fails).
- A chain ordered innermost→outermost (`[1, 0]` for outer-0/inner-1) instead of outermost→innermost.
- `branch_name_chain` populated with non-null values, or the chain length not aligned to the two
  fan-out boundaries.
- The scalar `fan_out_index` dropped or set to the outermost value rather than the innermost.
