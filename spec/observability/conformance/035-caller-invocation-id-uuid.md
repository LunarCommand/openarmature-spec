# 035 — Caller-Supplied `invocation_id` (UUID)

Verifies §5.1 (caller-supplied `invocation_id`) and §8.4.1 (Langfuse `trace.id`) for the UUID
case: a caller-supplied UUID is used verbatim on the span attribute and maps to the Langfuse
`trace.id` as its dashes-stripped 32-hex form — the behavior that existed before non-UUID values
were allowed.

**Spec sections exercised:**

- §5.1 — `openarmature.invocation_id` is caller-supplied (used verbatim); a UUID value is valid.
- §8.4.1 — Langfuse `trace.id` for a UUID `invocation_id` = the 32-char lowercase hex form
  (dashes stripped).

**Cases:**

1. `caller_uuid_invocation_id_used_verbatim` — caller passes
   `invocation_id = "550e8400-e29b-41d4-a716-446655440000"`. The span attribute carries it
   verbatim; the Langfuse `trace.id` is `550e8400e29b41d4a716446655440000`.

**Harness extensions:**

- `caller_invocation_id: "<value>"` — supplies the `invocation_id` at the harness `invoke()`
  call (per §5.1). Analogous to `caller_metadata` / the correlation-id surface.
- `expected.invocation_id` — the value the harness asserts on `openarmature.invocation_id`.

**What passes:**

- `openarmature.invocation_id` equals the caller's UUID verbatim.
- The Langfuse `trace.id` is the UUID's dashes-stripped 32-hex form.

**What fails:**

- The framework mints its own UUID instead of using the caller's value.
- The Langfuse `trace.id` keeps the dashes (36-char) or otherwise isn't the 32-hex form.
