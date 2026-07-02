# 040 — Subgraph Declared Same-Name Boundary

Verifies the **declared same-name projection boundary** — the checked middle between the implicit
field-name-matching default (fixture 006) and the explicit `inputs`/`outputs` rename maps (fixture 011). A
subgraph-as-node names the fields that cross the boundary as two field-name *sets* — an **in-set**
(`projects_in`) and an **out-set** (`projects_out`) — matching by the *same name* on both schemas. The form
is a complete boundary declaration: it has **no field-name-matching fallback**, so an empty set means
"nothing," symmetrically for both directions.

Both cases share the subgraph `inner`, which computes `doubled = seed * 2` (via `update_from_field`, per
fixture 017) so the projected-in `seed` is load-bearing.

**New harness directives (per §3.2):**

- **`projects_in: [<field>, ...]`** — the in-set. Each named subgraph field (same name on the parent
  schema) is copied from the parent field's current value at entry. Equivalent to an `inputs` entry whose
  subgraph and parent names coincide.
- **`projects_out: [<field>, ...]`** — the out-set. Each named subgraph field (same name on the parent
  schema) is merged into the same-named parent field via the parent's reducer at exit. Equivalent to an
  `outputs` entry whose parent and subgraph names coincide.

Both appear on a subgraph-as-node (`subgraph: <name>`) and are mutually exclusive with the explicit
`inputs`/`outputs` maps (fixture 041). These directives follow the fixture-header convention used for
`subgraph`/`inputs`/`outputs` (fixtures 006, 011), not conformance-adapter §5.4.

**Spec sections exercised:**

- §2 Subgraph — *Declared same-name projection boundary.* In-set copies same-named parent values in;
  out-set merges same-named subgraph values out via the parent's reducer.
- §2 Subgraph — the declared form is a complete declaration with no field-name-matching fallback; an empty
  out-set projects nothing (distinct from the default form's field-name matching).

**Cases:**

1. `declared_boundary_projects_named_fields` — `projects_in: [seed]`, `projects_out: [doubled]`.
2. `empty_out_set_projects_nothing` — `projects_in: [seed]`, `projects_out: []`.

**What passes:**

- Case 1 — `doubled == 10`: `projects_in: [seed]` copied parent.seed (5) into subgraph.seed, so
  `compute` produced `doubled = 5 * 2 = 10`, and `projects_out: [doubled]` merged it back via the parent's
  `last_write_wins`. If copy-in were skipped, subgraph.seed would be its schema default (0) and `doubled`
  would be 0.
- Case 1 — `scratch == "outer-scratch"`: `scratch` is in neither set, so the subgraph's `scratch`
  (`"sub-scratch"`) is discarded. The declared form has no name-match fallback, so the matching name does
  not project.
- Case 1 — `seed == 5`: `seed` is projected in but not in the out-set. The subgraph's `mark` node
  overwrites subgraph.seed to `777` (after `compute` read the projected-in `5`), yet `projects_out:
  [doubled]` does not carry `seed`, so the parent keeps `5`. If this were `777`, the out-set was not honored.
- Case 2 — `doubled == 42`: `projects_out: []` projects nothing out, so parent.doubled keeps the
  pre-subgraph value seeded by `outer_a` (42). The subgraph's computed `doubled` (10) does not reach the
  parent.
- Case 2 — `scratch == "outer-scratch"`: the empty out-set projects nothing, and there is no name-match
  fallback, so parent.scratch is untouched.
- Both cases — outer execution order is `[outer_a, outer_sub, outer_b]`: the subgraph is a single step.

**What fails:**

- Case 1 — `doubled == 0`: the in-set was ignored; subgraph ran from its own schema default for `seed`.
- Case 1 — `scratch == "sub-scratch"`: the implementation fell back to field-name matching for a field
  outside both sets (the declared form forbids this).
- Case 1 — `seed == 777`: the subgraph's post-`compute` write to `seed` was projected out even though
  `seed` is not in the out-set (the impl name-matched a field outside the out-set).
- Case 2 — `doubled == 10`: projection-out ran despite an empty out-set (no complete-declaration
  semantics).
- Case 2 — `scratch == "sub-scratch"` or `doubled` name-matched: the empty out-set fell back to field-name
  matching (the declared form has no fallback).
- Subgraph node names (`compute`, `mark`) appearing in `execution_order` — subgraphs compose as a single
  step.

**Contrast with fixture 006 (informative):**
Under the default form (no declaration, fixture 006), a subgraph field whose name matches a parent field
*is* projected out via field-name matching. Case 2 pins the opposite for the declared form: with
`projects_out: []`, the same matching names (`doubled`, `scratch`) do **not** project. A divergent
implementation that treats an empty out-set as "fall back to matching" fails case 2.
