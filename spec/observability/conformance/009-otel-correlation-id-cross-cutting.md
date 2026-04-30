# 009 — Correlation ID Cross-Cutting Across All Spans

Verifies §3 (architectural contract) and §5.6 (OTel realization). The correlation_id is the
join key for cross-backend pivots: a user with both OTel and Langfuse can search for the same
ID in either backend. The contract has three load-bearing parts — caller-supplied IDs are used
verbatim, auto-generated IDs are UUIDv4, and the context primitive resets between invocations.

**Spec sections exercised:**

- §3.1 Lifecycle and propagation — caller-supplied verbatim; auto-generate UUIDv4 when absent;
  reset context after invocation.
- §3.2 Distinction from `invocation_id` — both are present, but the spec treats them as
  separate fields (this fixture exercises only `correlation_id`; §5.1 covers `invocation_id`).
- §5.6 Cross-cutting attributes — `openarmature.correlation_id` MUST appear on every span.

**Cases:**

1. `caller_supplied_id_used_verbatim` — caller passes `"request-abc-123"`. Every span across
   the whole tree carries that exact string.
2. `auto_generated_uuidv4_when_absent` — no caller value. Framework generates a UUIDv4; every
   span carries that same UUIDv4.
3. `context_reset_between_invocations` — two back-to-back invocations of the same graph, no
   caller value on either. Each invocation's spans carry one uniform correlation_id; the two
   invocations' correlation_ids DIFFER (the context primitive reset between them).

**What passes:**

- Every span (invocation, node, subgraph, fan-out instance, retry attempt, LLM provider)
  carries `openarmature.correlation_id`.
- Caller-supplied value is used verbatim — no transformation, prefixing, or wrapping.
- Auto-generated value matches UUIDv4 canonical form.
- Each invocation has its own correlation_id; back-to-back invocations don't bleed.

**What fails:**

- Some spans missing the attribute (e.g., it appears on the invocation span but not on node
  spans) — cross-cutting contract is broken; the user can't filter for "all spans for this
  request" in the backend.
- Caller value transformed (prefixed, hashed, truncated).
- Auto-generated value is a counter, hash, or non-UUIDv4 — implementation drift breaks the
  "you don't supply one, you get a consistent UUIDv4" contract.
- Second invocation reuses the first invocation's correlation_id — context primitive leaked,
  making every subsequent invocation indistinguishable from the previous in the backend.
