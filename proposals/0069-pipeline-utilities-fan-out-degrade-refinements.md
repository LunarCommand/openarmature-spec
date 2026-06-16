# 0069: Pipeline Utilities — Fan-Out Degrade Contribution Refinements

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-15
- **Targets:** spec/pipeline-utilities/spec.md (§9.3 — three refinements to the fan-out degrade-contribution rules 0066 introduced: (1) correct the omitted-`extra_outputs` rule from "not contributed / like a skipped heterogeneous branch field" to **null at the instance's positional slot**, mirroring `collect_field`'s null slot and preserving index-alignment with `target_field`; (2) add a SHOULD that a non-degrade `instance_middleware` return covers `collect_field`, with an absent `collect_field` on **any** fan-in path yielding a **null slot** and the fan-in MUST NOT raise on it — generalizing §9.8's degrade-never-raises to all paths; (3) a new conformance fixture pinning a degraded instance's slot across a checkpoint + resume round-trip)
- **Related:** 0066 (the §9.3 degrade-contribution model + §9.8 compile check these refine), 0050 (`FailureIsolationMiddleware`, §6.3), 0009 / 0036 (fan-out collection + `instance_middleware`, §9.3 / §9.7), 0008 (checkpointing — the resume path the new fixture exercises), graph-engine §2 (reducers — `extra_outputs` merge in instance-index order)
- **Supersedes:** 0066 (the §9.3 omitted-`extra_outputs` "not contributed" clause only; the rest of 0066 — the degrade-*is*-the-contribution model, the §9.8 `collect_field` compile check, and the §11.7 branch skip — stands unchanged)

## Summary

0066 settled what a `FailureIsolation`-degraded fan-out instance contributes:
the degraded instance is a §9.3 *success* whose contribution **is** its
`degraded_update`, with `collect_field` and `extra_outputs` read from it by
subgraph field name; a static `degraded_update` omitting `collect_field` is a
compile error (§9.8); a callable one yields a graceful null slot. Wiring a
reference implementation against that contract surfaced three small follow-on
points 0066 left imprecise or unpinned. This proposal resolves all three:

1. **`extra_outputs` omission is a null *value*, not a "skip."** 0066's §9.3 says
   an omitted `extra_outputs` source is "not contributed … the same shape as a
   skipped heterogeneous branch field." That analogy is wrong for fan-out: a
   degraded instance contributes its value in instance-index order like any
   other (§9.4), so an omission should be a **null value** (matching
   `collect_field`'s null), not absence. For an extending reducer that keeps the
   field aligned with `target_field`; under other reducers a null and an absent
   contribution merge alike — so `null` is the uniform, safe rule. A "skip"
   would shorten an extending-reducer field and misalign it.
2. **An absent `collect_field` never raises, on any path.** §9.8 pins the
   callable-degrade case to a graceful null slot. The same gracefulness should
   hold uniformly: a non-degrade `instance_middleware` return SHOULD cover
   `collect_field`, and an absent one — by any route — yields a null slot rather
   than a fan-in raise (a raise would stop the graph under `fail_fast`, the
   outcome 0066 deliberately avoided).
3. **Degrade survives resume.** A degraded instance is a completed instance, so
   its slot (including a null slot) rolls forward on a checkpoint resume — but no
   conformance case exercises it. A fixture pins it.

## Motivation

All three are about a single principle 0066 established but did not carry all
the way through: **a fan-out collection is homogeneous and positional, and the
degrade path is graceful (never raises).** 0066 applied that to `collect_field`
(null slot, compile-guarded for the static footgun) but described `extra_outputs`
with a heterogeneous-branch analogy that contradicts it, left the
non-degrade-absent-`collect_field` case unstated, and pinned neither the
`extra_outputs` slot nor the resume round-trip with a fixture. The result is that
two conformant implementations could disagree on `extra_outputs` shape
(null-at-slot vs. shortened list) or on whether an absent `collect_field` off the
degrade path raises. These are the cross-impl-consistency gaps that surface only
when an implementation wires the contract end-to-end.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0); concrete version assigned at acceptance.
All changes are in pipeline-utilities §9.3 plus one conformance fixture.

### 1. `extra_outputs` omission → null value, not a skip (§9.3)

0066's §9.3 currently ends:

> When the `degraded_update` does not supply an `extra_outputs` `subgraph_field`,
> that field is simply not contributed by this instance — the same
> partial-contribution shape as a skipped heterogeneous branch field (§11.7).

This is **superseded**. §9.3 merges each `extra_outputs` field across instances
**via the parent's reducer in instance-index order** (§9.4), the reducer
accepting the value type the subgraph produces — so a degraded instance
contributes a *value* in its index position like any other, not a
presence/absence flag. An omission should therefore be a **null value**,
mirroring `collect_field`'s null, not a dropped contribution. The replacement
clause:

> When the `degraded_update` does not supply an `extra_outputs` `subgraph_field`,
> that instance contributes **null** as its value for the mapped parent field —
> rather than being absent — merged in instance-index order like any other
> instance's value (§9.4), the same null treatment as an omitted `collect_field`
> (above). For an extending reducer (e.g. `append`) this keeps the field
> index-aligned with `target_field`; under other reducers a null and an absent
> contribution merge alike, so `null` is the uniform rule. (This is **not** a
> heterogeneous branch skip: parallel-branch `outputs` are distinct parent
> fields with no per-instance value, §11.7.)

### 2. Absent `collect_field` is graceful on every path (§9.3)

§9.8 specifies that a **callable** `degraded_update` omitting `collect_field`
yields a null slot at runtime and MUST NOT raise. §9.3 gains a clause
generalizing that gracefulness and stating the success-path expectation:

> A non-degrade `instance_middleware` return SHOULD cover `collect_field` (it is
> the homogeneous collection slot; the §9.7 success contribution carries it).
> The fan-in reads `collect_field` such that an absent value — whether from a
> callable degrade that omits it (§9.8) or a non-conformant middleware return —
> yields a **null slot**; the fan-in MUST NOT raise on an absent `collect_field`.
> A runtime raise here would stop the graph under `fail_fast`, defeating
> isolation exactly as a degrade-time raise would (§9.8). The null is visible in
> `target_field`, so a non-conformant return surfaces without halting the run.

The static-mapping footgun remains compile-guarded (§9.8, unchanged); a code
middleware return is not compile-checkable, so — like the callable form — it is
handled gracefully at runtime.

### 3. Degrade survives checkpoint resume (fixture, below)

No normative change: a degraded instance completes (§9.3), so the existing §10
checkpoint/resume rules already roll its recorded slot forward. This proposal
adds the conformance fixture that pins it.

## Conformance test impact

### New fixture

A fixture under `pipeline-utilities/conformance/` (number assigned at
acceptance) — **degrade + extra_outputs slot + checkpoint resume**:

- A single-instance (or small) fan-out with `instance_middleware:
  [failure_isolation]`, `collect_field`, and an `extra_outputs` mapping, under a
  checkpointer.
- **Case — `extra_outputs` null slot.** A degrade whose `degraded_update`
  supplies `collect_field` but omits an `extra_outputs` source; assert the
  mapped parent field holds **null at that instance's slot** (index-aligned with
  `target_field`), not a shortened list.
- **Case — absent `collect_field` does not raise.** A callable degrade omitting
  `collect_field`; assert the slot is null and the graph does **not** stop
  (re-affirming §9.8 from the §9.3 generalization angle).
- **Case — degrade survives resume.** Checkpoint after the degraded instance
  completes, then resume; assert the degraded slot (the null `collect_field`
  slot and/or the degrade values, plus the null `extra_outputs` slot) is
  preserved on the rolled-forward fan-in — not recomputed or dropped.

Fixture 065 (0066) continues to pass: this proposal refines the `extra_outputs`
*omission* shape and the resume path, neither of which 065's supplied-value
cases exercise.

## Versioning

**MINOR bump** (pre-1.0):

- §9.3's omitted-`extra_outputs` rule changes from "not contributed" to a
  positional **null slot** (a conformance-expectation change), and gains the
  absent-`collect_field` SHOULD + never-raise clause.
- A new conformance fixture pins the `extra_outputs` null slot, the
  never-raise behavior, and the degrade-survives-resume round-trip.

**Behavior-change note.** Correctly-configured graphs (degrades that supply
their mapped fields) are unchanged. The pinned changes are: an omitted
`extra_outputs` source now contributes a positional null (vs. an ambiguous
"not contributed"), and an absent `collect_field` is uniformly a null slot
rather than a possible raise. Catch/degrade and graph-execution outcomes are
otherwise untouched.

## Out of scope

- **The 0066 degrade-contribution model, §9.8 compile check, and §11.7 branch
  skip.** Unchanged; this proposal only refines the `extra_outputs` omission
  shape, the absent-`collect_field` gracefulness, and the resume fixture.
- **Per-branch (heterogeneous) `outputs` omission.** §11.7's skip is correct for
  branches and stands — the asymmetry with fan-out's positional null is
  deliberate (homogeneous slot vs. distinct parent fields).
- **Promoting `extra_outputs` to a compile-checked slot.** `collect_field` is
  the homogeneous slot the compile check guards (§9.8); `extra_outputs` are
  secondary reducer-merged contributions with a graceful runtime null, no
  compile requirement.
- **The general `extra_outputs` merge mechanics.** §9.3's exact reducer-input
  shape for `extra_outputs` (per-value vs. list-at-once) is a pre-existing
  looseness; this proposal pins only the *degrade omission* (a null value in
  instance-index order) and does not otherwise redefine how non-degrade
  `extra_outputs` merge.

## Alternatives considered

- **`extra_outputs` omission as a shortened list ("skip").** The literal reading
  of 0066's current wording. Rejected: it misaligns `extra_outputs` from
  `target_field` (a consumer can no longer tell which result a given
  `extra_outputs` value belongs to), breaking the homogeneous positional
  contract.
- **Raise on an absent `collect_field` off the degrade path** (strict). Rejected:
  it reintroduces a fan-in raise that stops the graph under `fail_fast` — the
  outcome 0066 removed — and would require the fan-in to distinguish degrade
  returns from normal returns. A visible null slot surfaces the non-conformant
  return without halting the run.
- **No fixture for resume.** Rejected: the degrade-survives-resume path is
  composition of two accepted features but is exactly the checkpoint-adjacent
  resume path otherwise covered only by keying consistency, not a conformance
  case; a fixture pins it.
- **Fold these into 0066.** Not possible — 0066 is Accepted (immutable); these
  land as a superseding refinement per governance.
