# 0111: Fan-out Collect/Target Round-Trip Warning

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-07-28
- **Accepted:** 2026-07-29
- **Targets:** spec/pipeline-utilities/spec.md **§9.3 Per-instance fan-in** (the `projection_reducer_round_trip`
  pointer, ~L761–765): extend it so the warning also covers the fan-out **primary collect channel** — a parent
  field copied into an instance via `inputs` and collected back out via `collect_field` / `target_field`
  into that same parent field — not only the `inputs` / `extra_outputs` projection-map channel it names today.
  The warning stays defined in graph-engine §2; this proposal only widens the fan-out surface's pointer to the
  channel it currently omits. No change to graph-engine §2, to parallel-branches §11 (whose only projection-out
  channel is `outputs`, already covered by §11.4's pointer), or to any runtime behavior.
- **Related:** 0094 (defined the `projection_reducer_round_trip` warning in graph-engine §2 and added the §9.3
  fan-out pointer that named only `inputs` / `extra_outputs`; this closes the collect-channel gap in that
  pointer using the same round-trip definition and the same MUST/SHOULD-by-reducer-type rule)
- **Supersedes:**

## Summary

0094's fan-out round-trip pointer (§9.3) is **under-inclusive**. It flags a field round-tripped through the
`inputs` / `extra_outputs` projection-map channel but not the same field round-tripped through the fan-out's
**primary output channel** — `collect_field` → `target_field`. Both merge back through the parent's reducer,
so both double under a non-round-trip-idempotent reducer (`append`, `concat_flatten`, `bounded_append`,
`merge_all`); only one is currently named as warning. Because the warning is **MUST** for a canonical
non-idempotent reducer, this is a conformance-visible split: an implementation reading graph-engine §2's
general round-trip definition warns on the collect-channel round-trip, one reading §9.3's enumerated channel
does not — the same fan-out graph produces different compile-warning sets on two conforming implementations.

The fix is a one-surface widening: §9.3's pointer names the collect channel alongside the `extra_outputs`
channel, using the identical round-trip condition (same subgraph field carried in and back out into the same
parent field, into a reducer that is not round-trip-idempotent). A new fan-out conformance fixture pins the
collect-channel case (and its no-false-positive companion). This is behaviorally-normative for the same reason
0094 was: without a shared rule, two identical-looking fan-out graphs warn differently.

## Motivation

**The general definition already covers it; the fan-out pointer does not.** graph-engine §2 defines the
round-trip hazard generally: "a field projected *in* and then *back out* into the same parent field re-merges
… for a reducer that is not round-trip-idempotent … the unchanged value is merged a second time." §9.3 then
points fan-out at that warning, but names only one of the fan-out's two projection-out channels:

> A field carried into an instance via `inputs` and back out via `extra_outputs` through the same subgraph
> field round-trips through the parent's reducer; the graph-engine §2 `projection_reducer_round_trip`
> compile-time warning applies …

Fan-out has a **second, primary** projection-out channel that §9.3 itself routes through the parent's reducer:
the collected `collect_field` value is "merged … into the parent state … via the parent's reducer" for
`target_field`. A parent field seeded into each instance via `inputs` and collected straight back out via
`collect_field` / `target_field` round-trips exactly as an `extra_outputs` field does — and it is the *more
common* configuration, because collect/target is the fan-out's designed output path while `extra_outputs` is
a secondary side channel.

**The doubling is real and reproduces.** Take a parent field `results` with an `append`-family reducer, seeded
into each instance's subgraph field, and collected back out of that same field:

```
fan_out:
  subgraph: inner
  count: 2
  collect_field: acc            # subgraph field `acc`
  target_field: results         # parent field `results`
  inputs: {acc: results}        # subgraph `acc` <- parent `results`  (same field, in)
# parent: results: Annotated[list[str], concat_flatten]
```

`results`'s prior value is copied into every instance's `acc`, and every instance's `acc` is folded back into
`results` through `results`'s own reducer. Invoked with `results = ["seed"]` — each instance appending its own
item to `acc` before fan-in — the run yields `["seed", "seed", "new", "seed", "new"]`: the seed re-merged once
per instance, on top of the parent's pre-existing copy. That is precisely the
doubling the §2 warning exists to catch at compile time, and it currently goes unwarned under the §9.3
enumeration.

**Cross-implementation parity.** The warning is behaviorally-normative (graph-engine §2, MUST for a canonical
non-idempotent reducer). With §9.3 naming only the `extra_outputs` channel, an implementation that follows the
enumerated pointer emits nothing for the collect-channel round-trip while one that follows the §2 general rule
warns — a conformance-visible divergence on identical graphs, not a quality-of-implementation choice. Naming
the collect channel closes the split.

## Proposed change

### pipeline-utilities §9.3 — the round-trip pointer covers the collect channel

Extend the §9.3 `projection_reducer_round_trip` pointer so it names **both** fan-out projection-out channels:

- the `inputs` / `extra_outputs` map channel (already named), **and**
- the **primary collect channel** — a parent field `P` copied into an instance via `inputs` (`inputs`
  contains `S → P`, i.e. subgraph field `S` ← parent field `P`) and collected straight back out into that
  same parent field via `collect_field == S` and `target_field == P`.

When either channel round-trips a field into a parent reducer that is **not** round-trip-idempotent,
implementations **MUST** emit `projection_reducer_round_trip` for a §2 canonical non-idempotent reducer
(`append`, `concat_flatten`, `bounded_append`, `merge_all`) and **SHOULD** emit it for a custom reducer the
implementation classifies as non-idempotent — the same by-reducer-type rule 0094 already applies to the
`extra_outputs` channel and the general subgraph-as-node.

The collect-channel condition is fully static — `inputs`, `collect_field`, `target_field`, and the
`target_field` reducer are all fan-out config plus parent-schema data known at compile time — so, like the
`extra_outputs` case, it is deterministically classifiable and conformance-testable via
`expected_compile_warning`. The warning remains a **structural heuristic** (an implementation cannot prove the
instance left the value unchanged, so it MAY fire on a collect round-trip that legitimately replaces the
value) and changes **no runtime behavior**: the collected value still merges through the parent's reducer in
every case. Fan-out that collects a genuinely instance-computed value (a `collect_field` **not** seeded from
`target_field` via `inputs`) does **not** round-trip and MUST NOT warn on that basis, even into an `append`
reducer — the condition is the shared-field carry-in-and-back-out, not merely "collect into a growing
reducer."

### No change to graph-engine §2 or parallel-branches §11

- **graph-engine §2** already states the general round-trip definition that covers this case; its enumerated
  configurations (a)/(b)/(c) are scoped to the *general subgraph-as-node* surface (declared sets, explicit
  maps, field-name-matching default), and the fan-out and branch surfaces carry their own §9.3 / §11.4
  pointers. No §2 edit is needed.
- **parallel-branches §11** has **no** analogous gap: a `subgraph` branch projects out **only** via its
  `outputs` rename map (§11.4), which §11.4's pointer already covers; branches are heterogeneous with no
  primary collect channel ("no per-branch slot the way fan-out has one per instance," §11.7). The collect
  channel is unique to fan-out, so this proposal touches §9.3 only.

## Conformance test impact

One new pipeline-utilities fan-out fixture (number assigned at Accept), companion to the existing 077
(`extra_outputs`-channel round-trip):

- **Collect-channel round-trip — warns.** A fan-out node whose `inputs` seeds a parent field `P` (reducer
  `append` or another canonical non-idempotent reducer) into subgraph field `S`, with `collect_field == S`
  and `target_field == P`, compiles successfully and emits exactly `projection_reducer_round_trip`
  (`expected_compile_warning: [projection_reducer_round_trip]`, the exhaustive one-element list form). The
  fixture is isolated to this single round-trip — no `extra_outputs` round-trip on the same node — so the
  one-element assertion reads unambiguously (§5.8's warning list is an order-insensitive **set** of
  categories, so multiple round-trips on one node would still collapse to the single category entry).
- **No-false-positive companion — does not warn.** A fan-out node collecting a genuinely instance-computed
  `collect_field` (one **not** seeded from `target_field` via `inputs`) into a `target_field` whose reducer is
  `append` emits **no** warning (`expected_compile_warning: []`) — pinning that the trigger is the round-trip
  condition, not "collect into a growing reducer," so an over-warning implementation fails.

The SHOULD-level custom-reducer collect round-trip is not asserted by absence (an implementation MAY omit it),
consistent with 0094 keeping the custom case out of the exhaustive-list fixtures. Existing fan-out and
round-trip fixtures (042, 077) are unaffected — this adds the collect-channel case to an existing warning; it
changes none of their behavior.

## Versioning

**MINOR bump** (pre-1.0), additive-in-spirit. It broadens an existing advisory compile-time warning to a
fan-out channel the pointer omitted; it adds no new category, no runtime behavior, and no compile *error*. An
implementation already reading graph-engine §2's general round-trip definition is unaffected; one that read
§9.3's channel enumeration literally gains one more MUST-warn case. Ships as spec **v0.105.0** (pipeline-
utilities pointer text plus the new fixture).

## Alternatives considered

1. **Rule the §9.3 enumeration deliberate — collect/target is out of scope; do not warn.** Reject. It leaves
   the fan-out's *primary* output channel — the one authors reach for first — unwarned while the secondary
   `extra_outputs` side channel warns, an inverted, surprising carve-out. The doubling is identical and real
   (both merge through the parent's reducer), so exempting the primary channel defeats the warning's purpose.
   This would be a one-line PATCH clarification rather than a proposal, but it documents a footgun instead of
   flagging it.
2. **Widen graph-engine §2's (a)/(b)/(c) enumeration to name the fan-out collect channel.** Reject. §2's
   enumeration is deliberately scoped to the general subgraph-as-node projection surface; the fan-out and
   branch surfaces reach the warning through their own §9.3 / §11.4 pointers. The gap is in §9.3's pointer, so
   the fix belongs there, keeping §2 the surface-agnostic definition.
3. **Make the collect-channel round-trip a MUST compile *error*.** Reject — inconsistent with 0094, which
   made the round-trip a warning (never a failure) precisely because some round-trips legitimately replace the
   value and custom-reducer idempotency is not always statically determinable. The collect channel inherits
   the same warning-not-error stance.
4. **Also extend to parallel-branches.** Not applicable — branches have no primary collect channel; their sole
   projection-out surface is `outputs`, already covered by §11.4. No branch change is in scope.

## Open questions

- None. The round-trip condition, the MUST/SHOULD-by-reducer-type rule, and the conformance shape are all
  inherited unchanged from 0094; this proposal only names the channel 0094's §9.3 pointer omitted.

## Out of scope

- **The round-trip warning's definition, idempotency classification, and the `expected_compile_warning`
  directive** — all unchanged from 0094; this reuses them for the collect channel.
- **The `inputs` / `extra_outputs` map channel** — already covered by §9.3 and fixture 077; unchanged.
- **parallel-branches §11** — no analogous channel; unchanged.
- **Runtime fan-in semantics** — unchanged; the collected value still merges through the parent's reducer in
  every case. The warning is advisory only.
