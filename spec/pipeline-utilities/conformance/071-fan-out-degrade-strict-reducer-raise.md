# 071 — fan-out degrade null slot under a strict-element reducer raises

Pins the scope boundary of proposal 0069's degrade-never-raises guarantee. 0069 rules that an
absent `collect_field` (e.g. a `FailureIsolation` degrade that omits it) is a **null slot** and the
fan-in MUST NOT raise — but **only for null-tolerant reducers** (`append`). Under a strict-element
reducer (`concat_flatten` requires each update element to be a list; `merge_all` requires mappings —
graph-engine §2), a null slot is not a valid element, so the fan-in **MUST raise `ReducerError`**.
The degrade does not suppress it. This is the strict-reducer counterpart to fixture 069 Case 2,
which exercises the same null slot under null-tolerant `append` (graceful null, no raise).

**Spec sections exercised:**

- pipeline-utilities §9.3 — absent `collect_field` → null slot; the no-raise guarantee scoped to
  null-tolerant reducers (proposal 0069's 2b caveat).
- graph-engine §2 — `concat_flatten` requires list elements; violations raise `ReducerError` (§4).

**Case `degrade_null_slot_under_concat_flatten_raises_reducer_error`:**

- Single-instance fan-out; the instance fails and the `failure_isolation` *callable* degrade sets
  only `note`, omitting the collect_field `out` → null slot (a static degraded_update omitting the
  collect_field would be a §9.8 compile error, so the omission uses the callable form).
- `target_field` `results` uses `concat_flatten` → the null slot is not a list → the fan-in raises
  `ReducerError` from the fan-out node `process`.

**What passes:**

- The null slot under `concat_flatten` raises `ReducerError` (category `reducer_error`, surfaced
  from `process`).
- The `FailureIsolation` degrade does **not** suppress the `ReducerError` — the
  degrade-never-raises guarantee is correctly scoped to null-tolerant reducers only.

**What fails:**

- The fan-in returns a graceful null (no raise) under `concat_flatten` — the impl wrongly extended
  the null-tolerant guarantee to a strict reducer.
- A different error category surfaces, or the error is raised from the wrong node.
- The degrade's null slot is silently dropped rather than reduced (so no raise occurs).
