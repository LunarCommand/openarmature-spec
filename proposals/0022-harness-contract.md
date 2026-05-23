# 0022: Harness Contract

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-17
- **Accepted:**
- **Targets:** spec/harness/spec.md (creates)
- **Related:** 0020 (sessions — multiplexing key + cross-invoke state), 0021 (suspension — signal coordination), 0008 (checkpointing — shared persistence), 0007 (observability — turn-level spans)
- **Supersedes:**

## Summary

Create the `harness` capability spec. Defines the abstract behavioral contract
that any harness implementation MUST follow when wrapping the OA workflow
engine to serve a deployment runtime (HTTP server, event bus, queue worker,
CLI repl, etc.). Specifies the three inbound dispatch paths (new-session,
existing-active-session, signal-resume), the outbound dispatch surface (sync
return values, async dispatches via node bodies), the turn lifecycle abstract
over transport, the composition rules with sessions and suspension, and the
error semantics at the turn boundary. Runtime-neutral — the contract does not
assume request/response, event-driven, or any specific transport.

## Motivation

A production OA-based agent runs as a long-running worker that:

- Multiplexes many concurrent sessions
- Routes each inbound request / event to the right session
- Dispatches long-running work without blocking on it
- Resumes the right paused session when each external signal returns

This shape needs to compose with any deployment runtime:

- **Synchronous request/response** (FastAPI, Express, gRPC, CLI repl)
- **Asynchronous event-driven** (Inngest, AWS EventBridge, SQS, Kafka,
  RabbitMQ consumers)
- **Mixed** (REST in, event out, REST callback in)
- **Long-lived streaming** (WebSocket, SSE, gRPC bidi)

Today there is no spec-level contract for this layer. Each application
project rebuilds:

- The session router (how an inbound request finds its session_id)
- The signal coordinator (how an inbound callback finds its paused
  invocation)
- The turn-level error categorization (which engine errors propagate to
  the user vs which are retryable at the turn boundary)
- The composition with sessions (when to load, when to save) and with
  suspension (how to expose paused outcomes)
- The observability story (how to scope spans / metrics / logs to a
  turn)

Without a spec'd contract, harnesses ship by every team as one-offs.
Python and TypeScript chat harnesses would diverge in semantics.
Multiple harnesses within one language (chat vs FastAPI vs queue
worker) would diverge in turn handling. The cross-implementation
promise of OA breaks.

A spec'd harness contract:

- **Names the abstract turn boundary** — bounded by `invoke()` entry/exit,
  not by transport semantics. A turn under FastAPI is one
  request/response. A turn under Inngest is one event-handler
  invocation. The contract is the same.
- **Specifies three inbound paths.** New-session, existing-active-session
  (next turn of an ongoing conversation), signal-resume (callback for
  a paused invocation). Every harness routes inbound traffic into one
  of these three paths.
- **Specifies the composition.** How session_id is resolved at inbound,
  how session state is loaded/saved relative to invoke entry/exit, how
  paused outcomes surface to the harness, how the harness re-routes
  signal callbacks back to paused invocations.
- **Specifies error categorization at the turn boundary.** Which graph
  errors terminate the session, which surface as retryable transient
  errors, which require user correction.
- **Stays runtime-neutral.** The contract is about WHAT the harness
  does; specific runtimes (FastAPI, Inngest, CLI, etc.) ship as
  sibling-package implementations that satisfy the contract. The spec
  does not name any specific transport.

This proposal depends on proposals 0020 (sessions) and 0021 (suspension)
landing first; the harness contract composes both into the turn-level
runtime story.

## Detailed design

### 1. Purpose

The `harness` capability defines the behavioral contract that any
harness implementation MUST follow when wrapping the OA workflow engine
to serve a deployment runtime. The spec specifies abstract turn
semantics, dispatch path classification, composition rules with sessions
and suspension, error categorization at the turn boundary, and the
observability scope. Implementations ship concrete harnesses for
specific runtimes (HTTP servers, event buses, queue workers, CLI repls,
streaming connections, etc.).

This capability composes with:

- **graph-engine** — the harness invokes `invoke()`, which is the
  graph-engine's per-call surface. The harness is the layer above
  invoke; the engine is the layer below.
- **sessions** (proposal 0020) — the harness resolves `session_id` at
  inbound and threads it into `invoke()`. The engine handles the
  session load/save per the sessions spec.
- **suspension** (proposal 0021) — the harness handles the `suspended`
  outcome from `invoke()` by either returning it to the caller (sync
  runtimes) or by dispatching a signal-subscription to the runtime
  (async runtimes). On signal arrival, the harness routes the callback
  to the signal-resume inbound path.
- **observability** — turn boundaries map to span scopes; the harness
  is responsible for opening/closing turn-level spans around invoke.
- **checkpointing** (proposal 0008) — the harness MAY use checkpointing
  to make turn-level invokes resumable across worker restarts; not
  required by the contract.

This capability does NOT define:

- **Specific transport surfaces.** HTTP request schemas, event message
  formats, CLI argument shapes — these are per-harness implementation
  concerns.
- **Specific harness types.** Chat harness, FastAPI harness, Inngest
  harness, etc. — these are sibling-package implementations. The
  contract defines what they share; the implementations define how
  each surfaces.
- **Authentication / authorization.** Cross-cutting application
  concern, not a harness concern.
- **Rate limiting / quotas.** Runtime concerns, layered above the
  harness.
- **Multi-tenant routing logic.** Application concern; the harness
  receives a resolved `session_id` from the application's routing
  layer.

### 2. Concepts

**Harness.** The integration layer wrapping the OA engine for a
specific deployment runtime. Owns the inbound dispatch, the outbound
surface, the session lookup, and the signal-coordination logic.

**Turn.** One bounded execution of the workflow engine in service of an
inbound request or event. A turn corresponds to ONE call to `invoke()`
or `invoke(resume_invocation=...)`. A turn begins at invoke entry and
ends at invoke return (one of: completed, errored, or suspended).
The transport-level boundary (HTTP request lifetime, event-handler
duration, etc.) is set by the runtime, not by the harness contract.

**Inbound dispatch path.** One of the three classification paths the
harness routes inbound traffic into. See §3.

**Outbound surface.** The mechanisms by which the harness exposes
in-invocation effects to the runtime: sync return values, async
dispatches initiated from node bodies, and signal subscriptions
registered for paused invocations.

**Session resolver.** The harness's mechanism for mapping inbound
traffic to a `session_id`. Implementation-defined (a header field, a
URL path param, an event payload field, a CLI arg, etc.); the contract
specifies that resolution happens, not how.

**Signal coordinator.** The harness's mechanism for routing inbound
signal callbacks to the right paused invocation. Implementation-
defined; the contract specifies the coordination semantics, not the
mechanism.

### 3. Inbound dispatch paths

Every inbound transmission (request / event / CLI input) the harness
receives MUST be classified into exactly one of three paths:

#### 3.1 New-session path

The inbound transmission introduces a previously-unknown `session_id`
(or omits it, in which case the harness assigns one). The harness:

1. Resolves or generates `session_id`.
2. Constructs the initial state from the inbound payload per
   harness-implementation logic.
3. Calls `invoke(initial_state, session_id=<id>)`.
4. Handles the outcome per §5.

#### 3.2 Existing-active-session path

The inbound transmission carries a `session_id` for an existing session
that is NOT currently in suspended state. The harness:

1. Resolves `session_id`.
2. Constructs the next-turn state from the inbound payload. The
   session-state load happens inside `invoke()` per proposal 0020
   §6.1; the harness does NOT load session state itself.
3. Calls `invoke(initial_state, session_id=<id>)`.
4. Handles the outcome per §5.

The distinction from 3.1 is the existence of prior session state. The
contract treats both as "the session is the active scope for the turn";
the engine handles the load-or-not via proposal 0020's semantics.

#### 3.3 Signal-resume path

The inbound transmission carries a signal payload correlating to a
paused invocation. The harness:

1. Resolves the target `invocation_id` from the signal correlation
   (via the signal coordinator, see §6).
2. Constructs the `signal_payload` from the inbound transmission.
3. Calls `invoke(resume_invocation=<id>, signal_payload=<payload>)`.
4. Handles the outcome per §5.

A signal-resume MUST also implicitly belong to the paused invocation's
session (the engine threads `session_id` from the paused record). The
harness does not re-resolve `session_id` on signal-resume — the paused
record carries it.

#### 3.4 Path classification

The harness MUST classify every inbound transmission into exactly one
of 3.1 / 3.2 / 3.3 before calling `invoke()`. The classification is
the harness's responsibility; specific transports (HTTP routes, event
types, etc.) typically determine it. The contract requires the
classification be deterministic from the inbound payload (a given
payload always routes to the same path).

### 4. Turn lifecycle

A turn has three observable phases:

**Turn entry.** The harness calls `invoke()` (or
`invoke(resume_invocation=...)`). The engine's session-load, observer
setup, and graph execution begin per proposal 0020 and graph-engine
§3.

**Turn body.** Graph execution runs. Node bodies MAY:

- Read state.
- Write state updates (via reducers per graph-engine §2).
- Initiate sync outbound calls (HTTP requests, database queries, LLM
  provider calls, etc.). The harness has no role here; node bodies
  call out directly.
- Initiate async outbound dispatches (event publishes, job
  submissions, queue messages). The harness has no role here; node
  bodies dispatch directly. The application is responsible for
  arranging that the eventual response (the signal) routes back to
  the harness's signal coordinator.
- Suspend via `suspend(descriptor)` (per proposal 0021). The engine
  persists the paused-invocation record and returns from invoke.

**Turn exit.** `invoke()` returns one of three outcomes:

- **`completed`** — graph reached END. Final state is the return
  value. Session state auto-saves per proposal 0020 §6.1.
- **`errored`** — a node raised. Per graph-engine §4 error
  semantics. Session state state depends on the policy decision in
  proposal 0020 (current proposal: session does NOT save on error
  unless an explicit mid-invoke save fired).
- **`suspended`** — a node called `suspend()`. Per proposal 0021,
  the paused-invocation record is persisted, the suspended outcome
  is returned, and session state saves at suspend time.

The harness handles each outcome per §5.

The turn lifecycle is abstract over transport: a sync HTTP request
returns the outcome's surfaced shape directly; an async event handler
publishes a result-event derived from the outcome; a CLI repl prints
to stdout. The contract specifies the outcome shape; the surface is
per-implementation.

### 5. Outcome handling

The harness MUST handle each invoke outcome:

#### 5.1 Completed outcome

The harness exposes the final state (or a derived surface, depending
on the runtime) to the inbound caller. Implementation-defined how the
state maps to the transport surface; the contract requires that
completion is observably distinct from suspension and from error.

#### 5.2 Errored outcome

The harness categorizes the error per §7 and surfaces it. Some errors
terminate the session (e.g., a state-corruption error); others
surface as turn-level transient failures the caller MAY retry; others
surface as user-correctable errors (validation failures, missing
inputs, etc.).

#### 5.3 Suspended outcome

The harness:

1. Reads the signal descriptor from the suspended outcome.
2. Registers a signal subscription with the runtime per §6 — telling
   the runtime "when a signal matching this descriptor arrives,
   route it back to me via the signal-resume inbound path."
3. Returns an acknowledgment to the inbound caller indicating the
   turn paused — the transport-level shape of this acknowledgment is
   implementation-defined.
4. EXITS without blocking. The harness is now free to handle other
   turns for other sessions.

Step 4 is the load-bearing requirement. A harness MUST NOT block on
suspended turns. The whole point of the suspension primitive is that
the worker frees up to serve other traffic.

### 6. Signal coordinator

The harness owns the signal-coordination logic that ties together:

- **At suspend time:** Map the signal descriptor (from §5.3) into a
  runtime-specific subscription that will route matching signals
  back to the harness's signal-resume inbound path.
- **At signal arrival:** Map the arriving signal to the target
  paused `invocation_id` and the appropriate `signal_payload`.

Specific mechanisms are runtime-defined:

- **REST callback:** The harness registers an endpoint at `POST
  /callback/<invocation_id>`; the dispatched async job carries this
  URL; the callback fires by posting to the URL. The signal-resume
  inbound path receives the POST and extracts `invocation_id` from
  the URL.
- **Event bus:** The harness subscribes to a topic / pattern; the
  signal descriptor names the correlation key embedded in the
  awaited event; on event arrival, the harness looks up the
  paused-invocation record by correlation key.
- **Scheduled wakeup:** The harness registers a scheduled trigger
  (via a scheduler the runtime exposes); the trigger fires the
  signal-resume inbound path with the invocation_id stored in the
  schedule entry.

The contract requires that the signal coordinator be **complete**:
every suspended invocation MUST have a mechanism by which its awaited
signal can reach the harness's signal-resume path. The harness MAY
fail at suspend time (per §5.3 step 2) if it cannot register the
subscription; in that case the suspension converts to an error per
§7 (a new turn-level error category, `harness_signal_subscription_failed`).

### 7. Error categorization at the turn boundary

Engine errors propagating to the harness fall into three categories:

**7.1 Session-terminating errors.** Errors indicating the session's
state is corrupt or unsalvageable. Examples:

- `session_load_failed`
- `session_state_migration_chain_ambiguous`
- `session_state_migration_missing` (no recovery without a
  migration)
- State-schema validation failures that cannot resolve by retrying

The harness SHOULD surface these to the caller with a transport-
specific "session is broken; intervention required" indication and
SHOULD NOT auto-retry. Sessions in this state MAY be deleted by
operators.

**7.2 Retryable transient errors.** Errors that MAY succeed on retry
with the same inputs. Examples:

- `provider_unavailable`, `provider_rate_limit`,
  `provider_model_not_loaded`
- `session_save_failed` (if transient)
- `harness_signal_subscription_failed` (if transient)

The harness MAY auto-retry per its runtime conventions (e.g., an
event-driven harness leans on the runtime's retry mechanism;
a sync HTTP harness might retry inline or surface a retry-after
header).

**7.3 User-correctable errors.** Errors requiring caller action.
Examples:

- `provider_invalid_request` (the caller sent bad inputs)
- `suspension_resume_payload_invalid` (the signal payload doesn't
  match the schema)
- `provider_authentication` (credentials issue)

The harness surfaces these with diagnostic information; the caller
adjusts inputs and retries explicitly.

Implementations MAY refine these categories. The contract specifies
the three-bucket split; harness implementations classify specific
error categories into the buckets and surface them per their
transport's conventions.

### 8. Composition with capabilities

**8.1 Sessions (proposal 0020).** The harness threads `session_id`
into every `invoke()` per the inbound dispatch paths in §3. The
engine handles session load/save per proposal 0020 §6. The harness
does NOT directly access the SessionStore — the engine owns that
interaction.

**8.2 Suspension (proposal 0021).** The harness handles the
suspended outcome per §5.3 and the signal coordinator per §6. The
engine emits the paused-invocation record and the suspended outcome;
the harness handles the rest.

**8.3 Checkpointing (proposal 0008).** The harness MAY configure a
checkpointer on the compiled graph for mid-invoke crash recovery.
The contract does not require checkpointing; harnesses targeting
runtimes with durable handler execution (Inngest steps, AWS Lambda
durable workflows, etc.) MAY rely on the runtime's durability layer
in lieu of OA's checkpointer. Harnesses targeting non-durable
runtimes (plain FastAPI, stateless containers) SHOULD configure a
checkpointer to make multi-node invokes resumable.

**8.4 Observability (proposal 0007).** The harness opens a
turn-level span around `invoke()` carrying `openarmature.session_id`
and (on signal-resume) the descriptor attributes. The invocation
root span (per proposal 0007) is a child of the turn span. This
nesting lets trace UIs scope traces to turns when desired.

### 9. Per-harness-type implementations

The contract is abstract; concrete harness types ship as sibling
packages. Examples (not normative — names are illustrative):

- **`openarmature-chat`** — a thin chat-loop harness. The runtime is
  a programmatic loop; the inbound transmission is a chat message;
  the outbound surface is the assistant response. Suspension MAY
  surface as a pause-and-prompt-the-user shape.
- **`openarmature-fastapi`** — wraps OA into a FastAPI app. Inbound
  is HTTP request; outbound is HTTP response. Signal coordinator
  uses callback endpoints.
- **`openarmature-inngest`** — wraps OA into Inngest event handlers.
  Inbound is event; outbound is event publish; signal coordinator
  uses `step.waitForEvent`.
- **`openarmature-cli`** — wraps OA into a CLI repl. Inbound is
  stdin; outbound is stdout. Suspension MAY surface as "press enter
  to continue when ready".

Each per-harness-type implementation MAY ship its own conformance
suite (against the abstract contract here). Whether spec-level
per-harness-type sections (§9.1 chat, §9.2 HTTP, etc.) are added in
follow-on proposals is open; this proposal lands the abstract
contract first.

### 10. Errors

Canonical error categories introduced by this proposal:

- **`harness_session_id_unresolved`** — inbound transmission cannot
  be classified into a dispatch path because `session_id`
  resolution failed.
- **`harness_signal_subscription_failed`** — at suspend time, the
  harness could not register the subscription with the runtime
  (the suspension cannot be persisted as resolvable; converts to
  an error outcome).
- **`harness_signal_correlation_failed`** — at signal arrival, the
  signal coordinator cannot map the inbound transmission to a
  paused invocation.
- **`harness_path_classification_ambiguous`** — inbound
  transmission satisfies criteria for multiple paths or cannot be
  unambiguously classified.

### 11. Determinism

The harness is a control-flow layer; it does not affect deterministic
execution within a single invocation. Two replays of the same inbound
transmission against the same harness state should classify to the
same path and produce the same `invoke()` call (modulo timestamps and
engine-generated `invocation_id`s, which are non-deterministic by
design — see graph-engine §5).

Cross-turn determinism is not part of the contract: subsequent
turns observe the prior turn's saved session state, which means a
turn's behavior depends on history. This is correct and expected.

### 12. Cross-spec touchpoints

- **graph-engine §3 (Execution model)** — harness invokes `invoke()`;
  the contract is the abstract entry surface.
- **observability §4 (Span hierarchy)** — turn-level span wraps the
  invocation root span; cross-reference added.
- **sessions §3 (Identity scoping)** — harness threads `session_id`;
  cross-reference confirms.
- **suspension §5 (Suspended outcome) and §7 (Resume API)** — harness
  handles suspended outcomes and dispatches signal-resume invokes;
  cross-reference confirms.

### 13. Out of scope

- **Specific transport surfaces** (HTTP, gRPC, event bus, queue,
  stdin/stdout, WebSocket, …) — per-harness-implementation concerns.
- **Specific signal-delivery mechanisms** (REST callback, event
  subscription, scheduled trigger, queue subscription, …) — runtime
  concerns; the harness adapts.
- **Streaming token-level output.** A separate proposal (planned)
  would specify streaming hooks; this proposal stays at turn-level
  granularity.
- **Multi-tenant routing.** The harness receives a resolved
  `session_id`; the application's routing layer (above the harness)
  decides which tenant the session belongs to.
- **Rate limiting / quotas / authn / authz.** Cross-cutting application
  concerns.
- **Per-harness-type behavioral specs.** The chat harness, FastAPI
  harness, etc. each have their own behavioral surface (turn
  message shape, error response format, etc.); these are per-
  harness follow-on proposals if cross-impl consistency demands it.

## Conformance test impact

The harness contract is intrinsically tied to deployment runtimes,
making language-agnostic conformance fixtures awkward. The proposal
takes the following approach:

- **Abstract-contract fixtures** under `spec/harness/conformance/`
  that verify behavior through a reference harness with a synthetic
  in-process transport. The fixtures exercise the three inbound
  paths, the three outcome handlings, the error categorization
  buckets, and the signal-coordinator composition.
  - **`001-inbound-new-session`** — synthetic transmission with no
    session_id; harness creates one and invokes.
  - **`002-inbound-existing-session`** — synthetic transmission with
    a known session_id; harness invokes with session loaded.
  - **`003-inbound-signal-resume`** — synthetic signal carrying
    paused invocation_id; harness invokes resume.
  - **`004-outcome-completed`** — invoke returns completed; harness
    surfaces the final state.
  - **`005-outcome-errored`** — invoke returns errored; harness
    categorizes per §7.
  - **`006-outcome-suspended`** — invoke returns suspended; harness
    registers a signal subscription and exits without blocking.
  - **`007-signal-coordinator-roundtrip`** — suspend, register
    subscription, deliver signal, resume.
  - **`008-error-session-terminating`** — `session_load_failed` is
    classified as terminating; no auto-retry.
  - **`009-error-retryable-transient`** — `provider_unavailable` is
    classified as retryable.
  - **`010-error-user-correctable`** — `provider_invalid_request`
    surfaces with diagnostic info.

- **Per-harness-implementation suites** in each sibling package
  (`openarmature-fastapi`, `openarmature-chat`, etc.) verify the
  per-transport behavior. The spec defines the contract; the
  implementations verify they satisfy it.

## Alternatives considered

**Per-harness-type specs only (no abstract contract).** Skip this
abstract proposal; spec each harness type separately (chat, HTTP,
event-driven as first-class proposals).

Rejected: the cross-cutting contract (multiplexing, signal
coordination, session integration, error categorization) is the same
across transports. Spec'ing each harness type separately would
duplicate this content N times and let the implementations drift.
The abstract contract amortizes the cross-cutting work; per-harness-
type specs can layer on top for the transport-specific shape.

**Leave harnesses entirely to implementations.** No spec at all;
each implementation defines its own harness story.

Rejected: cross-impl consistency requires spec definition. A Python
FastAPI harness and a TypeScript Express harness should give the
user the same session multiplexing semantics, the same suspension
handling, the same error categorization. Without a spec, they would
diverge as different teams build them at different times.

**Define harnesses as a thin convenience layer with no behavioral
contract.** The spec acknowledges harnesses exist, points to sibling
packages, but says nothing about behavior.

Rejected: same as previous; produces drift. The point of speccing the
contract is to lock in the cross-impl behavioral promise.

**Spec the chat harness as the canonical model and let other harnesses
adapt.** Build the contract around chat as the prototype; FastAPI /
event-driven adapt.

Rejected: chat-as-prototype builds in synchronous, conversational
turn semantics that don't generalize. Event-driven harnesses do not
have a "conversation" shape; the contract has to be abstract enough
to fit both. Building the abstraction up from chat retrofits the
event-driven case; building it down from the cross-transport case
fits both natively.

## Open questions

- **Whether to spec per-harness-type behavior in follow-on proposals.**
  The chat harness specifically has rich turn-level semantics (message
  shape, conversation history flow, partial / streaming responses) that
  could warrant a `0023-harness-chat` follow-on. FastAPI, Inngest, etc.
  might or might not. Open: decide per-harness-type basis when each
  ships its first implementation and surfaces cross-impl questions.
- **Streaming hooks.** This proposal stays at turn-level granularity.
  Token-level streaming (SSE, gRPC bidi, WebSocket message-by-message)
  is a separate concern that could fit as either: (a) an extension to
  this proposal (a `streaming_response` outcome alongside
  completed/errored/suspended), or (b) a separate proposal that
  composes with this one. Recommendation: separate proposal,
  prerequisite-on-this-one.
- **The harness's relationship to `invoke()` callable shape.** This
  proposal assumes the harness calls `invoke()` directly. An
  alternative is that the harness wraps `invoke()` in a higher-level
  callable (e.g., `harness.handle(transmission)`). The callable-
  wrapping shape might be useful for testability; the contract says
  the harness MUST call `invoke()`, leaving the wrapping convention
  to implementations.
- **Where the abstract conformance fixtures actually run.** The
  abstract-contract fixtures need a "reference harness" with a
  synthetic transport to exercise the contract. This reference might
  ship in spec, in a sibling package, or in each implementation. Open:
  decide before the first conformance fixture lands.
- **Multi-language harness coordination.** When `openarmature-chat`
  ships in Python and later in TypeScript, both should give the
  user the same behavior. Cross-impl validation is hard for harnesses
  (they're runtime-bound; the runtimes differ). One option is to
  define cross-language test scenarios where both implementations
  must produce semantically-equivalent results. Worth designing
  before the first non-Python harness ships.
- **Whether sessions auto-load is mandatory at the harness layer.**
  This proposal assumes the harness ALWAYS resolves `session_id` and
  threads it into invoke. An alternative: stateless-mode harnesses
  that skip session resolution entirely (every turn is independent).
  Recommendation: stateless mode is `session_id=None` on the
  inbound dispatch; no special case needed. Confirming.
