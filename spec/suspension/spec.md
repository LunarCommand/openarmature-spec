# Suspension

Canonical behavioral specification for the OpenArmature suspension capability.

- **Capability:** suspension
- **Introduced:** spec version 0.47.0
- **History:**
  - created by [proposal 0021](../../proposals/0021-graph-suspension.md)
  - §8.7 *Deployment runtime / harness contract* paragraph tightened from a forward-looking placeholder ("formalized by the harness capability when its spec lands") to a concrete cross-reference into the now-existing harness capability spec — points at its §6 *Signal coordinator*, §3.3 *Signal-resume inbound dispatch path*, §5.3 *Suspended outcome handling* (harness MUST NOT block on suspended turns), and §7 *Error categorization at the turn boundary*. Suspension itself stays runtime-neutral; this is a documentary tightening of the cross-spec touchpoint by [proposal 0022](../../proposals/0022-harness-contract.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The `suspension` capability defines how an in-progress invocation can intentionally pause at a specific
node, persist its state under a typed signal descriptor, and later resume from the suspension point with a
payload that merges into invocation state. The pause/resume cycle MAY span workers, processes, regions,
and durations — the load-bearing case is **stateless workers**: a suspend on machine A and a resume on
machine B with nothing about the invocation living in any worker's memory between them.

The capability composes with:

- **graph-engine** — `suspend()` is invoked from inside a node body; the engine recognizes a `suspended`
  outcome from `invoke()` alongside `completed` and `errored`; NodeEvent gains a `suspended` phase per
  graph-engine §6.
- **pipeline-utilities** §10 *Checkpointing* — paused-invocation records use the same shared persistence
  mechanism as checkpoint records per the §10.15 composition rule.
- **sessions** (capability) — session state SHOULD save at suspend alongside the paused-invocation
  record; the atomic-suspend rule (§8.6) ensures fresh workers resuming see consistent state.
- **observability** — the suspending node's span carries suspension attributes per observability §5.8;
  the invocation root span closes with the `SUSPENDED` status flavor per observability §4.2; the resume
  invocation span carries the same `invocation_id` as the suspended one (per suspension §7's reused-id
  contract; the resume span and the suspend span are correlated via shared `invocation_id` per
  observability §4.3, with `correlation_id` inherited as a secondary identity per observability §3.1).

This capability does NOT define:

- **Application-level categorization of awaited signals** (human-approval, job-complete, scheduled,
  message-await, etc.) — these are application concerns, expressed via the descriptor's optional typed
  `metadata` field (a Pydantic / zod / equivalent model the application controls).
- **The transport for delivering signals** (REST callbacks, event buses, message queues, scheduled
  triggers, WebSocket frames, etc.) — these are deployment-runtime concerns. The runtime is responsible
  for the signal-coordination logic that routes inbound signals back to the right paused invocation;
  that contract is formalized by the harness capability (when its spec lands).
- **Timeout enforcement.** The descriptor MAY carry a timeout hint; the runtime owns enforcement.
- **Cancellation semantics for suspended invocations.** A suspended invocation MAY be cancelled by
  deleting the paused-invocation record (backend-defined operation) or by resuming with an
  application-defined cancel-signal payload that the graph routes to a terminal node. No first-class
  cancel API is defined here.

## 2. Concepts

**Suspension.** The intentional pause of an in-progress invocation at a specific node. The node body
invokes the engine-side `suspend()` operation, attaching a signal descriptor that names what the
invocation is awaiting. The engine persists the invocation state and returns control to the caller with
a `suspended` outcome.

**Signal descriptor.** Typed record attached at suspension. Carries a caller-supplied `signal_id`
(correlation token) and optional application-typed `metadata`. The descriptor lives on the persisted
paused-invocation record and is returned to the caller as part of the `suspended` outcome.

**Suspended outcome.** The return shape from `invoke()` when a graph suspends. Distinct from `completed`
(graph reached END) and `errored` (a node raised). Carries the `invocation_id`, the `correlation_id`,
the signal descriptor, the state at the suspension point, and the suspending node's qualified name.

**Signal payload.** The data delivered at resume time. Merged into invocation state before the graph
resumes from the suspension point. Shape is application-defined; the spec defines the merge semantics
(§6).

**Paused-invocation record.** The persisted state of a suspended invocation. Includes the serialized
state, the signal descriptor, the `invocation_id` / `correlation_id`, and the `completed_positions`
(which nodes finished before the pause). Stored using the same persistence machinery as proposal 0008's
checkpoint records per the pipeline-utilities §10.15 composition rule.

**Resume.** A subsequent `invoke()` call with `resume_invocation=<id>` and `signal_payload=<payload>`.
The engine loads the paused record, merges the signal payload into state, and resumes execution from
the node that suspended (the exact resume entry point is governed by `mark_node_completed`; see §3 and
§7).

## 3. The `suspend` operation

A node body invokes `suspend(descriptor, mark_node_completed=True)` to pause the current invocation.
Implementations expose this as:

- Python: a coroutine-returning function (`await suspend(descriptor, ...)`), context-var-aware,
  callable from within a node body.
- TypeScript: an async function or similar runtime-idiomatic surface.

**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `descriptor` | (required) | Signal descriptor per §4. |
| `mark_node_completed` | `True` | Whether to mark the suspending node as completed in the paused-invocation record's `completed_positions`. Controls resume behavior — see below. |

When `suspend(descriptor, mark_node_completed=True)` is called (default):

1. The engine MUST treat the call as the node's terminal action for this invocation. The node's `return`
   value (if any after suspend returns or if the node continues past suspend) is ignored.
2. The engine MUST persist the current invocation state, INCLUDING the suspending node in
   `completed_positions`. On resume, the engine continues with the node AFTER the suspending node, NOT
   by re-running the suspending node.
3. The engine MUST emit a `suspended` phase NodeEvent for the suspending node (per graph-engine §6).
4. The engine MUST return from `invoke()` with a `suspended` outcome (per §5).

When `suspend(descriptor, mark_node_completed=False)` is called:

1. Same as step 1 above — `suspend()` is terminal for this attempt.
2. The engine MUST persist the current invocation state, EXCLUDING the suspending node from
   `completed_positions`. On resume, the engine re-invokes the suspending node body with
   `signal_payload` merged into state (per §6). The node body MUST be written re-entrantly: it sees the
   resume as a fresh node-body execution against state that now carries the merged signal payload.
3. Same as steps 3 and 4 above.

**When to use which:**

- **`mark_node_completed=True` (default).** "Do work, then suspend; on resume, continue forward." The
  suspending node decided to pause and is done with its responsibility for this invocation. The
  follow-on work happens in the next node. Matches OA's "edges drive control flow; nodes do work"
  principle.
- **`mark_node_completed=False` (opt-in).** "Suspend, then do work; on resume, run this node body with
  the payload." The suspending node acts on the payload itself after resume rather than handing off to
  a follow-on node. Power-user shape; the node body must handle re-invocation cleanly.

**Resume re-invocation is not a retry.** Under `mark_node_completed=False`, re-invocation of the
suspending node body is NOT counted as a retry attempt: `attempt_index` (per graph-engine §6) does NOT
increment. Retry tracks node-body failures (per pipeline-utilities §6.1); resume tracks intentional
pauses. The axes are independent. A node body that re-runs after resume sees the same `attempt_index`
it had when it suspended.

**Multiple suspensions per node.** A node body MAY call `suspend()` again during re-invocation (with or
without `mark_node_completed=False`). Each suspension persists a new paused-invocation record (or
extends the existing one with a new descriptor — implementation choice). Multiple resume cycles per
node are permitted.

**Terminal-action mechanism.** `suspend()` is the node body's terminal action for the current attempt.
The engine MAY implement this via an internal control-flow exception (raised from `suspend()` and
propagated up through any wrapping middleware to the engine) or via an out-of-band sentinel return —
implementation choice. Implementations MUST document the exact mechanism. In either case the
user-visible contract is identical: control returns to `invoke()`'s caller via the `suspended` outcome,
and **user code (including middleware) MUST NOT attempt to catch or suppress the suspension**.
Implementations using the control-flow-exception mechanism SHOULD use an internal exception type that
is not part of the public API; well-formed user code MUST NOT wrap `suspend()` in a bare `try / except`
clause that would intercept such a type.

Persistence failure at suspend time is a separate concern: the engine raises
`suspension_persistence_failed` (§9) as a normal, catchable exception that user code MAY handle. The
suspension control flow and the persistence-failure exception are distinct mechanisms.

**Where `suspend()` MAY be called:**

| Context | Allowed |
|---|---|
| Inside a regular node body | ✅ |
| Inside a subgraph's node body (suspension propagates per §8.1) | ✅ |
| Inside a fan-out instance's node body (one instance suspends; see §8.2) | ✅ |
| Inside a parallel-branches branch's node body (one branch suspends; see §8.3) | ✅ |
| Outside an invocation | ❌ raises `suspension_in_unsupported_context` (§9) |
| Inside middleware (before, around, or after `next()`) | ❌ raises `suspension_in_unsupported_context` (§9) |

Middleware is meant to wrap node execution, not replace it with a suspension. Suspending from
middleware creates attribution ambiguity (which node is recorded as suspending? the wrapped one that
may never have run?) and gnarly re-entrancy semantics under `mark_node_completed=False`. Suspending
logic that needs to gate a node belongs in a preceding regular node, not in middleware. See §8.4 for
the full rationale.

## 4. Signal descriptors

A signal descriptor is a typed record with two fields:

| Field | Description |
|---|---|
| `signal_id` | String. A correlation token the application uses to match the awaited signal back to this suspension. Caller-supplied (the node body decides the value). The only required field — uniquely identifies what the invocation is waiting for, so the runtime can route the eventual signal back to this paused record. |
| `metadata` | Optional structured payload. Application-defined; the spec treats it as opaque round-trip data. |

The engine's contract over the descriptor is minimal: persist it as part of the paused-invocation
record, return it in the `suspended` outcome (§5), and make it available to observers (per graph-engine
§6's NodeEvent `descriptor` field). The engine does NOT inspect, validate, or interpret either field
beyond serialization round-tripping.

**Typed metadata via application schemas.** Applications that want structure, validation, or
categorization over the metadata field typically supply their own typed schema (Pydantic in Python, zod
in TypeScript, etc.) and pass instances. On round-trip, the application validates the metadata on the
other side. The spec keeps the engine out of the categorization business entirely — same shape as how
`Tool.parameters` (llm-provider §4) defers schema authority to the application via JSON Schema, and how
State (graph-engine §2) defers field-level types to user-defined typed-state models.

**Common metadata conventions implementations and runtimes MAY adopt (non-binding):**

- A `kind` / `type` key for application-level signal categorization (the application's enum; not
  normative across implementations).
- A `timeout_hint` key carrying an ISO-8601 duration or deadline timestamp; the enforcing runtime is
  responsible for timeouts.
- A `description` key for human-readable labels useful in ops dashboards.
- Runtime-specific keys for routing callbacks back to the right paused invocation (callback URL slots,
  subscription correlation tokens, etc.).

None of these are spec-mandated. An application that doesn't need them omits them; an application that
wants strict typing puts them under a model with required fields.

The descriptor is returned in the `suspended` outcome (§5) so the caller has everything it needs at
suspend time. On resume, the caller MAY echo back the descriptor for correlation (confirming the signal
that arrived matches the signal awaited).

## 5. Suspended outcome

When an invocation suspends, `invoke()` returns a structured outcome whose shape distinguishes
suspended from completed and errored:

| Field | Description |
|---|---|
| `invocation_id` | The invocation's unique id (same value the invocation would carry on completion). |
| `correlation_id` | The invocation's correlation id (same value the invocation would carry on completion). |
| `outcome` | One of `"completed"`, `"errored"`, `"suspended"`. |
| `state` | The invocation state at the suspension point. NOT the final state; the graph is paused, not done. |
| `descriptor` | The signal descriptor attached at suspend time. Caller stores this for later correlation. |
| `node_name` | The suspending node's registered name in its immediate containing graph, per graph-engine §6. |
| `namespace` | The ordered sequence of node names identifying the execution path from the outermost graph down to the suspending node, per graph-engine §6's `namespace` field shape (a list, not a delimiter-joined string). |

Implementations MAY return this as a discriminated union, an outcome object with optional fields, or a
result-pattern type — surface syntax is language-idiomatic. The spec defines the fields, not the shape.

A `completed` invocation continues to return its final state per graph-engine §3 semantics; an
`errored` invocation continues to raise per graph-engine §4. The `suspended` outcome is a new third
path.

## 6. Signal payload merge

The signal payload is merged into invocation state at resume entry. Merge semantics:

**Default: shallow field overlay.** Each field on `signal_payload` overwrites the corresponding field
in the loaded state. Reducers declared on the state schema (per graph-engine §2) are NOT consulted —
the merge is a direct field-by-field overwrite. Rationale: the signal payload represents authoritative
external data ("the human's decision is X", "the job result is Y"); applying reducers would obscure
this.

**Schema validation.** The merged state MUST validate against the state schema. If it does not, the
engine MUST raise `suspension_resume_payload_invalid` (§9).

**Extra fields.** Implementations MAY accept signal payloads with fields not declared on the state
schema (depending on the schema's default openness). The merge applies only to declared fields; extras
are dropped per the schema's policy.

Implementations MAY offer alternative merge strategies via builder configuration (a
suspension-payload-merge-strategy knob or equivalent) for cases where reducer-aware merge is desired.
The default behavior is the shallow overlay above.

## 7. Resume API

A subsequent `invoke()` call with `resume_invocation=<invocation_id>` and `signal_payload=<payload>`
triggers resume. The engine MUST:

1. Load the paused-invocation record from the configured persistence layer.
2. Validate that the record's status is `suspended` (not `completed`, `errored`, or never-existed); if
   not, raise `suspension_record_invalid` (§9).
3. Merge `signal_payload` into the loaded state per §6.
4. Determine the resume entry point from the paused record's `completed_positions`:
   - If the suspending node IS in `completed_positions` (i.e., `mark_node_completed=True` at suspend
     time — the default): emit `started` for the NEXT node downstream from the suspending node and
     continue from there. The suspending node is NOT re-run.
   - If the suspending node is NOT in `completed_positions` (i.e., `mark_node_completed=False` at
     suspend time): re-invoke the suspending node body. The body sees the merged state (signal payload
     overlaid) and runs as a fresh node-body execution. The `started` NodeEvent for the suspending
     node fires again.
5. Continue execution from that point per normal graph-engine semantics.

**`initial_state` on a resuming `invoke()` call** MAY be either:

- A "skeleton" instance (default values) — the engine ignores it and uses the loaded record's state.
  Useful when the caller doesn't have a meaningful state to supply.
- A partially-populated instance — the engine MAY merge it with the loaded state. Implementations MAY
  support this or require skeleton state on resume; the spec leaves the choice to implementations.
  Callers MUST NOT rely on cross-impl behavior beyond skeleton support.

**`invocation_id` is stable across suspend/resume cycles.** The resumed invocation carries the same
`invocation_id` as the suspended one (loaded from the paused record). This is the load-bearing contract
for cross-process resume — the harness routes inbound signals to a paused record by `invocation_id`,
and the resuming `invoke()` returns events scoped to that same id. (Distinct from the resume-on-error
rule per observability §5.1 — a paused-then-resumed invocation reuses the id; an error-then-restarted
invocation mints a fresh one.)

**Resume semantics with respect to checkpointing (pipeline-utilities §10).**

- The suspending node's `completed_positions` membership is determined by `mark_node_completed` at
  suspend time (per §3).
- Under the default (`mark_node_completed=True`), resume continues with the next node per normal
  checkpoint-resume semantics (pipeline-utilities §10.4).
- Under the opt-in (`mark_node_completed=False`), resume re-invokes the suspending node; subsequent
  nodes run normally after that re-execution completes.
- If checkpointing was independently enabled for this invocation, the resume continues to save
  intermediate state per the checkpointer configuration.

## 8. Composition with other capabilities

### 8.1 Subgraphs

A node inside a subgraph MAY call `suspend()`. The suspension propagates: the subgraph invocation
suspends, the outer node containing the subgraph also suspends as a consequence, the entire outer
invocation suspends. Resume re-enters at the subgraph's suspended node and continues; the outer graph's
projection-out happens normally once the subgraph completes after resume.

### 8.2 Fan-out

When one fan-out instance calls `suspend()`, the entire fan-out NODE suspends at the outer-graph
level. From the outer graph's perspective, the suspension is identical to a regular node calling
`suspend()` directly — the `mark_node_completed` parameter (per §3) controls resume behavior the same
way:

- **`mark_node_completed=True` (default).** On resume, the engine continues at the next node after
  the fan-out. The fan-out's aggregate output (`target_field`, etc.) is whatever was accumulated up
  to the suspend point; subsequent nodes see an incomplete aggregate.
- **`mark_node_completed=False`.** On resume, the fan-out node re-runs from scratch — all instances
  start fresh. The suspending instance's pending signal becomes meaningless; any signal payload
  delivered on resume is merged into outer-graph state and the fan-out begins anew with the merged
  state.

The descriptor that bubbles up is the suspending instance's, with `fan_out_index` annotated in the
descriptor's `metadata` so the runtime has attribution for which instance is awaited.

**Sibling instances are cancelled when any instance suspends**, regardless of `error_policy`. This is a
deliberate constraint:

- Under `error_policy="fail_fast"` (the default), cancellation on suspend is consistent with
  cancellation on error.
- Under `error_policy="collect"`, suspension is INCOMPATIBLE — the engine MUST raise
  `suspension_in_unsupported_context` (§9) when an instance inside a `collect`-mode fan-out calls
  `suspend()`. The fan-out cannot meaningfully aggregate partial results across multiple concurrent
  suspends within one node; the multi-suspend aggregate-descriptor case is deferred to a future
  proposal if real demand surfaces. The "wait for N parallel signals before continuing" pattern is
  achievable today via a node that dispatches N async jobs and then calls `suspend()` ONCE at the
  outer level, with the deployment runtime's signal-coordination logic aggregating the N signal
  arrivals before firing resume.

### 8.3 Parallel branches

Same shape as fan-out. The whole parallel-branches node suspends at the outer level when any branch
calls `suspend()`. The descriptor is the suspending branch's, with `branch_name` annotated in the
descriptor's `metadata`. Sibling branches are cancelled regardless of `error_policy`; suspension is
incompatible with `error_policy="collect"` for parallel-branches (same `suspension_in_unsupported_context`
error category).

**Design rationale (fan-out and parallel-branches both).** The "wait for many concurrent signals and
aggregate them" pattern often indicates a graph that would be clearer expressed as a sequence —
dispatch all the work in one node, suspend at the outer level, let the runtime coordinate the fan-in.
Engine-level multi-suspend would add significant complexity (partial aggregation, per-instance
timeouts, atomic vs incremental resume, descriptor reconciliation) for use cases that compose
naturally one layer up. v1 stays simple; a follow-on proposal MAY spec the multi-suspend case with
concrete use-case anchors if real demand surfaces.

### 8.4 Middleware

Middleware MAY wrap a suspending node. The middleware's pre-`next()` block runs normally; the
middleware's post-`next()` block does NOT run when the inner node suspends (since `next()` does not
return — it raises a typed internal control-flow exception, or returns a sentinel, per implementation).
Implementations MUST document the exact mechanism but the observable behavior is the same: post-suspend
middleware code does not execute on the suspending attempt.

**Middleware itself MUST NOT call `suspend()`.** Attempting to suspend from middleware (before, around,
or after the inner `next()` call) MUST raise `suspension_in_unsupported_context` (§9). Reasons:

- **Attribution ambiguity.** The paused record names a suspending node; if middleware suspends before
  the wrapped node runs, there is no clean answer for which node to attribute the suspension to. The
  wrapped node has not started; recording it as suspending would produce a `started`-then-`suspended`
  event pair without the node body ever executing, which is confusing for observers.
- **Composition gets pathological.** Two middlewares wrapping a node where the outer one suspends — on
  resume, do we re-enter the outer middleware from its top, the inner middleware (which never ran),
  or jump to the wrapped node? Each answer has different semantics; spec'ing the interaction is
  significant complexity.
- **Re-entrancy under `mark_node_completed=False`.** What does "re-run on resume" mean for middleware?
  The whole middleware chain? Just the suspending middleware? Different implementations would
  diverge.

The use cases for middleware-suspend (e.g., "gate this node behind a human approval") are achievable by
extracting the suspend into a preceding regular node, which keeps the engine and observability
attribution clean. The "do work, then suspend, then next node does work" pattern is the recommended
shape (and matches the `mark_node_completed=True` default).

### 8.5 Checkpointing

Suspension uses the same persistence mechanism as checkpointing per the pipeline-utilities §10.15
composition rule. Implementations MAY use a single backend store with a discriminator field
distinguishing checkpoint records from paused-invocation records, or separate stores. The spec treats
them as distinct record types with overlapping persistence requirements.

A paused-invocation record's lifetime is NOT bound to invocation completion — the record persists
until either (a) the invocation resumes and runs to completion, at which point the record MAY be
deleted per backend policy, or (b) the application explicitly deletes the record (cancellation), or
(c) backend-defined retention expires.

### 8.6 Sessions

When a session is bound to the invocation, the session SHOULD save at suspend time alongside the
paused-invocation record. This ensures a fresh worker resuming the suspension sees consistent session
state.

**Atomic suspend.** If session save fails at suspend, the engine MUST raise
`suspension_persistence_failed` (§9) and convert the invocation outcome from `suspended` to `errored`.
The paused-invocation record either is not written, or is rolled back / marked invalid if already
written — implementations MUST ensure subsequent resume attempts do not see a partial state (a
paused-invocation record present alongside a stale or missing session record). Suspend is observably
atomic: either both records persist consistently, or the invocation errors.

**Backend-level mitigation.** Transient failures (connection blips, brief backend unavailability,
intermittent timeouts) are the backend's responsibility. Well-implemented SessionStore backends SHOULD
apply internal retry policies, connection-pool warmup, and similar recovery strategies before reporting
a save failure to the engine. By the time the engine surfaces `suspension_persistence_failed`, the
backend has exhausted its recovery strategies and the failure is definitive. The engine does NOT
attempt retries at its layer; that responsibility lives where the backend semantics are known (network
shapes, error classifications, idempotency keys, etc.). Implementations MAY expose retry-policy knobs
as backend extensions (configurable retry counts on SessionStore wrappers, jittered-backoff defaults,
etc.), but the spec does not require them. The same backend-mitigation expectation applies to
checkpointer backends when persisting the paused-invocation record itself.

**Typical scope decomposition for long-running workflows.** `invocation_id` is stable for the lifetime
of the logical invocation across all suspend/resume cycles (see §7). Long-running workflows (weeks,
months) are typically modeled as MANY short invocations under one long-lived session, NOT as one long
invocation that pauses many times. Each user interaction / scheduled trigger / inbound event maps to
its own invocation; the session carries the accumulated cross-invocation context. Within any single
invocation, suspend/resume cycles are typically short and bounded. Genuinely long-running single
invocations (e.g., "send a letter, suspend, wait weeks for the mailed-in response") are supported but
uncommon; backend persistence and observability mappings handle the long-lived `invocation_id`
appropriately. When in doubt about which scope to use, prefer many-short-invocations-per-session over
one-long-invocation-with-many-pauses.

### 8.7 Deployment runtime / harness contract

The deployment runtime is responsible for the signal-coordination logic that routes inbound external
signals back to the right paused invocation. The suspension primitive provides the descriptor
(persisted on the paused record, returned in the suspended outcome, and surfaced on the
`suspended`-phase NodeEvent) plus the durable paused-invocation record; the runtime owns the
subscription side (callback URL allocation, event-bus subscription, scheduled-trigger registration,
etc.) and the lookup side (mapping arriving signals to the target `invocation_id`).

This contract is formalized by the harness capability spec, which specifies the signal-coordinator
contract (per its §6 *Signal coordinator*), the signal-resume inbound dispatch path (per its §3.3),
the suspended-outcome handling rule (per its §5.3 — harness MUST NOT block on suspended turns), and
the cross-capability error categorization for suspension-related errors at the turn boundary (per
its §7). Suspension itself is runtime-neutral — the descriptor's `signal_id` and `metadata` shapes
are the only interface points; the runtime decides how signals reach it and how they correlate.

## 9. Errors

Canonical error categories introduced by this capability:

- **`suspension_persistence_failed`** — engine could not persist the paused-invocation record at
  suspend time (or could not persist the session record alongside it per §8.6's atomic-suspend rule).
  Invocation outcome is `errored`, not `suspended`.
- **`suspension_record_invalid`** — resume requested for an `invocation_id` that is not in `suspended`
  status (`completed`, `errored`, never-existed, or already-resumed).
- **`suspension_resume_payload_invalid`** — merged signal payload does not validate against the state
  schema at resume time.
- **`suspension_in_unsupported_context`** — `suspend()` called from a context where it is not
  permitted. Reserved for: (a) `suspend()` called outside an invocation; (b) `suspend()` called inside
  a fan-out instance or parallel-branches branch whose containing node is configured with
  `error_policy="collect"` (per §8.2 / §8.3); (c) `suspend()` called from middleware (per §8.4).
  Implementations SHOULD detect (b) at compile / registration time when feasible; runtime detection is
  the spec-mandated minimum for all three cases.

## 10. Determinism

Suspension is a control-flow primitive; it does not perturb in-flight determinism. An invocation that
suspends and resumes produces the same final state and event sequence as an invocation that did not
suspend, provided the signal payload matches the data the application would have supplied directly.

The pause duration itself is not part of the invocation's deterministic contract — the engine cannot
guarantee how long an external signal takes to arrive. Observers timestamp events as they fire; the
resume events carry timestamps from the resume time, not the suspend time.

## 11. Cross-spec touchpoints

- **graph-engine §3 *Execution model*** — `invoke()` MAY return a `suspended` outcome distinct from
  completion or error.
- **graph-engine §6 *Observer hooks*** — NodeEvent's `phase` field gains `"suspended"`; the event
  carries the `descriptor` field; `completed` / `error` / `suspended` are mutually exclusive terminal
  phases for a given node in a given attempt.
- **pipeline-utilities §10.15 *Composition with suspension*** — shared persistence mechanism rule;
  paused-invocation record lifetime contract.
- **observability §4.2 *Status mapping*** — `SUSPENDED` status flavor on the invocation root span and
  the suspending node's span.
- **observability §4.3 *Parent-child rules* (*Suspended-resume invocation spans* paragraph)** —
  suspend and resume invocation spans share `invocation_id` (the load-bearing correlation, since
  suspension-resume reuses the suspended invocation's id per §7); `correlation_id` is inherited as a
  secondary identity per §3.1. OTel observers SHOULD additionally link the spans via OTel's
  span-link mechanism or a parent-of relationship per OTel conventions.
- **observability §5.8 *Suspension span attributes*** — `openarmature.suspension.signal_id` and
  flattened `openarmature.suspension.metadata.*` attributes on the suspending node's span.

## 12. Out of scope

- **Application-level signal categorization.** Whether an application groups its suspensions by
  `kind`, `category`, or any other axis is out of scope. Applications that need typed categorization
  supply a typed-state model for the descriptor's metadata field.
- **Signal delivery transport.** REST callbacks, event buses, queue messages, scheduled triggers —
  runtime concerns, addressed by the harness capability and per-runtime implementations.
- **Timeout enforcement.** The descriptor MAY carry a timeout hint; the runtime / harness owns
  enforcement. Implementations MAY add a default-timeout knob; the spec stays silent.
- **Cancellation.** An application MAY cancel a paused invocation by deleting the record (or by
  resuming with a cancel-signal payload that the graph interprets and routes to a terminal node). The
  primitive itself does not provide a cancel API.
- **Suspension at the engine-attempt level.** Suspension applies to whole invocations, not to
  individual retry attempts. A suspended invocation that resumes resumes the WHOLE invocation, not
  "the attempt within the retry that suspended."
- **Multi-suspend aggregation across concurrent fan-out instances or parallel branches.** The "wait
  for N concurrent signals" pattern is achievable via a single outer suspend with runtime-side
  fan-in (per §8.2 / §8.3). Engine-level multi-suspend is deferred to a future proposal if real
  demand surfaces.
