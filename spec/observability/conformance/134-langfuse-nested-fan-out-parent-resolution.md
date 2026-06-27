# 134 — Langfuse Nested Fan-Out Observation Parent Resolution

Verifies that the Langfuse observation tree resolves the Generation's parent by the **same**
chain-aware §5.5 *Lineage-resolved parent* rule as the OTel span tree, for both the nested
exact-match case and the orphan fallback case, per
[proposal 0084](../../../proposals/0084-nested-fan-out-span-lineage.md) §8.4.3 / §8.4.6. The two
backends MUST produce the same parent for a Generation in a nested fan-out instance. This is the
Langfuse mirror of OTel fixtures 132 (case 1) and 133 (case 2).

**Spec sections exercised:**

- §8.4.3 — the Generation's parent observation follows the §5.5 *Lineage-resolved parent* resolution:
  the calling node's `Span` observation identified by the event's lineage chain, and — when that
  observation is not open — the nearest open ancestor observation per §4.3.
- §8.4.6 — the same resolution for tool / non-Generation observations (cross-referenced; this fixture
  exercises the Generation path).
- §8.3 / §8.4.2 — fan-out node → dispatch `Span` observation (`fan_out_item_count` /
  `fan_out_error_policy`); fan-out instance → `Span` observation child (`fan_out_index` /
  `fan_out_parent_node_name` / `subgraph_name`, the instance observation being the subgraph wrapper).
- §8.9 — the Langfuse observation tree and the OTel span tree produce the same parent hierarchy.

## Topology

Standard nested fan-out, `concurrent_mode: concurrent` on the outer fan-out (matching 132 / 133;
first observability use of the directive, parsed by the shared adapter). The lineage is encoded by
the observation tree shape, with the scalar `fan_out_index` on each instance observation.

**Case 1 — nested exact-match** (mirrors OTel 132): `outer_seeds = [[0, 1], [2, 3]]` → 2 outer × 2
inner; each `ask` node issues an in-body LLM call.

| outer | inner | lineage chain | instance `fan_out_index` |
| ----- | ----- | ------------- | ------------------------ |
| 0     | 0     | `[0, 0]`      | `0`                      |
| 0     | 1     | `[0, 1]`      | `1`                      |
| 1     | 0     | `[1, 0]`      | `0`                      |
| 1     | 1     | `[1, 1]`      | `1`                      |

Each Generation parents under its own lineage-disambiguated `ask` Span observation; the innermost
`fan_out_index` repeats across outer instances, so the chain is what prevents cross-outer
mis-parenting (and the dropped-observation collision under concurrency).

**Case 2 — orphan fallback** (mirrors OTel 133): `outer_seeds = [[0], [0]]` → 2 outer × 1 inner; the
`guard` node issues its call from the wrapper pre-phase (calling node's Span observation not open).
Both inner instances carry inner `fan_out_index` 0; the chain (`[0, 0]` vs `[1, 0]`) routes each
orphan Generation to the correct inner instance. The orphan-call primitive `calls_llm_from_wrapper`
is defined in fixture 133.

| outer | inner | lineage chain | instance `fan_out_index` |
| ----- | ----- | ------------- | ------------------------ |
| 0     | 0     | `[0, 0]`      | `0`                      |
| 1     | 0     | `[1, 0]`      | `0`                      |

## Parenting outcome

- **Case 1.** Each `openarmature.llm.complete` Generation is a child of its own `ask` Span
  observation, which sits under the correct inner instance under the correct outer instance. All four
  inner subtrees appear (no dropped observations).
- **Case 2.** Each orphan Generation parents under its inner fan-out instance Span observation (the
  nearest open ancestor, since the `guard` Span observation is not open), appearing as a **sibling**
  of the `guard` Span — chain-resolved to the correct inner instance, never the outer NODE / Trace,
  never the coincidentally-indexed sibling.

In both cases the resolved Langfuse parent equals the OTel span parent for the same Generation
(`langfuse_parent_matches_otel_parent`).

## Fixture-specific invariant predicates

Per conformance-adapter §5.9, documented here.

- `no_inner_observations_dropped_under_concurrent_nesting` (case 1) — all four inner subtrees present.
- `generation_parents_under_own_lineage_calling_node_observation` (case 1) — each Generation under its
  own lineage `ask` observation, never a sibling sharing the innermost `fan_out_index`.
- `orphan_generation_parents_under_inner_fan_out_instance_observation` (case 2) — each orphan
  Generation under its inner fan-out instance observation, not the `guard` observation.
- `orphan_generation_not_under_coincidentally_indexed_sibling` (case 2) — outer 1's orphan Generation
  under the `[1, 0]` inner instance, not `[0, 0]`.
- `orphan_generation_not_under_fan_out_node_or_trace` (case 2) — never a fan-out NODE observation or
  the Trace root.
- `orphan_generation_sibling_of_calling_node_observation` (case 2) — sibling of the `guard`
  observation, not its child.
- `generation_count` — four (case 1) / two (case 2).
- `langfuse_parent_matches_otel_parent` — for every Generation the Langfuse parent observation
  corresponds to the OTel span parent (cross-backend agreement, §8.9).

**What passes:**

- Case 1: four Generations, each under its own lineage `ask` Span observation; the full two-level
  fan-out observation tree present.
- Case 2: two orphan Generations, each a sibling of its `guard` Span observation under the correct
  inner fan-out instance Span observation.

**What fails:**

- A Generation parents under the wrong inner instance (the coincident innermost `fan_out_index`
  sibling), under a fan-out NODE observation, or under the Trace root.
- Case 1: the second outer instance's inner observations are missing (dropped under concurrent
  nesting).
- Case 2: an orphan Generation parents under the `guard` observation (not open when the pre-phase call
  fires), or the Langfuse parent disagrees with the OTel parent.
