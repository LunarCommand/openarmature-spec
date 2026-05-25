# 0027: Pipeline Utilities — Explicit `result_is_error` on `FanOutInstanceProgress`

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-25
- **Accepted:**
- **Targets:** spec/pipeline-utilities/spec.md (extends the §10.11 `FanOutInstanceProgress` entry shape with one new required boolean field); spec/pipeline-utilities/conformance/052-checkpoint-fan-out-collect-errors-resume.yaml (extends saved-record assertions to exercise the new field)
- **Related:** 0009 (per-instance fan-out resume — the proposal that introduced the `FanOutInstanceProgress` shape)
- **Supersedes:**

## Summary

Add a required `result_is_error: bool` field to the per-instance entry
shape on `CheckpointRecord.fan_out_progress` (§10.11). The field
discriminates success contributions (rolled into the `target_field`
bucket on resume) from `collect`-mode error contributions (rolled into
the `errors_field` bucket). Implementations MUST consult the field on
resume rather than inferring routing from the shape of `result`. The
existing per-instance `result` field is unchanged.

## Motivation

§10.11's `FanOutInstanceProgress.result` carries the per-instance
contribution but is silent on how an implementation distinguishes
success from error contributions when rolling them forward at the
fan-in step on resume. The two cases are textually described — "for
success (any error_policy), the value contributed to the `target_field`
bucket; for `collect`-mode failures, the error entry contributed to the
`errors_field` bucket" — but the discrimination mechanism is left
implementation-defined.

The natural mechanism for an implementation is to inspect the shape of
`result` itself: if it looks like the engine's canonical error record
(e.g., a `dict` with `fan_out_index` and `category` keys), treat it as
an error; otherwise treat it as a success. This works for the engine's
own error-record shape but is fragile:

- **User state values can collide.** A user's `target_field` schema
  could legitimately contain values that match the error-record shape
  (a `dict` with those exact keys). Such a value would be misclassified
  on resume — routed to `errors_field` instead of `target_field`.
- **Cross-implementation drift.** The error-record shape is itself
  implementation-defined per §9.5; a Python implementation might use
  `{fan_out_index, category}` while a TypeScript implementation uses
  `{index, kind}`. Each implementation needs its own heuristic, and
  the heuristics drift in ways that prevent cross-implementation
  fixture sharing.
- **Implicit contract.** "How the implementation tells these apart" is
  a load-bearing detail that the spec leaves unstated. Adding the
  explicit field surfaces the discrimination as a normative field on
  the saved record shape, making the contract checkable.

The fix is small — one new boolean field, one rule about when it MUST
be set, one rule about how implementations MUST consult it on resume.
The cost of leaving the field unspecified scales with the number of
implementations; locking it in while one implementation exists is
essentially free.

## Detailed design

### §10.11 `FanOutInstanceProgress` entry shape: add `result_is_error`

Extend the per-instance entry list in §10.11 with one new field. The
revised entry shape is:

- `state` — unchanged. One of `completed`, `in_flight`, `not_started`.
- `result` — unchanged. The instance's durable contribution to the
  fan-out accumulator when `state == "completed"` (the value
  contributed to `target_field` for successes; the error entry
  contributed to `errors_field` for `collect`-mode failures). Unused
  for `in_flight` and `not_started`.
- `result_is_error` — **new**. Boolean discriminator for `completed`
  entries: `true` when the contribution is a `collect`-mode error
  entry that rolls forward into `errors_field`, `false` when the
  contribution is a success value that rolls forward into
  `target_field`. MUST be `false` (and the value of `result` ignored)
  for `state in {"in_flight", "not_started"}`.
- `completed_inner_positions` — unchanged.

The field is a normative part of the saved record shape: implementations
MUST populate it when writing a `completed` entry, MUST round-trip it
through `Checkpointer.save` / `Checkpointer.load`, and MUST consult it
when routing the rolled-forward contribution at the fan-in step on
resume. Heuristic inspection of `result` shape is no longer permitted —
the field is the authoritative discriminator.

### Per-`error_policy` population rules

The population rules align with §10.11.2:

- **`fail_fast` mode.** A failed instance leaves the entry in
  `in_flight` (no `completed` save fires for the failed slot, per
  §10.11.2). `result_is_error` for that entry is `false` (its
  `state` is not `completed`; the field's value is irrelevant per
  the contract above but MUST still be present in the serialized
  record with the default `false`). Instances that completed
  successfully before the failure have `result_is_error: false`.
- **`collect` mode.** Successful instances have
  `result_is_error: false` with `result` carrying the success value.
  Failed instances (whose failure was promoted to a `completed`
  contribution per §10.11.2) have `result_is_error: true` with
  `result` carrying the implementation's error-record value.

### Resume contract

The §10.11 resume contract is amended to read:

On resume, when an instance whose entry has `state == "completed"`
rolls its contribution forward to the fan-in step (per §9.3):

- If `result_is_error == false`, the contribution is routed to
  `target_field` (the success bucket), merged via the parent
  reducer per §10.11.1.
- If `result_is_error == true`, the contribution is routed to
  `errors_field` (the collect-mode error bucket) per §9.5 + §10.11.2.

Implementations MUST NOT inspect `result` shape to make this routing
decision. Implementations that previously relied on shape inspection
MUST update to consult `result_is_error`.

### §10.11.2 amendment: name the discrimination mechanism

§10.11.2 currently describes the two `collect`-mode resume outcomes
without naming the discrimination mechanism. Amend the `collect`
bullet by appending one sentence after its existing text. The
amended bullet reads (new text **bold**, surrounding text unchanged):

> - **`collect`.** The fan-out runs all instances regardless of
>   individual failures; failed slots are recorded in `errors_field`
>   at the fan-in step. On resume, instances marked `completed` are
>   skipped — their accumulator entry, either a success result for
>   `target_field` or a recorded error for `errors_field`, is
>   preserved and rolls forward to the fan-in step at fan-out
>   completion. Instances in `in_flight` or `not_started` re-run; if
>   they fail again, the failure is again recorded into the
>   accumulator as an error entry. **The `result_is_error` field on
>   the saved `FanOutInstanceProgress` entry (per §10.11)
>   discriminates the two cases: `result_is_error: true` routes the
>   contribution to `errors_field`; `result_is_error: false` routes it
>   to `target_field`. Implementations MUST consult this field rather
>   than inferring routing from `result` shape.**

No other §10.11.2 text changes. The `fail_fast` bullet is unchanged
because `fail_fast` does not produce `completed` entries for failed
instances and the discrimination question doesn't arise.

### Cross-spec touchpoints

- **Pipeline-utilities §10.11** — primary change site. The
  `FanOutInstanceProgress` entry shape gains the new field.
- **Pipeline-utilities §10.11.2** — amended per the section above
  (one sentence appended to the `collect` bullet).
- **Pipeline-utilities §10.11.1** — unchanged. Reducer-interaction
  rules apply to `target_field` contributions only; the
  `result_is_error` field determines which contributions count as
  `target_field` and which count as `errors_field`.
- **Pipeline-utilities §10.11.3 / §10.11.4** — unchanged. Retry-
  middleware composition rules and batching rules don't depend on
  the discrimination mechanism.
- **Graph-engine §6** — no changes.
- **Observability §5** — no changes.
- **LLM-provider** — no changes.

### No new error categories

The new field is data, not error-surface. No `checkpoint_*` category
additions; no §10.10 changes.

## Conformance test impact

### Modified existing fixture

`052-checkpoint-fan-out-collect-errors-resume.yaml` — modify the
`saved_record_assertions.fan_out_progress[process].instances` list to
assert the new field on each `completed` entry. Replace the existing
`result_kind: error` harness matcher on instance 2's entry with
`result_is_error: true`. The revised list reads:

```yaml
instances:
  - {state: completed, result: 10, result_is_error: false}
  - {state: completed, result: 20, result_is_error: false}
  # Instance 2's contribution is an error record under collect.
  - {state: completed, result_is_error: true}
  - {state: not_started}
  - {state: not_started}
```

The success entries (instances 0, 1) gain an explicit
`result_is_error: false` alongside their existing `result: N` value
assertion. Instance 2's entry asserts `result_is_error: true`; the
exact `result` value is not asserted because the error-record shape is
implementation-defined per §9.5 and the boolean discriminator is the
cross-implementation-checkable property the spec field guarantees.

### Retire `result_kind: error` harness primitive

The `result_kind: error` harness matcher used by fixture 052 prior to
this proposal was a workaround for asserting "the entry's `result` is
shaped like the engine's error record" without naming a specific
implementation-defined shape. With `result_is_error: bool` as a
normative field on the spec entry shape, the harness has a direct
boolean to assert against and the shape-inspection workaround is no
longer needed.

Implementations MUST remove the `result_kind: error` matcher from
their conformance harness adapters. Fixture 052 is the only existing
fixture using it; no other migration is needed. Future fixtures that
need to assert "this instance is a `collect`-mode error" use
`result_is_error: true`.

### No new standalone fixture

The fixture-052 modification exercises the round-trip end-to-end
(`completed` entries with both `result_is_error: true` and
`result_is_error: false` saved, then loaded, then routed correctly on
resume to `errors_field` and `target_field` respectively). A
standalone fixture would duplicate that coverage. If a future
implementation surfaces a discrimination edge case not covered here, a
follow-on can add one.

### No other fixture changes

All existing fixtures (048–054) other than 052 keep their existing
assertions unchanged. Fixtures that don't currently exercise
`fan_out_progress` matchers are unaffected by this proposal.

## Alternatives considered

### Leave the discrimination implementation-defined (status quo)

Rejected. The implementation-defined status quo works for a single
implementation that has shipped its own heuristic, but cross-
implementation conformance requires either (a) all implementations
agreeing on the same heuristic, which has no normative pressure to
align, or (b) an explicit normative field on the saved record. The
field is cheap to specify and impossible to misimplement once
specified.

The status quo also leaves user state schemas that collide with the
implementation's error-record shape as a silent footgun: a user state
value that happens to match the heuristic shape gets routed to the
wrong bucket on resume. The collision is unlikely in practice but
catastrophically silent when it happens.

### Discriminated-union wrapper on `result` itself

Replace `result: Any` with `result: {kind: "success", value: ...} |
{kind: "error", error: ...}`. Rejected on two grounds:

- The §10.11 shape passed to `Checkpointer.save` and round-tripped
  back through `Checkpointer.load` is part of the public surface
  consumers serialize. Changing the `result` shape from a free-form
  per-state-schema value to a wrapped discriminated union breaks the
  v1 round-trip semantics — the saved record's `result` would no
  longer be the value the user's state schema declares, but a wrapper
  around it.
- The boolean discriminator achieves the same correctness with less
  surface area. A wrapper adds value when there are multiple kinds
  to discriminate (3+); for exactly two cases, a flag is simpler.

### Separate `error_record: optional` field alongside `result`

Add `error_record: Any | None`; when the contribution is an error,
`result` is null and `error_record` is populated, and vice versa.
Rejected. Two parallel fields where only one is populated at a time is
a worse shape than one value + one boolean. The "which field is
populated" check is itself a discriminator — the boolean approach
just makes it explicit.

### Lift the error-record shape out of implementation-defined territory

Spec the canonical error-record shape (`{fan_out_index, category}` or
similar) and require all implementations to use it. Then the heuristic
on `result` shape becomes specification-safe.

Rejected. This conflates two concerns: how implementations represent
error records internally (§9.5 implementation-defined for good reason
— Python, TypeScript, and future languages each pick their own typed
shape) and how the framework discriminates success from error
contributions on resume. The boolean discriminator separates them
cleanly; locking in the error-record shape would unnecessarily
constrain implementations' internal representations.

## Open questions

None. The boolean-vs-discriminated-union shape choice, the population
rules per `error_policy`, and the resume routing contract are settled
in the proposal text above.
