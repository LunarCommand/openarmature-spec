# 057 — `openarmature.llm.attempt_index` single-attempt default

Verifies §5.5's `openarmature.llm.attempt_index` attribute in the single-attempt case — when
`complete()` is called without a `retry` parameter (the default), exactly ONE LLM provider span
emits carrying `openarmature.llm.attempt_index = 0`. This is the single-span backwards-compat
contract (the framing established before proposal 0050; preserved verbatim) plus the new
attribute's default-value contract.

**Spec sections exercised:**

- §5.5 baseline attribute set — `openarmature.llm.attempt_index` int; defaults to `0` when
  call-level retry is not configured (a single attempt produces a single span with
  `attempt_index = 0`).
- §5.5 single-span framing (preserved verbatim when call-level retry is absent).

**Cases:**

1. `llm_attempt_index_zero_on_single_attempt_call` — A graph with one LLM-calling node and a
   mocked provider returning a single successful response. `complete()` is called WITHOUT a
   `retry` parameter (default `None`). Asserts:
   - Exactly one LLM provider span emits (single-span case preserved).
   - The span carries `openarmature.llm.attempt_index = 0` (the default value).
   - The span carries the baseline `openarmature.llm.model` / `finish_reason` /
     `usage.*` attributes per §5.5 baseline.
   - The span is parented under the calling node's span per §4.

**What passes:**

- One LLM provider span emits.
- `openarmature.llm.attempt_index = 0` on the single span.
- Baseline §5.5 attributes still emit alongside the new attribute.

**What fails:**

- More than one LLM span emits — the implementation produced multiple attempts despite no
  retry being configured.
- The `openarmature.llm.attempt_index` attribute is missing — the new attribute MUST emit on
  every LLM provider span, not just retried calls.
- The attribute carries a non-zero value despite a single attempt — the default-value
  contract is violated.
