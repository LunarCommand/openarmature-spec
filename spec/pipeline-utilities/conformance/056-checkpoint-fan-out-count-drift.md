# 056 — Count drift on fan-out resume raises `checkpoint_record_invalid`

Verifies the §10.11 count-drift rule (per proposal 0029): when a saved
`fan_out_progress` entry's `instance_count` differs from the resumed
run's resolved count for the same fan-out node, the engine MUST raise
`checkpoint_record_invalid` (per §10.10) before any fan-out instance
work runs on the resumed path. Silent pad/truncate of the saved
`instances` list is not permitted — per-instance accumulator
contributions written under one `instance_count` cannot be reconciled
with a different count without risking dropped or duplicated entries
at the fan-in step, breaking §10.11.1's exactly-once reducer
guarantee.

**Spec sections exercised:**

- §10.11 "Count drift on resume" paragraph (the new normative rule).
- §10.10 `checkpoint_record_invalid` description (the category surface
  the rule routes through).
- §10.5 idempotency framing (the rule's motivation — resume continues
  the prior run's work, doesn't extend or truncate it).
- §10.11.1 reducer exactly-once guarantee (the invariant the rule
  protects).

**Harness primitives required:**

- `resume_with_modified_items: {<field>: <new-value>}` (new in 0029) —
  re-resolves the named field on the resumed graph's initial state to
  the new value, simulating "user changed the input set between
  runs." Implementations construct the resumed graph with the new
  default for the named field (or otherwise inject the change into
  the resumed run's initial state) before calling `invoke`. The
  resumed run resolves `items_field` against the modified value,
  producing the drift the rule guards against. Per-language mapping
  is idiomatic.
- `expected_error.category: checkpoint_record_invalid` — existing
  primitive (used by fixtures 030, 041, 047, etc.). Asserts the
  resumed `invoke` call raises with the named category before
  completing.

**What passes:**

- First run's `node_exception` is captured via the
  `abort_after_instance: 2` simulated crash (existing harness
  primitive from fixture 052).
- Resume with a different `items_field` count raises
  `checkpoint_record_invalid` before any fan-out instance work runs.
- Both cases (shrunk count from 5 → 3, grown count from 5 → 7)
  raise the same category — the rule applies symmetrically per
  proposal 0029's alternatives analysis.

**What fails:**

- Resume succeeds (no error raised) — would mean the implementation
  silently reconciled the count drift, contradicting the §10.11
  normative rule.
- Resume raises a different error category (`node_exception`,
  `checkpoint_save_failed`, etc.) — would mean the implementation
  raised but routed through the wrong surface; the spec mandates
  `checkpoint_record_invalid` specifically.
- Resume raises `checkpoint_record_invalid` AFTER dispatching some
  fan-out instance work — would mean the check ran too late;
  proposal 0029 mandates the check happen BEFORE any instance work
  runs on the resumed path (partial state mutation under an invalid
  record is exactly what the early-raise prevents).

**Notes:**

- The shrunk case's first-run state (instances 0-2 `completed`,
  instances 3-4 `not_started`) is not strictly required for the
  fixture's category assertion to fire — the count check happens at
  resume entry, before the per-instance state is consulted. Driving
  through partial completion is structural realism: the saved record
  reflects a real mid-fan-out crash, not a synthetic shape.
- The grown case's symmetric structure verifies that the rule
  applies regardless of whether the resumed count is smaller or
  larger. Asymmetric handling (e.g., "only raise when shrunk; pad
  silently when grown") was considered and rejected in proposal
  0029's *Alternatives considered* for inconsistency reasons.
- The `expected_error` block in the `resume` section is parallel
  shape to the `first_run_expected_error` block at the case level —
  same category-and-optional-raised-from matcher. No new
  expected-error-on-resume primitive is needed; the harness
  recognizes the `expected_error` key inside the `resume` block.
