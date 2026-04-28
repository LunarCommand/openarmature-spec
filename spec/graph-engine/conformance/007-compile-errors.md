# 007 — Compile-Time Errors

Table fixture. Each case is an invalid graph definition whose compilation MUST fail with a diagnostic error
in the named category.

**Spec sections exercised:**
- §2 Compiled graph — "Compilation MUST fail with a diagnostic error if the graph has: no declared entry
  node, unreachable nodes, dangling edges (references to nonexistent nodes), a node with more than one
  outgoing edge, or a field with more than one declared reducer."
- §2 Subgraph — "Compilation MUST fail with category `mapping_references_undeclared_field` if an `inputs`
  mapping names a parent field that is not declared in the parent's state schema, or a subgraph field
  that is not declared in the subgraph's state schema. The same rule applies symmetrically to `outputs`."

**Cases:**

1. `no_declared_entry` — entry omitted; no implicit-first-node default.
2. `unreachable_node` — node `orphan` has no incoming edge from any path starting at the entry.
3. `dangling_edge_target` — edge references a node name that is not declared.
4. `multiple_outgoing_edges` — node `a` has two outgoing static edges (branching must be expressed via a
   conditional edge, not multiple static edges).
5. `conflicting_reducers` — a field declares two distinct reducers.
6. `mapping_references_undeclared_field` — a subgraph-as-node `inputs` mapping names a parent field that
   is not declared in the parent's state schema. The spec applies the same rule symmetrically to
   `outputs` and to subgraph-side names; this case covers the parent-side variant.

**What passes:**
- Each case raises at compile time with a categorized error matching the fixture's `expected_compile_error`.
  The category identifiers used here are the canonical set mandated by §2 Compiled graph.

**What fails:**
- Any case compiles successfully.
- The error raised exposes no category identifier, or exposes one other than the mandated canonical string.
- Multiple compile-error cases collapse to a single generic error class without distinguishing category.
