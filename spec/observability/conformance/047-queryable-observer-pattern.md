# 047 — Queryable observer pattern end-to-end

Verifies §9 *Queryable observer pattern* — a concrete observer subclass with a read method
exposed on the instance, attached to a graph, is consumable by a downstream node that holds a
reference to the observer instance and calls the read method mid-invocation.

**Spec sections exercised:**

- §9 — Queryable observer pattern (attach → emit → consume cycle).
- §9.1 — Read-method contract (query-only, no routing side effects, no observer-side emission,
  non-blocking).
- §9.2 — Async-safety contract (read-consistent floor; no torn views).
- graph-engine §6 — Observer protocol baseline; observers receive events from the
  strictly-serial delivery queue.

**Cases:**

1. `queryable_observer_count_consumed_by_downstream_node` — A custom observer subclass with
   an in-memory counter incremented on every node event it receives, plus a `get_count()` read
   method returning the current value. The observer is attached at invoke time. A downstream
   node holds a reference to the observer instance and calls `get_count()` mid-invocation,
   capturing the value into a state field. **Per graph-engine §6**, observer delivery runs
   concurrently with graph execution — the engine MUST NOT await observer processing — so the
   captured count is bounded by the events emitted up to the moment of the read but
   implementations MAY have delivered any subset of them. The fixture asserts the count is a
   non-negative integer bounded above by the events emitted before the read fires (graph A → B
   → C, so by C's body 5 events have been emitted: A.started, A.completed, B.started,
   B.completed, C.started; C.completed has not yet fired). Strict equality with `5` is **not**
   a spec-conformant assertion (per §9.2's "MUST NOT guarantee that a read sees all events
   emitted up to a particular point in wall-clock time"); the range bound is.

**Harness extensions:** the harness MUST support attaching a custom observer instance to the
invocation AND providing a way for a node to reach that instance from inside its body (e.g., a
harness-provided lookup keyed on observer name). The test observer's logic is harness-supplied;
the spec contract being verified is the attach → emit → consume cycle and the read-method
contract.

**What passes:**

- The downstream node successfully reaches the observer instance and invokes `get_count()`.
- The captured count is an integer in `[0, 5]` (bounded by the events emitted before the read
  fires; the lower bound reflects §9.2's no-guaranteed-wall-clock-completeness rule).
- The observer is purely consumed — no graph state mutation by the observer; no routing
  influence; no cross-observer emission.

**What fails:**

- The downstream node cannot reach the observer instance — implementations MUST allow
  pipeline-attached observers to be referenced by nodes that hold the reference.
- The read returns a value outside `[0, 5]` (negative; > 5 — would mean events that hadn't
  been emitted yet were observed).
- The read returns a torn view (e.g., a partially-updated counter pair on observers that
  expose multiple correlated fields) — §9.2's read-consistent floor is violated.
- The observer's read method mutates graph state, influences routing, or emits to other
  observers — §9.1 violations.
