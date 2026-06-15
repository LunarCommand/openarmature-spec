# 065 — Fan-out failure-isolation degrade contribution

Verifies proposal 0066's §9.3 / §9.8 rules for what a `FailureIsolation`-degraded fan-out
instance contributes to its homogeneous collection. A degraded instance is a §9.3 *success* whose
contribution **is** its `degraded_update` (model ii): `collect_field` and each `extra_outputs`
`subgraph_field` are read **from the `degraded_update`** by subgraph field name — not merged onto
the instance's pre-failure subgraph state.

**Spec sections exercised:**

- §9.3 — *Degraded instances* (the contribution is the `degraded_update`; subgraph-field keying;
  null slot on omitted `collect_field`; `extra_outputs` skip on omission).
- §9.8 — *Fan-out degrade slot coverage* (static `degraded_update` must cover `collect_field`;
  callable form graceful at runtime).
- §11.7 — *Branch-middleware degrade* (the heterogeneous skip counterpart).

**Cases:**

1. `instance_degrade_fills_slot_and_extra_output` — a single-instance fan-out with
   `instance_middleware: [failure_isolation]` whose static `degraded_update` supplies both
   `collect_field` (`out`) and an `extra_outputs` `subgraph_field` (`note`). Asserts the collection
   slot holds the degrade `out` value AND the `note` value reaches the parent `notes` field — both
   read from the `degraded_update` by subgraph field name (the keying that distinguishes model ii;
   reading `extra_outputs` by the *parent* key would drop the contribution).
2. `static_degraded_update_missing_collect_field_compile_error` — a fan-out whose static
   `degraded_update` omits `collect_field`. Asserts graph compilation fails with
   `fan_out_degraded_update_missing_collect_field` (no execution).
3. `callable_degrade_omits_collect_field_null_slot` — a callable `degraded_update` that sets only a
   non-`collect_field` field. Asserts the `results` slot is **null** (the positional slot is
   preserved — the instance is not dropped), the rest of the contribution lands, and the graph does
   **not** stop (the degrade path never raises). Callable omission is not compile-checkable.
4. `branch_degrade_skips_uncovered_projected_field` — a parallel-branches branch whose branch
   middleware `degraded_update` does not cover a projected `outputs` field. Asserts the parent
   keeps its prior value (skip), with no compile error and no raise — the heterogeneous counterpart
   to the fan-out slot-coverage rule.

**What passes:**

- The degrade contribution comes from the `degraded_update`, keyed by subgraph field name.
- A static `degraded_update` missing `collect_field` is rejected at compile time.
- A callable omitting `collect_field` produces a null slot, gracefully (no stop), with the slot
  count preserved.
- A branch degrade that omits a projected field skips it (parent retains its prior value).

**What fails:**

- `collect_field` / `extra_outputs` read from the parent key, or from a merge onto pre-failure
  state, rather than from the `degraded_update` by subgraph field name (model i).
- A static `collect_field`-omitting `degraded_update` compiling instead of erroring.
- A degraded instance dropping out of the collection (N → N-1), or the degrade path raising under
  `fail_fast` and stopping the graph.

**Out of strict scope:** the exact null representation in `results` is the proposal's stated
behavior (model ii's null slot for an omitted `collect_field`); the collection field is typed to
admit it. `extra_outputs` compile-coverage is not checked (only `collect_field` is the homogeneous
slot, §9.8).
