# Harness

Canonical behavioral specification for the OpenArmature harness capability.

- **Capability:** harness
- **Introduced:** spec version 0.49.0
- **History:**
  - created by [proposal 0022](../../proposals/0022-harness-contract.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The `harness` capability defines the behavioral contract that any harness implementation MUST follow
when wrapping the OpenArmature workflow engine to serve a deployment runtime (HTTP server, event bus,
queue worker, CLI repl, streaming connection, etc.). The spec specifies abstract turn semantics,
dispatch path classification, composition rules with sessions and suspension, error categorization at
the turn boundary, the observability scope, and the harness-mode distinction (sessioned vs stateless).
Implementations ship concrete harnesses for specific runtimes; the spec defines what they share, the
implementations define how each surfaces.

The capability composes with:

- **graph-engine** — the harness invokes `invoke()`, which is the graph-engine's per-call surface.
  The harness is the layer above invoke; the engine is the layer below.
- **sessions** (when in sessioned mode) — the harness resolves `session_id` at inbound and threads
  it into `invoke()`. The engine handles the session load/save per the sessions spec.
- **suspension** — the harness handles the `suspended` outcome from `invoke()` by either returning
  it to the caller (sync runtimes) or by dispatching a signal-subscription to the runtime (async
  runtimes). On signal arrival, the harness routes the callback to the signal-resume inbound path.
- **observability** — turn boundaries map to span scopes; the harness MAY open / close a
  turn-level wrapper span around `invoke()` per observability §4.6 (optional — runtimes that
  already provide a transport-level parent span MAY skip the wrapper).
- **pipeline-utilities §10 *Checkpointing*** — the harness MAY use checkpointing to make
  turn-level invokes resumable across worker restarts; not required by the contract.

This capability does NOT define:

- **Specific transport surfaces.** HTTP request schemas, event message formats, CLI argument
  shapes — per-harness implementation concerns.
- **Specific harness types.** Chat harness, FastAPI harness, Inngest harness, etc. — sibling-package
  implementations. The contract defines what they share; the implementations define how each
  surfaces. The chat harness specifically gets a follow-on sub-spec (planned
  `0NNN-harness-chat` per proposal 0022 *Open questions* resolution); other per-harness-type
  sub-specs land as cross-impl-divergence risk warrants.
- **Authentication / authorization.** Cross-cutting application concern, not a harness concern.
- **Rate limiting / quotas.** Runtime concerns, layered above the harness.
- **Multi-tenant routing logic.** Application concern; the harness receives a resolved
  `session_id` (sessioned mode) from the application's routing layer or no identity (stateless
  mode).

## 2. Concepts

**Harness.** The integration layer wrapping the OpenArmature engine for a specific deployment
runtime. Owns the inbound dispatch, the outbound surface, the session lookup (sessioned mode), and
the signal-coordination logic.

**Turn.** One bounded execution of the workflow engine in service of an inbound request or event. A
turn corresponds to ONE call to `invoke()` or `invoke(resume_invocation=..., signal_payload=...)`. A
turn begins at invoke entry and ends at invoke return (one of: `completed`, `errored`, or
`suspended`). The transport-level boundary (HTTP request lifetime, event-handler duration, etc.)
is set by the runtime, not by the harness contract.

**Inbound dispatch path.** One of the classification paths the harness routes inbound traffic
into. See §3.

**Outbound surface.** The mechanisms by which the harness exposes in-invocation effects to the
runtime: sync return values, async dispatches initiated from node bodies, and signal subscriptions
registered for paused invocations.

**Session resolver.** The harness's mechanism for mapping inbound traffic to a `session_id` (in
sessioned mode). Implementation-defined (a header field, a URL path param, an event payload field,
a CLI arg, etc.); the contract specifies that resolution happens, not how. Stateless-mode harnesses
do NOT have a session resolver.

**Signal coordinator.** The harness's mechanism for routing inbound signal callbacks to the right
paused invocation. Implementation-defined; the contract specifies the coordination semantics, not
the mechanism.

**Harness mode (sessioned vs stateless).** A harness operates in one of two modes, determined at
construction:

- **Sessioned mode.** Every inbound transmission is associated with a `session_id` (resolved by the
  harness's session resolver). The harness threads `session_id` into every `invoke()`. Session
  state loads at invoke entry and saves at invoke exit per sessions §6.
- **Stateless mode.** Inbound transmissions carry no session identity. Every turn is independent.
  The harness does NOT resolve a `session_id`, does NOT invoke any SessionStore, and does NOT
  thread any `session_id` into `invoke()`. Used by deployment runtimes serving inherently stateless
  workloads (REST APIs without per-conversation context, batch processors, scoring services).

Stateless mode is first-class — not a degenerate sessioned case with `session_id = None`. The two
modes have different inbound dispatch classification (§3.1 / §3.2 / §3.3 vs §3.0) and different
sessions composition (per §8.1). Mode is fixed at harness construction; mixing modes within one
harness instance is out of scope (an application needing both shapes constructs two harness
instances, one per mode).

## 3. Inbound dispatch paths

Every inbound transmission (request / event / CLI input) the harness receives MUST be classified
into exactly one path. In **sessioned mode**, the path is one of §3.1 / §3.2 / §3.3. In
**stateless mode**, every transmission routes through §3.0.

### 3.0 Stateless transmission path (stateless-mode harnesses only)

The harness is configured in stateless mode (per §2 *Harness mode*). Every inbound transmission is
independent — the harness does NOT resolve a `session_id`, does NOT load or save session state, and
does NOT thread any `session_id` into the engine.

The harness:

1. Constructs the initial state from the inbound payload per harness-implementation logic.
2. Calls `invoke(initial_state)` — no `session_id` argument; no SessionStore interaction occurs
   even if one happens to be registered on the compiled graph.
3. Handles the outcome per §5.

A stateless-mode harness MUST NOT classify any transmission into §3.1 / §3.2 / §3.3 (the sessioned
paths). A sessioned-mode harness MUST NOT classify any transmission into §3.0. Mode is fixed at
construction; mixing modes within one harness instance is out of scope.

The signal-resume case under stateless mode (§3.3-equivalent) is permitted IF the runtime emits
identifiable resume signals carrying the paused-invocation_id. The stateless harness's signal
coordinator (§6) routes the signal to a resume invocation without any session context — the
paused-invocation record carries no `session_id` (it was created by a stateless invoke), so resume
threading is session-free.

### 3.1 New-session path (sessioned mode)

The inbound transmission begins a new session. Path 3.1 is classified by caller intent — the
transport routes the transmission as a new-session start (e.g., a dedicated "start session" HTTP
route, an event type meaning "begin work for this id", or simply the absence of any `session_id`).
The harness does NOT verify whether a supplied id already exists in the session store; that check
is the engine's responsibility per sessions §6.1.

The harness:

1. Resolves `session_id` from the inbound payload, or assigns a fresh one if absent.
2. Constructs the initial state from the inbound payload per harness-implementation logic.
3. Calls `invoke(initial_state, session_id=<id>)`.
4. Handles the outcome per §5.

### 3.2 Existing-active-session path (sessioned mode)

The inbound transmission continues an existing session. Path 3.2 is classified by caller intent —
the transport routes the transmission as a continuation of an ongoing session, and the
transmission carries a `session_id` naming that session. The harness does NOT verify whether the
session exists or its state — that check is the engine's responsibility per sessions §6.1.

The harness:

1. Resolves `session_id` from the inbound payload.
2. Constructs the next-turn state from the inbound payload. The session-state load happens inside
   `invoke()` per sessions §6.1; the harness does NOT load session state itself.
3. Calls `invoke(initial_state, session_id=<id>)`.
4. Handles the outcome per §5.

The distinction from 3.1 is caller intent: 3.1 starts a new session, 3.2 continues an existing
one. The engine resolves any disagreement between intent and store state per sessions §6's
semantics — e.g., a 3.2 transmission referencing a `session_id` that no engine-side record matches
surfaces as a `session_load_failed` error per §7.

### 3.3 Signal-resume path (sessioned mode; stateless-mode equivalent per §3.0)

The inbound transmission carries a signal payload correlating to a paused invocation. The harness:

1. Resolves the target `invocation_id` from the signal correlation (via the signal coordinator,
   see §6).
2. Constructs the `signal_payload` from the inbound transmission.
3. Calls `invoke(resume_invocation=<id>, signal_payload=<payload>)`.
4. Handles the outcome per §5.

A signal-resume MUST also implicitly belong to the paused invocation's session (in sessioned
mode — the engine threads `session_id` from the paused record). The harness does not re-resolve
`session_id` on signal-resume; the paused record carries it. In stateless mode, the
stateless-equivalent of this path (per §3.0's last paragraph) carries no `session_id` because the
paused record was created session-free.

### 3.4 Path classification

The harness MUST classify every inbound transmission into exactly one path before calling
`invoke()`. In sessioned mode, the choice is among 3.1 / 3.2 / 3.3; in stateless mode, every
transmission routes through 3.0 (with the resume-equivalent allowance per 3.0's last paragraph).
The classification is the harness's responsibility; specific transports (HTTP routes, event
types, etc.) typically determine it. The contract requires the classification be deterministic
from the inbound payload (a given payload always routes to the same path).

## 4. Turn lifecycle

A turn has three observable phases:

**Turn entry.** The harness calls `invoke()` (or `invoke(resume_invocation=...)`). The engine's
session-load (sessioned mode only), observer setup, and graph execution begin per sessions §6 and
graph-engine §3.

**Turn body.** Graph execution runs. Node bodies MAY:

- Read state.
- Write state updates (via reducers per graph-engine §2).
- Initiate sync outbound calls (HTTP requests, database queries, LLM provider calls, etc.). The
  harness has no role here; node bodies call out directly.
- Initiate async outbound dispatches (event publishes, job submissions, queue messages). The
  harness has no role here; node bodies dispatch directly. The application is responsible for
  arranging that the eventual response (the signal) routes back to the harness's signal
  coordinator.
- Suspend via `suspend(descriptor)` (per suspension §3). The engine persists the paused-invocation
  record and returns from invoke.

**Turn exit.** `invoke()` returns one of three outcomes per graph-engine §3 *Invocation outcomes*:

- **`completed`** — graph reached END. Final state is the return value. Session state auto-saves
  per sessions §6.1 (sessioned mode); no-op (stateless mode).
- **`errored`** — a node raised. Per graph-engine §4 error semantics. Session state behavior
  depends on sessions §6 (sessioned mode); no-op (stateless mode).
- **`suspended`** — a node called `suspend()`. Per suspension §3 + §5, the paused-invocation
  record is persisted, the suspended outcome is returned, and session state saves at suspend
  time (sessioned mode; atomic-suspend rule per suspension §8.6); no session save (stateless
  mode).

The harness handles each outcome per §5.

The turn lifecycle is abstract over transport: a sync HTTP request returns the outcome's
surfaced shape directly; an async event handler publishes a result-event derived from the
outcome; a CLI repl prints to stdout. The contract specifies the outcome shape; the surface is
per-implementation.

## 5. Outcome handling

The harness MUST handle each invoke outcome:

### 5.1 Completed outcome

The harness exposes the final state (or a derived surface, depending on the runtime) to the
inbound caller. Implementation-defined how the state maps to the transport surface; the contract
requires that completion is observably distinct from suspension and from error.

### 5.2 Errored outcome

The harness categorizes the error per §7 and surfaces it. Some errors terminate the session
(e.g., a state-corruption error); others surface as turn-level transient failures the caller MAY
retry; others surface as user-correctable errors (validation failures, missing inputs, etc.).

### 5.3 Suspended outcome

The harness:

1. Reads the signal descriptor from the suspended outcome (per suspension §5).
2. Registers a signal subscription with the runtime per §6 — telling the runtime "when a signal
   matching this descriptor arrives, route it back to me via the signal-resume inbound path."
3. Returns an acknowledgment to the inbound caller indicating the turn paused — the
   transport-level shape of this acknowledgment is implementation-defined.
4. EXITS without blocking. The harness is now free to handle other turns for other sessions /
   invocations.

Step 4 is the load-bearing requirement. A harness MUST NOT block on suspended turns. The whole
point of the suspension primitive (per suspension §1) is that the worker frees up to serve other
traffic.

## 6. Signal coordinator

The harness owns the signal-coordination logic that ties together:

- **At suspend time:** Map the signal descriptor (from §5.3) into a runtime-specific subscription
  that will route matching signals back to the harness's signal-resume inbound path.
- **At signal arrival:** Map the arriving signal to the target paused `invocation_id` and the
  appropriate `signal_payload`.

Specific mechanisms are runtime-defined:

- **REST callback.** The harness registers an endpoint at `POST /callback/<invocation_id>`; the
  dispatched async job carries this URL; the callback fires by posting to the URL. The
  signal-resume inbound path receives the POST and extracts `invocation_id` from the URL.
- **Event bus.** The harness subscribes to a topic / pattern; the signal descriptor names the
  correlation key embedded in the awaited event; on event arrival, the harness looks up the
  paused-invocation record by correlation key.
- **Scheduled wakeup.** The harness registers a scheduled trigger (via a scheduler the runtime
  exposes); the trigger fires the signal-resume inbound path with the `invocation_id` stored in
  the schedule entry.

The contract requires that the signal coordinator be **complete**: every suspended invocation
MUST have a mechanism by which its awaited signal can reach the harness's signal-resume path.
The harness MAY fail at suspend time (per §5.3 step 2) if it cannot register the subscription;
in that case the suspension converts to an error per §7 (the
`harness_signal_subscription_failed` category per §10).

## 7. Error categorization at the turn boundary

Errors that surface at the turn boundary — whether propagated from the engine or raised by the
harness itself — fall into three categories:

### 7.1 Session-terminating errors

Errors indicating the session's state is corrupt or unsalvageable. Examples:

- `session_load_failed` (sessions §10)
- `session_state_migration_chain_ambiguous` (sessions §10)
- `session_state_migration_missing` (sessions §10 — no recovery without a migration)
- State-schema validation failures that cannot resolve by retrying

The harness SHOULD surface these to the caller with a transport-specific "session is broken;
intervention required" indication and SHOULD NOT auto-retry. Sessions in this state MAY be
deleted by operators.

In stateless mode, session-terminating errors do not arise (no sessions to terminate); the
session-related categories simply don't appear.

### 7.2 Retryable transient errors

Errors that MAY succeed on retry with the same inputs. Examples:

- `provider_unavailable`, `provider_rate_limit`, `provider_model_not_loaded` (llm-provider §7)
- `session_save_failed` (if transient; sessions §10) — sessioned mode only
- `harness_signal_subscription_failed` (if transient; per §10)

The harness MAY auto-retry per its runtime conventions (e.g., an event-driven harness leans on
the runtime's retry mechanism; a sync HTTP harness might retry inline or surface a retry-after
header).

### 7.3 User-correctable errors

Errors requiring caller action. Examples:

- `provider_invalid_request` (llm-provider §7 — the caller sent bad inputs)
- `suspension_resume_payload_invalid` (suspension §9 — the signal payload doesn't match the
  schema)
- `provider_authentication` (llm-provider §7 — credentials issue)

The harness surfaces these with diagnostic information; the caller adjusts inputs and retries
explicitly.

Implementations MAY refine these categories. The contract specifies the three-bucket split;
harness implementations classify specific error categories into the buckets and surface them per
their transport's conventions.

## 8. Composition with capabilities

### 8.1 Sessions

Composition splits by harness mode (per §2):

- **Sessioned-mode harnesses** thread `session_id` into every `invoke()` per the inbound dispatch
  paths in §3.1 / §3.2 / §3.3. The engine handles session load/save per sessions §6. The harness
  does NOT directly access the SessionStore — the engine owns that interaction.
- **Stateless-mode harnesses** omit `session_id` from every `invoke()` per §3.0. The engine MUST
  NOT invoke any SessionStore even if one is registered on the compiled graph (the
  `session_id=absent` discipline from sessions §3 governs). Stateless harnesses MAY share a
  compiled graph with sessioned harnesses if an application instantiates both for different
  transport surfaces — the engine's behavior is determined per-invocation by whether `session_id`
  is supplied, not by graph configuration.

In both modes, the harness does NOT directly access the SessionStore; sessioned-mode harnesses
delegate to the engine via `session_id` threading, and stateless-mode harnesses don't touch it
at all.

### 8.2 Suspension

The harness handles the `suspended` outcome per §5.3 and the signal coordinator per §6. The
engine emits the paused-invocation record and the suspended outcome per suspension §5; the
harness handles the rest. Composition with sessions follows suspension §8.6's atomic-suspend
rule in sessioned mode; in stateless mode, the paused record persists without an accompanying
session record.

### 8.3 Checkpointing

The harness MAY configure a checkpointer on the compiled graph for mid-invoke crash recovery
per pipeline-utilities §10. The contract does not require checkpointing; harnesses targeting
runtimes with durable handler execution (Inngest steps, AWS Lambda durable workflows, etc.) MAY
rely on the runtime's durability layer in lieu of OpenArmature's checkpointer. Harnesses
targeting non-durable runtimes (plain FastAPI, stateless containers) SHOULD configure a
checkpointer to make multi-node invokes resumable.

### 8.4 Observability

The harness MAY open a turn-level wrapper span around `invoke()` per observability §4.6
(optional — runtimes that already provide a transport-level parent span MAY skip it). When the
wrapper IS opened, it carries:

- `openarmature.session_id` (sessioned mode only — absent in stateless mode per observability
  §5.6)
- The signal descriptor attributes per observability §5.8 on signal-resume turns

The invocation root span (per observability §4) becomes a child of the turn wrapper span when
present. This nesting lets trace UIs scope traces to turns when desired; when the wrapper is
absent, the invocation span attaches to whatever transport-level parent the runtime provides.

## 9. Per-harness-type implementations

The contract is abstract; concrete harness types ship as sibling packages. Examples (not
normative — names are illustrative):

- **`openarmature-chat`** — a thin chat-loop harness. The runtime is a programmatic loop; the
  inbound transmission is a chat message; the outbound surface is the assistant response.
  Suspension MAY surface as a pause-and-prompt-the-user shape. Typically sessioned-mode
  (per-conversation `session_id`).
- **`openarmature-fastapi`** — wraps OpenArmature into a FastAPI app. Inbound is HTTP request;
  outbound is HTTP response. Signal coordinator uses callback endpoints. MAY be sessioned (REST
  routes carrying session ids) OR stateless (REST routes without session identity).
- **`openarmature-inngest`** — wraps OpenArmature into Inngest event handlers. Inbound is event;
  outbound is event publish; signal coordinator uses `step.waitForEvent`. Typically sessioned-mode
  (conversation / workspace ids embedded in events).
- **`openarmature-cli`** — wraps OpenArmature into a CLI repl. Inbound is stdin; outbound is
  stdout. Suspension MAY surface as "press enter to continue when ready". Typically
  sessioned-mode (per-repl-instance session id).

Each per-harness-type implementation MAY ship its own conformance suite (against the abstract
contract here). Spec-level per-harness-type sub-specs land as cross-impl-divergence risk
warrants — **the chat harness is committed to a follow-on sub-spec** (planned proposal
`0NNN-harness-chat`), specifying the inbound message → session → invoke wiring, the outbound
assistant message → session → response wiring, and the higher-level callable surface
(`harness.send(session_id, message)` rather than hand-threading `invoke()` arguments). Other
per-harness-type sub-specs remain decided-per-case when each ships its first implementation.

## 10. Errors

Canonical error categories introduced by this capability:

- **`harness_session_id_unresolved`** — inbound transmission cannot be classified into a
  dispatch path because `session_id` resolution failed (sessioned mode only). Applies to §3.1 /
  §3.2 paths only; signal-resume (§3.3) draws `session_id` from the paused record. Stateless
  mode does not surface this category.
- **`harness_signal_subscription_failed`** — at suspend time, the harness could not register the
  subscription with the runtime (the suspension cannot be persisted as resolvable; converts to
  an error outcome per §5.3).
- **`harness_signal_correlation_failed`** — at signal arrival, the signal coordinator cannot
  map the inbound transmission to a paused invocation.
- **`harness_path_classification_ambiguous`** — inbound transmission satisfies criteria for
  multiple paths or cannot be unambiguously classified.

## 11. Determinism

The harness is a control-flow layer; it does not affect deterministic execution within a single
invocation. Two replays of the same inbound transmission against the same harness state should
classify to the same path and produce the same `invoke()` call (modulo timestamps, engine-
generated `invocation_id`s, and harness-generated `session_id`s when §3.1 assigns a fresh one
— all non-deterministic by design; see graph-engine §5).

Cross-turn determinism is not part of the contract: subsequent turns observe the prior turn's
saved session state (sessioned mode), which means a turn's behavior depends on history. This is
correct and expected.

## 12. Cross-spec touchpoints

- **graph-engine §3** *Invocation entry surface* — harness invokes `invoke()`; the contract is
  the abstract entry surface. Harness-mode determines whether `session_id` is supplied.
- **graph-engine §3** *Invocation outcomes* — the three outcomes the harness handles per §5.
- **observability §4** *Span hierarchy* — turn-level span wraps the invocation root span.
- **observability §5.6** *Cross-cutting attributes* — `openarmature.session_id` on every span
  emitted during sessioned-mode invocations; absent under stateless mode.
- **sessions §3** *Identity scoping* — harness threads `session_id` (sessioned mode); omits it
  (stateless mode).
- **sessions §6** *Lifecycle hooks* — engine handles load / save based on `session_id`
  presence.
- **suspension §5** *Suspended outcome* — harness handles per §5.3.
- **suspension §6** *NodeEvent and observer integration* — turn-level spans observe the
  suspended phase per the graph-engine §6 NodeEvent enum.
- **suspension §7** *Resume API* — harness dispatches signal-resume invokes per §3.3.
- **suspension §8.6** *Sessions composition* — atomic-suspend rule applies in sessioned mode.
- **pipeline-utilities §10** *Checkpointing* — optional harness configuration per §8.3.

## 13. Out of scope

- **Specific transport surfaces.** HTTP, gRPC, event bus, queue, stdin/stdout, WebSocket — per-
  harness-implementation concerns.
- **Specific signal-delivery mechanisms.** REST callback, event subscription, scheduled trigger,
  queue subscription — runtime concerns; the harness adapts.
- **Streaming token-level output.** A separate proposal (planned) would specify streaming hooks;
  this capability stays at turn-level granularity.
- **Multi-tenant routing.** The harness receives a resolved `session_id` (sessioned mode) from
  the application's routing layer; the routing layer decides which tenant the session belongs
  to.
- **Rate limiting / quotas / authn / authz.** Cross-cutting application concerns.
- **Per-harness-type behavioral specs.** The chat harness, FastAPI harness, etc. each have
  their own behavioral surface; chat is committed to a follow-on sub-spec per §9, others land
  per-case.
- **Mixing sessioned + stateless modes within one harness instance.** Mode is fixed at harness
  construction. An application needing both shapes constructs two harness instances, one per
  mode.
