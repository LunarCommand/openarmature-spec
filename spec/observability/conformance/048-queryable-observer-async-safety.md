# 048 — Queryable observer async-safety contract (informative)

Informative fixture documenting §9.2's read-consistent floor — concurrent reads while
events are being delivered to the same observer MUST NOT return torn or partially-mutated
views, but MUST NOT guarantee event-count completeness up to a particular wall-clock instant.
The fixture exercises the contract boundary; it does not enforce a strict event-count ordering.

This fixture is marked **informative** in proposal 0048 — it documents implementation-defined
behavior at the contract boundary rather than enforcing a single deterministic outcome.

**Spec sections exercised:**

- §9.2 — Async-safety contract; read-consistent floor; post-completion stability gating.
- graph-engine §6 — Strictly-serial observer delivery queue.

**Cases:**

1. `concurrent_read_returns_consistent_non_torn_view` — Parallel-branches over two siblings
   (per pipeline-utilities §11). Both branches emit events to the same queryable observer.
   While the branches are in flight, an outer node attempts to read the observer's count.
   Asserts the read returns a non-negative integer consistent with SOME point in the event
   stream — NOT a torn pair (e.g., a counter and a per-node-map that disagree because the read
   landed mid-mutation).

**Harness extensions:** the harness MUST support emitting concurrent events into a queryable
observer (parallel-branches with both branches firing into the same observer).

**What passes (any of these — implementation-defined ordering):**

- The read returns `N` where `N` is some integer between `0` and the total events emitted up
  to that point. The exact value is NOT spec-pinned; implementations MAY interleave reads and
  writes per their async-safety implementation choice.
- The internal state surfaced by the read is **mutually consistent** — e.g., if the observer
  tracks both a total counter and a per-event-type breakdown, the breakdown's sum equals the
  total counter at the moment of read.

**What fails:**

- The read returns a torn view: an inconsistent pair where the total counter and the per-type
  breakdown disagree (the read landed mid-mutation of one or the other).
- The read raises an exception due to a concurrent mutation (the contract is read-consistent;
  raising on concurrent access violates the *no torn view* rule by panicking instead of
  serving a consistent snapshot).
- The implementation guarantees event-count completeness up to a wall-clock instant that the
  spec does NOT mandate (over-promising the contract — implementations MAY offer stricter
  guarantees but the spec floor is read-consistency only).
