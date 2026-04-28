# 011 — Subgraph Explicit Input/Output Mapping

Verifies that a subgraph-as-node MAY declare `inputs` and/or `outputs` mappings that override the §2
defaults. The same compiled subgraph (`doubler`) is composed at three sites in the parent graph, each with
a different mapping configuration, and the parent's final state shows that each site behaved per the
spec's mapping rules.

**Spec sections exercised:**

- §2 Subgraph — *Explicit input/output mapping.* `inputs` is additive over the default no-projection-in;
  `outputs` replaces (does not extend) field-name matching for projection-out; the two directions are
  independent.
- §2 Subgraph — default no-projection-in (verified at the `sub_outputs_only` site, where absent `inputs`
  leaves subgraph.input at its schema default of 3 rather than copying any parent field).
- §2 Subgraph — default field-name matching for projection-out (verified at the `sub_inputs_only` site,
  where absent `outputs` causes subgraph.result and subgraph.note to merge into parent.result and
  parent.note via name matching).

**What passes:**

- `a_seen_input == 5`. The `inputs: {input: a}` mapping at `sub_full` copied parent.a (5) into
  subgraph.input. The subgraph's schema default for `input` is 3; if this assertion sees 3, the inputs
  mapping was ignored.
- `b_seen_input == 3`. At `sub_outputs_only`, no `inputs` was declared, so the subgraph ran from its own
  schema default (`input: 3`). If this is 7, the implementation incorrectly used field-name matching to
  copy parent.b in.
- `a_result == 99` and `b_result == 99`. Both sites' `outputs` mappings projected subgraph.result onto
  the named parent fields.
- `result == 99`. At `sub_inputs_only` (no `outputs` declared), default field-name matching projected
  subgraph.result onto parent.result. The other two sites' `outputs` mappings did NOT include parent.result,
  so they did not write it.
- `note == "computed"`. At `sub_inputs_only`, default field-name matching projected subgraph.note onto
  parent.note. At `sub_full` and `sub_outputs_only`, `outputs` did not include note, and outputs replaces
  field-name matching, so neither site wrote parent.note.
- Outer execution order is `[outer_a, sub_full, sub_inputs_only, sub_outputs_only, outer_z]` — each
  subgraph instance appears as a single step.

**What fails:**

- `a_seen_input == 3` — the `inputs` mapping was not applied; subgraph ran from schema defaults.
- `b_seen_input == 7` — absent `inputs` fell through to field-name matching (the spec forbids this).
- `result == -1` — `sub_inputs_only`'s default field-name matching for outputs did not run.
- `note == "outer-default"` — `sub_inputs_only`'s default field-name matching for outputs did not run.
- `a_result == -1` or `b_result == -1` — explicit `outputs` mapping did not project.
- Subgraph nodes (`compute`) appearing in `execution_order` — subgraphs compose as a single step.

**Mapping-rule summary (informative):**

| Site               | `inputs`        | `outputs`                               | Projection-in behavior       | Projection-out behavior |
|--------------------|-----------------|------------------------------------------|------------------------------|-------------------------|
| `sub_full`         | `{input: a}`    | `{a_seen_input: input, a_result: result}` | parent.a → subgraph.input    | only mapped fields project; `note` discarded |
| `sub_inputs_only`  | `{input: b}`    | (absent)                                 | parent.b → subgraph.input    | default field-name matching: `result`, `note` |
| `sub_outputs_only` | (absent)        | `{b_seen_input: input, b_result: result}` | subgraph schema defaults     | only mapped fields project; `note` discarded |
