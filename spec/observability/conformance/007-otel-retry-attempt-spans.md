# 007 — Retry Attempt Spans (One Span Per Attempt)

Verifies §4.2 (retry attempts produce sibling node spans, not nested) and §5.2
(`openarmature.node.attempt_index` disambiguates them). Each attempt is its own
started/completed pair from the §6 contract, so each attempt naturally maps to one span;
implementations that try to fold all attempts into a single span MUST fail this fixture.

**Spec sections exercised:**

- §4.2 Retry attempt spans — N attempts produce N sibling spans sharing the same parent.
- §4.5 Span name table — retry attempt spans share the wrapped node's name; disambiguated
  by `attempt_index`.
- §5.2 `openarmature.node.attempt_index` — required on every node span; `0` for non-retry,
  `0..N-1` for N attempts.

**Cases:**

1. `three_attempts_third_succeeds` — flaky node fails on attempts 0 and 1 with
   `provider_rate_limit`, succeeds on attempt 2. Three sibling `flaky` spans appear under the
   invocation span: attempts 0 and 1 with status ERROR + `openarmature.error.category`,
   attempt 2 with status OK.
2. `retry_exhausts_all_three_spans_error` — same flaky node but `fail_count: 999`. All three
   attempt spans are ERROR; the engine raises `node_exception`; the parent invocation span is
   also ERROR.

**What passes:**

- Three sibling spans (NOT one span representing the whole retry chain).
- `attempt_index` values are exactly `[0, 1, 2]` and unique among siblings.
- Status is per-attempt, not collapsed across attempts.
- Case 2: invocation span status propagates ERROR per §4.2 status rules.

**What fails:**

- Single span representing the whole retry sequence — `attempt_index` semantics lost.
- Attempt spans nested under each other (parent-child) instead of siblings.
- All attempt spans share `attempt_index: 0` (the framework didn't thread the §6 attempt_index
  field through to the OTel observer's span attributes).
- Case 1: third attempt span is ERROR despite eventual success — the observer attributed status
  from middleware behavior rather than the per-attempt `completed` event.
