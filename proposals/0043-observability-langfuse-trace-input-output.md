# 0043: Observability — §8 Langfuse `trace.input` / `trace.output` Population

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-29
- **Accepted:**
- **Targets:** spec/observability/spec.md (§8.4.1 — adds `trace.input` and `trace.output` rows with a three-lever source decision tree plus a follow-on *Trace input/output sourcing* paragraph defining the caller-hook contract; §8.9 — adds the `disable_state_payload` privacy knob symmetric to `disable_llm_payload`)
- **Related:** 0031 (Langfuse backend mapping — introduced §8), 0034 (caller-supplied invocation metadata — established the orthogonal `trace.metadata` surface), 0024 (LLM span payload — established the symmetric `disable_llm_payload` privacy knob the new knob mirrors)
- **Supersedes:**

## Summary

The §8 Langfuse mapping populates per-Observation `input` / `output` on
Generation observations (gated by `disable_llm_payload`) but leaves the
Trace's own `input` / `output` fields unset. The Langfuse UI's Traces list
view surfaces both columns at the trace level, so every OA + Langfuse user
sees them blank at the canonical entry point of the dashboard.

This proposal extends §8.4.1 to populate `trace.input` / `trace.output` via
a three-lever design:

1. **`disable_state_payload`** — a privacy knob symmetric to
   `disable_llm_payload`. Default ON per §8.9's privacy-safe posture; when
   OFF, the observer serializes `initial_state` → `trace.input` and final
   state → `trace.output`, subject to the existing payload-byte-cap
   truncation.
2. **Default-off minimal stub** — when the privacy knob is ON (the default)
   and no caller hook is supplied, populate
   `trace.input = {entry_node, correlation_id}` and
   `trace.output = {final_node, status}`. Privacy-safe (neither stub field
   carries application payload data) and makes the Trace list view scannable.
3. **Caller hooks** — two optional callables
   (`trace_input_from_state`, `trace_output_from_state`) the implementation
   exposes on the observer construction surface. When supplied, their
   return values become `trace.input` / `trace.output`. Returning the
   language's null sentinel falls through to lever 2 / lever 1 per the
   privacy knob.

## Motivation

The data exists at the invocation boundary — `initial_state` is what
`invoke()` was called with; the final state is what the engine returns —
but the observer doesn't surface it to the Trace level. Operators scanning
the Langfuse Traces list view can't see what each trace was about without
clicking in, finding the entry node, and reading its rendered prompt — or
finding the final node and inferring the outcome.

The current workaround is to wrap `invoke()` and call the Langfuse SDK's
`update_trace(input=..., output=...)` directly. Workable but duplicates
wiring across every OA + Langfuse user, and requires reaching past the
observer abstraction to hold the Langfuse client + the `trace_id`
correlation directly — defeating the observer-decoupled-from-any-concrete-
SDK framing the §8 mapping is built on.

The three-lever shape mirrors what §8 already established for Generation
`input` / `output` (privacy knob + payload truncation) and composes
orthogonally with 0034 (which targets `trace.metadata`, not
`trace.input` / `trace.output`; metadata is fixed at invoke time, the
trace-level input/output hooks read live state at entry and exit).

## Detailed design

The proposed normative changes are below. Anticipated bump: **MINOR**
(pre-1.0). The concrete spec version is assigned at acceptance.

### observability §8.9 — `disable_state_payload` privacy knob

§8.9 currently defines `disable_llm_payload` (default ON) as the
implementation-level opt-out for LLM-span input/output payload emission.
This proposal adds a symmetric knob:

> **`disable_state_payload: bool`** — opt-out for Trace-level `input` /
> `output` payload emission. Default ON. When ON, the observer does NOT
> serialize `initial_state` / final state directly onto `trace.input` /
> `trace.output`; the default-off minimal stub (§8.4.1) applies unless a
> caller hook overrides. When OFF, the observer serializes `initial_state`
> → `trace.input` and final state → `trace.output`, subject to the
> existing payload-byte-cap truncation (§5.5.5).

The two payload-privacy knobs are independent: `disable_llm_payload`
controls Generation-level input/output; `disable_state_payload` controls
Trace-level input/output. Implementations MAY expose them as a single
combined flag for convenience, but the spec defines them as two separate
concerns so callers can opt into Trace-level payload without enabling
LLM-payload emission (or vice versa).

### observability §8.4.1 — `trace.input` and `trace.output` rows

Two new rows are added to the §8.4.1 Trace-level mapping table:

| OA source | Langfuse Trace field |
|---|---|
| `initial_state` at invocation entry — sourced via the three-lever decision tree below the table | `trace.input` |
| Final state at invocation exit — sourced via the three-lever decision tree below the table | `trace.output` |

A new paragraph follows the table:

**Trace input/output sourcing.** The Trace-level input/output sources
resolve via the decision tree below, applied independently to each of
`trace.input` and `trace.output`:

1. **Caller hook supplied AND returns a non-null value** → the hook's
   return value is serialized to the Trace field.
2. **`disable_state_payload` is OFF** → the raw state object
   (`initial_state` for input, final state for output) is serialized to
   the Trace field, subject to the existing payload-byte-cap truncation.
3. **Otherwise (default)** → the minimal stub is used:
   - `trace.input` = `{"entry_node": <entry node name>, "correlation_id": <correlation ID>}`.
   - `trace.output` = `{"final_node": <name of the node whose execution preceded the END-reached transition, or that raised>, "status": <status enum below>}`.

The minimal stub carries no application payload — `entry_node` is the
graph's declared entry node name (already emitted as
`trace.metadata.entry_node` per §8.4.1) and `correlation_id` is the
invocation's correlation ID (already emitted as
`trace.metadata.correlation_id` per §8.4.1 / §8.5); `final_node` is the
graph-level identifier of the last node executed, not the node's
payload. The stub is therefore privacy-safe by construction.

**`status` enum.** The stub `trace.output.status` MUST be one of:

- `"completed"` — invocation reached END normally.
- `"failed"` — invocation raised at any node, edge, reducer, or boundary
  validator before reaching END.

The enum is closed at this spec version. Future proposals may extend it
(e.g., suspension states once that capability lands) by adding values via
the same maintenance discipline §8.4's emitted-key set uses.

**Caller-hook contract.** Implementations MAY expose two optional hook
callables on the §8 LangfuseObserver construction surface (per-language
idiomatic naming and shape — keyword constructor arguments, configuration
record fields, builder methods, etc.; the spec defines the contract, not
the surface syntax):

- `trace_input_from_state(state) → InputValue | None` — called once per
  invocation, at invocation entry, after the engine has constructed
  `initial_state` and before any node runs. Takes the raw state object
  (the typed-state instance in language-idiomatic form). Returns the
  value to use as `trace.input`. Returning the language's null sentinel
  falls through to the next lever in the decision tree.
- `trace_output_from_state(state) → OutputValue | None` — called once
  per invocation, at invocation exit, after the engine has produced the
  final state (whether the invocation reached END or failed). Same
  signature shape; falls through to the next lever on null.

Hook return types: any JSON-serializable value (object, array, primitive,
or string). Implementations MUST apply the existing payload-byte-cap
truncation if a hook's return value exceeds the cap.

Hook signature takes the raw state, not a typed wrapper or `NodeEvent`
— minimum added surface area, consistent with the framework's
"transparency over abstraction" framing.

### Resume semantics

On a resumed invocation (`invoke(resume_invocation=...)` per
pipeline-utilities §10.4), the framework mints a fresh `invocation_id` and
therefore a fresh Langfuse trace per §8.4.1's `trace.id` derivation. The
hooks fire on the resumed invocation as if it were a new invocation,
writing to the resumed trace's `input` / `output`. They do NOT overwrite
the original (now-completed) trace's fields — Langfuse trace identity is
per-`invocation_id`, and the resumed trace is a separate Langfuse object.
The `correlation_id` is preserved across the original and resumed traces
(per §3.1), so the operator can correlate the resume to its original via
metadata filtering.

## Conformance test impact

### New fixture

A new fixture under `observability/conformance/` (number assigned at
acceptance) exercises the decision tree:

- **Case 1 — default privacy, no hooks.** `disable_state_payload=True`
  (default), no callables supplied; assert the minimal stub appears on
  `trace.input` and `trace.output` with the correct stub fields.
- **Case 2 — `disable_state_payload=False`, no hooks.** Assert serialized
  `initial_state` on `trace.input` and serialized final state on
  `trace.output`, both subject to truncation if they exceed the cap.
- **Case 3 — hooks provided, returning non-null domain summary.** Assert
  the hook return values appear on the Trace fields verbatim; the stub
  does not appear; `disable_state_payload` is irrelevant to the outcome.
- **Case 4 — hooks provided, returning null sentinel.** Assert
  fallthrough — lever 2 if `disable_state_payload=False`, lever 1 stub
  otherwise.
- **Case 5 — resume.** First invocation runs to completion with one hook
  return value; a second `invoke(resume_invocation=...)` mints a fresh
  trace and the hooks re-fire writing the resumed-invocation values to
  the new trace's fields. The original trace's fields are unchanged.

### Unaffected

Existing §8 Langfuse fixtures continue to assert their existing payloads;
this proposal adds new Trace-level field expectations rather than changing
existing ones.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments
(concrete version assigned at acceptance):

- §8.9 gains the `disable_state_payload` knob (additive opt-out, default
  ON — privacy-safe default).
- §8.4.1 gains two new mapping-table rows + the *Trace input/output
  sourcing* sub-paragraph defining the decision tree and hook contract.
- A new conformance fixture exercises the four-lever decision tree + the
  resume case.

A caller working around the missing `trace.input` / `trace.output` by
calling the Langfuse SDK's `update_trace(input=..., output=...)` directly
will see OA-observer-supplied values appearing on the Trace fields after
this lands. The OA observer's values follow Langfuse SDK update semantics
(last-writer-wins on the same field), so the caller's direct update may be
clobbered or not depending on call order. Migration path: replace direct
`update_trace` calls with the new caller hooks (lever 3). The
breaking-change surface is narrow — only callers actively bypassing the
observer for these specific fields are affected.

## Out of scope

- **OTel-mapping equivalent.** OpenTelemetry has no `Trace`-level
  input/output concept (a trace is a collection of Spans sharing a
  `trace_id`; no Trace-level payload field). This proposal is
  Langfuse-specific by data-model construction. If a future OTel-aware
  backend grows a Trace-level payload concept, a separate proposal can
  map onto it.
- **Other current observability backends** (Phoenix / Arize, Honeycomb,
  Datadog APM, HyperDX). The OTel-attribute backends inherit nothing
  here; their Span attributes carry per-node input/output already.
- **Selectively merging caller hook output with the stub.** The decision
  tree treats the hook return value as a full replacement; partial
  override (hook returns `{"job_id": "..."}` and the stub fills the rest
  in) is rejected — implementations would have to define merge rules per
  field and the contract gets fuzzy. Callers wanting hybrid shapes can
  construct the full payload in their hook.
- **Suspension / paused-invocation status.** The `status` enum is
  closed at `{completed, failed}` for this spec version. The
  suspension capability (a future proposal) will extend the enum via
  the same maintenance discipline §8.4 uses.

## Alternatives considered

- **Caller-supplied input/output at `invoke()` time** (`invoke(trace_input=..., trace_output=...)`
  kwargs, analogous to 0034's caller-supplied metadata). Rejected: works
  for `trace_input` (known at invoke time) but breaks for `trace_output`
  — the caller doesn't know the output value at invoke time. Splitting
  the surface (caller-supplied `trace_input` kwarg + observer-side hook
  for `trace_output`) leaves an asymmetric API the spec would call out
  as a wart; the symmetric observer-hook design avoids it.
- **Reuse the 0034 metadata channel for input/output.** Use
  `trace.metadata` to carry input/output as additional keys. Rejected:
  input/output and metadata are semantically distinct in Langfuse —
  separate UI columns, separate data-model fields, separate lifecycle
  (metadata is fixed at invoke time; input/output reflect live state).
  Conflating them would lose Langfuse UI affordances (the dashboard's
  list view surfaces input/output as headline columns) and stretch
  what 0034 was scoped for.
- **Application owns it via `update_trace`** (the status quo).
  Rejected: duplicates wiring across every OA + Langfuse user, requires
  reaching past the observer abstraction to hold the Langfuse client +
  the `trace_id` correlation directly, and defeats the
  observer-decoupled-from-concrete-SDK framing the §8 mapping is built
  on.
- **Default the privacy knob OFF** (raw `initial_state` / final state on
  the Trace fields by default). Rejected: inconsistent with §8.9's
  privacy-safe-by-default posture (`disable_llm_payload` defaults ON);
  raw state may contain user-PII fields and should require an explicit
  opt-in.
- **Single combined privacy knob** controlling both LLM and Trace-level
  payloads. Considered as a convenience exposure; the spec keeps them
  separate (implementations MAY combine in their public API) so callers
  can opt one in without the other — they're independent concerns with
  different threat models (LLM payload = model interaction transcript;
  Trace-level state payload = application state shape).
- **Do nothing.** Leave `trace.input` / `trace.output` always blank for
  OA-emitted Langfuse traces. Rejected: the Traces list view is the
  canonical entry point of the Langfuse UI; leaving its columns blank
  is a discoverability gap every OA + Langfuse user hits, and the
  application-level workarounds duplicate wiring without addressing the
  underlying observer-abstraction concern.
