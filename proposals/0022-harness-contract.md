# 0022: Harness Contract

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-17
- **Accepted:** 2026-06-05
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

**Inbound dispatch path.** One of the classification paths the harness
routes inbound traffic into. See §3.

**Harness mode (sessioned vs stateless).** A harness operates in one of
two modes, determined at construction:

- **Sessioned mode.** Every inbound transmission is associated with a
  `session_id` (resolved by the harness's session resolver). The
  harness threads `session_id` into every `invoke()`. Session state
  loads at invoke entry and saves at invoke exit per sessions §6.
- **Stateless mode.** Inbound transmissions carry no session identity.
  Every turn is independent. The harness does NOT resolve a
  `session_id`, does NOT invoke any SessionStore, and does NOT thread
  any `session_id` into `invoke()`. Used by deployment runtimes
  serving inherently stateless workloads (REST APIs without per-
  conversation context, batch processors, scoring services).

Stateless mode is first-class — not a degenerate sessioned case with
`session_id = None`. The two modes have different inbound dispatch
classification (sessioned mode uses §3.1 / §3.2 / §3.3; stateless
mode uses §3.0) and different sessions composition (per §8.1).

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
receives MUST be classified into exactly one path. In **sessioned
mode**, the path is one of §3.1 / §3.2 / §3.3. In **stateless mode**,
every transmission routes through §3.0.

#### 3.0 Stateless transmission path (stateless-mode harnesses only)

The harness is configured in stateless mode (per §2 *Harness mode*).
Every inbound transmission is independent — the harness does NOT
resolve a `session_id`, does NOT load or save session state, and does
NOT thread any `session_id` into the engine.

The harness:

1. Constructs the initial state from the inbound payload per
   harness-implementation logic.
2. Calls `invoke(initial_state)` — no `session_id` argument; no
   SessionStore interaction occurs even if one happens to be
   registered on the compiled graph.
3. Handles the outcome per §5.

A stateless-mode harness MUST NOT classify any transmission into
§3.1 / §3.2 / §3.3 (the sessioned paths). A sessioned-mode harness
MUST NOT classify any transmission into §3.0. Mode is fixed at
construction; mixing modes within one harness instance is out of
scope (an application that needs both shapes constructs two harness
instances, one per mode).

The signal-resume case under stateless mode (§3.3-equivalent) is
permitted IF the runtime emits identifiable resume signals carrying
the paused-invocation_id. The stateless harness's signal coordinator
(§6) routes the signal to a resume invocation without any session
context — the paused-invocation record carries no `session_id` (it
was created by a stateless invoke), so resume threading is
session-free.

#### 3.1 New-session path

The inbound transmission begins a new session. Path 3.1 is classified
by caller intent — the transport routes the transmission as a new-
session start (e.g., a dedicated "start session" HTTP route, an event
type meaning "begin work for this id", or simply the absence of any
`session_id`). The harness does NOT verify whether a supplied id
already exists in the session store; that check is the engine's
responsibility per sessions §6.1.

The harness:

1. Resolves `session_id` from the inbound payload, or assigns a fresh
   one if absent.
2. Constructs the initial state from the inbound payload per
   harness-implementation logic.
3. Calls `invoke(initial_state, session_id=<id>)`.
4. Handles the outcome per §5.

#### 3.2 Existing-active-session path

The inbound transmission continues an existing session. Path 3.2 is
classified by caller intent — the transport routes the transmission
as a continuation of an ongoing session (e.g., a turn-on-existing-
session HTTP route, an event continuing a prior thread), and the
transmission carries a `session_id` naming that session. The harness
does NOT verify whether the session exists or its state — that
check is the engine's responsibility per sessions §6.1.

The harness:

1. Resolves `session_id` from the inbound payload.
2. Constructs the next-turn state from the inbound payload. The
   session-state load happens inside `invoke()` per proposal 0020
   §6.1; the harness does NOT load session state itself.
3. Calls `invoke(initial_state, session_id=<id>)`.
4. Handles the outcome per §5.

The distinction from 3.1 is caller intent: 3.1 starts a new session,
3.2 continues an existing one. The engine resolves any disagreement
between intent and store state per proposal 0020's semantics — e.g.,
a 3.2 transmission referencing a `session_id` that no engine-side
record matches surfaces as a `session_load_failed` error per §7.

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
path before calling `invoke()`. In sessioned mode, the choice is among
3.1 / 3.2 / 3.3; in stateless mode, every transmission routes
through 3.0 (with the resume-equivalent allowance per 3.0's last
paragraph). The classification is the harness's responsibility;
specific transports (HTTP routes, event types, etc.) typically
determine it. The contract requires the classification be
deterministic from the inbound payload (a given payload always routes
to the same path).

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
  semantics. Session state depends on the policy decision in
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

Errors that surface at the turn boundary — whether propagated from the
engine or raised by the harness itself — fall into three categories:

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

**8.1 Sessions (proposal 0020).** Composition splits by harness mode
(per §2):

- **Sessioned-mode harnesses** thread `session_id` into every
  `invoke()` per the inbound dispatch paths in §3.1 / §3.2 / §3.3.
  The engine handles session load/save per proposal 0020 §6. The
  harness does NOT directly access the SessionStore — the engine owns
  that interaction.
- **Stateless-mode harnesses** omit `session_id` from every
  `invoke()` per §3.0. The engine MUST NOT invoke any SessionStore
  even if one is registered on the compiled graph (the
  `session_id=absent` discipline from sessions §3 governs). Stateless
  harnesses MAY share a compiled graph with sessioned harnesses if an
  application instantiates both for different transport surfaces —
  the engine's behavior is determined per-invocation by whether
  `session_id` is supplied, not by graph configuration.

In both modes, the harness does NOT directly access the SessionStore;
sessioned-mode harnesses delegate to the engine via `session_id`
threading, and stateless-mode harnesses don't touch it at all.

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
suite (against the abstract contract here). Spec-level per-harness-type
sub-specs are added by follow-on proposals when cross-impl divergence
risk warrants the ratification. **The chat harness is committed to a
follow-on sub-spec** (planned proposal `0NNN-harness-chat`), per the
*Open questions* resolution below — chat-loop semantics (message-shape,
conversation-history threading, higher-level `harness.send(session_id,
message)` callable surface) have the highest cross-impl-divergence
risk and warrant ratification once across implementations. Other
per-harness-type sub-specs (FastAPI, Inngest, CLI, …) remain
decided-per-case when each ships its first implementation and
surfaces cross-impl questions. This proposal lands the abstract
contract first; the chat sub-spec layers on top.

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
same path and produce the same `invoke()` call (modulo timestamps,
engine-generated `invocation_id`s, and harness-generated `session_id`s
when §3.1 assigns a fresh one — all non-deterministic by design; see
graph-engine §5).

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
  - **`011-stateless-mode-no-session`** — stateless-mode harness
    invokes a graph without resolving a `session_id` and without
    invoking any SessionStore (even when one is registered on the
    compiled graph). Verifies §3.0 stateless-transmission path +
    §8.1 stateless-mode composition rule; asserts the SessionStore
    received zero load / save calls across the invocation.

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
  Resolved: **the chat harness gets a follow-on sub-spec** (planned
  proposal `0NNN-harness-chat`) that specifies the inbound message →
  session → invoke wiring, the outbound assistant message → session →
  response wiring, and the higher-level callable surface
  (`harness.send(session_id, message)` rather than hand-threading invoke
  arguments). Downstream demand surfaced during 0022's pre-Accept
  review (a reference chat agent in production would otherwise
  re-invent that contract per-deployment); a chat sub-spec ratifies
  the shape once for cross-impl consistency. FastAPI, Inngest, and
  other per-harness-type specs remain decided-per-case when each
  ships its first implementation. The abstract contract in this
  proposal is the foundation both chat and other harness types build
  on; chat is the first to commit because the chat-loop contract has
  the highest cross-impl-divergence risk.
- **Streaming hooks.** This proposal stays at turn-level granularity.
  Token-level streaming (SSE, gRPC bidi, WebSocket message-by-message)
  is a separate concern that could fit as either: (a) an extension to
  this proposal (a `streaming_response` outcome alongside
  completed/errored/suspended), or (b) a separate proposal that
  composes with this one. Recommendation: separate proposal,
  prerequisite-on-this-one.
- **The harness's relationship to `invoke()` callable shape.**
  Resolved at the abstract contract level: **the abstract contract
  stays neutral.** Concrete harness-type sub-specs (per Q1 — chat
  sub-spec planned) MAY mandate a higher-level callable surface
  (e.g., `harness.send(session_id, message)` for the chat case)
  appropriate to their transport model. Non-chat harness types MAY
  stay close to `invoke()` if no higher-level callable serves their
  shape. The abstract contract requires the harness MUST call
  `invoke()` somewhere on the inbound path; the wrapping convention
  is per-harness-type, not abstract.
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
  Resolved: **stateless mode is first-class** (per §2 *Harness mode*
  and the new §3.0 *Stateless transmission path*). The earlier draft
  framing treated stateless as a degenerate sessioned case with
  `session_id=None`, but downstream review surfaced real production
  use cases (REST APIs, batch processors, scoring services) where
  stateless is the natural deployment shape, and where the
  session-resolver / session-load / session-save machinery is dead
  code that doesn't belong on the inbound path. Stateless-mode
  harnesses don't resolve any `session_id`, don't invoke any
  SessionStore, and follow the §3.0 dispatch path instead of §3.1 /
  §3.2 / §3.3. The §8.1 sessions composition rule splits between
  sessioned and stateless modes explicitly. Mode is fixed at harness
  construction; an application needing both shapes constructs two
  harness instances.
