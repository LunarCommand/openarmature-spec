# 0075: Parallel-Branches Lightweight Callable Branches and Conditional Branches

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-18
- **Accepted:** 2026-06-18
- **Targets:** spec/pipeline-utilities/spec.md (§11 *Parallel branches* — §11.1.1 *Branch spec* gains an **inline-callable branch form** (`call`, an async function over the parent state returning a partial update) as an alternative to the compiled-`subgraph` form; §11.4 defines the callable branch's contribution; a new §11.10 *Conditional branches* adds an optional `when` predicate on any branch spec; notes in §11.6 / §11.7 / §11.8 / §11.9 cover how the callable form and skipped branches compose). spec/graph-engine/spec.md (§6 — a callable branch emits its observer `started` / `completed` pair keyed by its `branch_name`, since it is the unit of work; a `when`-skipped branch emits nothing). spec/observability/spec.md (§5.7 — a callable branch renders a branch span under its `branch_name` via the existing machinery; a skipped branch has no span). Plus new conformance fixtures under spec/pipeline-utilities/conformance/.
- **Related:** 0011 (parallel branches — the primitive this extends), 0044 (parallel-branches dispatch span — the §5.7 / graph-engine `branch_name` surface a callable branch reuses), 0050 / 0065 / 0074 (failure-isolation middleware + `catch` — reused per-branch for per-leg degrade), 0036 (fan-out collection reducers — the parent-reducer fan-in model §11.4 shares).
- **Supersedes:**

## Summary

`ParallelBranchesNode` (§11) requires each branch to be a **compiled subgraph** with its own state
schema and `inputs` / `outputs` projection (§11.1.1). For the common shape *"M heterogeneous lightweight
parallel calls over shared state, each independently failure-isolated"* — two SQL reads, two API fetches,
hybrid vector + full-text retrieval — that ceremony is too heavy, so consumers drop to a hand-rolled
concurrent-gather plus a bespoke per-result classify, forfeiting the correct cancellation discipline and
the per-leg observer events the primitive already provides.

This proposal extends `ParallelBranchesNode` rather than adding a third parallel primitive. It lands two
additive features: (1) an **inline-callable branch form** — a branch can be an async function over the
parent state that returns a partial update, with no subgraph / state schema / projection map; and (2)
**conditional branches** — an optional `when` predicate that skips a branch at dispatch when it does not
apply. Everything else the shape needs — concurrent execution (§11.3), fail-fast cancellation (§11.5),
per-branch failure-isolation + `FailureIsolatedEvent`s (§11.7), and reducer fan-in (§11.4) — already
exists and is reused unchanged. Existing subgraph branches are untouched.

## Motivation

A downstream consumer upgrading onto the native `ParallelBranchesNode` found three parallel-read sites of
the same shape — fire two independent reads concurrently, both scoped by shared inputs, each degradable on
its own (hybrid recall: vector ∥ full-text; paired DB reads). They evaluated `ParallelBranchesNode` and
kept a hand-rolled gather each time, because the per-"branch" cost was two state classes + two
single-node compiled subgraphs + two projection maps to replace what is really *"call this one function"*
— and one leg was **conditional** (skipped when there is no embedding), which a static branch set cannot
express without an always-run self-no-op branch.

The important point is that `ParallelBranchesNode` **already solves the hard parts** the hand-rolled
gather gets wrong: §11.5 has the engine cancel still-running branches correctly (so teardown / cancellation
propagates rather than being swallowed, a footgun of a naive `return_exceptions`-style gather), and §11.7
branch middleware (a `FailureIsolationMiddleware`) already emits a per-branch `FailureIsolatedEvent` on
degrade. So the gather sites are re-deriving — buggily — machinery the primitive has. The *only* real
barrier is the subgraph-ceremony weight plus the missing conditional. Removing those two makes the
correct, observable primitive adoptable for this shape; it does not add new concurrency, cancellation, or
observability surface.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Both features are additive — `call` is an alternative to
`subgraph` (existing subgraph branches unchanged), and `when` is optional (absent ⇒ the branch always
dispatches, current behavior). Concrete version is the maintainer's call at acceptance.

### §11.1.1 — inline-callable branch form

A branch spec's work is given by **exactly one of**:

- `subgraph` — a compiled subgraph reference (the current form), with its optional `inputs` / `outputs`
  projection (§11.2 / §11.4) and its own state schema.
- `call` — an **async function over the parent state** returning a partial update: `(parent_state) ->
  partial_update`. No subgraph, no state schema, no `inputs` / `outputs`. The function reads the parent
  state directly and returns parent-shaped fields.

The two forms are mutually exclusive on a single branch (declaring both is a compile-time
`parallel_branches_invalid_branch_spec` error — a new §11.9 category); a parallel-branches node MAY mix
subgraph branches and callable branches freely. Both forms carry the same optional `middleware` (§11.7)
and the new `when` (§11.10). A callable branch is the heterogeneous-parallel analogue of the lightweight
node body — the unit of work is one function, not a graph.

### §11.4 — callable-branch contribution

A subgraph branch builds its contribution by projecting its exit state through `outputs`. A **callable
branch's contribution is simply the partial update it returns** — parent-shaped already, so no projection
step. It is buffered and merged into parent state via the parent's reducer for each field, in branch
insertion order, exactly as §11.4 already specifies for subgraph-branch contributions (the buffer-then-
merge-once-at-completion model, deterministic per §11.8). Parent fields the callable does not return get
no contribution from that branch (partial contributions are first-class per §11.7); references in the
returned update to fields not declared on the parent state are a `state_validation_error` at merge time,
per the normal §4 / graph-engine contract.

### §11.10 — Conditional branches (new)

Any branch spec (subgraph or callable) MAY carry an optional **`when`** predicate `(parent_state) ->
bool`, evaluated **once at dispatch** against the parent state the parallel-branches node received:

- `when` absent (default) — the branch always dispatches (current behavior, unchanged).
- `when` returns `true` — the branch dispatches normally.
- `when` returns `false` — the branch is **skipped**: it is not dispatched, runs no work, contributes
  nothing to parent state, and emits no observer events and no span (§5.7). It simply does not appear in
  the run.

The `branches` mapping and its insertion order are unchanged; skipping is a runtime decision over the
declared set, not a change to the set. Among the branches that *do* dispatch, §11.8's insertion-order
determinism is unchanged. If **every** branch is skipped, the parallel-branches node completes as a no-op
(contributes nothing) — this is valid and distinct from the compile-time `parallel_branches_no_branches`
error (§11.9), which fires only on an empty *declared* mapping.

`when` is a deterministic function of dispatch-time parent state, so graph-engine §5 determinism holds:
the same input yields the same skipped set. (A `when` that consults nondeterministic sources is the same
SHOULD-document caveat §7 already states for conditional middleware.)

### §11.7 — failure-isolation on callable branches

A callable branch carries `middleware` like any branch, so per-leg failure-isolation is the existing
§11.7 branch-middleware contract applied to a callable branch: wrap the callable in a
`FailureIsolationMiddleware` (now category-gated via `catch`, proposal 0074) and a failing leg emits a
`FailureIsolatedEvent` and contributes its degraded update (or nothing). §11.7's *Branch-middleware
degrade* partial-contribution rule applies unchanged — a callable branch that degrades to a subset of
fields contributes only those. No new per-leg config (the request's "on-leg-error") is introduced;
per-leg degrade is branch middleware, exactly as for subgraph branches.

### Observer events and spans

A callable branch has no inner nodes, so **it is the unit**: it emits one `started` / `completed`
observer pair on the graph-engine §6 stream, keyed by its `branch_name` (the branch's key in the
`branches` mapping) as its event-source identity — paralleling how a subgraph branch's inner nodes carry
`branch_name`, but with the branch itself as the single emitting unit. The bundled OTel observer renders
it as a branch span under `branch_name` via the existing §5.7 machinery (no new attribute). A
`when`-skipped branch emits neither event nor span. Failure-isolation on a callable branch emits its
`FailureIsolatedEvent` per §11.7 as above.

## Conformance test impact

New fixtures under `spec/pipeline-utilities/conformance/` (the callable-branch `call` form and the `when`
predicate are expressed in the fixture `branches` directive, self-documented in the fixtures' headers,
paralleling the existing subgraph-branch directive):

- **073** — inline-callable branches basic: two `call` branches over shared parent state run concurrently
  and their returned partial updates merge into disjoint parent fields (no subgraph / projection).
- **074** — conditional `when` skip: a parallel-branches node with one branch carrying `when` that
  evaluates `false`; that branch is skipped (contributes nothing, no event), the sibling runs.
- **075** — per-leg failure-isolation on a callable branch: a `call` branch wrapped in
  `FailureIsolationMiddleware` raises, degrades to its configured update, and emits a
  `FailureIsolatedEvent`; the sibling branch completes normally.

The existing parallel-branches fixtures (032–036) are unchanged.

## Alternatives considered

- **A third primitive (a dedicated lightweight parallel-legs node).** Rejected: a "leg" is a degenerate
  branch (one function over parent state); a third parallel primitive alongside fan-out and
  parallel-branches is surface proliferation with a blurred boundary. Extending §11 reuses its
  concurrency, cancellation, isolation, observability, and fan-in wholesale.
- **A runtime-determined branch set** (compute *which* and *how many* heterogeneous branches at runtime).
  Out of scope: the declared set plus conditional skip covers the motivating need. A fully runtime-invented
  set is a larger, separable design (per-unit identity / resume / determinism implications) deferred to a
  future proposal if a workload requires it.
- **Express the conditional through graph routing instead of `when`.** Rejected: the branch set lives
  inside a single node; routing (conditional edges) operates *between* nodes and cannot skip one branch
  within a parallel-branches node. The condition belongs on the branch.
- **An always-run no-op branch for the conditional case.** Rejected: it clutters the trace with a no-op
  span and wastes a dispatch; `when` states the intent directly and produces a clean (absent) trace.
- **Give callable branches `inputs` / `outputs` projection too (symmetry with subgraph branches).**
  Rejected: a callable reads parent state and returns parent-shaped updates directly — projection is the
  subgraph form's concern. Adding it would re-import the ceremony this form exists to drop.
- **Do nothing — keep the hand-rolled gather.** Rejected: the gather forfeits the correct cancellation
  discipline (§11.5) and the per-leg `FailureIsolatedEvent`s (§11.7) the primitive already provides; the
  weight barrier is the only reason consumers avoid it, and this proposal removes it.

## Open questions

- **All-branches-skipped guard.** This proposal makes an all-skipped parallel-branches node a valid
  no-op. If a workload later wants an "at least one branch must dispatch" assertion, that is a small
  additive follow-on (a node-level flag), not a v1 concern.
