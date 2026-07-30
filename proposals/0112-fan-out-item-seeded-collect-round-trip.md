# 0112: Fan-out Item-Seeded Collect Round-Trip

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-07-29
- **Accepted:** 2026-07-29
- **Targets:** spec/pipeline-utilities/spec.md **§9.3 Per-instance fan-in** (the collect-channel round-trip
  clause added by 0111, ~L768–777): extend the round-trip condition so the collect channel warns when the
  `collect_field` is seeded from `target_field` by **either** fan-out projection-in mechanism — the `inputs`
  whole-value copy 0111 named, **or** the `items_field` / `item_field` per-item spread (the default fan-out
  mode) 0111 missed. Extends fixture **078** with an item-seeded round-trip case and an item-seeded
  no-false-positive case (no new fixture file). No change to the `inputs` / `extra_outputs` map channel, to
  graph-engine §2, to parallel-branches §11, or to any runtime behavior.
- **Related:** 0111 (added the collect-channel round-trip warning but scoped its seeding condition to
  `inputs`; this closes the item-seeding gap using the identical round-trip structure and MUST/SHOULD-by-
  reducer-type rule), 0094 (defined `projection_reducer_round_trip`), 0005 (fan-out `items_field` / `item_field`
  per-item projection)
- **Supersedes:**

## Summary

0111 closed the fan-out collect-channel round-trip only for `inputs`-based seeding. Fan-out has **two**
projection-in mechanisms, and the other one — `items_field` / `item_field`, the **default** fan-out mode —
seeds the collect field just as `inputs` does: it hands each instance one *element* of the `target_field`
list. When that seeded field is collected straight back into the same `target_field` through a
non-round-trip-idempotent reducer, it doubles once per instance, exactly as the `inputs`-seeded case does — but
0111's condition ("seeded from `target_field` via `inputs`") does not name it, so the more common spelling goes
unwarned. This proposal extends §9.3's collect-channel round-trip condition to cover both seeding spellings and
adds the item-seeded cases to fixture 078. It is behaviorally-normative for the same reason 0111 was: without
it, two implementations warn differently on the same default-mode fan-out graph.

## Motivation

**The default fan-out mode seeds the collect field, and 0111 missed it.** §9.1 defines two ways a subgraph
field is populated at instance entry: `inputs` (a whole parent value copied in) and `item_field` (one element
of the `items_field` list assigned in). 0111's round-trip condition names only the first. The second is not an
exotic corner — `items_field` / `item_field` is the default fan-out mode (`inputs` is the optional extra), so
the unwarned spelling is the *more* common one.

**The doubling is real and reproduces in the default mode.** Fan out over a parent list, assign each element
to a subgraph field, and collect that same field straight back into the same parent list:

```
fan_out:
  subgraph: inner
  items_field: results        # spread parent `results` element-wise...
  item_field: acc             # ...into subgraph `acc` (one element per instance)
  collect_field: acc          # collect that SAME field...
  target_field: results       # ...back into `results`
# parent: results: Annotated[list[str], append]
```

`results` is decomposed into per-instance `acc` values, and each instance's `acc` is appended back into
`results` through its own reducer. Invoked with `results = ["a", "b"]`, the run yields `["a", "b", "a", "b"]` —
the list re-merged on top of itself. That is the same round-trip hazard §2 warns about, on the same primary
collect channel, in the default spelling; under 0111 it compiles with zero warnings.

**The no-carve-out reasoning applies with equal force.** 0111 declined to exempt the primary collect channel
because warning the secondary `extra_outputs` channel while staying silent on the primary one would be
backwards. The same asymmetry recurs one level down: warning the `inputs` seeding spelling while staying
silent on the *default* `items_field` spelling is no more defensible. The hazard, the reducer, and the
doubling are identical; only the seeding mechanism differs.

## Proposed change

### pipeline-utilities §9.3 — the collect-channel round-trip covers both seeding spellings

Restate the collect-channel condition so it fires whenever the `collect_field` is seeded from `target_field`,
by either projection-in mechanism:

- **`inputs` whole-value copy** — an `inputs` entry keys `collect_field` to `target_field` (the 0111 case); or
- **`items_field` / `item_field` per-item spread** — `item_field` equals `collect_field` and `items_field`
  equals `target_field`, so each element of the `target_field` list is spread into the collected field.

In both spellings, the same field is seeded from `target_field` and collected straight back into that same
`target_field`; a round-trip into a non-round-trip-idempotent reducer doubles it once per instance, so
implementations **MUST** emit `projection_reducer_round_trip` for a §2 canonical non-idempotent reducer and
**SHOULD** emit it for a classified-custom one — the same by-reducer-type rule 0111 and 0094 already apply. A
`collect_field` seeded from **neither** mechanism (or whose seed is a *different* parent field — e.g. the
`items_field` list is `target_field` but `item_field` is not `collect_field`, so the collected field is
instance-computed, not the spread element) does not round-trip and does not warn on that basis.

Both spellings are statically determinable — `inputs`, `items_field`, `item_field`, `collect_field`,
`target_field`, and the `target_field` reducer are all fan-out config plus parent-schema data known at compile
time — so the warning stays a deterministic, conformance-tested compile-time diagnostic and remains a
structural heuristic (it may fire on a round-trip that legitimately replaces the value).

### No change to graph-engine §2, the map channel, or parallel-branches §11

- **graph-engine §2**'s general round-trip definition ("the same subgraph field carries a parent value in and
  back out into that same parent field") already covers item-seeding; its enumerated cases are
  general-subgraph-scoped, and the fan-out surface reaches the warning through §9.3's pointer. No §2 edit.
- The **`inputs` / `extra_outputs` map channel** is unchanged (0111 / 0094).
- **parallel-branches §11** is unaffected — a branch projects out only via its `outputs` map and has no
  per-item seeding or primary collect channel.

## Conformance test impact

Extends the existing fan-out collect round-trip fixture **078** (no new file) with two cases, using a second
subgraph whose seeded field is scalar (each `items_field` element is a single value):

- **Item-seeded round-trip — warns.** `items_field: results`, `item_field: acc`, `collect_field: acc`,
  `target_field: results` (reducer `append`) → the spread field is collected straight back → compiles with
  `expected_compile_warning: [projection_reducer_round_trip]`.
- **Item-seeded, different collect — does not warn.** `items_field: results`, `item_field: acc`, but
  `collect_field` is a *different*, instance-computed field into `target_field: results` (`append`) → not a
  round-trip (the seeded field is not the collected one) → `expected_compile_warning: []`. Pins that fanning
  over `target_field` alone does not trigger; only collecting the *seeded* field back does.

The two cases 0111 added to 078 (the `inputs`-seeded round-trip and the no-seed clean collect) are unchanged.
No fixture count change (078 gains cases, not a new file).

## Versioning

**MINOR bump** (pre-1.0), additive. Broadens the 0111 collect-channel warning to the second seeding spelling;
no new category, no runtime behavior change, no compile error. An implementation already reading graph-engine
§2's general round-trip definition is unaffected; one that read 0111's `inputs`-scoped condition literally
gains the item-seeded MUST-warn case. Ships as spec **v0.106.0** (pipeline-utilities §9.3 text plus the two new
fixture 078 cases).

## Alternatives considered

1. **Keep the condition `inputs`-scoped; do not warn on item-seeding.** Reject. It leaves the *default* fan-out
   mode's collect round-trip unwarned while the optional `inputs` spelling warns — the same inverted asymmetry
   0111 rejected for the primary-vs-secondary channel, now for the default-vs-optional seeding. The doubling is
   identical and more likely to be hit.
2. **Widen graph-engine §2's enumeration to name the item-seeding case.** Reject — §2's enumeration is
   general-subgraph-scoped; item-seeding is a fan-out concept, so the fix belongs in §9.3's pointer, keeping §2
   surface-agnostic.
3. **A new fixture rather than extending 078.** Reject — 078 is the fan-out collect round-trip fixture; the
   item-seeded cases belong alongside the `inputs`-seeded ones, and keeping them together makes the seeding
   spellings a single comparable set.

## Open questions

- None. The round-trip structure, the MUST/SHOULD-by-reducer-type rule, and the conformance shape are all
  inherited from 0111 / 0094; this proposal only adds the second seeding spelling 0111's condition omitted.

## Out of scope

- **`count` mode** — no per-item seeding, so no item-seeded round-trip; the `inputs` channel (0111) still
  applies in `count` mode.
- **The `inputs` / `extra_outputs` map channel and the round-trip warning's definition** — unchanged from
  0111 / 0094.
- **parallel-branches §11** — no analogous seeding or collect channel; unchanged.
- **Runtime fan-in semantics** — unchanged; the warning is advisory only.
