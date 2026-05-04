# 031 — Correlation ID Preserved Across Resume

Verifies §10.4 step 3 (resume preserves the original `correlation_id`) and step 4
(resume mints a new `invocation_id`). The correlation_id is the cross-backend pivot key
per observability §3 — a user reading logs in HyperDX or traces in Langfuse must be able to
find both the original failed attempt and the successful resumed attempt by the same
correlation_id. The invocation_id is the within-backend per-attempt identifier and is
distinct across attempts.

**Spec sections exercised:**

- §10.4 step 3 — resumed invocation keeps the original `correlation_id`.
- §10.4 step 4 — resumed invocation mints a new `invocation_id`; each attempt at
  completing the graph is its own invocation in the observability sense.
- Observability §3 — correlation_id is invocation-scoped and flows across detached/resumed
  contexts unchanged.
- Observability §3.2 — `correlation_id` and `invocation_id` are distinct fields and MUST
  NOT be conflated.

**Cases:**

1. `caller_supplied_correlation_id_flows_through_resume` — caller passes
   `correlation_id="my-business-request-42"`; node B fails on first run; resume; assert
   both runs' spans/logs carry the same correlation_id; assert the two runs have different
   invocation_ids.
2. `auto_generated_correlation_id_preserved_across_resume` — no caller value; framework
   auto-generates a UUIDv4 on first run; resume preserves that UUIDv4 (no new one
   generated).

**What passes:**

- Both runs' spans and log records carry the same `openarmature.correlation_id` value.
- The original and resumed runs have different `openarmature.invocation_id` values.
- The saved record's `correlation_id` matches the caller-supplied (case 1) or first-run
  auto-generated (case 2) value.
- Cross-backend pivot works: a user filtering by correlation_id finds both attempts.

**What fails:**

- Resume generates a new correlation_id (would break cross-attempt correlation; the user
  cannot find their failed-then-recovered request via the join key).
- Resume reuses the original invocation_id (would conflate attempts; the observability
  story for "this is the second attempt" is lost).
- Saved record stores correlation_id and invocation_id as the same value (would violate
  observability §3.2's distinctness requirement).
- Caller-supplied correlation_id is transformed (prefixed, hashed, suffixed-with-attempt-
  number) instead of used verbatim across both runs.
