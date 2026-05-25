# 0029: Pipeline Utilities — Strict `checkpoint_record_invalid` on fan-out `instance_count` drift

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-25
- **Accepted:** 2026-05-25
- **Targets:** spec/pipeline-utilities/spec.md (adds a normative rule under §10.11 mandating `checkpoint_record_invalid` on count drift; extends §10.10's `checkpoint_record_invalid` description to enumerate count drift as a failure mode); spec/pipeline-utilities/conformance/056-checkpoint-fan-out-count-drift.yaml (new fixture exercising the resume-time error path)
- **Related:** 0008 (checkpointing — defines `checkpoint_record_invalid` and the §10.5 idempotency framing the new rule operationalizes), 0009 (per-instance fan-out resume — defines the `instance_count` field whose drift this rule guards)
- **Supersedes:**

## Summary

Mandate that the engine MUST raise `checkpoint_record_invalid` (per
§10.10) when a saved record's `CheckpointRecord.fan_out_progress`
entry carries an `instance_count` that does NOT equal the count
resolved for the same fan-out node on the resumed run. Silent
pad-or-truncate of the saved `instances` list is not permitted —
per-instance accumulator entries written under one `instance_count`
cannot be reconciled with a different count without risking dropped
or duplicated contributions, breaking §10.11.1's exactly-once
reducer guarantee.

## Motivation

§10.11's per-instance entry shape includes an `instance_count` field
("the resolved instance count for this fan-out (per §9 `count` or
`items_field` mode)"). The field is written at save time and read
at resume time, but §10.11 is silent on what the engine MUST do
when the saved value differs from the count the resumed run resolves
(e.g., the user shrank or grew the `items_field` list between
crash and resume).

§10.5's idempotency framing says "resume re-runs the same work the
crashed run was performing," which implies the count should match —
but this is implicit, not normative. Two coherent positions exist
under the current spec text:

- **Permissive (silent pad/truncate).** The engine pads the
  `instances` list with `not_started` entries when the count grew,
  or truncates trailing entries when the count shrank, then proceeds
  with resume. The user's count change is silently absorbed.
- **Strict (raise on mismatch).** The engine raises
  `checkpoint_record_invalid` per §10.10. The user must either
  cohere the inputs (restore the items list to its pre-crash shape)
  or restart cleanly.

The permissive position silently drops `completed` contributions
when the user shrinks the count, breaking §10.11.1's exactly-once
guarantee under the `append` reducer: an instance whose `completed`
state and `result` field were durably saved gets dropped on resume,
leaving the accumulator one entry short. The user has no diagnostic
that anything was lost — the resume "succeeds" with the wrong final
state.

The strict position surfaces the divergence as a categorized error
the user can act on. The trade-off is one extra failure mode users
must reason about, but the failure happens at resume time (loudly)
rather than as a silent contribution loss (which only surfaces
through downstream symptoms or never).

Strict is also the option that composes cleanly with future tooling:
a user who wants to "edit a saved record and resume against the
edited shape" can do so explicitly (re-save a coherent record),
rather than implicitly relying on the engine's reconciliation
behavior. The permissive position would mask incoherent edits.

The current spec's silent-on-count-drift status leaves implementations
free to pad/truncate permissively or to raise on mismatch. Behavior in
shipping implementations currently leans toward permissive
reconciliation — pragmatic defensive convenience rather than a
deliberate spec position. Surfacing the rule normatively chooses one
direction so cross-implementation conformance is well-defined. The
issue was raised during a proposal-0009 implementation review pass.

## Detailed design

### §10.11: add a count-drift rule under the entry-shape description

Add the following paragraph immediately after §10.11's bulleted
list describing the per-instance entry shape (`state`, `result`,
`result_is_error`, `completed_inner_positions`), before the
"`completed` is the load-bearing state" paragraph:

> **Count drift on resume.** When the engine loads a saved record
> and finds a `fan_out_progress` entry whose `instance_count` does
> NOT equal the count the resumed run resolves for the same fan-out
> node (per §9 `count` or `items_field` mode), the engine MUST
> raise `checkpoint_record_invalid` (per §10.10). Implementations
> MUST NOT silently pad the saved `instances` list with
> `not_started` entries when the resumed count is larger, nor
> silently truncate trailing entries when the resumed count is
> smaller — per-instance accumulator contributions written under
> one `instance_count` cannot be reconciled with a different count
> without risking dropped or duplicated entries at the fan-in step,
> breaking §10.11.1's exactly-once reducer guarantee. Users who
> intentionally change a fan-out's input set between runs MUST
> start a fresh invocation rather than resume.

The rule applies to every `fan_out_progress` entry; a record with
multiple fan-out entries raises on the first mismatch encountered.
The error category is the existing `checkpoint_record_invalid` —
no new category is minted.

### §10.10: extend `checkpoint_record_invalid` description

Append the following sentence to §10.10's existing description of
`checkpoint_record_invalid` (which currently enumerates failure
modes like "the serialized record is corrupt" and "the
post-migration state fails the current state class's
deserialization"):

> The category also covers `fan_out_progress[*].instance_count`
> drift between save and resume per §10.11 — a saved per-instance
> accumulator shape that is structurally incompatible with the
> resumed run's resolved count.

This is a textual amendment to the existing category, not a new
category. Mutual-exclusion rules with other categories
(`checkpoint_state_migration_*`) remain unchanged.

### Cross-spec touchpoints

- **Pipeline-utilities §10.11** — primary site (new normative
  paragraph).
- **Pipeline-utilities §10.10** — amended `checkpoint_record_invalid`
  description (one new sentence enumerating the failure mode).
- **Pipeline-utilities §10.5** — no text change. The §10.5
  idempotency framing already implies count consistency; the new
  §10.11 rule operationalizes that implication on the fan-out
  surface.
- **Pipeline-utilities §10.11.1** — no text change. The exactly-once
  reducer guarantee is what the new rule protects.
- **Graph-engine §9** — no text change. The `count` /
  `items_field` resolution rules already define how the resumed
  count is determined.
- **Observability** — no changes.
- **LLM-provider** — no changes.

### Multi-fan-out records

A saved record's `fan_out_progress` MAY contain multiple entries
(when nested fan-outs or parallel fan-out branches were in flight at
save time). The count-drift rule applies independently to each
entry; the engine MUST raise on the FIRST mismatch encountered. The
error message SHOULD identify which `fan_out_node_name` and
`namespace` triggered the raise so the user can diagnose. The
identification mechanism is implementation-defined per §10.10's
error-payload framing.

### Resume-time check, not save-time

The count drift can only be observed at resume time, when the
resumed run resolves its current count and compares against the
saved value. Implementations MUST perform the check before
dispatching any fan-out instance work on the resumed run — failing
fast prevents partial state mutation under an invalid record.

## Conformance test impact

### New fixture: 056-checkpoint-fan-out-count-drift

A focused fixture exercising the new normative rule:

- Build a graph with a fan-out node whose `items_field` produces 5
  instances on the first run.
- Drive the first run through partial fan-out completion (some
  instances `completed`, others `in_flight` or `not_started`); abort.
- On the resume attempt, change the `items_field` source to produce
  a different count (e.g., 3 instances).
- Assert: resume raises `checkpoint_record_invalid` (per the §10.10
  category surface) BEFORE any fan-out instance work runs.

The fixture exercises both directions of drift in two cases:
- **Shrunk count** (saved 5, resumed 3): would have silently dropped
  the 2 trailing entries under permissive behavior; strict raises.
- **Grew count** (saved 3, resumed 5): would have silently padded
  with `not_started` entries under permissive behavior; strict
  raises.

Both cases hit the same error category; the fixture verifies the
category surfaces (not the impl-defined error payload, which is
language-ergonomic per §10.10).

### Harness primitive: `resume_with_modified_items`

A new fixture primitive for fixture 056 (no other existing fixture
needs it). Lets the fixture re-build the graph on the resume side
with a different `items_field` default value, simulating "user
shrank/grew the input set between runs":

```yaml
resume:
  from_first_run: true
  resume_with_modified_items:
    items: [10, 20, 30]   # resumed run resolves 3 instances
  expected_error:
    category: checkpoint_record_invalid
```

Per-language harness adapters wire this into the resumed graph
construction. Small extension (~5–10 lines per adapter).

### No other fixture changes

Existing fixtures (024–031, 048–055) don't exercise count drift —
they all use stable `items_field` lists across save and resume.
None are affected by the new rule.

## Alternatives considered

### Permissive pad/truncate (status quo)

Rejected. Silent contribution loss breaks §10.11.1's exactly-once
guarantee. A user shrinking the items list between runs gets a
"successful" resume with the wrong final state — no diagnostic that
anything was lost. The §10.5 idempotency framing implies count
consistency; making the implication normative aligns the engine
with the framing.

### Mint a new error category (`checkpoint_count_drift`)

Rejected. The existing `checkpoint_record_invalid` already covers
"saved record is structurally incompatible with the current graph
or state." Count drift is a structural incompatibility in the same
shape (the saved `instances` list shape doesn't match the resumed
graph's fan-out resolution). Minting a new category adds API
surface for no behavioral benefit; users who care about
discriminating count drift from other invalid-record causes can
inspect the impl-defined error payload (per §10.10's
language-ergonomic message field).

### User-supplied tolerance / reconciliation hook

Rejected as over-engineered. A hook would let the user say
"resume with the smaller count and drop the missing entries" or
"resume with the larger count and treat the new entries as
not_started." The spec's role is the framework's contract, not
user-extensible reconciliation logic. A user who genuinely needs
that behavior can manually edit the saved record before re-invoking
(a separate user-space concern, not a framework primitive).

### Raise on resume but log-and-continue under a flag

Rejected. A "permissive resume" flag would split the spec contract
into two behaviors implementations need to support, doubling the
test surface for no clear benefit. The strict behavior is the
correct default; users wanting to absorb count changes can build
that logic on top of the spec contract (in their resume orchestration
layer).

### Apply the rule only when the count SHRANK (not when it grew)

Rejected as inconsistent. Padding with `not_started` for a grown
count would seem benign (new entries just dispatch normally on
resume), but it interacts poorly with §10.11.1: the user might
have intended the new entries to share some property the saved
entries didn't (e.g., a different item type entering the list).
Treating shrunk and grown counts symmetrically — both are structural
incompatibilities — is simpler and more defensive.

## Open questions

None. The strict-vs-permissive choice is settled in favor of strict
above; the error-category reuse vs new-category question is settled
in favor of reuse; the resume-time check requirement is settled;
the multi-fan-out behavior is settled.
