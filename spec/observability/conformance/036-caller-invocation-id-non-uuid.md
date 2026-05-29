# 036 — Caller-Supplied `invocation_id` (non-UUID)

Verifies §5.1 (a caller-supplied `invocation_id` MAY be any non-empty URL-safe string) and
§8.4.1's deterministic Langfuse `trace.id` derivation for the non-UUID case — including that the
derivation matches Langfuse's own `create_trace_id(seed)` and that the raw id is preserved in
`trace.metadata.invocation_id`.

**Spec sections exercised:**

- §5.1 — `openarmature.invocation_id` carries a caller-supplied non-UUID value verbatim.
- §8.4.1 — non-UUID `invocation_id` → `trace.id` = first 16 bytes of `SHA-256(invocation_id)`
  (UTF-8) as 32 lowercase hex; raw id ALSO written to `trace.metadata.invocation_id`. The
  derivation equals `create_trace_id(seed=invocation_id)`.

**Cases:**

1. `caller_non_uuid_invocation_id_derives_trace_id` — caller passes
   `invocation_id = "run_abc123"`. The span attribute carries it verbatim; the Langfuse
   `trace.id` is `29b50a6c08dabfeaeb1696301f4fabe1`
   (`sha256("run_abc123").digest()[:16].hex()`); `trace.metadata.invocation_id` is `"run_abc123"`.

**Harness extensions:**

- `caller_invocation_id: "<value>"` — supplies the `invocation_id` at `invoke()` (per §5.1),
  same primitive as fixture 035.

**What passes:**

- `openarmature.invocation_id` equals `"run_abc123"` verbatim.
- The Langfuse `trace.id` is the deterministic SHA-256-first-16-bytes hex (matching
  `create_trace_id`).
- `trace.metadata.invocation_id` carries the raw `"run_abc123"` for lookup.

**What fails:**

- The non-UUID value is passed through unchanged as `trace.id` (invalid Langfuse trace id) — the
  v0.10.0 behavior this fixture replaces.
- The derivation differs from `create_trace_id(seed)` (e.g., a different hash or byte count), so
  a consumer's `create_trace_id(raw_id)` lookup misses.
- The raw id is not written to `trace.metadata.invocation_id` (lookup by the original value
  broken).
