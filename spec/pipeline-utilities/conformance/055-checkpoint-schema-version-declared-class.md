# 055 — Canonical `schema_version` source: declared class wins

Verifies §10.2's canonical-source rule (per proposal 0028): when a user
passes a subclass instance whose `schema_version` shadows the declared
graph state class's `schema_version`, all saved records during the
invocation MUST carry the DECLARED class's value, not the runtime
instance's value.

**Spec sections exercised:**

- §10.2 `schema_version` paragraph — the canonical source is the
  outermost declared graph state class, not the runtime instance's
  class.
- §10.3 save granularity — exercises outer dispatch saves, fan-out
  instance internal saves, and the fan-out node's own completion
  save in a single invocation, so the canonical-source rule is
  verified across all save sites.
- §10.12 migration lookup consistency — the declared-class rule
  preserves the invariant that resume-time migration lookups can
  always find a chain when one exists (subclass shadowing would
  otherwise write versions the registry doesn't know about).

**Harness primitives required:**

- `runtime_state_subclass: {schema_version: "<v>"}` (new in 0028) —
  declares that the invocation passes an instance of a subclass of
  the declared state class, where the subclass overrides
  `schema_version`. Implementations construct a subclass at
  fixture-run time and instantiate it against `invoke()`. Per-language
  mapping is idiomatic: Python `type("Subclass", (DeclaredClass,),
  {"schema_version": "<v>"})`; TypeScript structural subtyping with
  override; etc.
- `every_save_assertions.schema_version: "<v>"` (new in 0028) —
  asserts that every captured save during the invocation has the
  given `schema_version`, not just the latest. Stronger than
  `saved_record_assertions.schema_version` because it catches
  implementations that drift on intermediate save sites.

**What passes:**

- Every save during the invocation has `schema_version: "v1"`,
  including the outer dispatch saves (when the `process` node
  completes), the fan-out instance internal saves (one per instance
  per inner-node completion), the fan-out node's own completion save,
  and any in-flight save snapshots fired during execution. The
  declared class's value flows uniformly through the engine.

**What fails:**

- Any save reports `schema_version: "v2"` — would mean the
  implementation read the runtime instance's class somewhere in the
  engine, contradicting §10.2's canonical-source rule.
- The latest save reports `"v1"` but intermediate saves report `"v2"`
  — would catch the implementation pattern (pre-0028) where the outer
  dispatch save reads the declared class but the fan-out instance
  save helpers read the instance class. Either internal pattern is
  a §10.2 violation; both must read declared.

**Notes:**

- The fixture uses success-only execution to keep the assertions
  focused on `schema_version`. The §10.11 fan-out resume contract
  (per-instance progress, retry composition, etc.) is exercised
  elsewhere (fixtures 048–054); this fixture's scope is the
  canonical-source rule only.
- The subclass with shadowed `schema_version` is a per-language
  ergonomic. Python implementations construct a subclass via
  `type(...)` calls or the equivalent; TypeScript implementations use
  the language's structural-subtyping facilities. The fixture YAML
  declares the override abstractly under `runtime_state_subclass`;
  per-language harness adapters map to the language idiom.
- No `saved_record_assertions.schema_version` is needed alongside
  `every_save_assertions.schema_version` because the latter subsumes
  the former (the latest save is included in "every save").
