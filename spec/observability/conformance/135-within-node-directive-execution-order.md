# 135 — Within-Node Directive Execution Order

Pins conformance-adapter §8.3's **Directive execution order** rule: a node's
sibling directives execute in fixture-document order. The two cases place the
**same** two order-sensitive directives — `augment_metadata` (a §3.4 write) and
`capture_invocation_metadata_into` (a §3.4 point-in-time read) — in opposite
document order, and the captured snapshot diverges, which can hold only if the
adapter executes them in document order (not sorted-by-key, not arbitrary).
Fixtures 043/045 exercise the rule incidentally; this pins it directly.

**Spec sections exercised:**

- conformance-adapter §8.3 *Execution* — the *Directive execution order* rule.
- observability §3.4 — the `set` / `get_invocation_metadata` write/read composition (the order-sensitive directives).

## Case 1 — `augment_then_capture_sees_the_write`

Document order: `augment_metadata: {marker: set}` then
`capture_invocation_metadata_into: captured`. The capture runs after the write,
so `captured` = `{tenantId: T1, marker: set}`.

- `capture_after_augment_sees_write` — the snapshot contains `marker`.

## Case 2 — `capture_then_augment_misses_the_write`

The same two directives, opposite document order:
`capture_invocation_metadata_into: captured` then `augment_metadata: {marker: set}`.
The capture is a point-in-time read taken before the augment, so `captured` =
`{tenantId: T1}` only.

- `capture_before_augment_misses_write` — the snapshot omits `marker`.

## What proves the rule

The only difference between the two cases is directive order; the divergent
`captured` snapshots (`{T1, marker}` vs `{T1}`) are reproducible only when the
adapter honors document order. A sorted-by-key or arbitrary-order adapter would
produce the same result for both cases (or a nondeterministic one), failing one.

## Fixture-specific invariant predicates

Per conformance-adapter §5.9, documented here:

- `capture_after_augment_sees_write` — case 1's capture observed the augment's write.
- `capture_before_augment_misses_write` — case 2's capture ran before the augment and did not observe its write.
