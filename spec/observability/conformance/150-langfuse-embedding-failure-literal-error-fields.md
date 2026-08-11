# 150 — embedding failure error_type / error_message asserted literally (proposal 0107)

Demonstrates the net-new `raises: {error_type, message}` mock sub-directive (conformance-adapter §5.15). Fixture
137 renders the same ERROR-level `Embedding` observation but can assert `error_type` / `error_message` only by
**format** (`<any-string>`), because its failure is HTTP-status-triggered and the vendor `type` / `message` are
impl-derived — not cross-impl deterministic. 0107 lets a `mock_embedding` entry carry literal exception values
via `raises`, so the observation's `error_type` / `error_message` can be asserted **literally**, closing the
137/138 gap (the retrieval analogue of the tool path's `mock_tool: {raises: {error_type, message}}`, fixture
098).

**Spec sections exercised:**

- conformance-adapter §5.15 — the `mock_embedding` `raises: {error_type, message}` sub-directive: a failing
  `embed()` raises with the literal `error_type` / `error_message`, while `status` fixes the §7 `error_category`.
- observability §8.4.5 — the ERROR-level `Embedding` observation; `statusMessage` = the §7 category,
  `error_type` / `error_message` in metadata, no `output`.

**Case:**

1. `embedding_failure_error_fields_asserted_literally` — the `mock_embedding` entry carries `status: 503`
   (→ `provider_unavailable`) **and** `raises: {error_type: "ServiceUnavailableError", message: "the embedding
   endpoint returned 503"}`. The Langfuse `Embedding` observation emits at ERROR level, `statusMessage:
   "provider_unavailable"`, and `metadata.error_type` / `error_message` equal to the **literal** `raises`
   values.

**What passes:**

- `metadata.error_type == "ServiceUnavailableError"` and `metadata.error_message == "the embedding endpoint
  returned 503"` (literal, from `raises`); `statusMessage == "provider_unavailable"` (from `status`); no
  `output`; `openarmature_input_count: 2`.

**What fails:**

- Asserting `error_type` / `error_message` only by format when the harness supplied literal values; sourcing the
  `error_category` from `raises` rather than the `status`; or emitting an `output` on a failure observation.

**Payload flag (proposal 0118).** This fixture sets `disable_provider_payload: false`. The observation's
`error_message` is harvested exception text gated by that flag (observability §5.5.4), and asserting it
**literally** is this fixture's whole purpose, so the flag must permit it. `error_type` is a
classification token and is not gated. Consequently the request-side `input` also populates, as in the
flag-off case of the sibling format-assertion fixture. The flag's own gating of the message is covered by
fixture 159.
