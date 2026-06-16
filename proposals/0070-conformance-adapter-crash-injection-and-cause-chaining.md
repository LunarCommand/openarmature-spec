# 0070: Conformance Adapter — Crash/Resume Vocabulary, Crash-Injection, and Cause-Chaining

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-16
- **Targets:** spec/conformance-adapter/spec.md (§5.6 — formalize the **crash/resume directives** [`first_run_expected_error`, `resume` / `from_first_run`] and add a **`crash_injection`** directive that simulates a crash at a checkpoint boundary independent of an instance failure; §5.8 — formalize the **saved-record + resume-outcome assertions** [`saved_record_assertions` / `fan_out_progress`, `instances_executed_during_resume` / `instances_skipped_during_resume`]; §5.1 — add an optional **`cause`** [exception-chaining] to the failure-mock directives, with the failure-mock family itself formalized in a follow-on); plus demonstrating fixtures
- **Related:** 0055 (conformance-adapter capability — this fills the §5 vocabulary gap it left), 0008 / 0009 / 0010 (checkpointing + resume — what the crash/resume directives exercise), 0050 / 0065 / 0068 (failure isolation + the cause chain — what `cause`-chaining exercises), 0069 (the degrade+resume fixture `crash_injection` unblocks)
- **Supersedes:**

## Summary

The conformance-adapter capability (0055) was "descriptive of what exists," but §5's directive vocabulary never captured the **crash→save→resume machinery** the checkpoint fixtures depend on: `first_run_expected_error`, `resume: {from_first_run: true}`, `saved_record_assertions: {fan_out_progress: …}`, and the `instances_executed_during_resume` / `instances_skipped_during_resume` outcome assertions (used by 050/051/053 …) appear nowhere in §5.6 / §5.8, which document only `checkpointer:`.

This proposal **formalizes that crash/resume vocabulary** (documenting what the adapter already implements) and **adds two new directives** the v0.14.0 implementation review needs:

- **`crash_injection`** (§5.6) — simulate a crash at a checkpoint boundary **independent of an instance failure**, so resume can be tested from *any* saved state. Today the only way to reach a resume is an instance genuinely failing under `fail_fast`; that can't express "a degraded instance (which *completes*, never propagates) survives a checkpoint round-trip."
- **mock `cause`** (§5.1) — an optional nested cause on a failure mock's raised error, so a mock can raise a **chained** exception (a categorized error caused by another). Today no mock produces a cause chain, so a fixture can't exercise a multi-link non-carrier cause chain.

The **failure-mock family** itself — the organically-grown `flaky*` directives (five overlapping variants: `flaky` / `failure_sequence`, `flaky_per_index`, `flaky_by_index`, `flaky_instance_only`, `flaky_resume_aware`) — is *not* formalized here. Faithfully cataloging (or rationalizing) it is a focused follow-on (see *Out of scope*). `cause` attaches to whatever a failure mock raises and needs only a light anchor, not the full catalog; `crash_injection` builds on the crash/resume directives, which *are* formalized here.

## Motivation

Two accepted behaviors can't be pinned by a conformance fixture today purely for lack of test vocabulary, not lack of spec:

- **0069's degrade+resume** — a `FailureIsolation`-degraded fan-out instance *completes* (the failure is caught), so it never triggers the `fail_fast` crash the existing resume fixtures rely on. With uniform `instance_middleware` (§9.7) there's no way to have one instance degrade and a sibling propagate without contortion. A `crash_injection` directive — "crash after instance N's completion save" — expresses the real scenario directly: a degraded slot is saved, the process crashes, resume rolls it forward.
- **0068's outermost-wins cause derivation** — the derived `category` is the *outermost non-carrier* link with a category, so a deliberate surface re-categorization wins. Demonstrating that needs a chain with **two categorized non-carrier links**, which only exists if a mock raises `ErrorA caused by ErrorB`. A mock `cause` produces exactly that.

Adding `crash_injection` on top of an **undocumented** resume base would be a half-measure — so this proposal first writes down the crash/resume vocabulary it extends, paying down the 0055 §5 gap this review exposed. The failure-mock family `cause` attaches to is larger and more organic than a clean documentation pass — five overlapping `flaky*` variants — so its full formalization is split to a follow-on; `cause` itself needs only a light anchor (any failure mock's raised error MAY carry one).

`crash_injection` is the more fundamental of the two — it makes resume testable from *any* checkpoint state (all-success, all-degraded, mid-instance), not just instance-failure states, which benefits many future fixtures beyond 0069.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0); concrete version assigned at acceptance. All changes are in conformance-adapter §5 + demonstrating fixtures. The formalized directives are **descriptive of the adapter behavior the existing fixtures already require** — no implementation change for the documented-existing parts; only `crash_injection` and mock `cause` are new adapter capabilities.

### §5.1 — `cause` on failure mocks (new)

The failure mocks the fixtures use — the organically-grown `flaky*` family (`flaky` /
`failure_sequence`, `flaky_per_index`, `flaky_by_index`, `flaky_instance_only`,
`flaky_resume_aware`) — are **not** formalized here; that catalog (and any rationalization) is a
focused follow-on (see *Out of scope*). What this proposal adds is one cross-cutting capability on
whatever such a mock raises:

> - **`cause: {category: <category|null>, message: <str>, cause: {…}}`** — an optional field on a
>   failure mock's raised error (e.g. a `failure_sequence` entry, or a `flaky*` mock's failure). When
>   present, the raised error is chained to an originating cause (the host language's exception-cause
>   linkage — Python `raise … from`, TypeScript `{ cause }`); `cause` nests recursively for
>   multi-link chains. The adapter MUST construct the chain so a consumer walking the cause chain
>   (e.g. pipeline-utilities §6.3's failure-isolation event) observes each link with its `category` /
>   `message`. Carriers the **engine** adds (graph-engine §4 `node_exception`) are independent of this
>   mock-authored chain.

### §5.6 — crash/resume directives (formalize) + `crash_injection` (new)

Document the existing crash→save→resume machinery:

> - **`first_run_expected_error: {category: <category>, raised_from: <node_name>}`** — top-level. The
>   error expected to end the **first** run (before resume): a `flaky*` mock (the failure-mock
>   family, formalized in the follow-on) fails, propagates under `fail_fast`, and the engine surfaces
>   this category from the named node. Pairs with `resume:`.
> - **`resume: {from_first_run: <bool>, expected: {…}, invariants: {…}}`** — top-level. After the
>   first run ends (via `first_run_expected_error` or `crash_injection`), the adapter resumes the
>   invocation from the saved checkpoint (`from_first_run: true` resumes the same invocation id) and
>   asserts the resumed run's `expected` block (a normal expected block) plus any resume-specific
>   `invariants`.

Add the new crash-injection directive:

> - **`crash_injection: {<boundary>}`** — top-level; an alternative to `first_run_expected_error` for
>   triggering a resume **without** an instance failure. The adapter runs the graph until the named
>   checkpoint boundary's save has fired, then abandons the in-flight run, retaining only the
>   persisted checkpoint; the first run has **no** asserted outcome (it "crashed"), and `resume:`
>   loads from that checkpoint. `<boundary>` is one of:
>   - **`after_node: <node_name>`** — crash immediately after the node's terminal checkpoint save.
>   - **`after_fan_out_instance: {node: <fan_out_node>, index: <int>}`** — crash immediately after the
>     given fan-out instance's `completed` save fires (per §10.11); the saved record reflects sibling
>     instance states as of that moment (per the fan-out's execution mode).
>
>   `crash_injection` pairs with `resume:` the same way `first_run_expected_error` does. It lets a
>   fixture checkpoint a fan-out where some instances **completed** (including `FailureIsolation`-
>   degraded instances, which complete rather than propagate) and assert, on resume, that those slots
>   roll forward unchanged while not-yet-run instances dispatch.

### §5.8 — saved-record + resume-outcome assertions (formalize)

> - **`saved_record_assertions: {fan_out_progress: {<node_name>: {instance_count: <int>, instances:
>   [<instance_assertion>, …]}}}`** — top-level. Asserts the checkpoint record's saved fan-out
>   progress at first-run end. Each `<instance_assertion>` is
>   `{state: <not_started|in_flight|completed> | state_one_of: [<state>, …], result: <value>,
>   result_is_error: <bool>, completed_inner_positions: [{node_name, attempt_index}, …]}` (fields
>   optional; assert what the fixture cares about). `state_one_of` accommodates dispatch-timing
>   nondeterminism (e.g. a sibling `in_flight` vs `not_started` under concurrent execution).
> - **`instances_executed_during_resume: [<int>, …]`** / **`instances_skipped_during_resume:
>   [<int>, …]`** — appear under a `resume:` block. Assert which fan-out instances re-ran on resume
>   (failed / cancelled / not-yet-started) vs. were skipped (completed-and-rolled-forward, including
>   degraded instances).

## Conformance test impact

Demonstrating fixtures (numbers assigned at acceptance) live under the **exercising capability's**
directory (`pipeline-utilities/conformance/`) — conformance-adapter is a meta capability with no
fixtures directory of its own:

- **`crash_injection` resume** — a fan-out under a checkpointer where instance 0 completes, a
  `crash_injection: {after_fan_out_instance: {node: process, index: 0}}` ends the first run with **no**
  error, and resume rolls instance 0 forward (skipped) while instance 1 runs. Exercises the directive
  with a plain (non-degraded) completion first.
- **mock `cause` chain** — a node whose `flaky` failure carries a `cause` (a categorized error caused
  by another categorized error); a `FailureIsolation` at a non-node placement catches it, and the
  failure-isolation event's `chain` records both non-carrier links with the engine carrier flagged,
  with the derived `category` the **outermost** non-carrier (pinning pipeline-utilities §6.3 / 0068's
  surface-wins derivation — the case 0068's fixture 066 left out for lack of this directive).

These two directives also unblock, in their own proposals' accepts:

- **0069** — the degrade+resume fixture (`crash_injection` after a degraded instance's save).
- **0068** — the nested multi-carrier case (verify parent-node middleware on a parallel-branches node
  is already adapter-expressible per §11.6; if so, no further vocabulary needed).

## Versioning

**MINOR bump** (pre-1.0):

- §5.6 / §5.8 gain documentation of the crash/resume vocabulary (descriptive of existing adapter
  behavior — no behavior change for these), plus two new adapter capabilities (`crash_injection`,
  mock `cause`).
- Demonstrating fixtures for the two new directives.

**Behavior-change note.** The formalized-existing directives codify what conformant adapters already
implement (the fixtures exercise them today), so they impose no new requirement beyond writing it
down. `crash_injection` and mock `cause` are genuinely new adapter capabilities a conformant adapter
MUST add. No capability *behavior* spec changes — this is test-vocabulary only.

## Out of scope

- **The failure-mock family catalog / rationalization.** The five organically-grown `flaky*`
  directives (`flaky` / `failure_sequence`, `flaky_per_index`, `flaky_by_index`,
  `flaky_instance_only`, `flaky_resume_aware`) are *not* formalized here — faithfully documenting
  them, or rationalizing them into one parameterized `flaky` (attempt / run / instance / invocation
  modes), is a focused follow-on proposal. This proposal adds only the cross-cutting `cause` field
  they can all carry.
- **Formalizing every other undocumented §5 convention.** Not a blanket sweep of all inline
  conventions (e.g. per-fixture `update_pure_from_state` operations stay inline per §3.2 / 0055's
  design).
- **A "broken middleware" mock** (a custom `instance_middleware` that drops `collect_field`). 0069's
  §9.3 SHOULD covers that case with a documented null consequence; exercising a deliberately
  non-conformant middleware is not worth a dedicated mock.
- **Capability behavior changes.** Nothing here changes graph-engine / pipeline-utilities / etc.
  behavior; it adds the test vocabulary to *exercise* already-accepted behavior.

## Alternatives considered

- **Per-index mock failure categories + an `FailureIsolation` predicate** (instead of
  `crash_injection`, to trigger a resume by making one instance degrade and a sibling propagate).
  Rejected: a contortion that models a fake scenario (a predicate-differentiated sibling failure) to
  reach the real one (a crash after a degrade). `crash_injection` expresses the actual event — a
  process crash at a checkpoint boundary — and generalizes to resume-from-any-state.
- **Leave the existing mock/resume vocabulary informal; add only the two directives** (the "narrow"
  option). Rejected: it builds spec'd directives on undocumented conventions, and leaves the 0055 §5
  gap open. Documenting what `crash_injection` / `cause` extend is the complete version.
- **Mock `cause` as a flat second category on the same entry** (rather than a nested `cause`).
  Rejected: a single chain can be deeper than two links (carrier → re-categorized → originating);
  the recursive `cause` expresses arbitrary depth and matches the host languages' native chaining.
