# 0014: Pipeline Utilities — State Migration Hooks for Checkpoints

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-13
- **Targets:** spec/pipeline-utilities/spec.md (adds §10.12 *State migrations*; modifies §10.2, §10.10)
- **Related:** 0008 (checkpointing contract reserving `schema_version`), 0001
- **Supersedes:**

## Summary

Activate the `schema_version` field that proposal 0008 reserved on `CheckpointRecord`, and add a
registration surface for **state migrations**: user-supplied transformations that run on
checkpoint load when a saved record's `schema_version` does not match the current state schema's
`schema_version`. A compiled graph MAY register an ordered set of migrations; the engine walks
them on load to project a stored record's state into the current shape. Two new canonical error
categories cover migration-related failures: `checkpoint_state_migration_missing` (no
chain of registered migrations connects the stored version to the current version) and
`checkpoint_state_migration_failed` (a registered migration function raised during chain
application).

## Motivation

Proposal 0008 left this hook deliberately empty. §10.2 reserved `schema_version` as a string
"implementation-defined; lets backends evolve the record shape without breaking older saved
records," and §10.10 introduced `checkpoint_record_invalid` for "state shape mismatch, missing
required fields, incompatible `schema_version`." But §10 did not specify how a user evolves the
state schema between runs without invalidating their existing checkpoints, and the current
contract gives them only two options: stay on the old schema forever, or discard checkpoints on
every schema change and re-run from scratch.

For long-running LLM pipelines this bites in two places:

- **Iteration cost.** A pipeline with expensive intermediates (frame extraction, ASR cleanup,
  visual narration, embedding computation) re-runs hours of work whenever the state schema
  evolves. Adding one optional field to a state class invalidates every prior checkpoint.
- **Production migration.** When a deployed pipeline ships a new state shape, in-flight
  invocations from the previous deploy cannot resume against the new code — they raise
  `checkpoint_record_invalid` per §10.10. The operator's only path is to drain the previous
  deploy, accept the loss, or maintain a sidecar process to manually convert records.

The state-snapshot pattern §10 codifies makes the migration story tractable: the record carries
the state as a serialized representation, plus a version identifier. A function `(serialized
state at version V) -> (serialized state at version V+1)` is enough to bridge a schema bump.
Migration chains generalize this across multiple bumps.

The contract is small (one new section §10.12, a clarified §10.2 field, one new error category)
and the user-facing surface is one registration call per migration. Pipelines that never evolve
their schema pay nothing.

## Detailed design

### Pipeline-utilities §10.2: `schema_version` becomes user-facing

Amend the §10.2 description of `schema_version` to make it a state-class-level identifier (set
by the user on their state definition), not an implementation-internal field. The current
text:

> `schema_version` — string. Implementation-defined; lets backends evolve the record shape
> without breaking older saved records.

Replace with:

> `schema_version` — string. Carries the version identifier of the user's state schema at the
> time the record was saved. The state definition MAY expose a stable, user-controlled
> `schema_version` identifier (the surface for declaring it is per-language ergonomic — e.g.,
> a class attribute in Python, a constant in TypeScript). When declared, the framework reads
> `schema_version` from the state definition at save time and writes it onto the record.
> State classes that do not declare a `schema_version` are treated as carrying an
> implementation-defined sentinel value (typically the empty string), and are not
> migration-eligible until they declare one. Users intending to evolve their schema across
> deploys MUST declare an explicit `schema_version` so that migrations (per §10.12) can be
> registered against it.

The framework does not constrain the version identifier's syntax. Users MAY use semver, integer
counters, date stamps, or content hashes — whatever makes sense for their evolution discipline.
Two distinct identifiers are treated as distinct versions; identical identifiers are treated
as the same version.

### Pipeline-utilities §10.12: State migrations (new subsection)

#### 10.12.1 Migration registration

A compiled graph MAY register zero or more **state migrations**. Each migration is described
by three pieces:

- `from_version` — the `schema_version` identifier the migration accepts as input.
- `to_version` — the `schema_version` identifier the migration produces as output.
- A **migration function** that, given a serialized state representation at `from_version`,
  returns a serialized state representation at `to_version`. The serialized form is whatever
  shape the active Checkpointer round-trips (per §10.1's "backends pick their own
  serialization"); the framework SHOULD pass the migration the most-deserialized form that is
  still independent of the current state class (e.g., a plain dict in Python, an
  `unknown`-shaped object in TypeScript) so the migration is not constrained by the user's
  current state-class definitions.

Migration support requires the active Checkpointer to be able to expose a structural
intermediate form of the loaded state (a plain dict, a JSON tree, or similar) that is
independent of the current state class definition. Backends using JSON, msgpack, or
similar schema-independent encodings naturally satisfy this; the SQLiteCheckpointer
reference implementation (per §10.11) does so by default. Backends using class-bound
serialization (Python pickle of state class instances) or live in-memory references to
typed state objects (the InMemoryCheckpointer reference implementation) cannot expose a
class-independent intermediate. When such a backend encounters a version mismatch on load
AND one or more migrations are registered, it MUST raise `checkpoint_record_invalid` per
§10.10 with the version mismatch in the error description; the migration registry has no
opportunity to bridge versions in that case. Implementations MUST document whether their
Checkpointer backend supports state migration.

The registration surface is per-language ergonomic. Python implementations are expected to
expose this on `GraphBuilder` (e.g., `with_state_migration(...)`); TypeScript implementations
may expose it on the builder or as a configuration object. The registration concept is what
this spec mandates: migrations are bound to the compiled graph and consulted during
checkpoint load.

A compiled graph's migration set is **ordered by `(from_version, to_version)` pair**. The
order of registration does not affect chain resolution; chains are resolved by version pair,
not by registration order. Two migrations with the same `from_version` and same `to_version`
MUST raise a configuration-time error (the chain is ambiguous). Two migrations with the
same `from_version` and different `to_version` define a branched migration graph; chain
resolution (§10.12.2) is responsible for picking a path.

#### 10.12.2 Chain resolution

When `Checkpointer.load(invocation_id)` returns a record whose `schema_version` does not match
the current state schema's `schema_version`, the engine MUST attempt to resolve a **migration
chain** from the record's version to the current version using the graph's registered
migrations.

Chain resolution proceeds:

1. Build a directed graph over registered migrations: each migration is an edge from its
   `from_version` to its `to_version`.
2. Find any path from the record's `schema_version` to the current state schema's
   `schema_version`. Implementations MAY use any reasonable search (BFS for shortest path is
   recommended).
3. If at least one path exists, apply the migrations along the path in order: each
   migration's output becomes the next migration's input. The final serialized state is
   passed to the current state class's deserialization step (per §10.1 round-trip integrity).
4. If no path exists, raise `checkpoint_state_migration_missing` (per §10.10 below).

If a migration function itself raises during step 3 (chain application), the engine MUST
wrap the raised exception as `checkpoint_state_migration_failed` (per §10.10) and propagate
it to the caller. The migration's exception is preserved as the cause per the language's
idiom (`__cause__` in Python). Subsequent migrations in the chain MUST NOT run; the engine
abandons the chain at the failing migration and the resume attempt fails as a whole.

Migrations MUST be pure functions of their input (no I/O, no implicit state, deterministic
output for a given input). The framework does not enforce purity — users who violate the
contract risk non-deterministic resume, but the spec mirrors 0008 §10.5's idempotency
stance: the contract is documented, not policed. The engine MAY consult the migration registry multiple times
during a single resume — for example, when subgraph parent states (§10.2 `parent_states`)
also need migration. Implementations MUST apply the same chain resolution to each
parent-state entry; in the absence of per-parent version metadata, parent states MUST be
treated as carrying the same `schema_version` as the outer record. (A future proposal may
add per-parent versioning if subgraph state schemas evolve independently of the outer
schema; for now the outer record's `schema_version` is authoritative.)

#### 10.12.3 No-op when versions match

When the loaded record's `schema_version` equals the current state schema's
`schema_version`, the engine MUST NOT consult the migration registry; the record is loaded
directly per §10.4. This is the common-case fast path and incurs no migration overhead.

#### 10.12.4 Composition with `checkpoint_record_invalid`

Proposal 0008's `checkpoint_record_invalid` (§10.10) covers structural incompatibility a
migration cannot fix — e.g., the serialized record itself is corrupt, or the post-migration
state fails the current state class's deserialization. After a migration chain runs, if the
final deserialized state still raises `checkpoint_record_invalid`, that error propagates
unchanged. Migrations are an opportunity to *avoid* `checkpoint_record_invalid` on
schema-version mismatches; they are not a recovery mechanism for arbitrary record
corruption.

If no migrations are registered for a graph and a loaded record's `schema_version` does not
match the current schema, the engine MUST raise `checkpoint_state_migration_missing` (the
new category below), NOT `checkpoint_record_invalid`. Distinguishing the two categories
matters: the former is actionable ("register a migration"); the latter is not ("the record
is broken").

### Pipeline-utilities §10.10: New error category

Add to §10.10:

> New canonical runtime category: `checkpoint_state_migration_missing` — raised on
> `invoke(resume_invocation=X)` when the loaded record's `schema_version` does not match the
> current state schema's `schema_version` AND no chain of registered migrations connects the
> two. Non-transient. The error MUST carry at least the record's `schema_version`, the
> current schema's `schema_version`, and a description of the registered migration set
> (in a form appropriate to the host language) so the user can see what migrations would
> need to be added.

> New canonical runtime category: `checkpoint_state_migration_failed` — raised when a
> user-supplied migration function raises during chain application (per §10.12.2).
> Non-transient (a buggy migration is deterministic; retrying without changing the
> migration code will not succeed). The error MUST carry the failing migration's
> `from_version` and `to_version`, and the underlying exception as cause (per the
> language's idiom).

Replace the existing §10.10 `checkpoint_record_invalid` description with:

> Canonical runtime category: `checkpoint_record_invalid` — raised when
> `Checkpointer.load(X)` returns a record whose schema is incompatible with the current
> graph (state shape mismatch, missing required fields, OR a post-migration state that
> fails to deserialize against the current state class per §10.12.4). Non-transient.

The "incompatible `schema_version`" reason from the original §10.10 text is removed;
raw `schema_version` mismatches now route through `checkpoint_state_migration_missing`
per §10.12 (or through `checkpoint_state_migration_failed` if a migration is registered
but raises).

The amended `checkpoint_record_invalid` category covers structural failures and
post-migration deserialization failures. The three categories are mutually exclusive on
any given resume: the engine evaluates version compatibility first (routing through
`checkpoint_state_migration_missing` if no chain exists), then applies the chain (routing
through `checkpoint_state_migration_failed` if a migration raises), then attempts
deserialization (routing through `checkpoint_record_invalid` if the post-migration state
cannot deserialize).

### Cross-spec touchpoints

This proposal does not modify graph-engine. The state-class declaration of
`schema_version` is a per-language ergonomic surface that does not require a graph-engine
spec change.

This proposal does not modify observability. Migration runs SHOULD be visible in the §6
observer stream so the OTel mapping (per observability §5) can surface them as spans
during resume, but the exact event shape is left to the implementation. A span like
`openarmature.checkpoint.migrate` with attributes for `from_version`, `to_version`, and
the chain length is the recommended shape. This is `SHOULD` rather than `MUST` because
migrations run at most once per resume and the observability overhead is negligible
either way; implementations choosing not to emit are accepting the loss of migration
visibility in their trace UI.

This proposal does not modify llm-provider.

## Conformance test impact

Add fixtures under `spec/pipeline-utilities/conformance/`. Each fixture is a pair
(`NNN-name.yaml` + `NNN-name.md`) per the conformance README:

- **`0NN-state-migration-additive-field.yaml`** — state class declares
  `schema_version = "v2"`. A saved record exists at `schema_version = "v1"` carrying a
  state that lacks an optional field added in v2. One migration registered: `v1 → v2`
  populates the new field with its default. Call `invoke(resume_invocation=...)`; assert
  the migration runs once, the resumed invocation sees the populated default, and
  execution proceeds normally.
- **`0NN+1-state-migration-chain.yaml`** — state class at `schema_version = "v3"`. A
  saved record exists at `v1`. Two migrations registered: `v1 → v2` and `v2 → v3`.
  Assert both run in order on resume and the resumed invocation sees the final v3 shape.
- **`0NN+2-state-migration-missing.yaml`** — state class at `v2`, saved record at `v1`,
  no migrations registered. Assert resume raises `checkpoint_state_migration_missing`
  (NOT `checkpoint_record_invalid`); assert the error carries `from_version=v1`,
  `to_version=v2`, and an empty migration-set description.
- **`0NN+3-state-migration-versions-match-no-op.yaml`** — record at `v2`, state class
  at `v2`. Assert resume does NOT consult the migration registry (no migration runs, no
  migration event fires) and the record loads via the §10.4 fast path.
- **`0NN+4-state-migration-parent-states-migrated.yaml`** — saved record was taken at a
  subgraph-internal save point; `parent_states` is populated with one outer-graph state
  at `v1`. State class at `v2` with one registered `v1 → v2` migration. Assert the
  migration runs once for the outer record's `state` AND once for each entry in
  `parent_states`, and the resumed subgraph re-enters correctly with the migrated
  parent state.
- **`0NN+5-state-migration-post-migration-deserialization-fails.yaml`** — record at
  `v1`, state class at `v2`, registered `v1 → v2` migration produces output that does
  not match the v2 state class's deserialization contract (e.g., a required field is
  missing). Assert resume raises `checkpoint_record_invalid` (per §10.10's existing
  contract), NOT `checkpoint_state_migration_missing`. Verifies the §10.12.4
  category-distinction rule.
- **`0NN+6-state-migration-no-path-in-registry.yaml`** — state class at `v2`, saved
  record at `v1`, migrations registered but none form a chain from `v1` to `v2` (e.g.,
  a `v3 → v4` migration is registered, unrelated to the v1→v2 path). Assert resume
  raises `checkpoint_state_migration_missing` (same category as the empty-registry
  case); assert the error carries `from_version=v1`, `to_version=v2`, and a
  migration-set description listing the registered (but unhelpful) migrations so the
  user can see what IS available. Complements `0NN+2` to verify the error category
  surfaces uniformly across both empty and no-path-found registry states.
- **`0NN+7-state-migration-function-raises.yaml`** — state class at `v2`, saved record
  at `v1`, registered `v1 → v2` migration function raises a `KeyError` mid-execution
  (simulating a buggy user-supplied migration). Assert resume raises
  `checkpoint_state_migration_failed`; assert the error exposes the underlying
  `KeyError` as cause, and carries `from_version=v1` and `to_version=v2`. Verifies
  the §10.12.2 contract that a raising migration aborts the chain and propagates as
  the dedicated category (NOT `checkpoint_record_invalid`).

(Fixture numbering deferred until proposals 0009 and 0011 are Accepted with finalized
fixture numbering; this proposal's accept PR will pick the next available slot.)

## Alternatives considered

### Force users to embed migration logic inside the state class's deserialization

Rejected. State classes are user-domain types; pushing migration logic into their
deserialization hooks (e.g., `__init_subclass__` magic, custom `model_validator` in
Pydantic) couples the state schema to its full version history and bloats every state
class with code that runs only during resume. A separate registration surface keeps
migrations localized to the graph build site, where they belong alongside the rest of
the graph's configuration.

### Auto-discover migrations by inspecting state-class fields

Rejected. "Auto-migration" (e.g., "v1 has fields A, B; v2 has fields A, B, C — auto-add
C with its default") works for additive changes but fails on field renames, shape
changes, and any semantic transformation. Spec mandating auto-discovery would
under-serve any non-trivial migration; spec NOT mandating it but allowing
implementations to ship one as a convenience layer over the registration surface is the
right level of constraint. The spec specifies the explicit registration; user libraries
or per-implementation conveniences can layer auto-discovery on top.

### Use semver for `schema_version` and resolve chains by version arithmetic

Rejected. Semver constrains the version identifier syntax; users with non-semver
versioning (date stamps, content hashes, integer counters) would have to translate.
Chain resolution via graph search over registered edges is identifier-agnostic and
imposes no syntactic constraint. Users who want semver discipline can adopt it without
the spec requiring it.

### Bind migrations to the Checkpointer protocol instead of the compiled graph

Rejected. Migrations are state-schema concerns (they transform user state, not backend
storage), and they vary across graphs even when the same Checkpointer is shared (two
graphs sharing a SQLite store may have different state schemas evolving on different
cadences). Binding to the compiled graph keeps the concern local to the graph build
site; the Checkpointer remains a pure storage layer.

### Persist a record-shape `schema_version` (backend-internal) separately from the
state-schema `schema_version` (user-facing)

Considered. Proposal 0008's original phrasing of `schema_version` ("lets backends evolve
the record shape without breaking older saved records") suggested a backend-internal
field. This proposal repurposes the field to the user-facing meaning instead of adding a
second field. Rationale: the backend-internal record-shape evolution is already
addressable inside the backend's own deserialization step (a SQLite backend can stamp
its rows with a backend version and migrate them on read without exposing this to the
framework); the user-facing state-schema evolution is the case that needs a
spec-mandated registration surface. Sharing one field for the user-facing meaning is
cleaner. If a backend later needs a distinct record-shape version, it can be added
without affecting the user-facing migration surface.

## Open questions

None at time of submission.
