# 041 — Declared-Boundary Compile Errors

Table fixture. Each case is an invalid subgraph-as-node projection whose compilation MUST fail with a
diagnostic error in the named category. Exercises the declared same-name projection boundary
(`projects_in` / `projects_out`, introduced in fixture 040).

**Spec sections exercised:**

- §2 Subgraph — "The same `mapping_references_undeclared_field` rule applies to the declared same-name
  sets: compilation MUST fail if an in-set or out-set names a field not declared on the relevant schema (a
  same-name field is checked on both the parent and the subgraph schema)."
- §2 Subgraph — "Declaring both the same-name sets and an explicit `inputs`/`outputs` mapping on one
  subgraph-as-node MUST fail compilation with category `conflicting_projection_forms`."
- §2 Compiled graph — the canonical compile-error category list (`mapping_references_undeclared_field`,
  `conflicting_projection_forms`).

**Cases:**

1. `declared_field_absent_on_schema` — `projects_out: [nonexistent]` names a field declared on neither the
   parent nor the subgraph schema. The declared form reuses proposal 0002's field-existence validation, so
   the name-drift the default form would silently swallow becomes a compile error.
2. `conflicting_projection_forms` — one node declares both the same-name sets (`projects_in` /
   `projects_out`) and an explicit `inputs` map. The declared sets and the explicit maps are mutually
   exclusive; a node uses at most one of the default (nothing declared), the sets, or the maps.

**What passes:**

- Case 1 raises at compile time with category `mapping_references_undeclared_field`.
- Case 2 raises at compile time with category `conflicting_projection_forms`.
- Each error surfaces before any node body runs.

**What fails:**

- Any case compiles successfully.
- The error raised exposes no category identifier, or one other than the mandated canonical string.
- Case 2 collapses into a generic error instead of the dedicated `conflicting_projection_forms` category.
