# 073 — Parallel branches: inline-callable branch form

Verifies §11.1.1's **inline-callable branch form** (proposal 0075): a branch
given as `call` — an async function over the parent state returning a
parent-shaped partial update — rather than a compiled `subgraph` with its own
state schema + `inputs` / `outputs` projection.

## Spec coverage

- §11.1.1 — `call` branch form (alternative to `subgraph`; no projection).
- §11.4 — a callable branch's contribution is its returned partial update,
  merged via the parent reducer (buffer-then-merge, insertion order).
- §11.3 — concurrent execution (unchanged).

## Case

`callable_branches_run_without_subgraph` — a parallel-branches node with two
`call` branches (`vector`, `fts`), each an inline function returning a
parent-shaped update into a disjoint field. Both run concurrently; the returned
updates merge via the parent reducer, yielding `vector_result: 1` +
`fts_result: 2`. No subgraph, state schema, or projection map is involved. The
outer execution order is just `[retrieve]` — the node is one dispatch (§11.6).

## Anti-cases (would indicate a broken implementation)

- A callable branch's returned update is dropped or not merged via the parent
  reducer — the `call` form's contribution path (§11.4) isn't wired.
- The `call` form is rejected as requiring a `subgraph` — the alternative branch
  form isn't recognized.
