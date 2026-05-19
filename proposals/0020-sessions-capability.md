# 0020: Sessions Capability

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-17
- **Accepted:**
- **Targets:** spec/sessions/spec.md (creates), spec/observability/spec.md (modifies §5.1 + §5.6 to add `session_id`), spec/pipeline-utilities/spec.md (modifies §10 cross-reference)
- **Related:** 0008 (checkpointing — sibling persistence capability), 0014 + 0018 (migration machinery — reuse pattern), 0007 (observability propagation)
- **Supersedes:**

## Summary

Create the `sessions` capability spec. Defines `Session` (a typed state record
persisted under a stable identifier across multiple `invoke()` calls),
`SessionStore` (the load / save / delete / list protocol), and `SessionState`
(the optional narrower projection type that distinguishes session state from
invoke state). Specifies the identity-scoping trio (`session_id` /
`invocation_id` / `correlation_id`), auto-save-on-completion as the default
lifecycle, last-write-wins concurrency, optional schema migration reusing the
`MigrationRegistry` shape from proposals 0014 / 0018, and outermost-graph-only
composition with subgraph / fan-out / parallel-branches.

## Motivation

OA today handles two persistence concerns:

- **Per-invocation checkpointing** (proposal 0008) — durably save state at each
  node boundary so a crashed `invoke()` can be resumed mid-graph.
- **Per-invocation schema migration** (proposals 0014 / 0018) — apply state
  migrations when a saved record is resumed under an upgraded state schema.

Both are scoped to a single `invoke()`. Neither handles the "agent handles a
stream of calls, accumulating context between them" pattern:

> A customer-support agent receives a message, replies, and remembers the
> conversation history for the next message. A coding assistant receives a
> request, completes a task, and remembers what files it has touched for the
> next request. A multi-step orchestrator receives a high-level goal, decomposes
> it across several invokes, and remembers the plan between steps.

Each of these is a session — a stable identity bound to a typed state bag that
persists across many separate `invoke()` calls. Today every project rebuilds
this layer: an application-level map from `session_id` to the most-recent
`invocation_id`, glue code to call `invoke(resume_invocation=...)` per turn, a
hand-rolled store for the cross-invoke state, and an ad-hoc convention for how
session state composes with the per-invoke state schema.

A spec'd sessions capability:

- **Names the identity scope.** `session_id` (caller-supplied, cross-invoke) is
  the third member of the identity trio alongside `invocation_id` (engine-
  generated, per-invoke) and `correlation_id` (per-invocation cross-attempt).
- **Defines the persistence protocol.** `SessionStore` mirrors `Checkpointer`
  but with session-keyed semantics. Reference backends ship for testing
  (in-memory) and single-process apps (SQLite); production-grade backends
  (Redis, Postgres, DynamoDB, the user's own choice) layer in via the protocol.
- **Settles the state-shape question.** Sessions get an optional narrower
  `SessionState` type projected from the full invoke state. Scratch fields
  stay in invoke state; durable cross-invoke fields ride in `SessionState`.
- **Specifies lifecycle.** Load on invoke entry (when `session_id` is supplied
  and a store is registered), save on invoke exit. Mid-invoke explicit save
  available for long invokes that want to commit progress before END.
- **Reuses migration machinery.** Sessions live across deploys; schema
  migration is mandatory. The `MigrationRegistry` shape from proposals 0014 /
  0018 lifts cleanly with renamed bindings.
- **Pins composition rules.** Session state is an outermost-graph concern.
  Subgraphs, fan-out instances, and parallel branches don't see it directly;
  they see whatever the outer graph projects through normal projection.

The capability is designed to compose with two near-term sibling proposals:

- **Proposal 0021 (graph suspension)** uses sessions as the natural cross-
  invocation state layer for paused-and-resumed agents.
- **Proposal 0022 (harness contract)** uses sessions as the multiplexing key —
  each inbound request / event names a `session_id`, the harness dispatches
  accordingly.

Sessions are the foundational primitive for both follow-ons. This proposal
lands first.

## Detailed design

### 1. Purpose

The `sessions` capability defines the contract by which named, typed state
records persist across multiple `invoke()` calls under a stable caller-supplied
identifier. The spec establishes the storage protocol, state-shape rules,
lifecycle hooks, schema migration, concurrency policy, composition with other
capabilities, and observability propagation. Implementations and sibling-
package backends ship the concrete forms.

The capability composes with:

- **graph-engine** — `session_id` joins `invocation_id` / `correlation_id` as a
  spec-defined identity attribute available throughout an invocation.
- **pipeline-utilities §10 (checkpointing)** — shared persistence mechanism is
  permitted but not required; session storage MAY use the checkpointer's
  backend, a separate store, or any combination. The semantics are distinct
  (sessions = cross-invoke, checkpoints = per-invoke).
- **observability** — `session_id` becomes a span attribute on the invocation
  root span and a structured-log field on every log record emitted within an
  invocation bound to a session.

This capability does NOT define:

- The specific storage backend (SQLite, Redis, Postgres, cloud-managed services
  — implementations and sibling packages ship these).
- Session-level conversation history (the sequence of LLM messages a chat agent
  exchanges — that's an application-owned data structure, possibly stored *in*
  session state, but its shape is not normative).
- Distributed locking primitives (backend-implementation concern).
- TTL / expiry / garbage collection (backend-implementation concern).
- Multi-session merging / handoff (application-level orchestration).

### 2. Concepts

**Session.** The typed state record persisted under a `session_id`. Carries
the application's cross-invoke state plus identity metadata (the `session_id`,
optional `schema_version` for migration). Distinct from invoke state — see
§4 on the projection split.

**SessionStore.** The load / save / delete / list protocol implementations
satisfy to provide session persistence. Mirrors the `Checkpointer` protocol
but with session-keyed semantics.

**SessionRecord.** The on-disk representation of a session: `session_id` +
serialized state + schema_version + opaque backend metadata (created_at,
updated_at, version counter for optimistic concurrency, etc.). Implementations
MAY add fields; the spec defines the minimum.

**SessionState.** The optional typed projection of cross-invoke state — a
narrower view than the full invoke `State` that excludes per-invoke scratch
fields. See §4. Implementations MAY omit the projection when the full invoke
state is the right session shape.

**session_id.** A caller-supplied string identifier scoped across many
invocations. Stable for the lifetime of the application's session concept (a
user's conversation, a long-running task, a per-tenant workspace, etc.).
Engine never generates it; the caller is responsible for supplying it.

### 3. Identity scoping

A spec-defined identity trio threads through an invocation context:

| Identity | Lifetime | Generator | Purpose |
|---|---|---|---|
| `invocation_id` | One `invoke()` call | Engine (UUIDv4 if caller doesn't supply) | Joins state, span, and log records within a single invocation |
| `correlation_id` | One invocation across attempts | Engine (preserved across resume) | Joins retries / resumes of the same invocation |
| `session_id` | Many invocations under one identity | **Caller** | Joins the session's accumulated state across separate invokes |

When `session_id` is supplied to `invoke()`, the engine:

1. Threads `session_id` through invocation context (alongside `invocation_id`
   and `correlation_id`) so observers, log records, and node bodies that read
   the context see it.
2. If a `SessionStore` is registered on the compiled graph: loads the existing
   session record (if any), merges its state into the initial invoke state
   (per §4 projection rules), and proceeds with invocation.
3. On invocation completion (END reached): writes the resulting state back to
   the store under the same `session_id` (per §5 lifecycle rules).

When `session_id` is omitted, the engine MUST NOT call into the SessionStore
even if one is registered. The session machinery is opt-in per-invoke.

### 4. Session shape and projection

Two valid configurations:

**4.1 Full-state sessions.** The invocation's `State` type IS the session state.
On invoke entry, the loaded record's state replaces the supplied initial state
(or merges per the implementation's reducer semantics; see open questions).
On invoke exit, the final state is written to the store.

Simple, fits cases where every state field is durable across invokes (no scratch
fields, no per-invoke temporary buffers).

**4.2 Projected sessions.** A separate `SessionState` type is declared on the
builder. The session record stores only the `SessionState` slice; the full
invoke `State` MAY contain additional fields that are NOT persisted across
invokes (per-invoke scratch, intermediate buffers, error accumulators, etc.).

The projection is defined by:

- A `SessionState` type declaration (separate Pydantic model / TypeScript
  interface — implementation-defined).
- An inbound projection: load the session record's `SessionState` and merge
  its fields into the initial invoke state at invoke entry.
- An outbound projection: read the session-state fields from the final invoke
  state and write them as the new session record at invoke exit.

Field mapping between `SessionState` and `State` SHOULD use the same projection
machinery as proposal 0002 (`ExplicitMapping`) and proposal 0001's
`FieldNameMatching` — same fields by name by default; explicit mapping when
names differ.

**Recommendation.** Implementations SHOULD default to projected sessions
(§4.2) — the explicit projection prevents accidentally persisting scratch
fields. Full-state sessions (§4.1) are a permitted shorthand when the invoke
state IS the session state.

### 5. SessionStore protocol

A `SessionStore` implementation MUST expose four async operations:

#### 5.1 `load(session_id)`

Async. Returns `SessionRecord | None`. None when no record exists for the
given `session_id`.

Implementations SHOULD treat a stale-version mismatch as part of load (i.e.,
returning the record with its `schema_version` so the caller can route through
migration before merging into state); see §7 on migration.

#### 5.2 `save(session_id, record)`

Async. Writes the record, overwriting any existing record under the same
`session_id`. Last-write-wins default — see §8 on concurrency for stricter
options.

Implementations MAY return a backend-specific result token (version counter,
ETag, etc.) for use by callers implementing optimistic-concurrency on top of
the base protocol. The spec defines the base protocol as void-return; richer
return types are backend extensions.

#### 5.3 `delete(session_id)`

Async. Removes the record. Idempotent — deleting a non-existent session MUST
NOT raise.

#### 5.4 `list(filter=None)`

Async. Returns an iterable of `SessionSummary` records (lightweight metadata —
`session_id`, `schema_version`, `updated_at`; NOT the full serialized state).
Filter parameter is implementation-defined; the spec recommends supporting
`updated_after`, `created_after`, `schema_version` as common filters.

Implementations MUST support listing all sessions when filter is None. Pagination
MAY be implementation-specific (cursor, offset/limit, etc.).

#### 5.5 Reference backends

Specific backends are implementation choice, mirroring how proposal 0008
handled checkpointers. The spec defines the protocol; implementations
bundle reference backends and the wider ecosystem layers production-grade
backends as sibling packages.

Reference-implementation guidance for OpenArmature implementations:

- **Bundled minimum: in-memory backend.** Every conforming implementation
  SHOULD ship an in-memory backend (e.g., `InMemorySessionStore`)
  suitable for testing, documentation examples, and ephemeral dev
  workflows. The in-memory backend MUST satisfy the full `SessionStore`
  protocol from §5.1–§5.4; ephemerality is the only carve-out (state
  vanishes on process exit).
- **Bundled recommended: embedded-database backend.** Implementations
  SHOULD also ship an embedded-database backend (e.g.,
  `SQLiteSessionStore` in Python, an equivalent in TypeScript) suitable
  for single-process production apps without an external database
  dependency. This matches the precedent set by `SQLiteCheckpointer`
  (proposal 0008) and `FilesystemPromptBackend` (proposal 0017) — every
  capability that involves persistence ships an embedded-database
  reference backend so docs / quickstarts / single-machine deployments
  work out of the box.
- **Out-of-tree: production backends.** Redis, Postgres, DynamoDB, the
  vendor-managed equivalents, and per-application stores layer in as
  sibling packages (`openarmature-redis`, `openarmature-postgres`,
  etc.) or as application-internal code. The spec does not require
  implementations to ship these; the protocol is enough.

Implementations that omit the in-memory or embedded backends remain
conforming if they satisfy the protocol, but lose the
docs-quickstart-just-works property that motivates the recommendation.

### 6. Lifecycle hooks

#### 6.1 Auto-save (default)

When a `SessionStore` is registered AND `session_id` is supplied to `invoke()`:

- **Invoke entry:** engine calls `SessionStore.load(session_id)`. If a record
  exists, the engine applies §7 migration if needed, then merges via §4
  projection into the initial state. If no record exists, the supplied initial
  state proceeds unchanged.
- **Invoke exit (END reached):** engine constructs a SessionRecord from the
  final state per §4 projection, then calls `SessionStore.save(session_id,
  record)`.

Failures during load propagate as load-time errors (a typed
`session_load_failed` category). Failures during save propagate as save-time
errors (`session_save_failed`); the invocation's state was already committed at
END, so save failures do NOT roll back the invoke result, but DO signal that
subsequent invokes will see the prior session state.

#### 6.2 Explicit mid-invoke save

A node MAY explicitly call `save_session()` (engine-side API) to commit current
session-projected state mid-invoke. Useful for long invocations that want to
expose partial progress to subsequent invokes (e.g., a session showing
"processing step 3 of 5" while the invoke continues).

Implementations MAY provide this as a node-body callable, a context-manager,
or an engine method — the spec defines the behavior, not the surface syntax.

Multiple mid-invoke saves overwrite previous saves under the same `session_id`.
If invoke exits normally after a mid-invoke save, the auto-save at END writes
the final state (which subsumes the mid-invoke save).

#### 6.3 Opt-out from auto-save

When `auto_save=False` is set on the builder registration (e.g.,
`builder.with_session_store(store, auto_save=False)`), the engine MUST NOT
save automatically at invoke exit. Sessions persist only via explicit
mid-invoke `save_session()` calls.

Default is `auto_save=True`.

### 7. Schema migration

Sessions live longer than deploys. A session created under `SessionState v1`
may be loaded under a graph expecting `SessionState v2`. The `MigrationRegistry`
machinery from proposals 0014 / 0018 lifts cleanly.

A graph builder MAY register session migrations:

```
builder.with_session_migration(from_version, to_version, migration_fn)
```

The migration function takes the loaded SessionRecord's dict-form state and
returns a dict in the target version's shape. Chain resolution semantics are
identical to checkpoint state migration (proposal 0014 + 0018): BFS over
registered edges; ambiguous chains raise the canonical
`session_state_migration_chain_ambiguous` category (mirror of the checkpoint
category from proposal 0018).

The engine resolves and applies the chain at invoke entry, between
`SessionStore.load()` and the §4 projection merge. A session record loading
under a graph that lacks a migration path raises the canonical
`session_state_migration_missing` category (mirror of the checkpoint category
from proposal 0014).

**Reuse vs fork:** Implementations MAY share the `MigrationRegistry` type
between checkpoint state migration (proposal 0014) and session state migration
(this proposal). Whether to share or fork is implementation-defined. The
spec-level categories are distinct (`session_state_migration_*` vs
`checkpoint_state_migration_*`) because the lifecycles are distinct.

### 8. Concurrency

Multiple in-flight invokes MAY share a `session_id` (concurrent requests from
the same user, parallel tasks against the same workspace, etc.). The spec
defines a default policy with an extension point for stricter guarantees.

**8.1 Default: last-write-wins.** Concurrent invokes against the same
`session_id` run independently. Each loads the session state at invoke entry,
runs to END with its own state copy, and saves at invoke exit. The last save
wins; earlier saves are overwritten without notification. This is the natural
shape for read-mostly sessions and for cases where the application enforces
session-level serialization above OA.

**8.2 Optimistic concurrency.** A backend MAY surface a version counter (or
ETag, or generation number) on `SessionRecord` and accept an optional
`expected_version` parameter on `save()`. When the backend detects a version
mismatch, it raises the canonical `session_write_conflict` category. The
spec defines the category and the optional `expected_version` parameter; the
backend ships the implementation.

The application decides what to do on conflict (retry, fail the invoke,
surface to user, etc.). The engine does NOT retry session saves automatically.

**8.3 Pessimistic locking.** A backend MAY layer additional methods
(`acquire_lock(session_id)`, `release_lock(session_id)`) on top of the base
protocol. Spec defines the protocol surface; lock semantics are backend-
defined.

### 9. Composition with other capabilities

**9.1 Subgraphs (proposal 0001, 0002).** Subgraphs do NOT see session state
directly. They see whatever the outer graph projects in via normal `inputs` /
`outputs` projection. Session state is an outermost-graph concern.

**9.2 Fan-out (proposal 0005).** Fan-out instances are subgraph invocations —
they do NOT see session state directly. Per-instance state comes from the
outer graph's projection.

**9.3 Parallel branches (proposal 0011).** Same as fan-out: branches are
subgraph invocations; session state is invisible to them except through the
outer graph's projection.

**9.4 Checkpointing (proposal 0008).** Checkpointing and sessions are
orthogonal persistence layers:

- Checkpointing: per-invocation, durable mid-invoke state, lifetime ends with
  the invocation (modulo backend retention policy).
- Sessions: per-session, durable cross-invoke state, lifetime managed by the
  application.

The two MAY share a backend store but the spec keeps the semantics separate.
An invocation MAY use both, neither, or either independently.

**9.5 Graph suspension (proposal 0021, planned).** When a graph suspends
mid-invoke (per the suspension proposal), session state SHOULD save at
suspend-time alongside the paused-invocation record, so a fresh worker
resuming the suspended invocation sees consistent session state. The
suspension proposal specifies the integration; this proposal anticipates it.

### 10. Errors

Four canonical error categories:

- **`session_load_failed`** — `SessionStore.load()` raised an unrecoverable
  error. The invoke MUST NOT proceed.
- **`session_save_failed`** — `SessionStore.save()` raised at invoke exit (or
  mid-invoke). The invoke's state was already committed at the time of save;
  callers see this as a post-completion error and decide how to handle it.
- **`session_state_migration_missing`** — `SessionStore.load()` returned a
  record with a `schema_version` for which no migration chain to the current
  schema is registered. Non-transient.
- **`session_state_migration_chain_ambiguous`** — the registered migration
  set contains a duplicate `(from_version, to_version)` pair or multiple
  distinct shortest paths between source and target. Mirror of the
  checkpoint category from proposal 0018; same resolution semantics.
- **`session_write_conflict`** — optimistic-concurrency conflict surfaced
  by a backend that supports it. See §8.2.

### 11. Cross-spec touchpoints

#### 11.1 graph-engine §6 (NodeEvent)

`NodeEvent` gains an optional `session_id` field, populated when the
invocation is bound to a session. Observers reading the event see it
alongside `invocation_id` / `correlation_id`.

#### 11.2 observability §5.1 (invocation span attributes) and §5.6 (cross-cutting)

The invocation root span gains an `openarmature.session_id` attribute when
the invocation is bound to a session. Every span under that invocation
inherits the attribute (per §5.6 cross-cutting rules). Structured logs emitted
during the invocation include `session_id` as a field on every record.

#### 11.3 pipeline-utilities §10 (checkpointing)

Add a paragraph at the end of §10 noting that sessions (this proposal) are a
sibling persistence layer with cross-invoke scope; an invocation MAY use both
independently.

### 12. Determinism

Sessions are a side-effect layer; they do not affect deterministic execution
within a single invocation. An invocation's node ordering, observer event
ordering, and final state (modulo loaded session content) are determined by
the graph topology and reducers, not by the session backend.

The session record's `updated_at` timestamp is a backend concern; it does not
contribute to invocation determinism.

### 13. Out of scope

- **TTL / expiry / GC.** Backend concern; spec stays silent.
- **Distributed locking.** Backend extension; spec defines the protocol
  surface, not the lock implementation.
- **Multi-session merging / handoff.** Application-level orchestration.
- **Conversation history.** Sessions store the state ALONGSIDE conversation
  history (or any other application data). The history's shape is not
  normative.
- **Cross-session memory / knowledge stores.** Per-user profiles spanning
  many sessions, semantic / episodic / procedural memory, vector-indexed
  knowledge bases, and any "agent remembers things across users and
  conversations" layer. A future proposal (working title: **agent memory**)
  will spec this as a sibling capability. Sessions cover per-identity-scoped
  typed state only — "this conversation accumulates" lives in sessions,
  "I remember things about this user across all their conversations" does
  not. The distinction maps onto LangGraph's checkpointer (≈ sessions) vs
  store (≈ agent memory) split. Sessions land first as the foundational
  persistence primitive; memory composes on top, with different access
  patterns (queried mid-node, not loaded at invoke entry) and different
  identity scoping (namespace hierarchies, not a single session_id).
- **Session-level observers.** Observers today are graph-level (per compiled
  graph) or invocation-level (per `invoke()` call). Cross-invocation
  observers spanning a session are out of scope; an application that needs
  them can correlate via `session_id` across invocation spans.
- **Migration chain compile-time validation.** Proposal 0018 left this as
  SHOULD for checkpoints; same disposition here. Implementations SHOULD
  detect ambiguity at compile time when feasible; load-time detection is the
  spec-mandated minimum.

## Conformance test impact

New fixtures under `spec/sessions/conformance/`:

- **`001-session-basic-resume`** — first invoke saves session; second invoke
  with the same `session_id` loads the saved state.
- **`002-session-no-store-registered`** — `session_id` supplied but no store
  registered; invoke proceeds with the supplied initial state; nothing is
  saved.
- **`003-session-store-registered-no-id`** — store registered but
  `session_id` omitted; invoke proceeds without loading or saving.
- **`004-session-projected-state`** — `SessionState` type narrower than
  invoke `State`; scratch fields are NOT persisted; cross-invoke fields are.
- **`005-session-auto-save-off`** — `auto_save=False`; engine does NOT save
  at invoke exit even after END.
- **`006-session-mid-invoke-save`** — explicit `save_session()` call mid-
  invoke commits partial state; subsequent invokes see the partial state if
  the original invoke crashes before END.
- **`007-session-migration-basic`** — v1 record resumes under v2 graph with
  registered migration.
- **`008-session-migration-missing`** — v1 record resumes under v2 graph
  with NO registered migration; raises
  `session_state_migration_missing`.
- **`009-session-migration-chain-ambiguous`** — duplicate `(from, to)` pair
  raises `session_state_migration_chain_ambiguous` at registration.
- **`010-session-composition-subgraph`** — subgraph does NOT see session
  state directly; outer graph projects in / out.
- **`011-session-composition-fan-out`** — fan-out instances do NOT see
  session state directly.
- **`012-session-observability`** — `session_id` propagates to NodeEvent +
  span attribute + log record fields.

In-memory and SQLite reference stores ship as part of the
`openarmature-python` implementation, not as spec fixtures. The spec defines
the protocol; implementations provide the backends.

## Alternatives considered

**Keep sessions as a userland pattern.** The "Session-as-checkpoint-resume"
pattern in the patterns docs scoping thread describes how to build sessions
today by composing `correlation_id` + `resume_invocation` + an application-
managed `session_id → invocation_id` map.

Rejected: the pattern works mechanically but each project rebuilds:
- The store layer (every app picks Redis, SQLite, Postgres, …)
- The state-projection convention (every app decides what survives a turn)
- The migration story (every app reinvents schema versioning)
- The observability tagging (every app decides whether `session_id` flows to
  observers)

Cross-impl consistency requires spec-level definition. Python and TypeScript
sessions should give the user the same behavior; userland patterns can't
enforce that.

**Fold into pipeline-utilities §12 alongside checkpointing (§10) and parallel
branches (§11).** Reuses the existing capability bucket.

Rejected: pipeline-utilities is otherwise per-invocation (subgraphs,
middleware, fan-out, branches). Sessions are fundamentally cross-invocation —
a different scope. A separate capability dir surfaces the scope distinction
to readers immediately, instead of burying it as a subsection.

**Single `State` type only, no projection.** Sessions just save and restore
the whole `State` at invoke boundaries.

Rejected: invites accidentally persisting scratch fields. The default of
"every field is session-durable" is the wrong default for non-trivial state
shapes (LLM call buffers, retry counters, observer accumulators, etc., all
end up in the session record). The explicit projection makes the durable
slice obvious.

**Engine-generated `session_id`.** Like `invocation_id`, the engine could
auto-generate a `session_id` when none is supplied.

Rejected: the whole point of a session is that the caller knows its identity
across invokes — a user's chat session, a tenant's workspace, etc. Engine-
generation would force every caller to capture the id and re-supply it, with
no benefit. Better to require explicit caller-supplied IDs.

**Built-in TTL / expiry on the protocol.** Spec a `ttl_seconds` parameter on
`save()` so the backend handles expiry uniformly.

Rejected: backends have wildly different expiry mechanisms (Redis SETEX,
DynamoDB TTL attribute, SQLite explicit purge job, …). Forcing one shape
on the protocol either over-specifies (only some backends can honor it) or
under-specifies (TTL semantics differ by backend). Better to leave expiry
out and let each backend expose its own knob.

## Open questions

- **Migration in core proposal vs spin-off.** The python scoping doc raised
  the option of a separate "Session migration" proposal mirroring 0014 →
  0018's split. This draft includes migration in the core because it's
  load-bearing for any non-trivial sessions deployment (sessions outlive
  deploys; migration is the first thing users hit). If reviewers want a
  split, the migration section (§7) lifts out cleanly into a follow-on
  proposal that adds the `session_state_migration_*` categories.
- **Reducer semantics for §4.1 full-state load.** When the engine loads a
  session record under a full-state configuration, does the loaded state
  REPLACE the supplied initial state, or does it MERGE per the state's
  declared reducers? Replacement is simpler. Merging is more flexible (a
  caller could pre-populate certain fields). Recommendation: REPLACE; caller
  who needs merge logic can do it explicitly. But worth confirming.
- **`session_state_migration_chain_ambiguous` vs sharing the checkpoint
  category.** Proposal 0018 named `checkpoint_state_migration_chain_ambiguous`
  for the checkpoint case. This proposal names a parallel
  `session_state_migration_chain_ambiguous` category for sessions. An
  alternative is to share a single `state_migration_chain_ambiguous`
  category. Recommendation: separate categories; the two lifecycle scopes
  benefit from distinct error surfaces for observability and operator
  tooling.
- **Whether `with_session_store()` registers the store on the builder vs
  the engine globally.** Per-graph registration is consistent with how
  `with_checkpointer` works (proposal 0008). Confirming the same shape here.
- **`SessionRecord` field set.** Minimum spec'd fields: `session_id`,
  serialized state, `schema_version`. Common backend extensions:
  `created_at`, `updated_at`, version counter. Should the spec name the
  extensions as RECOMMENDED, or leave them entirely backend-defined? Mild
  recommendation toward naming the extensions in spec (helps cross-backend
  consistency for observability dashboards).
