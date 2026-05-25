# 0028: Pipeline Utilities — Canonical source for `schema_version` on saved records

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-25
- **Accepted:**
- **Targets:** spec/pipeline-utilities/spec.md (clarifies §10.2's `schema_version` paragraph to name the canonical source); spec/pipeline-utilities/conformance/055-checkpoint-schema-version-declared-class.yaml (new fixture exercising subclass-shadowing)
- **Related:** 0014 (state migration — the system that consumes `schema_version`), 0009 (per-instance fan-out resume — surfaced the inconsistency across save sites)
- **Supersedes:**

## Summary

Clarify §10.2's `schema_version` paragraph to name the outermost
declared graph state class as the canonical source for writing
`CheckpointRecord.schema_version`. Implementations MUST read
`schema_version` from the state class declared at graph construction
time (e.g., the class passed to a `GraphBuilder` constructor), not
from `type(state)` at save time. The distinction matters only when a
user passes a State subclass instance that shadows the declared
`schema_version`, but the clarification removes a latent
cross-implementation drift and aligns all save sites in any given
implementation.

## Motivation

§10.2's `schema_version` paragraph currently reads "the framework reads
`schema_version` from the state definition at save time and writes it
onto the record." The phrase "the state definition" is ambiguous when
the user can pass a State subclass instance whose `schema_version`
differs from the class declared at graph construction time:

```python
class MyState(State):
    schema_version: ClassVar[str] = "v1"

class MyStateSubclass(MyState):
    schema_version: ClassVar[str] = "v2"  # shadows the parent

graph = GraphBuilder(MyState).compile()  # declared with MyState ("v1")
await graph.invoke(MyStateSubclass())     # runtime instance is "v2"
```

Two readings of the current text are both spec-conformant:

- **Declared class wins.** `schema_version` on the saved record is the
  value declared on `MyState` (`"v1"`), regardless of which subclass
  instance the user passes. This is what `_maybe_save_checkpoint`
  effectively does today in the reference Python implementation
  (`self.state_cls.schema_version` — sourced from the compiled graph's
  declared class).
- **Instance class wins.** `schema_version` on the saved record is the
  value on `type(state)` (`"v2"` in the subclass case). This is what
  the fan-out save helpers (`_save_instance_completed`,
  `_save_instance_in_flight`) in the same reference implementation do
  today (after the proposal-0027 impl-review pass switched them to
  `type(parent_states_prefix[0]).schema_version`).

These two readings disagree only under subclass shadowing, but they
disagree silently — the same invocation can write inconsistent
`schema_version` values across its saves depending on which save site
fires (the outer save loop vs. the fan-out instance save helpers).

The §10.12 migration system is built around the declared graph state
class. Migrations are registered as `from_version` → `to_version`
pairs against the graph; on resume, the engine looks up a migration
chain from the saved record's `schema_version` to the current declared
class's `schema_version`. If saves used the instance class, a subclass
that shadows the declared version would write a `schema_version` the
migration registry doesn't know about, and resume would fail to find a
chain — `checkpoint_state_migration_missing` per §10.10. The declared
class is the only consistent choice for the migration system.

Locking in the declared-class rule normatively does two things:

- **Aligns save sites within an implementation.** Every save the
  engine writes carries the same `schema_version`, regardless of
  whether the save fires from the outer dispatch loop, a fan-out
  instance, or a subgraph internal node.
- **Eliminates cross-implementation drift.** A future TypeScript
  implementation reading the current spec text could land on either
  reading; the explicit rule forces alignment with the existing
  Python implementation's outer-save-loop behavior.

## Detailed design

### §10.2 `schema_version` paragraph: name the canonical source

Replace the sentence "When declared, the framework reads
`schema_version` from the state definition at save time and writes it
onto the record." with the following two sentences:

> When declared, the framework reads `schema_version` from the
> **outermost declared graph state class** (the state class passed to
> the graph constructor — e.g., `GraphBuilder(MyState)` in Python or
> the equivalent in another language idiom) at save time and writes
> that value onto the record. Implementations MUST NOT source
> `schema_version` from the runtime instance's class (e.g.,
> `type(state).schema_version` in Python) when the user passes a State
> subclass instance whose `schema_version` shadows the declared
> class's value — the declared class is the canonical source for all
> save sites in the engine (outermost-graph saves, subgraph-internal
> saves, fan-out instance internal saves, fan-out node completion
> saves), so resume sees a single consistent `schema_version` and the
> §10.12 migration registry's `from_version`/`to_version` lookups
> resolve unambiguously.

No other §10.2 text changes. The surrounding paragraphs (the
implementation-defined-sentinel rule for state classes that don't
declare `schema_version`, the no-syntax-constraint rule, the
distinct-vs-same-identifier rule) all remain.

### Implementation note: threading the declared class

The clarification names the outermost declared graph state class as
the canonical source but does not prescribe how implementations make
it available to all save sites. In a typical reference implementation
the outermost graph's compiled object holds a reference to the
declared state class; save sites bound to that compiled object (e.g.,
the outer dispatch loop) read it directly. Save sites that don't
have direct access to the compiled object (e.g., fan-out instance
save helpers in a separate module) need the class threaded through
the invocation context. Implementations are free to choose the
threading mechanism (context object field, closure capture, etc.);
the spec only mandates that all save sites read from the declared
outermost class.

### Cross-spec touchpoints

- **Pipeline-utilities §10.2** — primary change site (the
  `schema_version` paragraph clarification).
- **Pipeline-utilities §10.12.1 / §10.12.2** — no text changes. The
  migration system already implicitly assumed the declared class
  (migrations are registered against declared `from_version` /
  `to_version` pairs); this proposal makes that assumption explicit
  on the save side.
- **Graph-engine §1** — no changes (the "user's declared outermost
  state schema" framing already implies the declared class).
- **Observability** — no changes.
- **LLM-provider** — no changes.

### No behavioral change for the common case

Implementations whose save sites already use the declared graph state
class consistently see no behavior change. The clarification removes
an implicit choice that no implementation had a reason to make
heterogeneously; it just makes the no-heterogeneity rule explicit.
The fixture (below) exercises the only scenario where heterogeneous
choices produce observable behavior — a subclass instance with a
shadowed `schema_version`.

## Conformance test impact

### New fixture: 055-checkpoint-schema-version-declared-class

A focused fixture exercising the declared-vs-instance distinction:

- Define a graph state class with `schema_version: "v1"`.
- Define a subclass of that state class with `schema_version: "v2"`
  (shadows the parent's value).
- Build a graph declared against the parent class.
- Invoke the graph passing an instance of the subclass.
- Drive the invocation to a fan-out completion (so multiple save
  sites fire — the outer dispatch loop, the fan-out instance save
  helpers, and the fan-out node's own completion).
- Assert: every saved record's `schema_version` equals `"v1"` (the
  declared value), regardless of which save site fired it.

The fixture is small (single-case YAML, ~50 lines) and exercises both
the spec text clarification and the load-bearing implementation
threading (the declared class must be visible to all save sites).
Without this fixture, the new normative rule has no automated
conformance coverage.

### No other fixture changes

Existing fixtures (024–031, 048–054) do not declare State subclasses
that shadow `schema_version`, so their saved records already carry
the declared value uniformly. The new normative rule introduces no
new failure mode for them. Verified by spot-check: none of the
existing pipeline-utilities fixtures construct subclass-shadowed
state schemas.

## Alternatives considered

### Instance class wins

Rejected. Would force the §10.12 migration registry to look up
migrations against runtime-instance versions, which means a subclass
that shadows the declared version writes a `schema_version` the
registry doesn't know about. Resume would surface as
`checkpoint_state_migration_missing` for a subclass-using workflow,
even though no actual schema drift has occurred — a user accidentally
sub-classing their state would break their resume path with no
diagnostic clue what went wrong.

### Status quo (leave the spec text ambiguous)

Rejected. The reference Python implementation already has the
inconsistency surfaced (different save sites in the same engine make
different choices); a future TypeScript implementation reading the
current spec text could land on either reading. Cross-implementation
drift is the predictable outcome. The explicit normative rule is
cheap to specify and impossible to misimplement once specified.

### Make `schema_version` migration-system-aware at save time

Have the framework consult the migration registry at save time to
pick which `schema_version` to write. Rejected as over-engineered.
The migration registry's job is consuming `schema_version` on resume,
not producing it on save. The producer is the user's declared schema;
the canonical source rule is what aligns producer and consumer
without coupling them.

### Spec a runtime-instance-check that raises when the instance shadows

Detect subclass shadowing at save time and raise an error. Rejected.
Python's structural type system makes subclassing a common pattern
that users may not realize affects `schema_version` (e.g., adding a
helper method on a subclass). Raising at save time would be surprising
and would block legitimate subclassing. The declared-class rule lets
subclassing continue to work; only the `schema_version` value on
saved records is normatively fixed.

## Open questions

None. The declared-vs-instance choice is settled in favor of declared
above; the canonical-source rule applies to all save sites uniformly;
no per-language ergonomic question remains beyond the implementation's
choice of mechanism for threading the declared class to save sites.
