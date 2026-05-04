# 0009: Pipeline Utilities — Per-Instance Fan-Out Resume

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-04
- **Targets:** spec/pipeline-utilities/spec.md (revises §10.3, §10.7; adds §10.11)
- **Related:** 0005, 0008
- **Supersedes:**

## Summary

Replace proposal 0008's v1 atomic-restart fan-out resume with **per-instance fan-out resume**:
when a fan-out is in flight at crash time, on resume the engine re-runs only the instances
that did not complete and merge into outer state. Instances whose results were already merged
are skipped. The change has three coordinated parts: the engine saves at fan-out instance
internal `completed` events (reversing 0008's §10.3 elision); the `CheckpointRecord`'s
`fan_out_progress` field is now populated and consulted on resume; and Checkpointer backends
gain a configurable batching knob scoped to fan-out internal saves so high-instance-count
fan-outs do not produce overwhelming write volume. The contract for non-fan-out work
(outermost graph, subgraph internals, fan-out node-level completion) is unchanged.

## Motivation

Proposal 0008 ships fan-out resume as atomic — a crash mid-fan-out causes the entire fan-out
to re-run on resume. This is the simpler v1 contract and was the right call for a first
release of the Checkpointer protocol, but it is a real cost in the workloads that motivate
having checkpointing in the first place. Two specific cases:

- **Large LLM fan-outs.** A 1,000-document scoring fan-out crashes after 800 instances have
  completed and merged. Atomic restart re-runs 1,000 LLM calls instead of 200 — an 80% waste
  of the most expensive resource in the pipeline. Cost per resume is multiples of cost per
  successful run.
- **Long-running per-item processing.** A 50-instance fan-out where each instance takes 10
  minutes (extraction, retrieval, summarization) crashes 4 hours in. Atomic restart loses 4
  hours of work even though most instances completed.

In both cases the v1 contract makes resume technically correct but practically uneconomic.
Per-instance resume restores the economics: only the not-yet-completed instances re-run, and
the work already done stays done. The cost — fan-out internal saves and the bookkeeping to
match instance results to merged contributions — is real but bounded by the configurable
batching knob and is paid only inside fan-outs (the rest of the spec is unchanged).

## Detailed design

### Pipeline-utilities §10.3 (revised): Save granularity — fan-out internal saves enabled

Replaces the corresponding rule in proposal 0008 §10.3.

The engine fires a save at every graph-engine §6 `completed` event from the following sources:

- **Outermost-graph nodes.** Unchanged from 0008.
- **Subgraph-internal nodes.** Unchanged from 0008.
- **Fan-out instance internal nodes.** One save per inner-node completion within an instance.
  `parent_states` is populated per §10.2 (the fan-out instance's outer state is the parent);
  `fan_out_progress` is populated per §10.11 to disambiguate which `fan_out_index` slot the
  event belongs to.
- **Fan-out node itself.** One save when the fan-out as a whole has finished and its results
  have merged back into outer state. Unchanged from 0008 in shape; in v2 this save also
  finalizes `fan_out_progress` to mark all instances complete.

The "engine does NOT save during fan-out instance execution" rule from 0008 §10.3 is removed.

### Pipeline-utilities §10.7 (revised): Fan-out resume — per-instance

Replaces 0008 §10.7 atomic-restart with per-instance resume.

On resume into a fan-out that was in flight at crash time, the engine consults the saved
record's `fan_out_progress` field and treats each instance as one of three states:

- **Completed and merged.** The instance ran in the prior execution, its result was merged
  via reducer into outer state, and that merge is reflected in the saved `state`. On resume,
  the engine MUST NOT re-run the instance and MUST NOT re-merge its result. The instance is
  skipped entirely.
- **In-flight at save time.** The instance had begun execution (its first inner node fired
  `started`) but had not completed and merged before the crash. On resume, the engine re-runs
  the instance from its entry point with the same projected per-instance state as the
  original run. The reducer fires when the re-run instance's terminal inner node completes,
  contributing the result to outer `state` for the first time (the original attempt
  contributed nothing because it never reached the merge).
- **Not yet started.** The instance had not been dispatched at save time. On resume, the
  engine dispatches the instance normally.

### Pipeline-utilities §10.11 (new): `fan_out_progress` semantics

The `CheckpointRecord.fan_out_progress` field is a per-fan-out-node mapping (when one or more
fan-outs are in flight at save time). Each entry carries:

- `fan_out_node_name` — the name of the fan-out node in the parent graph.
- `namespace` — the §6 namespace identifying the fan-out node uniquely (handles nested
  subgraphs that contain fan-outs).
- `instance_count` — the resolved instance count for this fan-out (per pipeline-utilities §9
  count or items_field mode).
- `instances` — a sequence of per-instance status entries indexed by `fan_out_index` (`0` to
  `instance_count - 1`). Each entry carries:
  - `state` — one of `completed`, `in_flight`, `not_started`.
  - `completed_inner_positions` — for `in_flight` entries, the inner-node `completed_positions`
    recorded inside this instance up to save time. Unused for `completed` and `not_started`.

`completed` is the load-bearing state. An instance's `completed` status MUST mean: the
instance's reducer fire happened AND the resulting outer state is what the saved record's
`state` field reflects. The atomicity contract is that the engine's per-instance "complete +
merge + save" sequence MUST be ordered such that a crash between merge and save leaves the
instance in `in_flight` state on the saved record (so resume re-runs it). A crash after the
save has succeeded is reflected as `completed` and the instance is skipped. This is the same
correctness model as the rest of §10 — work that hadn't been recorded as saved at crash time
re-runs on resume.

### Pipeline-utilities §10.11.1: Reducer interaction

Per pipeline-utilities §1, fan-out results are merged via the parent state's reducer for the
`target_field`. Per-instance resume preserves the reducer's effect:

- `last_write_wins` — `completed` instances' results already overwrote whatever was there;
  re-running them would no-op (the reducer would write the same value again, assuming
  determinism under §5). Skipping them is correct.
- `append` — `completed` instances' results are already appended to the list in saved
  `state`. Re-running them would double-append, which is incorrect. Skipping is required for
  correctness.
- `merge` — `completed` instances' contributions are already merged into the dict-shaped
  outer field. Re-running would re-merge the same keys (idempotent for `merge` semantics).
  Skipping is correct and avoids redundant work.

The `append` reducer case is why per-instance resume cannot be a "best-effort, may double-
contribute" model. The `completed` status is a correctness guarantee.

### Pipeline-utilities §10.11.2: Composition with `error_policy`

Per pipeline-utilities §9.5, fan-out has two error policies:

- **`fail_fast`.** A failed instance cancels its in-flight siblings; the fan-out raises. On
  resume after a `fail_fast` cancellation: the previously-failed instance is in `in_flight`
  state on the saved record (its terminal inner node never fired `completed`, so no merge,
  so no `completed` save). The previously-cancelled siblings are also in `in_flight` or
  `not_started` state. All of these re-run on resume per §10.7. Instances that had completed
  and merged before the failure remain `completed` and are skipped.
- **`collect`.** The fan-out runs all instances regardless of individual failures; failed
  slots are recorded in `errors_field`. On resume, instances marked `completed` are skipped
  per their normal contribution (whether successful or failed-and-recorded — the `errors_field`
  contribution counts as a merge for `fan_out_progress` purposes). Instances in `in_flight` or
  `not_started` re-run; if they fail again, the failure is again recorded in `errors_field`.

### Pipeline-utilities §10.11.3: Composition with `instance_middleware`

Per pipeline-utilities §9.7, `instance_middleware` (notably retry) wraps each instance's
whole subgraph invocation as a unit. Per-instance resume composes with retry middleware as
follows:

- An instance whose retry middleware exhausted in the prior run produces a `fail_fast`
  cancellation (or a `collect`-recorded failure) per §9.5. The instance's `fan_out_progress`
  state at save time is `in_flight` (no successful merge ever happened — the engine never
  saw a `completed` event for the terminal inner node).
- On resume, the instance re-runs with `attempt_index` reset to `0` per §10.6 — the retry
  budget restarts. This matches the "fresh execution attempt" semantics of resume.
- An instance whose retry middleware succeeded mid-run (e.g., attempt 2 of 3 succeeded) saved
  its `completed` state at the success. On resume, that instance is skipped — the retry
  history is not preserved, but the result is.

### Pipeline-utilities §10.11.4: Configurable batching for fan-out internal saves

Fan-out internal saves can be high-volume in workloads with many instances and many inner
nodes per instance. To keep the cost manageable, Checkpointer backends MAY support
**configurable batching** scoped specifically to fan-out internal saves. The configuration is
per-Checkpointer-instance and implementation-defined (per-language ergonomics: a constructor
parameter, a builder method, etc.). The behavioral contract:

- The configuration knob applies ONLY to fan-out instance internal `completed` events (saves
  triggered per §10.3 from inside a fan-out instance). It does NOT apply to outermost-graph
  saves, subgraph-internal saves, or the fan-out node's own completion save — those remain
  synchronous per §10.3 because they are correctness-critical for resume.
- When batching is enabled, the backend MAY buffer fan-out internal saves and flush them at
  configured intervals (count-based, time-based, or both). The buffered saves represent the
  most recent state of in-flight fan-out instances.
- When the fan-out completes (the engine fires the fan-out node's own `completed` event), the
  backend MUST flush all buffered fan-out internal saves before the fan-out node's save
  returns. This guarantees that the fan-out's success state is durably recorded before the
  engine proceeds.
- A crash with buffered-but-unflushed fan-out internal saves loses those buffered records.
  On resume, instances whose `completed` state was buffered-only re-run (the saved record
  reflects the most recent flushed state). This is acceptable because re-running a completed
  instance under per-instance resume's correctness rules requires a fresh contribution: an
  instance whose `completed` status was lost reverts to `in_flight` or `not_started` and the
  reducer rules in §10.11.1 still apply (the instance contributes to outer state for the
  first time on resume).

The cost trade-off is explicit: batching trades fewer durable writes per fan-out instance for
some redundant re-execution on crash recovery. Backends document their batching defaults and
configuration shape; users opt in with eyes open.

Default behavior is **no batching** (every fan-out internal save is synchronously durable),
to preserve the simplest correctness story for users who do not yet understand their
workload's cost profile.

### Cross-spec touchpoints

- **Pipeline-utilities §10.3** — revised per the §10.3 revision above; fan-out internal saves
  enabled.
- **Pipeline-utilities §10.7** — replaced per the §10.7 revision above; per-instance resume.
- **Pipeline-utilities §10.11** — new section, the per-instance contract details.
- **Graph-engine §6** — no changes. The `completed` event stream is unchanged; the engine's
  decision to call `Checkpointer.save` at fan-out instance internal events is purely a
  pipeline-utilities §10 concern.
- **Observability §5.4** — no changes. Fan-out span hierarchy and attributes are unchanged;
  the per-instance resume model produces no additional spans on the resumed run beyond what a
  fresh fan-out execution produces.
- **LLM-provider §1-§8** — no changes.

## Conformance test impact

### Modified existing fixtures

- `028-checkpoint-fan-out-atomic-restart.yaml` — REMOVED. The atomic-restart contract is
  superseded by per-instance resume; the v1 fixture's expected behavior no longer applies.
  Replaced by `032` and `033` below.

### New fixtures: pipeline-utilities (032-038)

- `032-checkpoint-fan-out-per-instance-resume-skips-completed.yaml` — fan-out with 5
  instances; instances 0, 1, 2 complete and merge; abort during instance 3's first inner
  node; saved record has `fan_out_progress` with instances 0-2 as `completed`, instance 3
  as `in_flight`, instance 4 as `not_started`; on resume, assert instances 0-2 are NOT
  re-run (no `started` events for them), instances 3-4 run normally, final state matches a
  successful uninterrupted run.
- `033-checkpoint-fan-out-per-instance-resume-append-reducer.yaml` — fan-out with 4 instances
  using `append` reducer; instances 0 and 1 complete and merge `[10]` and `[20]` to outer
  list; abort during instance 2; on resume, assert outer list ends as `[10, 20, 30, 40]`
  with NO duplicate values from re-merging completed instances. This is the load-bearing
  correctness fixture for §10.11.1.
- `034-checkpoint-fan-out-in-flight-instance-restart.yaml` — fan-out with 3 instances; one
  instance is mid-execution (its first inner node `started` but second inner node not yet
  fired) at save time; on resume, assert that instance restarts from its entry point (NOT
  from its mid-execution position), runs to completion, and contributes its result via
  reducer for the first time.
- `035-checkpoint-fan-out-fail-fast-resume.yaml` — fan-out with 4 instances and
  `error_policy: fail_fast`; instance 1 fails causing siblings to cancel; abort the whole
  invocation; on resume, instance 0 (which completed before the failure) is skipped; failed
  and cancelled instances all re-run; if they all succeed, final state reflects a successful
  fan-out.
- `036-checkpoint-fan-out-collect-errors-resume.yaml` — fan-out with 5 instances and
  `error_policy: collect`; 2 instances complete successfully, 1 records an error to
  `errors_field`, 2 are not yet started at crash time; on resume, the 3 saved instances
  (success + success + error-recorded) are all skipped (their contributions, including the
  error record, are already in saved state); the 2 not-started instances run; if they
  succeed, final state has 4 successes + 1 error.
- `037-checkpoint-fan-out-instance-middleware-retry-resume.yaml` — fan-out with
  `instance_middleware: [retry]`; one instance fails and exhausts its retry budget in the
  prior run, recording in_flight at save time; on resume, the instance re-runs with
  `attempt_index` reset to 0 (per §10.6); a different mock injection allows it to succeed
  this time; assert final state reflects all instances succeeding.
- `038-checkpoint-fan-out-batching-buffered-saves-lost-on-crash.yaml` — Checkpointer
  configured with fan-out batching (flush every 5 saves); fan-out with 10 instances; a few
  instances complete-and-merge into the buffer but the buffer hasn't flushed before crash;
  on resume, those instances re-run because their `completed` state was buffered-only and
  lost (per §10.11.4); final state is correct; the test verifies acceptable redundancy
  under batching, not silent data corruption.

## Alternatives considered

### Keep atomic-restart and let users opt out per-fan-out

Rejected. Per-instance resume is the right default — atomic restart's economics are bad
enough that most fan-out users want per-instance behavior, and exposing the choice as a
per-fan-out config knob would force users to learn the distinction at fan-out construction
time. Per-instance resume costs the engine fan-out internal saves but the configurable
batching knob mitigates that for high-instance-count workloads. Users who want atomic
behavior can achieve it by writing nothing — running the fan-out without checkpointing
attached — but most users want fast resume more than they want minimum write volume.

### Save instance results pre-merge so resume can re-merge

Rejected. The "save the per-instance result before the reducer fires; on resume, re-issue
the merge" model would let the engine recover from a "merge happened but save didn't" race.
But it requires a different record shape (a per-instance result staging area), introduces a
new failure mode (saved-but-not-merged results that resume must replay through the reducer),
and is no more correct than the simpler "merge + save together; lose at most one instance's
merge" model in §10.11. The simpler model is sufficient for the workloads that motivate
per-instance resume.

### Persist `attempt_index` across resume for retry middleware on instances

Rejected. Per-instance resume preserves §10.6's "attempt_index resets to 0 on resume" rule
unchanged. An instance whose retry middleware exhausted in the prior run gets a fresh retry
budget on resume, consistent with the "resume is a new execution attempt" framing. Users
who want strict retry-budget accounting across resume attempts can implement that at the
application level (record exhaustion in state, check on entry) — the framework does not
take a position.

### Make fan-out internal saves atomic-with-merge via two-phase commit or similar

Rejected. Two-phase commit between the engine's reducer and the Checkpointer's `save` is
overkill for this problem. The "save after merge; lose at most one instance on crash" model
is sufficient, well-understood, and requires no additional protocol surface. Backends
wanting stronger atomicity (e.g., Temporal's event-journal-as-truth) achieve it through
their own mechanisms inside `save`.

## Open questions

- **Does configurable batching also apply to subgraph-internal saves?** Subgraph internals
  fire saves per §10.3 (unchanged from 0008), and a long-running subgraph with many inner
  nodes could face similar volume concerns. Lean toward extending the §10.11.4 batching knob
  to subgraph internals (with the same flush-on-subgraph-completion guarantee), but this
  proposal scopes the knob to fan-out internals only for clarity. A follow-on can extend
  batching if the need is demonstrated.
- **Should `fan_out_progress` be visible in the `list()` summary?** A user inspecting saved
  invocations might want to see "fan-out X is at instance 800 of 1000" without loading the
  full record. Lean: NOT in v2; add as a separate optimization if backends want richer
  summaries.
- **What happens if the graph topology changed between crash and resume (e.g., the user
  edited the fan-out's inner subgraph)?** This is a general resume-after-code-change concern
  that 0008 already declares out of scope. v2 inherits that constraint: the resumed graph
  MUST be structurally identical to the original. A `schema_version` mismatch would surface
  as `checkpoint_record_invalid` (per 0008 §10.10).
