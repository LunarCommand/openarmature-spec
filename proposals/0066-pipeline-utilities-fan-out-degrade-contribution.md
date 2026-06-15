# 0066: Pipeline Utilities — Fan-Out Failure-Isolation Degrade Contribution

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-14
- **Accepted:** 2026-06-15
- **Targets:** spec/pipeline-utilities/spec.md (§9.3 — specify that a `FailureIsolation`-degraded fan-out instance is a §9.3 *success* whose contribution **is its `degraded_update`**, with `collect_field` and each `extra_outputs` `subgraph_field` read from the `degraded_update` by subgraph field name; §9 — a new compile-time validation that a **static** `degraded_update` on a fan-out `instance_middleware` `FailureIsolation` covers `collect_field`, with the **callable** form contributing a null slot gracefully at runtime if it omits it (never a raise); §11.4 / §11.7 — confirm the heterogeneous parallel-branches *skip*; a new compile-time error category `fan_out_degraded_update_missing_collect_field`, defined in §9 the same way §11.9 defines `parallel_branches_no_branches`); plus a new conformance fixture
- **Related:** 0050 (`FailureIsolationMiddleware` + `degraded_update`, pipeline-utilities §6.3), 0065 (cause fidelity at non-node placements — wiring its fixture 064 surfaced this), 0009 / 0036 (fan-out collection + `instance_middleware`, §9.3 / §9.7), 0011 (parallel branches — §11.4 / §11.7), graph-engine §2 (compile-time validation / error categories)
- **Supersedes:**

## Summary

Proposal 0050's `FailureIsolationMiddleware` can run as fan-out instance middleware (§9.7). When
it catches and degrades an instance, **what that instance contributes to the homogeneous
collection** (`collect_field` → `target_field`) is a real semantic question §9.3 leaves
unsettled — and a homogeneous N-items-→-N-results collection makes it load-bearing (unlike the
heterogeneous parallel-branches case, where partial contributions are first-class).

This proposal settles it:

1. **A degraded instance is a success, and its contribution *is* the `degraded_update`.**
   `FailureIsolation` catches the failure and returns the subgraph's projected partial update
   (§9.7), so the engine sees a normal completion, not a failure — the instance keeps its slot
   (slot omission, §9.5, is for genuinely-failed instances only). The `degraded_update` **is** the
   instance's projected contribution: §9.3 reads `collect_field` and each `extra_outputs`
   `subgraph_field` **from the `degraded_update` mapping**, by subgraph field name. It is **not**
   merged onto the instance's pre-failure subgraph state — failure isolation substitutes a clean,
   caller-specified result for the failed computation rather than reconstructing partial state.
2. **Guard the slot footgun at compile time; stay graceful at runtime.** Because the
   `degraded_update` is the contribution, a degraded instance that omits `collect_field` leaves
   its slot null — almost always a misconfiguration in a homogeneous collection downstream
   indexes positionally. OA's strict-over-silent posture rejects that. But a *runtime* raise would
   (under `fail_fast`) stop the graph — isolation defeating its own purpose — so the guard lands at
   **graph-compile time** for the **static** `degraded_update` form (caught at construction), and
   the **callable** form (not statically checkable) contributes a null slot gracefully at runtime,
   never raising.
3. **Confirm the parallel-branches counterpart.** Heterogeneous branch middleware (§11.4) that
   omits a projected `outputs` field contributes nothing for it (the parent keeps its prior /
   sibling value) — the deliberate asymmetry with fan-out's slot-required rule.

## Motivation

**Why now.** This surfaced while wiring 0065's fixture 064. Fan-out's collection is
**homogeneous** — N items each contribute one value into a single collection via `collect_field`
→ `target_field`, positionally — so "what does a degraded instance put in slot N" is a genuine
semantic question. (Parallel-branches is *heterogeneous*: each branch contributes its own distinct
parent fields, so a partial / skipped contribution is already first-class. That asymmetry is the
crux of the differing answers.)

**The model decision.** §9.3 / §9.7 do not unambiguously say whether a degraded instance's
contribution is **(ii)** its `degraded_update` (the projected partial the middleware returns) or
**(i)** the `degraded_update` merged onto the instance's pre-failure subgraph state. This proposal
adopts **(ii)**: the `degraded_update` *is* the contribution. Model (i) would make a degraded
instance's collected value depend on how far the subgraph progressed before failing — a
half-computed pre-failure value, or the schema default — which is unpredictable and a silent
footgun, and it is in tension with the slot-coverage guard below (under a merge, an omitted
`collect_field` is not necessarily "missing"). Model (ii) is predictable (the degraded result is
exactly what the caller specified, independent of subgraph progress) and matches failure
isolation's purpose: substitute a known-good fallback, not reconstruct unreliable partial state.

**The footgun, under model (ii).** A degraded instance whose `degraded_update` omits
`collect_field` contributes **no value for its slot** — a null lands in `target_field` at that
position, indistinguishable from a legitimate null and silently consumed by the reducer.
OA consistently rejects exactly this kind of silent-but-wrong value (strict-undefined prompt
variables; 0065's cause-fidelity not masking the real error; 0041's reserved-key rejection).

**Why the guard cannot be a runtime raise.** The obvious strict fix — raise when a degraded
instance's `degraded_update` omits `collect_field` — is self-defeating. A degrade-time raise
behaves like any instance failure: under `error_policy: fail_fast` it cancels siblings and
propagates a `node_exception` (§9.5), **stopping the graph** (or hitting an outer middleware);
under `collect` it records the instance in `errors_field`, turning a would-be degraded *success*
into a *failure*. Either way, the mechanism the developer added to keep the graph running becomes
the thing that breaks it — and only when a degrade path actually fires, possibly in production.
The strictness therefore belongs at **compile time**, where erroring is the expected, safe outcome
and the running graph is never affected.

## Detailed design

The proposed normative changes are below. Anticipated bump: **MINOR** (pre-1.0). The concrete
spec version is assigned at acceptance.

### pipeline-utilities §9.3 — the degraded-instance contribution

§9.3 gains a paragraph specifying the degrade-path contribution:

> **Degraded instances.** A fan-out instance whose `instance_middleware` chain includes a
> `FailureIsolationMiddleware` (§6.3) that catches and returns a `degraded_update` **completes
> successfully** from the fan-out's perspective — the middleware returns the subgraph's projected
> partial update (§9.7), so the engine sees a normal instance completion, not a failure. Slot
> omission (§9.5) applies only to genuinely-failed (uncaught) instances; a degraded instance is
> never dropped from the collection. The instance's projected contribution **is the
> `degraded_update`**: §9.3 reads `collect_field`'s value, and each `extra_outputs`
> `subgraph_field`'s value, **from the `degraded_update` mapping**, by subgraph field name (the
> `degraded_update` is a subgraph-space partial, §9.7). The `degraded_update` is **not** merged
> onto the instance's pre-failure subgraph state for projection — failure isolation substitutes a
> clean result for the failed computation. When the `degraded_update` does not supply
> `collect_field`, the instance's slot is **null** (its positional slot is preserved — see the
> compile-time and runtime rules in §9). When the `degraded_update` does not supply an
> `extra_outputs` `subgraph_field`, that field is simply not contributed by this instance (its
> parent reducer sees no contribution from it — the same partial-contribution shape as a skipped
> heterogeneous branch field, §11.4).

### pipeline-utilities §9 — compile-time `collect_field` coverage for static `degraded_update`

A new compile-time validation (reported per the graph-engine §2 compile-time error contract, with
its error category defined here in §9, mirroring `parallel_branches_no_branches` in §11.9):

> **Fan-out degrade slot coverage.** When a fan-out node's `instance_middleware` includes a
> `FailureIsolationMiddleware` whose `degraded_update` is a **static mapping**, the graph MUST be
> rejected at compile time if that mapping does not include `collect_field`. Because the
> `degraded_update` is the instance's contribution (§9.3) and the collection is homogeneous (one
> positional slot per instance), a static `degraded_update` omitting `collect_field` would leave
> that slot null — a misconfiguration the spec catches at construction rather than letting a
> silent null reach the collection. The error category is
> `fan_out_degraded_update_missing_collect_field` (reported per the graph-engine §2 compile-time
> error contract).
>
> When `degraded_update` is the **callable** form (`(state) -> partial_update`, §6.3), its output
> is not knowable at compile time, so no compile-time check applies. At runtime, a callable that
> omits `collect_field` yields a **null** slot per §9.3; the degrade path MUST remain graceful — it
> MUST NOT raise on an omitted `collect_field`, because a degrade-time raise would convert the
> isolation into a graph-stopping failure (§9.5). Callable `degraded_update`s that degrade fan-out
> instances SHOULD set `collect_field`.

Scope note: the compile check covers `collect_field` only — the homogeneous slot. `extra_outputs`
fields are secondary, non-slot contributions merged via their own reducers; an omitted one is
simply not contributed by that instance (§9.3), with no compile requirement.

### pipeline-utilities §11.4 / §11.7 — confirm the parallel-branches skip

§11 gains a clarifying note (no behavior change):

> **Branch-middleware degrade.** A `FailureIsolationMiddleware` running as branch middleware
> (§11.7) that returns a `degraded_update` not covering a projected `outputs` field contributes
> nothing for that field — the parent retains its prior / sibling-branch value, per §11.4's
> buffer-then-merge model. Parallel branches are heterogeneous (each branch contributes its own
> distinct parent fields), so a partial contribution is first-class; there is no per-branch "slot"
> the way fan-out has one per instance. This is the deliberate counterpart to §9's fan-out
> slot-coverage rule: heterogeneous → partial contributions skip; homogeneous → the slot
> (`collect_field`) is required (compile-checked for the static `degraded_update` form).

## Conformance test impact

A new fixture under `pipeline-utilities/conformance/` (number assigned at acceptance) exercising
the degrade contribution on fan-out, with `extra_outputs`:

- **Slot filled + extra_outputs from the degraded_update.** A single-instance fan-out with
  `instance_middleware` `[FailureIsolation, Retry]` whose static `degraded_update` supplies both
  `collect_field` and an `extra_outputs` `subgraph_field`; the instance degrades. Assert the
  collection slot holds the degrade `collect_field` value AND the `extra_outputs` value reaches the
  parent field — both read from the `degraded_update` by subgraph field name.
- **Static omit → compile error.** A fan-out whose `FailureIsolation` static `degraded_update`
  omits `collect_field`; assert graph compilation fails with
  `fan_out_degraded_update_missing_collect_field` (no execution).
- **Callable omit → null slot, no stop.** A callable `degraded_update` that omits `collect_field`;
  assert the instance contributes a **null** slot, the collection keeps N slots, and the graph does
  NOT stop (no raise on the degrade path).
- **Parallel-branches skip.** A branch-middleware `FailureIsolation` whose `degraded_update` omits
  a projected `outputs` field; assert the parent keeps its prior value (skip), with no compile
  error and no raise.

The existing 0065 fixture 064 (whose cases all *supply* `collect_field`) passes unchanged — this
proposal adds the omit-case rules, which 064 does not exercise.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments (concrete version
assigned at acceptance):

- §9.3 gains the *Degraded instances* paragraph (contribution = the `degraded_update`).
- §9 gains the compile-time *Fan-out degrade slot coverage* rule and the
  `fan_out_degraded_update_missing_collect_field` compile-time error category.
- §11 gains the *Branch-middleware degrade* confirmation note.
- A new conformance fixture covers the slot / compile-error / callable-null / branch-skip cases.

**Behavior-change note.** The only new *behavior* is the compile-time error for a static
`degraded_update` omitting `collect_field` on a fan-out instance-middleware `FailureIsolation` — a
construction-time rejection of a misconfiguration. Runtime degrade behavior for correctly
configured graphs is unchanged, and the runtime degrade path never raises (a callable that omits
`collect_field` yields a null slot, gracefully).

## Out of scope

- **Model (i): merging the `degraded_update` onto the pre-failure subgraph state.** Rejected — it
  makes the collected value depend on how far the subgraph progressed before failing
  (half-computed value, or schema default), which is unpredictable and a silent footgun, and it is
  in tension with the slot-coverage compile check. Model (ii) — the `degraded_update` *is* the
  contribution — is predictable and consistent. (See Motivation.)
- **A runtime raise on the omit case.** Rejected — it converts isolation into a graph-stopping
  failure (§9.5) and surfaces only at the degrade path. The guard is compile-time; runtime stays
  graceful.
- **Dropping a degraded instance from the collection (N → N-1).** Rejected — a degraded instance
  is a success, not a failure; dropping breaks the positional slot-per-item invariant. Omission
  (§9.5) is for genuinely-failed instances only.
- **Compile-time coverage of `extra_outputs` fields.** Out of scope — `extra_outputs` are
  secondary, reducer-merged contributions, not the homogeneous slot; an omitted one is simply not
  contributed (§9.3). Could be revisited if a real workload shows a need.
- **Compile-time validation of callable `degraded_update`s.** Not possible (output unknown at
  build); the callable form is graceful-at-runtime (null slot, no raise).
- **Reopening 0065 or the parallel-branches branch-middleware state-space fix.** Settled.

## Alternatives considered

- **Model (i) — merge `degraded_update` onto pre-failure subgraph state.** The §9.3 "final value"
  language *could* be read as projecting `collect_field` from a merged final subgraph state. Rejected
  for the reasons above (unpredictable, silent footgun, tension with the compile check); model (ii)
  is cleaner and predictable.
- **Always-graceful, no compile check.** Never stops the graph, but a static `degraded_update` that
  forgets `collect_field` silently emits a null into the collection. Rejected: the compile check
  catches the common (static) misconfiguration early at no runtime cost; OA's strict-over-silent
  posture.
- **Runtime raise on omit.** Rejected — self-defeating; see Motivation / Out of scope.
- **Drop the degraded instance (option B).** Rejected — degrade ≠ failure; breaks the
  slot-per-item invariant.
- **Symmetric treatment of fan-out and parallel-branches.** Rejected — the homogeneous (fan-out,
  slot-per-item) vs heterogeneous (parallel-branches, distinct fields) distinction is real and
  load-bearing; a uniform "skip" would reintroduce the fan-out slot footgun, and a uniform
  "require" would wrongly force every branch to cover fields it has no stake in.
