# 037 — Langfuse `trace.input` / `trace.output` Sourcing

Verifies §8.4.1's *Trace input/output sourcing* paragraph (proposal 0043): the three-lever
decision tree for `trace.input` / `trace.output` emission plus resume semantics.

**Spec sections exercised:**

- **§8.2** — Trace entity carries `input` / `output` payload fields as headline columns.
- **§8.4.1** *Trace input/output sourcing* — the `disable_state_payload` privacy knob
  (default ON, mirroring §5.5.4's `disable_llm_payload`), the three-lever decision tree
  (caller hook → raw state when knob is OFF → minimal stub by default), the closed `status`
  enum on the minimal stub's `trace.output`, the caller-hook contract, and resume
  semantics.

**Cases:**

1. `default_privacy_no_hooks_stub_emitted` — lever 3 (default): privacy knob ON, no hooks;
   minimal stub appears on both Trace fields.
2. `disable_state_payload_off_raw_state_emitted` — lever 2: privacy knob OFF, no hooks;
   serialized `initial_state` / final state appear on the Trace fields.
3. `hooks_non_null_replace_decision_tree` — lever 1: both hooks return non-null; their
   return values appear verbatim, short-circuiting levers 2 and 3.
4. `hooks_null_fallthrough_to_stub` — lever 1 fallthrough: both hooks return null;
   fallthrough applies, lever 3 (stub) emits with the privacy knob at its default ON.
5. `resume_hooks_refire_to_resumed_trace` — resume semantics: two-invoke flow with a
   checkpoint; first invoke aborts mid-graph, second resumes; each invoke mints its own
   Langfuse trace (per §8.4.1) and the hooks fire independently on each; the resumed
   trace's fields reflect the resume's hook returns; the first trace's fields are
   unchanged.

**Harness extensions:**

- `langfuse_observer.disable_state_payload: bool` — Langfuse-observer-level privacy knob
  (default ON). Toggles between lever 2 (raw-state serialization) and lever 3 (minimal
  stub) when no hook overrides.
- `langfuse_observer.trace_input_from_state: <mock-name>` — harness mock identifier
  (per-language idiomatic; e.g., `returns_job_input_summary`, `returns_null`,
  `returns_state_snapshot`) referencing a callable the harness wires in.
- `langfuse_observer.trace_output_from_state: <mock-name>` — same shape as
  `trace_input_from_state`, but fired at invocation exit.
- `expected.langfuse_trace.input` / `expected.langfuse_trace.output` — assertion on the
  Trace's JSON-typed payload fields (§8.2).
- `first_run_expected.langfuse_trace` — resume-case-specific: assertions on the FIRST
  invoke's Langfuse trace before the resume runs (distinct from `resume.expected.langfuse_trace`,
  which asserts the resumed second invoke's trace).
- `resume.expected.first_trace_unchanged: bool` — resume-case-specific: harness asserts the
  first invoke's Langfuse trace `input` / `output` fields are unchanged after the resume
  completes. Confirms the resumed invocation writes to its own (new) trace, not back to the
  original.
- `invariants.hooks_refire_on_resumed_trace: bool` — resume-case-specific: harness asserts the
  `trace_input_from_state` / `trace_output_from_state` hooks fired on the resumed invocation
  (in addition to the first invocation), with the resumed values landing on the resumed trace.

**What passes:**

- Cases 1, 2, 3, 4 — the single-invoke Langfuse Trace emitted by each invocation carries
  the expected `input` / `output` per the decision-tree branch.
- Case 5 — two distinct Langfuse traces are emitted, one per invoke. Each carries the
  hook return value computed at that invoke's entry / exit; `correlation_id` is the same
  across both traces; `trace.id` differs; the first trace's fields are unchanged after
  the resume completes.

**What fails:**

- `trace.input` / `trace.output` remain blank despite a hook returning a non-null value
  (lever 1 not applied).
- Privacy knob OFF but serialized state does not appear on the Trace fields (lever 2 not
  applied).
- Default privacy with no hooks emits raw state instead of the minimal stub (lever 3 not
  applied).
- Hooks returning null fail to fall through (the Trace field carries `null` instead of
  the appropriate fallthrough value).
- Resume case mutates the first trace's `input` / `output` instead of writing to the
  resumed trace's own fields.
- The minimal stub's `status` is a value outside the closed `{completed, failed}` enum.
