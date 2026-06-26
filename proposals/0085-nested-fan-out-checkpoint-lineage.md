# 0085: Pipeline Utilities — Nested-Fan-Out Checkpoint Lineage and No-Mis-Skip Invariant

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-26
- **Accepted:** 2026-06-26
- **Targets:** spec/pipeline-utilities/spec.md — §10.11: (a) a normative *no-mis-skip* invariant (the engine MUST NOT apply a saved `fan_out_progress` entry's completed-instance skips unless the entry positively matches the re-entering execution's enclosing fan-out instance lineage, else it re-runs); (b) a new optional `enclosing_fan_out_lineage` field on each entry — the outermost→innermost chain of enclosing fan-out instances — making the same inner fan-out node distinguishable per outer instance so nested resume skips correctly and §10.11.1 exactly-once extends to nested fan-outs; rewrite the §10.11 `namespace` bullet's claim that `namespace` *uniquely* identifies the fan-out node; the count-drift check re-resolves the count per lineage-qualified entry and runs only on positively-matched entries. §10.2: reconcile the "per-fan-out-node mapping" record-shape framing for same-node multiplicity. §10.7: add the lineage-match precondition to the per-instance resume skip decision (cross-referencing the no-mis-skip invariant). Reconcile the 0029 "Multi-fan-out records" note. New conformance fixtures for nested-fan-out resume.
- **Related:** 0009 (per-instance fan-out resume — defined `fan_out_progress` and §10.11), 0027 (`result_is_error` discriminator), 0029 (count-drift + the "Multi-fan-out records" note this extends), 0045 (observability lineage-aware augmentation — the runtime analogue of the same enclosing-instance lineage).
- **Supersedes:**

## Summary

The `fan_out_progress` checkpoint record (§10.11) keys a fan-out's per-instance progress by `(namespace, fan_out_node_name)` only. For a fan-out **nested inside an outer fan-out instance**, every outer instance traverses the same node path, so all outer instances' inner-fan-out progress collapses to one entry with one flat `instances` list — last-write-wins on save. On resume, an engine that trusts that colliding entry would skip inner instances completed by a *different* outer instance and roll the wrong results forward: silent wrong output. This proposal (a) adds a normative **no-mis-skip invariant** — when the engine cannot positively match a saved entry to the re-entering instance lineage, it re-runs rather than skips — and (b) adds an optional **`enclosing_fan_out_lineage`** to each entry so the engine *can* match per outer instance and skip correctly, extending §10.11.1's exactly-once guarantee to nested fan-outs. (a) closes a latent cross-implementation correctness hole; (b) turns nested resume from always-re-run into a correct skip. Both are backward-compatible: a non-nested fan-out carries an empty lineage and behaves exactly as today.

## Motivation

§10.11's per-instance resume identifies a fan-out's progress by `(namespace, fan_out_node_name)`. `namespace` is a node-name path (graph-engine §6) and `fan_out_index` is a single scalar — neither carries an enclosing-instance dimension. So for an inner fan-out node that executes once per outer fan-out instance, every outer instance produces the *same* key, and the saved record holds one entry with one flat `instances` list. The per-outer-instance inner progress collides; the last save wins.

On resume this admits two outcomes, and the spec currently mandates neither:

- **Re-run from scratch** (the safe outcome): the engine, unable to trust the colliding entry, re-runs the inner fan-out. Re-running work whose contribution was never durably reconciled is correctness-preserving per §10.7.
- **Mis-skip** (the unsafe outcome): the engine trusts the colliding entry, skips inner instances marked `completed` — but those completions belong to a *different* outer instance — and rolls their results forward into the wrong enclosing accumulator. The resumed run silently produces wrong output, with no count-drift trip (each colliding outer instance resolves the same inner `instance_count`).

Because §10.11 doesn't say which outcome is required, it is an implementation choice — a latent cross-implementation correctness hole. §10.11.1's exactly-once reducer guarantee is, today, only actually guaranteed for flat (single-level) fan-outs.

The runtime observability layer already distinguishes nested instances — via the live dispatch-ancestor call stack (proposal 0045) — but checkpoint *restore* has no live stack to fall back on; the enclosing lineage must be persisted in the record. The engine has that lineage in its execution context at save time (it is running inside the outer instance); the gap is purely that the record shape has nowhere to carry it.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). (b) is a record-format addition but backward-compatible — existing flat records carry an empty/absent `enclosing_fan_out_lineage` and resume exactly as today; (a) tightens previously-undefined nested-resume behavior and changes no conforming flat-fan-out behavior.

### (a) No-mis-skip invariant (§10.11)

Add a normative rule to §10.11:

> **No mis-skip across enclosing instances.** On resume, before applying a saved `fan_out_progress` entry's `completed` skips to a re-entering fan-out, the engine MUST verify the entry's `enclosing_fan_out_lineage` positively matches the lineage of the re-entering execution (the ordered chain of enclosing fan-out instances it is running within). If no saved entry positively matches — including a legacy record that carries no `enclosing_fan_out_lineage` for a fan-out that is in fact nested inside an outer fan-out instance — the engine MUST treat the re-entering fan-out as having no saved progress (all instances `not_started`) and re-run it, rather than apply a non-matching entry's skips. Re-running un-matched work is correctness-preserving (§10.7 — no accumulator entry was reconciled); applying a non-matching entry's skips is not, as it would roll a different enclosing instance's contributions into the wrong accumulator.
>
> **Positive match.** A positive match requires the saved entry's `enclosing_fan_out_lineage` to equal the re-entering execution's lineage element-for-element. An **empty** saved lineage positively matches an **empty** re-entering lineage — a flat, non-nested fan-out — so existing flat records resume exactly as before this proposal. A non-empty re-entering lineage never positively matches an absent or empty saved lineage, nor the reverse.

This precondition attaches to §10.7's per-instance resume skip decision, where "Completed → MUST NOT re-run … skipped" is stated: the skip applies only after a positive lineage match; without one, §10.7's three-state handling treats the instance as `not_started`.

### (b) `enclosing_fan_out_lineage` field (§10.11)

Add an optional field to each `fan_out_progress` entry (after `instances`):

> - `enclosing_fan_out_lineage` — an ordered sequence (outermost → innermost) of enclosing fan-out instance identifiers, each `{namespace, fan_out_node_name, fan_out_index}`, identifying the chain of fan-out instances within which this fan-out is running. Empty / absent for a fan-out that is not nested inside another fan-out instance (a top-level fan-out, or a fan-out reached through static subgraph nesting only — backward-compatible with records written before this field existed). When present, it distinguishes the same inner fan-out node executing once per enclosing outer instance: an entry is keyed by `(namespace, fan_out_node_name, enclosing_fan_out_lineage)`, so `fan_out_progress` MAY contain multiple entries sharing a `(namespace, fan_out_node_name)` that differ only in `enclosing_fan_out_lineage`.

§10.11.1's exactly-once guarantee then extends to nested fan-outs: with `enclosing_fan_out_lineage` distinguishing each enclosing instance's inner-fan-out progress, each inner instance within each enclosing instance contributes exactly once across a resume.

### Count-drift and the §10.2 / §10.11 / 0029 reconciliations

The count-drift check (§10.11) is re-resolved and applied **per lineage-qualified entry**. A nested inner fan-out using `items_field` may resolve a different `instance_count` per enclosing instance (its count comes from that enclosing instance's state), so the resumed count is computed for each `enclosing_fan_out_lineage` and compared against the matching saved entry — not once for the node. Count-drift is checked **only on positively-matched entries**: an unmatched legacy entry is handled by the no-mis-skip invariant (treated as no saved progress and re-run) and never reaches the count-drift comparison, so the invariant and §10.11's existing MUST-raise-on-count-drift do not conflict.

Three existing statements assert the old single-entry / unique-key framing and are reconciled at accept: §10.2's "`fan_out_progress` — per-fan-out-node mapping" record-shape description; the §10.11 `namespace` bullet's claim that `namespace` *uniquely* identifies the fan-out node (true only together with `enclosing_fan_out_lineage` for an instance-nested fan-out); and 0029's "Multi-fan-out records" note, which already allows multiple entries for *distinct* fan-out nodes and now also allows multiple entries for the *same* `(namespace, fan_out_node_name)` distinguished by `enclosing_fan_out_lineage`.

### No graph-engine §6 event change

The enclosing lineage is available in the engine's execution context at save time, so it is sourced into the checkpoint record directly; graph-engine §6's `fan_out_index` stays a single scalar and no event-shape change is required. (Confirmed in principle with the python implementation; revisit at accept if the engine in fact needs §6 to surface the lineage.)

## Conformance test impact

A new pipeline-utilities fixture (`076-nested-fan-out-resume-lineage`) exercises nested-fan-out resume: an outer fan-out over two items, each outer instance running an inner fan-out, resumed from a mid-flight record in which both outer instances are `in_flight` — so the inner fan-out node appears as two distinct lineage-qualified entries (same `(namespace, fan_out_node_name)`, differing `enclosing_fan_out_lineage`). It asserts (1) the entries are matched per `enclosing_fan_out_lineage`, not collapsed; (2) each outer instance skips only *its own* completed inner instances; (3) no inner instance is mis-skipped across outer instances — the resumed accumulator equals a from-scratch run. A companion case pins the safety floor: a legacy-shaped record with no `enclosing_fan_out_lineage` forces a full re-run.

The fixture **seeds** the precise two-entry record (`seeded_record` / `resume: {from_seeded_record: true}`, the mechanism the migration suite 039–047 uses) rather than crash-producing it: a two-distinct-entry mid-flight state requires two outer instances in flight at once (concurrent outer execution), whose exact per-instance states at a crash save are dispatch-timing-dependent, and `crash_injection` boundaries are not lineage-qualified. Seeding pins the state deterministically and exercises the consume-side contract (lineage-matched skip / no mis-skip / exactly-once accumulator) — the correctness property this proposal adds. Requirements (2)/(3) use fixture-specific invariant predicates (conformance-adapter §5.9); the only new record content is `enclosing_fan_out_lineage`.

Out of scope for this fixture (noted for a possible follow-on): a deterministic *crash-produced* (write-side) variant would need lineage-qualified `crash_injection` boundaries and a lineage-qualified `saved_record_assertions.fan_out_progress` shape (which today keys per node name, one entry per node). `seeded_record` is established by the migration fixtures but not yet enumerated in conformance-adapter §5.6; seeding a `fan_out_progress` (carrying `enclosing_fan_out_lineage`) is new usage the adapter must support.

## Versioning

**MINOR bump** (pre-1.0): §10.11 gains an optional record field and a no-mis-skip invariant. Existing flat-fan-out records (empty lineage) resume identically; the invariant only constrains previously-undefined nested-resume behavior. The concrete version is the maintainer's call at acceptance.

## Out of scope

- **Flat (single-level) fan-out resume** — unchanged.
- **graph-engine §6 event shape** — unchanged; this is a checkpoint-record-only change.
- **Parallel-branches nesting.** A parallel branch nested inside a fan-out instance (or a fan-out inside a branch) is a structurally analogous lineage question; whether the checkpoint record needs a branch dimension alongside `enclosing_fan_out_lineage` is deferred to a follow-on unless the same collision is demonstrated for branches.

## Alternatives considered

- **Nest the `instances` list under an outer-instance index** (instead of a per-entry `enclosing_fan_out_lineage`). Rejected: a more invasive restructuring of the record shape; the per-entry lineage field is purely additive (flat records carry an empty lineage and are unchanged) and reuses the existing multi-entry allowance (0029's "Multi-fan-out records").
- **The safety floor alone (mandate re-run, no lineage field).** Rejected: it closes the mis-skip hole but leaves every nested-fan-out resume re-running from scratch — §10.11.1 exactly-once would still not extend to nested instances. The lineage field is what turns the safe re-run into a correct skip; (a) and (b) are complementary, not alternatives.
- **Do nothing.** Rejected: the collision admits a silent mis-skip (wrong output) on resume, and the spec mandates neither outcome today — a latent cross-implementation correctness hole.

## Open questions

- **Engine save-time lineage availability** — confirm with the python implementation that the enclosing fan-out instance lineage is available when the checkpoint record is built (so no graph-engine §6 event-shape change is needed). The implementation indicated it is.
- **Branch nesting** — whether fan-out/parallel-branches cross-nesting has the same persisted-collision gap and should be folded in here or addressed in a follow-on.
