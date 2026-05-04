# 0008: Pipeline Utilities — Checkpointing

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-30
- **Targets:** spec/pipeline-utilities/spec.md (adds §10)
- **Related:** 0001, 0003, 0004, 0005, 0007
- **Supersedes:**

## Summary

Add a normative **Checkpointer** contract to pipeline-utilities §10 that lets a graph invocation
persist its state at well-defined save points and resume from a prior invocation_id without
restarting from scratch. The contract is backend-agnostic in the same architectural sense the
v0.7.0 observability spec is backend-agnostic: pipeline-utilities §10 defines the protocol; the
core package ships an in-memory and a SQLite implementation; durable-execution platforms
(Temporal, DBOS, Restate) plug in as sibling packages. Graph-engine §6 supplies the save-point
trigger — every `completed` event is a candidate save. On resume, the engine consults the
Checkpointer for the latest record and continues from the first incomplete node in graph
topology.

## Motivation

Charter §1.3 names "checkpoint/resume" as a first-class pipeline-utilities concern; charter §4.2
enumerates `Checkpoint` as a core abstraction; charter §2.2 cites two reference projects that
each rebuilt this pattern independently:

> Multi-hour runs fail at item 847 of 1,200. Restart from scratch is not acceptable. Bird-Dog
> and Audio Refinery both built this independently.

A third internal pipeline project (referred to below as the "state-snapshot reference") uses a
JSON-per-stage checkpoint pattern that is closer to the state-snapshot model this proposal
adopts, and is explicitly cited as a motivating example in the design discussion below. No
prior proposal has specified the contract.
Pipelines doing meaningful LLM work today either rebuild this pattern from scratch (the audio-
refinery approach: filesystem outputs as implicit checkpoint), wire up a heavyweight workflow
runtime (Temporal class), or accept that interrupted runs are unrecoverable.

The architectural choice this proposal codifies is **the seam, not the backend**. Just as
observability §1 defines the cross-backend contract and §2-§9 provide one specific OTel
realization, pipeline-utilities §10 defines the Checkpointer protocol and ships two reference
implementations alongside it; future durable-execution adapters and observability-backend-style
sibling packages plug in without spec changes. This pattern keeps OA's commitment to
"transparency over abstraction" (charter §3.1 principle 8) — the contract is small, the
storage decisions are explicit, and the user can swap implementations by installing a different
sibling.

### Reference patterns from existing projects

Two production projects have built versions of this independently. Both are referenced for
motivation; neither dictates the spec, but the spec is informed by what they converged on.

**Content-addressable-output reference (Audio-refinery).** Resume is a content-addressable-
output pattern: each pipeline stage writes its output to a deterministic path derived from a
stable per-item identifier; on re-run, each stage checks "does output exist and is it
non-empty?" and skips items already complete. There is no separate checkpoint storage — the
output filesystem is the checkpoint. This works because outputs are content-addressable and
atomic, but only addresses the "stage output already on disk" case; it does not capture
intermediate state.

**State-snapshot reference (internal pipeline project).** Resume is a state-snapshot pattern:
each pipeline stage's output (a typed list of records) is serialized to JSON in a checkpoint
directory. On re-run, each stage's first action is to load the checkpoint; if it returns
non-None, the stage skips execution and uses the loaded data; otherwise it runs and saves at
the end. Granularity is per-stage; per-item granularity is achieved with a per-item filename
suffix.

The proposal adopts the state-snapshot shape (durable record per save point) as the **core
contract** because state-snapshot generalizes — every pipeline has state; not every pipeline
has filesystem-addressable outputs. The content-addressable-output shape — bypass-execution-
when-output-exists — is layered on top by the user as a small middleware (a `(state) -> bool`
predicate around a node) using the existing pipeline-utilities §6 middleware seam, and is
**explicitly out of scope** for this proposal.

## Detailed design

### Pipeline-utilities §10: Checkpointing

#### 10.1 Checkpointer protocol

Implementations MUST define a Checkpointer abstraction with four operations:

- `save(invocation_id: str, record: CheckpointRecord) -> None` — persist a checkpoint record
  for the given invocation. After return, the record MUST be durable across process crashes
  for backends that document durability (in-memory backends are NOT durable and MUST document
  this). Default behavior is **synchronous** — `save` returns only after persistence succeeds.
- `load(invocation_id: str) -> CheckpointRecord | None` — return the most recent record for
  this invocation, or `None` if no record exists. The returned record MUST be structurally
  identical to what `save` last wrote for this invocation_id (round-trip integrity).
- `list(filter: CheckpointFilter | None = None) -> Iterable[CheckpointSummary]` —
  enumerate saved invocations. The summary shape includes at minimum `invocation_id`,
  `correlation_id`, `last_saved_at`, and `completed_node_count`. The `filter` shape is
  implementation-defined (per-language ergonomic API: query record matching by date range,
  correlation_id, completion status, etc.).
- `delete(invocation_id: str) -> None` — remove all records for the given invocation.
  Implementations MUST tolerate `delete` on a non-existent invocation_id (no-op, no error).

The protocol leaves serialization to the backend. The `CheckpointRecord` is an in-memory typed
object the engine hands to `save`; backends MAY pickle, JSON-encode, protobuf-serialize, or
keep references to live objects (in-memory backends). Each backend's documentation MUST state
which state shapes it supports — e.g., "JSON-native types only," "anything pickleable," "any
shape supported by Temporal's data converter."

#### 10.2 Checkpoint record shape

The `CheckpointRecord` carries:

- `invocation_id` — string. Per graph-engine v0.6.0 / observability §5.1; framework-generated
  UUIDv4 at invocation start.
- `correlation_id` — string. Per observability §3; caller-supplied or framework-generated;
  flows unchanged across resume (a resumed invocation keeps the original `correlation_id`,
  which is invocation-scoped).
- `state` — the post-merge outermost state at the latest save point. Type is the user's
  declared outermost state schema (graph-engine §1).
- `completed_positions` — ordered sequence of `NodePosition` records, one per completed node
  attempt that has been merged. Each position carries `namespace` (per graph-engine §6),
  `node_name`, `step` (monotonic across the invocation, including subgraph-internal nodes),
  `attempt_index`, and `fan_out_index` (when present).
- `fan_out_progress` — when the latest save point is inside an in-flight fan-out, a structure
  capturing per-instance status: completed instances (with their results already merged into
  `state`), in-flight instances (which `fan_out_index` slots were running at save time), and
  not-yet-started instances. This is required for §10.7 fan-out resume; for the v1 atomic-
  resume model (see §10.7), the field MAY be absent and the engine treats fan-out as a unit.
- `parent_states` — when the latest save point is inside a subgraph or fan-out instance, the
  ordered sequence of containing-graph states (outermost first). Per graph-engine §6
  semantics; preserved across resume so the engine can re-enter the subgraph correctly.
- `last_saved_at` — timestamp. Implementation-defined precision; SHOULD be monotonic per
  invocation (later saves have later timestamps).
- `schema_version` — string. Implementation-defined; lets backends evolve the record shape
  without breaking older saved records.

#### 10.3 Save granularity — every `completed` event

The engine offers a save point at every graph-engine §6 `completed` event for the outermost
graph (i.e., one save point per node attempt that finishes — successful merge or failure
captured). The engine calls `Checkpointer.save(invocation_id, current_record)` with the
record reflecting state immediately after the event. Save is **synchronous** (the engine
awaits `save` before continuing to the next node) so that a crash immediately after a
`completed` event cannot have lost the corresponding save.

Backends MAY batch internally — e.g., a high-throughput backend might buffer multiple records
and flush at intervals — but the protocol's behavioral contract is "what `load` returns after
a `save` completes is what was saved." Backends that batch MUST flush before `save` returns
to honor this; backends that defer flushing accept the risk of losing the last buffered
records on crash.

Subgraph-internal `completed` events also fire saves, with `parent_states` populated per
§10.2. This means a long-running subgraph generates one save per inner-node completion, and
resume can re-enter the subgraph at any boundary.

`completed` events from inside fan-out instances also save, populating `fan_out_progress`.

#### 10.4 Resume model — `invoke(resume_from=invocation_id)`

To resume, the application calls `invoke(...)` with a `resume_from` parameter naming a prior
`invocation_id`. The engine:

1. Calls `Checkpointer.load(resume_from)`. If `None` is returned, the engine raises a
   resume-failure error (canonical category `checkpoint_not_found`). If non-None, proceed.
2. Restores the loaded `state` as the post-merge state at the latest save point.
3. Restores the `correlation_id` from the loaded record (a resumed invocation keeps its
   original `correlation_id`; cross-backend pivots remain valid).
4. Generates a new `invocation_id` for the resumed run. **Resume produces a new invocation
   per execution attempt, not a continuation of the original invocation_id.** Rationale: each
   attempt at completing the graph is its own invocation in the observability and audit
   sense; the `correlation_id` provides the cross-attempt join key.
5. Determines the resume entry point by inspecting `completed_positions`: the engine resumes
   from the first node in graph topological order whose position is not in
   `completed_positions`. Subgraph re-entry uses `parent_states` to reconstruct the subgraph
   stack.
6. Runs from that entry point to graph termination, dispatching `started`/`completed` events
   normally for the resumed nodes, with `attempt_index` reset to 0 (per §10.6).

The state-restore-not-event-replay choice is deliberate. OA's reducer/partial-update model
(graph-engine §1) makes state at any node boundary equivalent to "all prior nodes' merged
contributions" — there is no need to replay events to reconstruct it. Event-replay (the
Temporal model) is required when nodes are not deterministic and must consult their
journaled past results; OA's graph-engine §5 already mandates determinism for the same input,
so state-restore is sufficient.

#### 10.5 Idempotency contract

Nodes MUST be idempotent under re-execution. A crash mid-node (between a node's `started`
event and its `completed` event) leaves the node's external side effects in an unknown state;
on resume, the engine re-runs that node from its start. Nodes that perform non-idempotent
external operations (POST to a payment API, send an email) MUST guard those operations with
the user's own idempotency mechanism (idempotency keys, conditional database writes, output-
existence checks at the node body's entry).

This matches both reference patterns cited above: stages are idempotent under re-execution
because output-file presence (content-addressable-output reference) or checkpoint-file
presence (state-snapshot reference) blocks duplicated work. OA does not enforce idempotency
— it documents the contract.

#### 10.6 Retry on resume — `attempt_index` resets

When a node is resumed (i.e., it had a `started` but not a `completed` event in the saved
record, or it had not yet started), its `attempt_index` resets to `0`. Retry budgets configured
on the wrapped node (per pipeline-utilities §6.1) restart fresh on resume.

Rationale: retry budgets exist to bound transient-failure recovery during a single execution
attempt. A resumed invocation is a new execution attempt; the user's intent in resuming is
generally "give it a fresh chance," not "honor whatever attempts the prior process used up."
Persisting `attempt_index` across resume would surprise users whose retry budget got exhausted
in the prior process and now find that resume can't recover from a single transient failure.

This is consistent with §10.4's choice to mint a new `invocation_id` for the resumed run:
each resume is a fresh invocation in the observability sense, with its own retry budget.

#### 10.7 Fan-out resume — atomic in v1

When a fan-out is in flight at crash time (some instances completed and merged; some in-
flight; some not yet started), v1 resume re-runs the **entire fan-out** from scratch. The
fan-out node's `completed_positions` entry is absent until all instances have completed and
merged; on resume, the engine sees the fan-out as not-yet-completed and restarts it.

The cost: instances whose work already completed and merged to `state` get re-run. For
fan-outs whose inner work is expensive (LLM calls, API requests), this is undesirable. A
follow-on proposal will add **per-instance resume**, where `fan_out_progress` is consulted
on resume and only the not-yet-completed `fan_out_index` slots are re-dispatched. The
follow-on requires careful spec around state semantics (instances whose merges happened
must not re-merge on resume) and is deferred to keep this proposal scope-bound.

Implementations MAY populate `fan_out_progress` on save in v1 (it is harmless detail), but
the engine MUST NOT consult it during resume in v1 — atomic restart is the v1 behavior.

#### 10.8 Composition with §6 observer hooks

`Checkpointer.save` calls SHOULD emit a graph-engine §6-style observer event so the
observability mapping (per OTel mapping §6) can surface checkpoint saves as spans. The exact
event shape — name, attributes — is left to the implementation; a span like
`openarmature.checkpoint.save` with attributes for `invocation_id`, `last_saved_at`, and
backend identifier is the recommended shape.

This is `SHOULD` rather than `MUST` because not all backends will want the observability
overhead — a high-throughput in-memory checkpointer issuing 10K+ events per second per
invocation would dwarf the actual graph events. Backends MAY suppress event emission via
configuration; users choosing to do so accept the loss of save-point visibility in their
trace UI.

#### 10.9 Composition with detached trace mode (observability §4.4)

Detached trace mode (observability §4.4) and checkpoint scope are **independent**. Detached
trace mode is purely about trace UI organization — fragmenting the OTel span tree of a single
invocation into multiple traces for backend display. Checkpoint scope is about execution
recovery — what unit of work resumes as a unit.

A single `invoke()` call produces exactly one Checkpointer record set keyed by one
`invocation_id`, regardless of how many detached traces its execution produced. The
`CheckpointRecord` captures whatever state and progress exists at save time; resume is
unified at the top-level invocation. A user who configured a fan-out as detached for trace-
visualization reasons does not gain or lose any per-instance resume granularity from that
configuration — that is a fan-out resume question (§10.7), not a detached-trace question.

#### 10.10 Errors

New canonical runtime category: `checkpoint_not_found` — raised when `invoke(resume_from=X)`
is called and `Checkpointer.load(X)` returns `None`. Non-transient (no auto-recovery via
retry — the checkpoint genuinely does not exist).

New canonical runtime category: `checkpoint_save_failed` — raised when `Checkpointer.save`
itself raises during a `completed` event handler. The behavior of the engine on save failure
is implementation-defined: implementations MAY treat save failure as a transient that bubbles
up via standard middleware (allowing user retry middleware to reattempt), or MAY raise to the
caller of `invoke()` immediately. Implementations MUST document their choice.

New canonical runtime category: `checkpoint_record_invalid` — raised when
`Checkpointer.load(X)` returns a record whose schema is incompatible with the current graph
(state shape mismatch, missing required fields, incompatible `schema_version`). Non-
transient.

### Backend layering

The proposal mandates the protocol; sibling-package adapters are NOT specified normatively.
Implementations are expected to ship the protocol plus at least the minimal in-core
implementations described below. Reference adapters for durable-execution platforms
(Temporal, DBOS, Restate) ship as separate packages and follow the protocol; their existence
is informative (charter §3.2 backend-as-sibling-package pattern) and not within the spec
scope.

In-core reference implementations:

- **InMemoryCheckpointer** — keeps records in a Python `dict` (or per-language equivalent).
  Not durable across process crashes. Useful for tests, short-lived runs, and development.
  Accepts any state shape.
- **SQLiteCheckpointer** — persists records to a SQLite database with WAL mode. Durable
  across process crashes within a single host. Accepts any pickleable state shape (Python)
  or any JSON-native shape (cross-language portable mode, configurable). Charter §3.2
  already accepts SQLite as a core dependency for `openarmature-eval`, so adding it for core
  checkpoint is consistent with existing dependency footprint.

Sibling-package adapters (informative, NOT specified by this proposal):

- `openarmature-temporal` — adapts Temporal's event-journal-and-data-converter to the
  Checkpointer protocol. Multi-day human-in-loop pauses, cross-machine fault tolerance.
- `openarmature-dbos` — adapts DBOS's Postgres-backed step journal. Lighter than Temporal,
  Postgres-native.
- `openarmature-restate` — adapts Restate's RPC-native journal.
- `openarmature-redis-checkpoint` — adapts Redis as a fast networked store; useful for
  multi-worker pipelines on a shared host.

Each adapter package MAY add its own configuration ergonomics on top of the Checkpointer
protocol (e.g., Temporal namespace selection); none change the protocol's behavioral contract.

### Cross-spec touchpoints

This proposal does not modify graph-engine §6, but it depends on the v0.6.0 started/completed
event pair model: the `completed` event is the save trigger. No graph-engine spec changes are
required.

This proposal does not modify observability §1-§9, but recommends a SHOULD-level integration
in §10.8: implementations SHOULD surface checkpoint saves through the observability event
stream so trace UIs can render them. The detailed OTel mapping for checkpoint events is
deferred — implementations are free to span them as they see fit pending a follow-on
observability proposal that specifies the canonical span shape (e.g.,
`openarmature.checkpoint.save` with attributes).

This proposal does not modify llm-provider §1-§8.

## Conformance test impact

### New fixtures: pipeline-utilities (024-031)

- `024-checkpoint-save-on-every-completed-event.yaml` — linear graph, in-memory checkpointer
  attached, run normally; assert `Checkpointer.save` was called once per `completed` event,
  with state snapshots reflecting post-merge state at each save.
- `025-checkpoint-resume-from-completed-position.yaml` — three-node linear graph; abort the
  run by raising in node B; assert checkpoint records exist for node A's completed event;
  call `invoke(resume_from=invocation_id)`; assert node A is NOT re-run (no `started` event
  emitted for it during resume), node B and node C run normally, final state matches the
  uninterrupted run's final state.
- `026-checkpoint-record-shape.yaml` — assert the saved record contains all §10.2 required
  fields (`invocation_id`, `correlation_id`, `state`, `completed_positions`, `parent_states`,
  `last_saved_at`, `schema_version`); assert their values are well-formed.
- `027-checkpoint-attempt-index-resets-on-resume.yaml` — node wrapped with retry middleware
  (max_attempts: 3); fail node 3 times to exhaust retry budget; checkpoint exists from the
  first attempt's `completed` event was never reached so checkpoint reflects state before the
  node; `invoke(resume_from=...)` with a retry-success-after-attempt-2 mock; assert resume's
  `attempt_index` starts at 0 and node succeeds on the second attempt of the resumed run
  (i.e., budget did NOT carry over).
- `028-checkpoint-fan-out-atomic-restart.yaml` — fan-out with 3 instances, instances 0 and 1
  complete and merge before instance 2's failure aborts the run; checkpoint exists; on resume,
  assert the fan-out is re-run from scratch (all 3 instances re-dispatch) and final results
  reflect a fresh fan-out execution. Verifies §10.7 atomic-restart behavior in v1.
- `029-checkpoint-subgraph-resume.yaml` — outer graph with a subgraph containing two inner
  nodes; abort during the subgraph's second inner node; checkpoint exists with `parent_states`
  populated; on resume, assert the engine re-enters the subgraph correctly (subgraph's first
  inner node is NOT re-run; second inner node re-runs).
- `030-checkpoint-not-found.yaml` — `invoke(resume_from=fabricated_id)` against an empty
  checkpointer; assert the engine raises a runtime error with category `checkpoint_not_found`.
- `031-checkpoint-correlation-id-preserved-across-resume.yaml` — invoke with explicit
  `correlation_id=abc-123`; abort mid-run; resume; assert the resumed invocation's spans
  (per OTel mapping §5.6) and log records (per OTel mapping §7) all carry the original
  `correlation_id` of `abc-123`, NOT a new auto-generated one. Cross-cuts to observability
  §3.

## Alternatives considered

### Mandate JSON serialization for the record

Rejected. Forcing JSON would either constrain the user's state schema to JSON-native types
(losing the ability to checkpoint pipelines whose state contains datetimes, numpy arrays,
custom dataclasses without escape hatches) or force OA to ship a serialization library
(taking a position on Pydantic vs. attrs vs. cattrs that has nothing to do with the
checkpointing contract). Backends pick their own serialization; documented per backend.

### Save granularity at "checkpoint barriers" rather than every node

Rejected. The charter's `@step(checkpointable=True)` decorator hints at opt-in barriers; this
proposal instead defaults to save-after-every-node and lets backends batch internally if cost
matters. Reasoning: every-node save is the simpler primitive, composes with the existing §6
event stream without new graph concepts, and lets cost-sensitive backends (SQLite with batch
flush, Temporal with native batching) handle granularity as an implementation concern. A
future proposal MAY introduce explicit barriers if the every-node default proves too coarse
in production.

### Event-replay (Temporal model) instead of state-restore

Rejected. Event-replay requires nodes to be deterministic AND to consult journaled past
results for any non-deterministic operation (HTTP calls, random, time, IDs); this is the
strict workflow-determinism constraint Temporal imposes. OA's graph-engine §5 mandates same-
input-same-output determinism but does NOT constrain in-node nondeterminism (LLM calls,
network requests are routine). State-restore is sufficient given OA's reducer/partial-update
model — state at any boundary is fully captured by post-merge state. Event-replay would
constrain user node implementations far more than what's needed.

### Per-instance fan-out resume in v1

Rejected for v1, deferred to a follow-on. Per-instance resume requires careful semantics
around in-flight instance state, partial reduction, and merge ordering; getting it right
demands its own proposal. v1 atomic-restart is acceptable for the common case (small to
medium fan-outs) and explicit about the cost (instances whose work completed get re-run).

### Bundle an `IdempotencyMiddleware` (audio-refinery shape) in this proposal

Rejected. The audio-refinery pattern — bypass node execution when an output-existence
predicate returns true — is a userland concern that composes with the existing pipeline-
utilities §6 middleware seam. A user wanting audio-refinery semantics writes a small custom
middleware around their nodes; OA does not need to spec this. Bundling would expand the
proposal's surface without adding to the contract; users pay for surface area in concept
count, and the every-node save granularity gives them the resume guarantee already.

### Checkpointer as a §6 observer (write-only)

Rejected. Observers are write-only and best-effort by §6 contract — the engine never reads
from them, and observer errors do not interrupt the graph run. Checkpointing is bidirectional
(the engine reads on resume) and consequential (a save failure may be a correctness issue).
These are different roles; conflating them would weaken both contracts. Checkpointer is its
own protocol with its own contract.

## Open questions

None at time of submission.
