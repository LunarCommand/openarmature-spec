# 0021: Graph Suspension and External Signal Resume

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-17
- **Accepted:** 2026-06-03
- **Targets:** spec/suspension/spec.md (creates), spec/graph-engine/spec.md (modifies §3 execution model + §6 NodeEvent to add `suspended` phase), spec/observability/spec.md (modifies §4 span lifecycle + §5 attributes), spec/pipeline-utilities/spec.md (modifies §10 checkpointing — shared persistence integration)
- **Related:** 0008 (checkpointing — shared persistence machinery), 0020 (sessions — composes with suspension for cross-invoke pause), 0003 (observer hooks — paused-phase events), 0001 (graph-engine foundation — node phases)
- **Supersedes:**

## Summary

Create the `suspension` capability spec. Introduces
`suspend(descriptor, mark_node_completed=True)` as a node-side
operation that intentionally pauses an invocation, persists its state
to a durable store, and returns control to the caller with a typed
suspended outcome. The `mark_node_completed` parameter (default
`True`) controls resume behavior: under the default, the engine
continues with the node AFTER the suspending node on resume; the
opt-in `False` re-invokes the suspending node body with the signal
payload merged into state. Resume happens via
`invoke(resume_invocation=..., signal_payload=...)` from any worker
with persistence access. Signal descriptors are typed records
(`signal_id` + optional application-typed `metadata`) describing what
the invocation is waiting for; applications supply typed metadata
schemas (Pydantic / zod) at their discretion. Generalizes
human-in-the-loop, long-running async work, scheduled wakeups, and
external-event-await as flavors of one primitive.

## Motivation

Production agents routinely need to dispatch work that doesn't complete within
the lifetime of a single `invoke()` call:

- **Human approval gates.** A node decides "this action needs sign-off"; the
  graph pauses; later a human approves; the graph resumes.
- **Long-running async jobs.** A node dispatches a slow tool call (browser
  automation, code execution sandbox, multi-minute API job); the graph
  pauses; a callback later delivers the result; the graph resumes.
- **Scheduled wakeups.** A node decides "check back in 24 hours"; the graph
  pauses; a scheduled trigger later resumes it.
- **External event coordination.** A node dispatches a message into a queue /
  bus / topic and pauses waiting for a correlated reply.

Today, the OA engine cannot represent any of these natively. A node returns,
the invocation reaches END (or an artificial sentinel state), and the
application is responsible for:

- Storing some out-of-band marker "this invocation is paused, waiting for X"
- Detecting when the awaited signal arrives
- Calling `invoke(resume_invocation=...)` to resume

The engine has no concept of "paused" as distinct from "completed" or
"errored". Observers conflate the three. Cross-implementation behavior
varies: Python and TypeScript would each invent their own pause conventions.
Every project rebuilds the pause / resume coordination glue.

A spec'd suspension primitive lifts the pattern into the engine:

- **A first-class paused phase** alongside started / completed / error.
  Observers see "this node intentionally suspended pending an external
  signal" as a distinct event, not a synthetic completed-with-pending-marker.
- **A typed signal descriptor** that the node attaches at suspend time. The
  application / harness uses the descriptor to subscribe to the awaited
  signal (a queue topic, an event type, a callback URL slot, a scheduled
  trigger, etc.). Signal descriptors are spec-defined at the protocol level
  (`signal_id` + optional application-typed `metadata`); applications supply
  typed metadata schemas (Pydantic / zod) at their discretion.
- **A uniform resume API.** `invoke(resume_invocation=..., signal_payload=...)`
  works the same way whether the resume is triggered by a human's approval,
  a job-completion event, a scheduled wakeup, or any other signal.
- **Cross-process resume.** The paused-invocation record persists durably;
  any worker with persistence access can resume. This is what makes
  multi-pod / multi-region / serverless deployments work.
- **Composes with sessions (proposal 0020) and the harness contract
  (proposal 0022).** Session state auto-saves at suspend; the harness's
  signal-coordinator path looks up paused invocations and resumes them.

This proposal generalizes what would otherwise be three or four narrower
proposals (HITL, async-job-wait, scheduled-wakeup, message-await) into one
primitive whose semantics are shared. The specific awaited-signal
categories (human approval, job completion, scheduled wakeup, message
correlation, etc.) are application-level concerns layered on top via the
descriptor's metadata; the engine sees only "suspend, persist, resume on
signal".

### Stateless workers as the architectural consequence

The motivating shape this enables — and the property worth naming
explicitly — is **stateless workers**. Between a suspend on machine A
and a resume on machine B, nothing about the invocation lives in any
worker's memory. The paused-invocation record is in shared durable
storage; any worker with access can resume; workers are fully
interchangeable. Machine A may scale down, drain, or die before the
resume signal arrives — the invocation is unaffected because the state
moved from "in machine A's process memory" to "in the durable backend"
at suspend time.

This is the same pattern as stateless HTTP servers backed by shared
session storage: servers are interchangeable, data lives in a backend
they all read. The suspension primitive applies that pattern to
in-progress workflow execution. Without it, the originating worker's
process memory holds the only continuation of a paused graph;
cross-process resume is impossible.

Composition with the other in-flight proposals delivers the full
stateless-worker shape:

1. **Suspension (this proposal)** — provides the pause/resume primitive
   with cross-process resume as the load-bearing case.
2. **Checkpointing (proposal 0008)** — provides the durable backend
   for the persisted state; the same backend serves paused-invocation
   records.
3. **Sessions (proposal 0020)** — provides cross-invoke state under a
   stable identity so the multiplexed worker pool can pick up the right
   conversation / task / workspace on each inbound signal.
4. **Harness contract (proposal 0022)** — provides the dispatch logic
   that routes inbound signals to any available worker, which looks up
   the paused record by `invocation_id` and resumes.

Take any one of those away and the pattern degrades. Suspension alone
gets you the pause/resume primitive; the full stateless-worker shape
emerges when the wave composes.

This matches the runtime shapes OA aims to support natively: pure REST
(any HTTP server replica handles the callback), pure event-driven
(Inngest Connect / EventBridge / Kafka workers, any consumer in the
pool picks up the resume event), and mixed (REST in, event out, REST
callback in — possibly hitting three different worker instances over
the invocation's lifetime). The same agent code runs under all three
because the engine doesn't assume worker affinity at any pause point.

## Detailed design

### 1. Purpose

The `suspension` capability defines how an invocation can intentionally pause
mid-execution, persist its state under a typed signal descriptor, and later
resume from the suspension point with a payload that merges into invocation
state. The capability composes with checkpointing (proposal 0008) for the
shared persistence mechanism, with sessions (proposal 0020) for cross-invoke
state continuity across the pause, and with the harness contract (proposal
0022) for the signal-coordination logic in deployment runtimes.

This capability does NOT define:

- Application-level categorization of awaited signals (human-approval,
  job-complete, scheduled, message-await — these are application
  concerns; applications categorize via typed metadata schemas at
  their own discretion).
- The transport for delivering signals (REST callbacks, event buses, message
  queues, scheduled jobs — these are deployment-runtime concerns).
- Timeout enforcement (spec MAY define a timeout *hint* on the descriptor;
  the runtime / harness owns enforcement).
- Cancellation semantics for suspended invocations (out of scope; can be
  modeled as a synthetic resume with a cancel-signal payload at the
  application level).

### 2. Concepts

**Suspension.** The intentional pause of an in-progress invocation at a
specific node. The node body invokes the engine-side `suspend()` operation,
attaching a signal descriptor that names what the invocation is awaiting.
The engine persists the invocation state and returns control to the caller
with a `suspended` outcome.

**Signal descriptor.** Typed record attached at suspension. Carries a
caller-supplied `signal_id` (correlation token) and optional
application-typed `metadata`. The descriptor lives on the persisted
paused-invocation record and is returned to the caller as part of the
`suspended` outcome.

**Suspended outcome.** The return shape from `invoke()` when a graph
suspends. Distinct from completed (graph reached END) and errored (a node
raised). Carries the `invocation_id`, the `correlation_id`, and the signal
descriptor.

**Signal payload.** The data delivered at resume time. Merged into
invocation state before the graph resumes from the suspension point. Shape
is application-defined; the spec defines the merge semantics.

**Paused-invocation record.** The persisted state of a suspended invocation.
Includes the serialized state, the signal descriptor, the
`invocation_id`/`correlation_id`, and the `completed_positions` (which
nodes finished before the pause). Stored using the same persistence
machinery as proposal 0008's checkpoint records; backends MAY use a shared
store with a discriminator field or separate stores.

**Resume.** A subsequent `invoke()` call with `resume_invocation=<id>` and
`signal_payload=<payload>`. The engine loads the paused record, merges the
signal payload into state, and resumes execution from the node that
suspended.

### 3. The `suspend` operation

A node body invokes `suspend(descriptor, mark_node_completed=True)` to
pause the current invocation. Implementations expose this as:

- Python: a coroutine-returning function (`await suspend(descriptor, ...)`),
  context-var-aware, callable from within a node body.
- TypeScript: an async function or similar runtime-idiomatic surface.

**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `descriptor` | (required) | `SignalDescriptor` per §4. |
| `mark_node_completed` | `True` | Whether to mark the suspending node as completed in the paused-invocation record's `completed_positions`. Controls resume behavior — see below. |

When `suspend(descriptor, mark_node_completed=True)` is called (default):

1. The engine MUST treat the call as the node's terminal action for this
   invocation. The node's `return` value (if any after suspend returns or
   if the node continues past suspend) is ignored.
2. The engine MUST persist the current invocation state, INCLUDING the
   suspending node in `completed_positions`. On resume, the engine
   continues with the node AFTER the suspending node, NOT by re-running
   the suspending node.
3. The engine MUST emit a `suspended` phase NodeEvent for the suspending
   node (see §6 below).
4. The engine MUST return from `invoke()` with a `suspended` outcome
   (see §5).

When `suspend(descriptor, mark_node_completed=False)` is called:

1. Same as step 1 above — `suspend()` is terminal for this attempt.
2. The engine MUST persist the current invocation state, EXCLUDING the
   suspending node from `completed_positions`. On resume, the engine
   re-invokes the suspending node body with `signal_payload` merged into
   state (per §8). The node body must be written re-entrantly: it sees
   the resume as a fresh node-body execution against state that now
   carries the merged signal payload.
3. Same as steps 3 and 4 above.

**When to use which:**

- **`mark_node_completed=True` (default).** "Do work, then suspend; on
  resume, continue forward." The suspending node decided to pause and
  is done with its responsibility for this invocation. The follow-on
  work happens in the next node. Matches OA's "edges drive control
  flow; nodes do work" principle.
- **`mark_node_completed=False` (opt-in).** "Suspend, then do work; on
  resume, run this node body with the payload." The suspending node
  acts on the payload itself after resume rather than handing off to a
  follow-on node. Power-user shape; the node body must handle
  re-invocation cleanly.

Re-invocation under `mark_node_completed=False` is NOT a retry attempt:
`attempt_index` (per graph-engine §6) does NOT increment. Retry tracks
node-body failures; resume tracks intentional pauses. The axes are
independent. A node body that re-runs after resume sees the same
`attempt_index` it had when it suspended.

A node body MAY call `suspend()` again during re-invocation (with or
without `mark_node_completed=False`). Each suspension persists a new
paused-invocation record (or extends the existing one with a new
descriptor — implementation choice). Multiple resume cycles per node are
permitted.

`suspend()` is the node body's terminal action for the current
attempt. The engine MAY implement this via an internal control-flow
exception (raised from `suspend()` and propagated up through any
wrapping middleware to the engine, per §9.4) or via an out-of-band
sentinel return — implementation choice. Implementations MUST document
the exact mechanism. In either case the user-visible contract is
identical: control returns to `invoke()`'s caller via the `suspended`
outcome, and **user code (including middleware) MUST NOT attempt to
catch or suppress the suspension**. Implementations using the
control-flow-exception mechanism SHOULD use an internal exception type
that is not part of the public API; well-formed user code MUST NOT
wrap `suspend()` in a bare `try / except` clause that would intercept
such a type.

Persistence failure at suspend time is a separate concern: the engine
raises `suspension_persistence_failed` (§10) as a normal, catchable
exception that user code MAY handle. The suspension control flow and
the persistence-failure exception are distinct mechanisms.

**Where `suspend()` can be called:**

- ✅ Inside a regular node body
- ✅ Inside a subgraph's node body (suspension propagates; see §9)
- ✅ Inside a fan-out instance's node body (one instance suspends; behavior
  per §9)
- ✅ Inside a parallel-branches branch's node body (one branch suspends;
  behavior per §9)
- ❌ Outside an invocation (raises if called)
- ❌ Inside a middleware (before, around, or after the inner `next()`
  call). MUST raise `suspension_in_unsupported_context` per §10.
  Middleware is meant to wrap node execution, not replace it with a
  suspension; suspending from middleware creates attribution ambiguity
  (which node is recorded as suspending? the wrapped one that may
  never have run?) and gnarly re-entrancy semantics under
  `mark_node_completed=False`. Suspending logic that needs to gate a
  node belongs in a preceding regular node, not in middleware.

### 4. Signal descriptors

A signal descriptor is a typed record with two fields:

| Field | Description |
|---|---|
| `signal_id` | String. A correlation token the application uses to match the awaited signal back to this suspension. Caller-supplied (the node body decides the value). The only required field — uniquely identifies what the invocation is waiting for, so the harness can route the eventual signal back to this paused record. |
| `metadata` | Optional structured payload. Application-defined; the spec treats it as opaque round-trip data. |

The engine's contract over the descriptor is minimal: persist it as part
of the paused-invocation record, return it in the `suspended` outcome
(§5), and make it available to observers. The engine does NOT
inspect, validate, or interpret either field beyond serialization
round-tripping.

**Typed metadata via application schemas.** Applications that want
structure, validation, or categorization over the metadata field
typically supply their own typed schema (Pydantic in Python, zod in
TypeScript, etc.) and pass instances:

```python
class ApprovalMetadata(BaseModel):
    kind: Literal["approval", "review", "escalation"]
    approver_pool: str
    expected_at: datetime | None = None

descriptor = SignalDescriptor(
    signal_id="approval-12345",
    metadata=ApprovalMetadata(kind="approval", approver_pool="finance"),
)
```

On round-trip, the application validates the metadata on the other
side (`ApprovalMetadata.model_validate(loaded_metadata)`). The spec
keeps the engine out of the categorization business entirely — same
shape as how `Tool.parameters` (llm-provider §4) defers schema
authority to the application via JSON Schema, and how State (graph-
engine §2) defers field-level types to user-defined Pydantic models.

Common metadata conventions implementations and harnesses MAY adopt
(non-binding):

- A `kind` / `type` key for application-level signal categorization
  (the application's enum; not normative across implementations).
- A `timeout_hint` key carrying an ISO-8601 duration or deadline
  timestamp; the enforcing runtime is responsible for timeouts
  (see §11).
- A `description` key for human-readable labels useful in ops
  dashboards.
- Harness-specific keys for routing callbacks back to the right
  paused invocation (callback URL slots, subscription correlation
  tokens, etc.).

None of these are spec-mandated. An application that doesn't need
them omits them; an application that wants strict typing puts them
under a Pydantic model with required fields.

The descriptor is returned in the `suspended` outcome (§5) so the
harness has everything it needs at suspend time. On resume, the
caller MAY echo back the descriptor for correlation (confirming the
signal that arrived matches the signal awaited).

### 5. Suspended outcome

When an invocation suspends, `invoke()` returns a structured outcome whose
shape distinguishes suspended from completed and errored:

| Field | Description |
|---|---|
| `invocation_id` | The invocation's unique id (same as it would carry on completion). |
| `correlation_id` | The invocation's correlation id (same as it would carry on completion). |
| `outcome` | One of `"completed"`, `"errored"`, `"suspended"`. |
| `state` | The invocation state at the suspension point. NOT the final state; the graph is paused, not done. |
| `descriptor` | The signal descriptor attached at suspend time. Caller stores this for later correlation. |
| `node_name` | The node that suspended (qualified-name form per graph-engine §6). |

Implementations MAY return this as a discriminated union, an outcome
object with optional fields, or a result-pattern type — surface syntax is
language-idiomatic. The spec defines the fields, not the shape.

A completed invocation continues to return its final state per graph-engine
§3 semantics; an errored invocation continues to raise per graph-engine §4.
The `suspended` outcome is a new third path.

### 6. NodeEvent and observer integration (cross-spec: graph-engine §6)

`NodeEvent` gains a new `phase` value: `"suspended"`. The event fires when
a node calls `suspend()`. The event carries the standard NodeEvent fields
(node_name, namespace, correlation_id, invocation_id, attempt_index, etc.)
plus:

| Field | Description |
|---|---|
| `descriptor` | The signal descriptor attached at suspend time. Observers reading the event see what the invocation is waiting for. |

The `suspended` phase is mutually exclusive with `completed` and `error`
for a given node in a given invocation — a node that suspends does NOT
also emit `completed`. The `started` event still fires before `suspended`
(the node began executing before it suspended).

Spec-side changes to graph-engine §6:

- Add `"suspended"` to the enumerated `phase` values.
- Add `descriptor` to the NodeEvent field table, noting it is populated
  only when `phase == "suspended"`.
- Add a paragraph clarifying that `completed`/`error`/`suspended` are
  mutually exclusive terminal phases for a node in one attempt.

### 7. Resume API

A subsequent `invoke()` call with:

```
invoke(initial_state, resume_invocation=<invocation_id>, signal_payload=<payload>)
```

triggers resume. The engine MUST:

1. Load the paused-invocation record from the configured persistence
   layer.
2. Validate that the record's status is `suspended` (not `completed` or
   `errored`); if not, raise `suspension_record_invalid`.
3. Merge `signal_payload` into the loaded state (see §8 on merge
   semantics).
4. Determine the resume entry point from the paused record's
   `completed_positions`:
   - If the suspending node IS in `completed_positions` (i.e.,
     `mark_node_completed=True` at suspend time — the default):
     emit `started` for the NEXT node downstream from the suspending
     node and continue from there. The suspending node is NOT re-run.
   - If the suspending node is NOT in `completed_positions` (i.e.,
     `mark_node_completed=False` at suspend time): re-invoke the
     suspending node body. The body sees the merged state (signal
     payload overlaid) and runs as a fresh node-body execution. The
     `started` NodeEvent for the suspending node fires again.
5. Continue execution from that point per normal graph-engine semantics.

The `initial_state` parameter on a resuming invoke MAY be either:

- A "skeleton" instance (default values) — the engine ignores it and uses
  the loaded record's state. Useful when the caller doesn't have a
  meaningful state to supply.
- A partially-populated instance — the engine MAY merge it with the
  loaded state. Implementations MAY support this or require skeleton
  state on resume; the spec leaves the choice to implementations. Caller
  MUST NOT rely on cross-impl behavior beyond skeleton support.

Resume semantics with respect to checkpointing (proposal 0008):

- The suspending node's `completed_positions` membership is determined
  by `mark_node_completed` at suspend time (per §3).
- Under the default (`mark_node_completed=True`), resume continues
  with the next node per normal checkpoint-resume semantics.
- Under the opt-in (`mark_node_completed=False`), resume re-invokes
  the suspending node; subsequent nodes run normally after that
  re-execution completes.
- If checkpointing was independently enabled for this invocation, the
  resume continues to save intermediate state per the checkpointer
  configuration.

### 8. Signal payload merge

The signal payload is merged into invocation state at resume entry. Merge
semantics:

- **Default: shallow field overlay.** Each field on `signal_payload`
  overwrites the corresponding field in the loaded state. Reducers
  declared on the state schema (per graph-engine §2) are NOT consulted —
  the merge is a direct field-by-field overwrite. Rationale: the signal
  payload represents authoritative external data ("the human's decision
  is X", "the job result is Y"); applying reducers would obscure this.
- **Schema validation.** The merged state MUST validate against the
  state schema. If it does not, the engine MUST raise
  `suspension_resume_payload_invalid`.
- **Extra fields.** Implementations MAY accept signal payloads with
  fields not declared on the state schema (depending on the schema's
  default openness). The merge applies only to declared fields; extras
  are dropped per the schema's policy.

Implementations MAY offer alternative merge strategies via builder
configuration (`with_suspension_payload_merge_strategy=...`) for cases
where reducer-aware merge is desired. The default behavior is the
shallow overlay above.

### 9. Composition with other capabilities

**9.1 Subgraphs (proposal 0001, 0002).** A node inside a subgraph MAY
call `suspend()`. The suspension propagates: the subgraph invocation
suspends, the outer node containing the subgraph also suspends as a
consequence, the entire outer invocation suspends. Resume re-enters at
the subgraph's suspended node and continues; the outer graph's
projection-out happens normally once the subgraph completes after resume.

**9.2 Fan-out (proposal 0005).** When one fan-out instance calls
`suspend()`, the entire fan-out NODE suspends at the outer-graph level.
From the outer graph's perspective, the suspension is identical to a
regular node calling `suspend()` directly — the `mark_node_completed`
parameter (per §3) controls resume behavior the same way:

- **`mark_node_completed=True` (default).** On resume, the engine
  continues at the next node after the fan-out. The fan-out's
  aggregate output (`target_field`, etc.) is whatever was accumulated
  up to the suspend point; subsequent nodes see an incomplete
  aggregate.
- **`mark_node_completed=False`.** On resume, the fan-out node
  re-runs from scratch — all instances start fresh. The suspending
  instance's pending signal becomes meaningless; any signal payload
  delivered on resume is merged into outer-graph state and the
  fan-out begins anew with the merged state.

The descriptor that bubbles up is the suspending instance's, with
`fan_out_index` annotated in `metadata` so the harness has attribution
for which instance is awaited.

**Sibling instances are cancelled when any instance suspends**,
regardless of `error_policy`. This is a deliberate constraint:

- Under `error_policy="fail_fast"` (the default), cancellation on
  suspend is consistent with cancellation on error.
- Under `error_policy="collect"`, suspension is INCOMPATIBLE — the
  engine raises a configuration-time or runtime error
  (`suspension_in_unsupported_context`, see §10) when an instance
  inside a `collect`-mode fan-out calls `suspend()`. The fan-out
  cannot meaningfully aggregate partial results across multiple
  concurrent suspends within one node; spec'ing the multi-suspend
  aggregate-descriptor case is deferred. The "wait for N parallel
  signals before continuing" pattern is achievable today via a
  node that dispatches N async jobs and then calls `suspend()` ONCE
  at the outer level, with the harness's signal coordinator
  aggregating the N signal arrivals before firing resume (per
  proposal 0022's signal-coordinator contract). The harness layer
  is the right home for this fan-in logic; the engine stays simple.

**9.3 Parallel branches (proposal 0011).** Same shape as fan-out.
The whole `add_parallel_branches_node` suspends at the outer level
when any branch calls `suspend()`. The descriptor is the suspending
branch's, with `branch_name` annotated in `metadata`. Sibling
branches are cancelled regardless of `error_policy`; suspension is
incompatible with `error_policy="collect"` for parallel-branches
(same `suspension_in_unsupported_context` error category).

**Design rationale.** The "wait for many concurrent signals and
aggregate them" pattern often indicates a graph that would be
clearer expressed as a sequence — dispatch all the work in one
node, suspend at the outer level, let the harness coordinate the
fan-in. Engine-level multi-suspend would add significant complexity
(partial aggregation, per-instance timeouts, atomic vs incremental
resume, descriptor reconciliation) for use cases that compose
naturally one layer up. v1 stays simple; a follow-on proposal can
spec the multi-suspend case with concrete use-case anchors if real
demand surfaces.

**9.4 Middleware (proposal 0004).** Middleware MAY wrap a suspending
node. The middleware's pre-`next()` block runs normally; the middleware's
post-`next()` block does NOT run when the inner node suspends (since
`next()` does not return — it raises a typed internal control-flow
exception, or returns a sentinel, per implementation). Implementations
MUST document the exact mechanism but the observable behavior is the
same: post-suspend middleware code does not execute on the suspending
attempt.

**Middleware itself MUST NOT call `suspend()`.** Attempting to suspend
from middleware (before, around, or after the inner `next()` call) MUST
raise `suspension_in_unsupported_context` (§10). Reasons:

- **Attribution ambiguity.** The paused record names a suspending
  node; if middleware suspends before the wrapped node runs, there's
  no clean answer for which node to attribute the suspension to. The
  wrapped node hasn't started; recording it as suspending would
  produce a `started`-then-`suspended` event pair without the node
  body ever executing, which is confusing for observers.
- **Composition gets pathological.** Two middlewares wrapping a node
  where the outer one suspends — on resume, do we re-enter the
  outer middleware from its top, the inner middleware (which never
  ran), or jump to the wrapped node? Each answer has different
  semantics; spec'ing the interaction is significant complexity.
- **Re-entrancy under `mark_node_completed=False`.** What does "re-run
  on resume" mean for middleware? The whole middleware chain? Just
  the suspending middleware? Different implementations would diverge.

The use cases for middleware-suspend (e.g., "gate this node behind a
human approval") are achievable by extracting the suspend into a
preceding regular node, which keeps the engine and observability
attribution clean. The "do work, then suspend, then next node does
work" pattern is the recommended shape (and matches the
`mark_node_completed=True` default).

**9.5 Checkpointing (proposal 0008).** Suspension uses the same
persistence mechanism as checkpointing. Implementations MAY use a single
backend store with a discriminator field distinguishing checkpoint
records from paused-invocation records, or separate stores. The spec
treats them as distinct record types with overlapping persistence
requirements.

A paused-invocation record's lifetime is NOT bound to invocation
completion — the record persists until either (a) the invocation
resumes and runs to completion, at which point the record MAY be
deleted per backend policy, or (b) the application explicitly deletes
the record (cancellation), or (c) backend-defined retention expires.

**9.6 Sessions (proposal 0020).** When a session is bound to the
invocation, the session SHOULD save at suspend time alongside the
paused-invocation record. This ensures a fresh worker resuming the
suspension sees consistent session state.

**If session save fails at suspend, the engine MUST raise**
`suspension_persistence_failed` (§10) and convert the invocation
outcome from `suspended` to `errored`. The paused-invocation record
either is not written, or is rolled back / marked invalid if already
written — implementations MUST ensure subsequent resume attempts do
not see a partial state (a paused-invocation record present alongside
a stale or missing session record). Suspend is observably atomic:
either both records persist consistently, or the invocation errors.

**Backend-level mitigation.** Transient failures (connection blips,
brief backend unavailability, intermittent timeouts) are the
backend's responsibility. Well-implemented SessionStore backends
SHOULD apply internal retry policies, connection-pool warmup, and
similar recovery strategies before reporting a save failure to the
engine. By the time the engine surfaces
`suspension_persistence_failed`, the backend has exhausted its
recovery strategies and the failure is definitive. The engine does
NOT attempt retries at its layer; that responsibility lives where
the backend semantics are known (network shapes, error
classifications, idempotency keys, etc.). Implementations MAY expose
retry-policy knobs as backend extensions (configurable retry counts
on SessionStore wrappers, jittered-backoff defaults, etc.), but the
spec does not require them.

The same backend-mitigation expectation applies to checkpointer
backends (proposal 0008) when persisting the paused-invocation
record itself.

**Typical scope decomposition for long-running workflows.**
`invocation_id` is stable for the lifetime of the logical invocation
across all suspend/resume cycles — see §7. Long-running workflows
(weeks, months) are typically modeled as MANY short invocations under
one long-lived session, NOT as one long invocation that pauses many
times. Each user interaction / scheduled trigger / inbound event maps
to its own invocation; the session carries the accumulated cross-
invocation context. Within any single invocation, suspend/resume
cycles are typically short and bounded. Genuinely long-running single
invocations (e.g., "send a letter, suspend, wait weeks for the
mailed-in response") are supported but uncommon; backend persistence
and observability mappings handle the long-lived `invocation_id`
appropriately (paused records persist as long as needed; observers
use span links between suspend and resume spans per §11). When in
doubt about which scope to use, prefer many-short-invocations-per-
session over one-long-invocation-with-many-pauses.

**9.7 Harness contract (proposal 0022, planned).** The harness contract
specifies how a deployment runtime routes signal callbacks back to the
right paused invocation. The suspension primitive provides the
descriptor + persisted record; the harness is responsible for the
external signal coordination.

### 10. Errors

Canonical error categories introduced by this proposal:

- **`suspension_persistence_failed`** — engine could not persist the
  paused-invocation record at suspend time. Invocation outcome is
  errored, not suspended.
- **`suspension_record_invalid`** — resume requested for an
  `invocation_id` that is not in `suspended` status (completed,
  errored, never-existed, or already-resumed).
- **`suspension_resume_payload_invalid`** — merged signal payload
  does not validate against the state schema at resume time.
- **`suspension_in_unsupported_context`** — `suspend()` called from a
  context where it is not permitted. Reserved for: (a) `suspend()`
  called outside an invocation; (b) `suspend()` called inside a
  fan-out instance or parallel-branches branch whose containing node
  is configured with `error_policy="collect"` (per §9.2 / §9.3);
  (c) `suspend()` called from middleware (per §9.4). Implementations
  SHOULD detect (b) at compile / registration time when feasible;
  runtime detection is the spec-mandated minimum for all three cases.

### 11. Observability (cross-spec: observability §4, §5)

The invocation root span MUST close at suspend time with a status code
indicating the invocation paused (distinct from "OK" / "ERROR" — the
spec extends §4.2 status mapping to include a `SUSPENDED` flavor, which
backends map per their convention).

The suspending node's span closes with the same suspended status, and
carries the signal descriptor as a span attribute set:

- `openarmature.suspension.signal_id` — the descriptor's `signal_id`.
- `openarmature.suspension.metadata.*` — flattened descriptor
  metadata fields. Applications using a typed metadata schema
  (Pydantic / zod) get the model's fields surfaced as individual
  span attributes by the implementation's serializer.

A new invocation span opens on resume; the resume span and the suspend
span share `correlation_id` so trace UIs can join them. Whether the
resume span is a continuation of the suspend span or a sibling under
the same trace is backend-mapping-dependent (OTel observers SHOULD use
span links or a parent-of relationship per OTel conventions).

### 12. Determinism

Suspension is a control-flow primitive; it does not perturb in-flight
determinism. An invocation that suspends and resumes produces the same
final state and event sequence as an invocation that did not suspend,
provided the signal payload matches the data the application would have
supplied directly.

The pause duration itself is not part of the invocation's deterministic
contract — the engine cannot guarantee how long an external signal
takes to arrive. Observers timestamp events as they fire; the resume
events carry timestamps from the resume time, not the suspend time.

### 13. Out of scope

- **Application-level signal categorization.** Whether an application
  groups its suspensions by `kind`, `category`, or any other axis is
  out of scope. Applications that need typed categorization supply a
  Pydantic / zod model for the descriptor's metadata field.
- **Signal delivery transport.** REST callbacks, event buses, queue
  messages, scheduled triggers — runtime concerns, addressed by the
  harness contract (proposal 0022) and per-runtime implementations.
- **Timeout enforcement.** The descriptor MAY carry a timeout hint;
  the runtime / harness owns enforcement. Implementations MAY add a
  default-timeout knob; the spec stays silent.
- **Cancellation.** An application MAY cancel a paused invocation by
  deleting the record (or by resuming with a cancel-signal payload
  that the graph interprets and routes to a terminal node). The
  primitive itself does not provide a cancel API.
- **Suspension at the engine-attempt level.** Suspension applies to
  whole invocations, not to individual retry attempts. A suspended
  invocation that resumes resumes the WHOLE invocation, not "the
  attempt within the retry that suspended."

## Conformance test impact

New fixtures under `spec/suspension/conformance/`:

- **`001-basic-suspend-resume`** — single-node graph, node calls suspend
  with a descriptor, invoke returns suspended outcome; second invoke with
  resume_invocation + signal_payload runs to completion.
- **`002-suspend-payload-merge`** — signal_payload fields overlay onto
  loaded state; resumed graph reads the merged values.
- **`003-suspend-payload-invalid-schema`** — signal_payload fails state
  schema validation; raises `suspension_resume_payload_invalid`.
- **`004-resume-invalid-record`** — resume requested for non-suspended
  invocation_id; raises `suspension_record_invalid`.
- **`005-suspend-in-subgraph`** — subgraph node suspends; outer invocation
  suspends; resume re-enters at the subgraph's node.
- **`006-suspend-in-fan-out-fail-fast`** — one fan-out instance suspends
  under the default `error_policy="fail_fast"`; siblings cancel; outer
  invocation suspends with descriptor referencing the instance
  (`fan_out_index` annotated in metadata).
- **`007-suspend-in-fan-out-collect-rejected`** — one fan-out instance
  configured with `error_policy="collect"` calls `suspend()`; engine
  raises `suspension_in_unsupported_context` per §9.2 (collect + suspend
  is incompatible in v1).
- **`008-suspend-in-parallel-branches-fail-fast`** — one branch suspends
  under `fail_fast`; siblings cancel; outer invocation suspends with
  descriptor referencing the branch (`branch_name` annotated in
  metadata).
- **`009-suspend-in-parallel-branches-collect-rejected`** — one branch
  configured with `error_policy="collect"` calls `suspend()`; engine
  raises `suspension_in_unsupported_context` per §9.3.
- **`010-suspend-observability-event`** — observer sees a `suspended`
  phase NodeEvent with the descriptor.
- **`011-suspend-span-status`** — OTel span closes with suspended status.
- **`012-suspend-with-sessions`** — session state saves at suspend;
  resume sees the saved session state.
- **`013-suspend-with-checkpointer`** — paused-invocation record persists
  via the configured checkpointer backend.
- **`014-suspend-wrapped-by-middleware`** — middleware wraps a node that
  itself calls `suspend()`; the middleware's pre-`next()` block runs
  normally; the post-`next()` block does NOT execute on the suspending
  attempt.
- **`015-suspend-in-middleware-rejected`** — middleware itself calls
  `suspend()` (rather than its wrapped node doing so); engine raises
  `suspension_in_unsupported_context` per §9.4.

## Alternatives considered

**Keep this as an application-level pattern.** The "Human-in-the-loop"
pattern in the patterns docs scoping thread describes how to model pause
today by composing `terminate-with-sentinel` + `correlation_id` +
`resume_invocation`.

Rejected for the same reasons sessions are not just a pattern:

- The pause/completed/error trichotomy is engine-level. Observers need
  to distinguish — conflating "node intentionally paused" with "node
  finished" or "node failed" obscures the runtime story.
- Cross-impl consistency demands spec definition. Python and TypeScript
  agents pausing for human input should give the same observable
  semantics.
- Every project rebuilds the pause-coordination logic. A primitive
  amortizes that work.

**Spec only HITL.** Define a narrower "human-in-the-loop" primitive
that handles pause for human input specifically.

Rejected: the underlying mechanism is identical across pause causes.
A separate primitive for HITL, then later separate primitives for
async-job-wait and scheduled-wakeup, would split what's fundamentally
one engine capability into three near-duplicates. The signal descriptor
type is the only difference; spec'ing one primitive with a typed
descriptor is the right shape.

**Reuse checkpoint resume directly.** Don't introduce a paused phase;
have nodes return a sentinel state, application stores some out-of-band
"this is paused" marker, application calls `resume_invocation` when
the signal arrives.

Rejected: this is essentially the do-nothing alternative dressed up.
The engine still can't distinguish "intentionally paused" from "crashed
mid-invoke" for observability or operations. The application still
rebuilds the coordination glue. No spec leverage.

**Synchronous pause inside one process.** Suspension semantically
blocks the caller until the signal arrives (the engine yields back to
the caller, the caller waits, then re-enters).

Rejected: this is just `await` and doesn't need spec definition. The
load-bearing case is cross-process resume — pause on one worker,
resume on a different worker, possibly in a different region, possibly
hours or days later. Synchronous pause is achievable today with no
spec changes; the cross-process case is what this proposal exists to
enable.

**Engine-managed signal delivery.** The engine could own the subscription
to awaited signals (callback URLs, event subscriptions, scheduled
triggers, etc.) and resume invocations automatically when signals
arrive.

Rejected: this conflates the engine (a workflow primitive) with the
runtime (the deployment context — REST server, event bus client,
scheduler, etc.). The runtime varies by deployment; the engine should
not bake in any specific runtime's signal-delivery mechanism. The
descriptor + harness-contract split keeps the layers clean.

## Open questions

None at this time. The original draft surfaced six design choices;
all have been resolved through pre-PR review. The list is preserved
here as a placeholder section per the proposal template; reviewers
may add open questions during PR review.
