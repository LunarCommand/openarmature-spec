# Sessions

Canonical behavioral specification for the OpenArmature sessions capability.

- **Capability:** sessions
- **Introduced:** spec version 0.33.0
- **History:**
  - created by [proposal 0020](../../proposals/0020-sessions-capability.md)
  - §3 *Identity scoping* gained a *Harness threading* paragraph noting that deployments wrapping the engine via a harness (per the harness capability spec) are responsible for resolving `session_id` from inbound traffic and threading it into every `invoke()` call in sessioned mode; stateless-mode harnesses never thread a `session_id`. Documentary cross-reference; no behavior change at the sessions layer (the omit-and-skip rule was already normative) by [proposal 0022](../../proposals/0022-harness-contract.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The `sessions` capability defines the contract by which named, typed state records persist across multiple
`invoke()` calls under a stable caller-supplied identifier. This spec establishes the storage protocol,
state-shape rules, lifecycle hooks, schema migration, concurrency policy, composition with other
capabilities, and observability propagation. Implementations and sibling-package backends ship the concrete
forms.

The capability composes with:

- **graph-engine** — `session_id` joins `invocation_id` / `correlation_id` as a spec-defined identity
  attribute available throughout an invocation. Like those identifiers, it is supplied at `invoke()` and
  propagated through the ambient invocation context (§3); it is not a field on the §6 `NodeEvent`.
- **pipeline-utilities §10 (checkpointing)** — the shared persistence mechanism is permitted but not
  required; session storage MAY use the checkpointer's backend, a separate store, or any combination. The
  semantics are distinct (sessions = cross-invoke, checkpoints = per-invoke).
- **observability** — `session_id` becomes a cross-cutting span attribute (observability §5.6) on every span
  emitted within a session-bound invocation and a structured-log field (observability §7) on every log
  record emitted within such an invocation.

This capability does NOT define:

- The specific storage backend (SQLite, Redis, Postgres, cloud-managed services — implementations and
  sibling packages ship these).
- Session-level conversation history (the sequence of LLM messages a chat agent exchanges — that is an
  application-owned data structure, possibly stored *in* session state, but its shape is not normative).
- Distributed locking primitives (backend-implementation concern).
- TTL / expiry / garbage collection (backend-implementation concern).
- Multi-session merging / handoff (application-level orchestration).

## 2. Concepts

**Session.** The typed state record persisted under a `session_id`. Carries the application's cross-invoke
state plus identity metadata (the `session_id`, optional `schema_version` for migration). Distinct from
invoke state — see §4 on the projection split.

**SessionStore.** The load / save / delete / list protocol implementations satisfy to provide session
persistence. Mirrors the `Checkpointer` protocol (pipeline-utilities §10) but with session-keyed semantics.

**SessionRecord.** The stored representation of a session: `session_id` + serialized state +
`schema_version` + opaque backend metadata (created_at, updated_at, version counter for optimistic
concurrency, etc.). Implementations MAY add fields; the spec defines the minimum.

**SessionState.** The optional typed projection of cross-invoke state — a narrower view than the full invoke
`State` that excludes per-invoke scratch fields. See §4. Implementations MAY omit the projection when the
full invoke state is the right session shape.

**`session_id`.** A caller-supplied string identifier scoped across many invocations. Stable for the
lifetime of the application's session concept (a user's conversation, a long-running task, a per-tenant
workspace, etc.). The engine never generates it; the caller is responsible for supplying it.

## 3. Identity scoping

A spec-defined identity trio threads through an invocation context:

| Identity | Lifetime | Generator | Purpose |
|---|---|---|---|
| `invocation_id` | One `invoke()` call | Engine (UUIDv4 if caller doesn't supply) | Joins state, span, and log records within a single invocation |
| `correlation_id` | One invocation across attempts | Engine (preserved across resume) | Joins retries / resumes of the same invocation |
| `session_id` | Many invocations under one identity | **Caller** | Joins the session's accumulated state across separate invokes |

`session_id` is supplied at `invoke()` through the same per-language idiomatic surface as `correlation_id`
and `invocation_id` (a keyword argument, a field on an invocation-config record, or equivalent;
graph-engine §3). When `session_id` is supplied, the engine MUST:

1. **Propagate it via the language's idiomatic context primitive** — Python `ContextVar`, TypeScript
   `AsyncLocalStorage`, equivalents — so that it is readable from anywhere within the invocation's async
   call tree, including inside nodes, middleware, and observers, without explicit threading through
   function arguments. This mirrors the `correlation_id` propagation contract (observability §3.1). The
   engine MUST reset the context after the invocation completes so subsequent invocations start clean.
2. If a `SessionStore` is registered on the compiled graph: load the existing session record (if any),
   apply §7 migration if needed, and merge its state into the initial invoke state per §4 projection rules,
   then proceed with the invocation.
3. On invocation completion (END reached): write the resulting state back to the store under the same
   `session_id` per §6 lifecycle rules.

When `session_id` is omitted, the engine MUST NOT call into the `SessionStore` even if one is registered.
The session machinery is opt-in per-invoke.

**Harness threading.** In deployments wrapping the engine via a harness (per the harness capability spec),
the harness is responsible for resolving `session_id` from inbound traffic and threading it into every
`invoke()` call — in **sessioned mode**. **Stateless-mode harnesses** never thread a `session_id`; every
turn invokes the engine without one and the session machinery stays inert. The harness capability spec
defines the contract for both modes; this capability defines what happens when `session_id` IS supplied
(per the above) or is NOT (the omit-and-skip rule above). The two contracts compose without duplication.

## 4. Session shape and projection

Two valid configurations:

**4.1 Full-state sessions.** The invocation's `State` type IS the session state. On invoke entry, the
loaded record's state is merged into the supplied initial state (per the implementation's reducer
semantics). On invoke exit, the final state is written to the store.

Simple; fits cases where every state field is durable across invokes (no scratch fields, no per-invoke
temporary buffers).

**4.2 Projected sessions.** A separate `SessionState` type is declared on the builder. The session record
stores only the `SessionState` slice; the full invoke `State` MAY contain additional fields that are NOT
persisted across invokes (per-invoke scratch, intermediate buffers, error accumulators, etc.).

The projection is defined by:

- A `SessionState` type declaration (a separate typed-state schema — implementation-defined form).
- An inbound projection: load the session record's `SessionState` and merge its fields into the initial
  invoke state at invoke entry.
- An outbound projection: read the session-state fields from the final invoke state and write them as the
  new session record at invoke exit.

Field mapping between `SessionState` and `State` SHOULD use the same projection machinery as subgraph
input/output mapping (graph-engine §2): same fields by name by default; explicit mapping when names differ.

**Recommendation.** Implementations SHOULD default to projected sessions (§4.2) — the explicit projection
prevents accidentally persisting scratch fields. Full-state sessions (§4.1) are a permitted shorthand when
the invoke state IS the session state.

## 5. SessionStore protocol

A `SessionStore` implementation MUST expose four async operations.

### 5.1 `load(session_id)`

Async. Returns `SessionRecord | None`. None when no record exists for the given `session_id`.

Implementations SHOULD return the record together with its `schema_version` so the caller can route through
migration before merging into state; see §7.

### 5.2 `save(session_id, record)`

Async. Writes the record, overwriting any existing record under the same `session_id`. Last-write-wins
default — see §8 for stricter options.

Implementations MAY return a backend-specific result token (version counter, ETag, etc.) for use by callers
implementing optimistic concurrency on top of the base protocol. The spec defines the base protocol as
void-return; richer return types are backend extensions.

### 5.3 `delete(session_id)`

Async. Removes the record. Idempotent — deleting a non-existent session MUST NOT raise.

### 5.4 `list(filter=None)`

Async. Returns an iterable of `SessionSummary` records (lightweight metadata — `session_id`,
`schema_version`, `updated_at`; NOT the full serialized state). The filter parameter is
implementation-defined; the spec recommends supporting `updated_after`, `created_after`, and
`schema_version` as common filters.

Implementations MUST support listing all sessions when filter is None. Pagination MAY be
implementation-specific (cursor, offset/limit, etc.).

### 5.5 Reference backends

Specific backends are an implementation choice, mirroring how checkpointers are handled (pipeline-utilities
§10). The spec defines the protocol; implementations bundle reference backends and the wider ecosystem
layers production-grade backends as sibling packages.

Reference-implementation guidance for OpenArmature implementations:

- **Bundled minimum: in-memory backend.** Every conforming implementation SHOULD ship an in-memory backend
  suitable for testing, documentation examples, and ephemeral dev workflows. The in-memory backend MUST
  satisfy the full `SessionStore` protocol from §5.1–§5.4; ephemerality is the only carve-out (state
  vanishes on process exit).
- **Bundled recommended: embedded-database backend.** Implementations SHOULD also ship an embedded-database
  backend (e.g., SQLite-backed) suitable for single-process production apps without an external database
  dependency. This matches the precedent set by the embedded-database checkpointer and prompt backend —
  every capability that involves persistence ships an embedded-database reference backend so docs /
  quickstarts / single-machine deployments work out of the box.
- **Out-of-tree: production backends.** Redis, Postgres, DynamoDB, vendor-managed equivalents, and
  per-application stores layer in as sibling packages (`openarmature-redis`, `openarmature-postgres`, etc.)
  or as application-internal code. The spec does not require implementations to ship these; the protocol is
  enough.

Implementations that omit the in-memory or embedded backends remain conforming if they satisfy the
protocol, but lose the docs-quickstart-just-works property that motivates the recommendation.

## 6. Lifecycle hooks

### 6.1 Auto-save (default)

When a `SessionStore` is registered AND `session_id` is supplied to `invoke()`:

- **Invoke entry:** the engine calls `SessionStore.load(session_id)`. If a record exists, the engine applies
  §7 migration if needed, then merges via §4 projection into the initial state. If no record exists, the
  supplied initial state proceeds unchanged.
- **Invoke exit (END reached):** the engine constructs a `SessionRecord` from the final state per §4
  projection, then calls `SessionStore.save(session_id, record)`.

Failures during load propagate as a `session_load_failed` error (§10). Failures during save propagate as
`session_save_failed`; the invocation's state was already committed at END, so save failures do NOT roll
back the invoke result, but DO signal that subsequent invokes will see the prior session state.

### 6.2 Explicit mid-invoke save

A node MAY explicitly request a session save (engine-side API) to commit current session-projected state
mid-invoke. Useful for long invocations that want to expose partial progress to subsequent invokes (e.g., a
session showing "processing step 3 of 5" while the invoke continues).

Implementations MAY provide this as a node-body callable, a context manager, or an engine method — the spec
defines the behavior, not the surface syntax.

Multiple mid-invoke saves overwrite previous saves under the same `session_id`. If invoke exits normally
after a mid-invoke save, the auto-save at END writes the final state (which subsumes the mid-invoke save).

### 6.3 Opt-out from auto-save

When `auto_save=False` is set on the builder registration, the engine MUST NOT save automatically at invoke
exit. Sessions then persist only via explicit mid-invoke saves (§6.2). Default is `auto_save=True`.

## 7. Schema migration

Sessions live longer than deploys. A session created under `SessionState v1` may be loaded under a graph
expecting `SessionState v2`. The state-migration machinery from checkpointing (pipeline-utilities §10.12)
lifts cleanly.

A graph builder MAY register session migrations keyed by `(from_version, to_version)`. The migration
function takes the loaded record's dict-form state and returns a dict in the target version's shape. Chain
resolution semantics are identical to checkpoint state migration: a breadth-first search over registered
edges; an ambiguous chain raises the canonical `session_state_migration_chain_ambiguous` category (§10).

The engine resolves and applies the chain at invoke entry, between `SessionStore.load()` and the §4
projection merge. A session record loading under a graph that lacks a migration path raises the canonical
`session_state_migration_missing` category (§10). A registered migration function that raises during chain
application surfaces the failure as the canonical `session_state_migration_failed` category (§10),
preserving the raised exception as cause; subsequent migrations in the chain MUST NOT run, and the graph
MUST NOT run.

**Reuse vs fork.** Implementations MAY share the migration-registry type between checkpoint state migration
(pipeline-utilities §10.12) and session state migration. Whether to share or fork is implementation-defined.
The spec-level categories are distinct (`session_state_migration_*` vs `checkpoint_state_migration_*`)
because the lifecycles are distinct.

## 8. Concurrency

Multiple in-flight invokes MAY share a `session_id` (concurrent requests from the same user, parallel tasks
against the same workspace, etc.). The spec defines a default policy with an extension point for stricter
guarantees.

**8.1 Default: last-write-wins.** Concurrent invokes against the same `session_id` run independently. Each
loads the session state at invoke entry, runs to END with its own state copy, and saves at invoke exit. The
last save wins; earlier saves are overwritten without notification. This is the natural shape for
read-mostly sessions and for cases where the application enforces session-level serialization above OA.

**8.2 Optimistic concurrency.** A backend MAY surface a version counter (or ETag, or generation number) on
`SessionRecord` and accept an optional `expected_version` parameter on `save()`. When the backend detects a
version mismatch, it raises the canonical `session_write_conflict` category. The spec defines the category
and the optional `expected_version` parameter; the backend ships the implementation. The application decides
what to do on conflict (retry, fail the invoke, surface to user, etc.). The engine does NOT retry session
saves automatically.

**8.3 Pessimistic locking.** A backend MAY layer additional methods (`acquire_lock(session_id)`,
`release_lock(session_id)`) on top of the base protocol. The spec defines the protocol surface; lock
semantics are backend-defined.

## 9. Composition with other capabilities

**9.1 Subgraphs (graph-engine §2).** Subgraphs do NOT see session state directly. They see whatever the
outer graph projects in via normal `inputs` / `outputs` projection. Session state is an outermost-graph
concern.

**9.2 Fan-out (pipeline-utilities §9).** Fan-out instances are subgraph invocations — they do NOT see
session state directly. Per-instance state comes from the outer graph's projection.

**9.3 Parallel branches (pipeline-utilities §11).** Same as fan-out: branches are subgraph invocations;
session state is invisible to them except through the outer graph's projection.

**9.4 Checkpointing (pipeline-utilities §10).** Checkpointing and sessions are orthogonal persistence
layers:

- Checkpointing: per-invocation, durable mid-invoke state, lifetime ends with the invocation (modulo backend
  retention policy).
- Sessions: per-session, durable cross-invoke state, lifetime managed by the application.

The two MAY share a backend store but the spec keeps the semantics separate. An invocation MAY use both,
neither, or either independently.

**9.5 Graph suspension ([proposal 0021](../../proposals/0021-graph-suspension.md)).** When a graph suspends
mid-invoke, session state SHOULD save at suspend-time alongside the paused-invocation record, so a fresh
worker resuming the suspended invocation sees consistent session state. The suspension capability specifies
the integration; this capability provides the save-at-suspend hook it builds on.

## 10. Errors

Six canonical error categories:

- **`session_load_failed`** — `SessionStore.load()` raised an unrecoverable error. The invoke MUST NOT
  proceed.
- **`session_save_failed`** — `SessionStore.save()` raised. When raised by the auto-save at invoke exit
  (§6.1), the invoke's final state was already committed and the failure surfaces to the `invoke()`
  caller as a post-completion error; the invoke result does NOT roll back, but subsequent invokes will
  see the prior session state. When raised by an explicit mid-invoke save (§6.2), the failure surfaces
  at the point of the save call within the invocation — the node body that requested the save sees the
  error in the language's idiomatic form and MAY swallow, retry, or propagate it as a normal node
  failure (which the engine then handles per graph-engine §4).
- **`session_state_migration_missing`** — `SessionStore.load()` returned a record with a `schema_version`
  for which no migration chain to the current schema is registered. Non-transient.
- **`session_state_migration_chain_ambiguous`** — the registered migration set contains a duplicate
  `(from_version, to_version)` pair or multiple distinct shortest paths between source and target. Same
  resolution semantics as the checkpoint category (pipeline-utilities §10.12).
- **`session_state_migration_failed`** — a registered migration function raised during chain application.
  The engine MUST surface this category (mirror of `checkpoint_state_migration_failed`, pipeline-utilities
  §10.12), preserving the raised exception as cause. Subsequent migrations in the chain MUST NOT run;
  the graph MUST NOT run.
- **`session_write_conflict`** — an optimistic-concurrency conflict surfaced by a backend that supports it.
  See §8.2.

## 11. Cross-spec touchpoints

### 11.1 observability §5.6 (cross-cutting span attributes) and §7 (log correlation)

When an invocation is bound to a session, `openarmature.session_id` is emitted as a §5.6 cross-cutting span
attribute — it appears on every span emitted during the invocation (the invocation span and every node,
subgraph, fan-out instance, LLM provider, and retry span beneath it), the same scope as
`openarmature.correlation_id`. Structured logs emitted during the invocation carry `openarmature.session_id` as a
log-record field on every record (observability §7), via the same OTel Logs bridge mechanism as
`correlation_id`.

Because `session_id` propagates through the ambient invocation context (§3), observers and node bodies that
read the context see it without it being carried on the §6 `NodeEvent`. This matches how `invocation_id` and
`correlation_id` reach observers and logs today.

### 11.2 pipeline-utilities §10 (checkpointing)

Sessions are a sibling persistence layer with cross-invoke scope; an invocation MAY use checkpointing and
sessions independently (§9.4). pipeline-utilities §10 carries the reciprocal note.

## 12. Determinism

Sessions are a side-effect layer; they do not affect deterministic execution within a single invocation. An
invocation's node ordering, observer event ordering, and final state (modulo loaded session content) are
determined by the graph topology and reducers, not by the session backend.

The session record's `updated_at` timestamp is a backend concern; it does not contribute to invocation
determinism.

## 13. Out of scope

- **TTL / expiry / GC.** Backend concern; the spec stays silent.
- **Distributed locking.** Backend extension; the spec defines the protocol surface, not the lock
  implementation.
- **Multi-session merging / handoff.** Application-level orchestration.
- **Conversation history.** Sessions store state ALONGSIDE conversation history (or any other application
  data). The history's shape is not normative.
- **Cross-session memory / knowledge stores.** Per-user profiles spanning many sessions; semantic /
  episodic / procedural memory; vector-indexed knowledge bases; and any "agent remembers things across
  users and conversations" layer are a separate capability concern. Sessions cover per-identity-scoped typed
  state only — "this conversation accumulates" lives in sessions; "I remember things about this user across
  all their conversations" does not. Sessions land first as the foundational persistence primitive; a
  cross-session memory layer composes on top, with different access patterns (queried mid-node, not loaded
  at invoke entry) and different identity scoping (namespace hierarchies, not a single `session_id`).
- **Session-level observers.** Observers are graph-level (per compiled graph) or invocation-level (per
  `invoke()` call). Cross-invocation observers spanning a session are out of scope; an application that
  needs them can correlate via `session_id` across invocation spans.
- **Migration chain compile-time validation.** Same disposition as checkpoints (pipeline-utilities §10.12):
  implementations SHOULD detect ambiguity at compile time when feasible; load-time detection is the
  spec-mandated minimum.
