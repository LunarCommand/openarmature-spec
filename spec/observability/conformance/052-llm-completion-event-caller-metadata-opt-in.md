# 052 — `LlmCompletionEvent.caller_invocation_metadata` opt-in

Verifies the OPTIONAL `caller_invocation_metadata` field on `LlmCompletionEvent` (per
graph-engine §6 field table). Default behavior: field is null / absent. When the observer is
configured to include the metadata (per-language opt-in mechanism), the field is populated with
a snapshot of the caller-supplied invocation metadata at the time of the LLM call.

**Spec sections exercised:**

- graph-engine §6 — `caller_invocation_metadata` field definition (OPTIONAL; opt-in).
- observability §3.4 — Caller-supplied invocation metadata + `get_invocation_metadata()` read
  primitive (the snapshot's source).

**Cases:**

1. `caller_invocation_metadata_absent_when_opt_in_disabled` — A graph with one LLM-calling
   node; `invoke()` supplies `{"user_id": "u123"}`. A custom observer collects events with
   `include_caller_metadata: false` (default). Asserts the captured `LlmCompletionEvent` has
   `caller_invocation_metadata = null`.

2. `caller_invocation_metadata_populated_when_opt_in_enabled` — Same graph + caller metadata.
   The observer is configured with `include_caller_metadata: true`. Asserts the captured
   `LlmCompletionEvent` has `caller_invocation_metadata = {"user_id": "u123"}` — a snapshot
   of the in-scope metadata at the time of the LLM call.

**Harness extensions:** the harness MUST support a per-observer `include_caller_metadata` flag
controlling the field's population, plus observer-internal storage of captured events and
observer-introspection expectations matching the captured event's `caller_invocation_metadata`
field (observers MUST NOT mutate state per graph-engine §6).

**What passes:**

- Case 1: `caller_invocation_metadata` is `null` (default, opt-in disabled).
- Case 2: `caller_invocation_metadata` carries the snapshot `{"user_id": "u123"}`.
- The snapshot is an immutable view (mutation by the consumer MAY raise per the language's
  immutability conventions; the spec contract is "do not assume mutation succeeds").

**What fails:**

- Case 1: the field is populated despite opt-in being disabled — the default-off rule is
  load-bearing for keeping event size small.
- Case 2: the field is absent despite opt-in being enabled — the per-language opt-in
  mechanism did not take effect.
- Case 2: the snapshot returns a mutable mapping — the immutability contract from
  `get_invocation_metadata()` applies to the snapshot.
