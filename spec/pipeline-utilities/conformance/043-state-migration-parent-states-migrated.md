# 043 — State Migration Parent States Migrated

Saved record at a subgraph-internal save point. `parent_states` carries
one outer-graph entry at `schema_version="v1"`. The registered `v1 -> v2`
migration MUST run for both the outer-record state AND each entry in
`parent_states` — per §10.12.2's parent-state migration rule.

**Spec sections exercised:**

- §10.12.2 — "the engine MAY consult the migration registry multiple
  times during a single resume — for example, when subgraph parent states
  (§10.2 `parent_states`) also need migration."
- §10.12.2 — "in the absence of per-parent version metadata, parent
  states MUST be treated as carrying the same `schema_version` as the
  outer record."

**What passes:**

- The migration is invoked exactly twice (once for the outer record's
  state, once for the single `parent_states` entry).
- The resumed subgraph re-enters correctly with the migrated parent state
  in scope.
- Final outer state has `new_field == "v2_default"` and `outer_x == 5`.

**What fails:**

- The migration is invoked only once (only the outer record's state was
  migrated; `parent_states` was loaded as-is and the subgraph re-entered
  with stale state).
- The migration is invoked more than twice (would mean the engine
  consulted the registry too many times).
