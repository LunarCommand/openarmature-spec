# 137 — Langfuse embedding failure observation

Verifies observability §8.4.5's *Failure observations* paragraph (proposal 0089): an
`EmbeddingFailedEvent` renders an ERROR-level `Embedding` observation — NOT a `Generation`, and
NOT a success — via the generic §4.2 / §8.4.2 error mapping, mirroring §8.4.6's tool failure
(fixture 098) and the success counterpart (fixture 083).

**Spec sections exercised:**

- observability §8.4.5 — *Failure observations*: `ERROR` level, the §7 `error_category` as
  `observation.statusMessage`, `error_type` / `error_message` in metadata, and no `output` (no
  response was received).
- observability §8.4.2 — the generic `openarmature.error.category` →
  `observation.level = "ERROR"` + `observation.statusMessage = <category>` mapping the failure
  paragraph routes through.
- observability §8.4.5 field mappings — the request-side `openarmature_input_count` (length of
  `input_strings`) survives on the failure observation; the response-derived
  `openarmature_dimensions` / `openarmature_response_id` do not (no response).

**Cases:**

1. `embedding_failure_renders_error_level_observation_payload_suppressed` — default config
   (`disable_provider_payload=True`). The `Embedding` observation emits at `ERROR` with
   `statusMessage = "provider_unavailable"`, `error_type` / `error_message` in metadata, and
   `openarmature_input_count`; `input` is suppressed (null) and `output` is null (no response).
2. `embedding_failure_no_output_even_with_payload_flag_off` —
   `disable_provider_payload=False`. The request-side `input` (the strings list) populates as in
   083's flag-off case, but `output` stays null — the absence is intrinsic (no response), not a
   payload-gating artifact. `ERROR` level + `statusMessage` + error metadata are unchanged by the
   flag.

**Harness notes (per conformance-adapter §3.2):**

- The failure is triggered by `mock_embedding` returning HTTP 503, classified as
  `provider_unavailable` (the directive vocabulary of fixture 075). The `expected_error` block
  asserts the exception still propagates out of `embed()`.
- `error_type` / `error_message` are asserted by format (`<any-string>`), not literal: the mock
  body supplies a vendor `type` + `message` so both surface non-empty, but their exact values are
  impl-derived (the fixture-073 vendor-error-type idiom). `error_category` (the deterministic §7
  category, here `provider_unavailable`) is the literal-asserted field, via `statusMessage`.

**What passes:**

- Observation type is `embedding` (not `generation`); `ERROR` level; `statusMessage` is the §7
  category; `error_type` / `error_message` in metadata; no `output` under either payload posture.

**What fails:**

- The failure renders as a `Generation` or generic `span` (wrong dedicated type), or as a
  success-level observation.
- `output` populated under the payload-off flag (the failure has no response to render).
- `statusMessage` omitted, or set to something other than the §7 `error_category`.
