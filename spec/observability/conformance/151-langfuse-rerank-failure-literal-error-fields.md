# 151 — rerank failure error_type / error_message asserted literally (proposal 0107)

The rerank sibling of fixture 150. Demonstrates the `raises: {error_type, message}` mock sub-directive
(conformance-adapter §5.15) on the **rerank** path: fixture 138 renders the same ERROR-level `Retriever`
observation but can assert `error_type` / `error_message` only by **format** (`<any-string>`), because its
failure is HTTP-status-triggered and the vendor `type` / `message` are impl-derived. 0107 lets a `mock_rerank`
entry carry literal exception values via `raises`, so the observation's `error_type` / `error_message` can be
asserted **literally** — closing the 137/138 gap for rerank as fixture 150 does for embedding.

**Spec sections exercised:**

- conformance-adapter §5.15 — the `mock_rerank` `raises: {error_type, message}` sub-directive: a non-2xx entry
  overrides only the exception's literal `error_type` / `error_message`, while `status` fixes the §7
  `error_category`.
- observability §8.4.7 — the ERROR-level `Retriever` observation; `statusMessage` = the §7 category,
  `error_type` / `error_message` in metadata, no `output`.

**Case:**

1. `rerank_failure_error_fields_asserted_literally` — the `mock_rerank` entry carries `status: 503`
   (→ `provider_unavailable`) **and** `raises: {error_type: "ServiceUnavailableError", message: "the rerank
   endpoint returned 503"}`. The Langfuse `Retriever` observation emits at ERROR level, `statusMessage:
   "provider_unavailable"`, and `metadata.error_type` / `error_message` equal to the **literal** `raises`
   values.

**What passes:**

- `metadata.error_type == "ServiceUnavailableError"` and `metadata.error_message == "the rerank endpoint
  returned 503"` (literal, from `raises`); `statusMessage == "provider_unavailable"` (from `status`); no
  `output`; the request-side `openarmature_query_length` / `openarmature_document_count` / `openarmature_top_k`.

**What fails:**

- Asserting `error_type` / `error_message` only by format when the harness supplied literal values; sourcing the
  `error_category` from `raises` rather than the `status`; or emitting an `output` on a failure observation.

**Payload flag (proposal 0118).** This fixture sets `disable_provider_payload: false`. The observation's
`error_message` is harvested exception text gated by that flag (observability §5.5.4), and asserting it
**literally** is this fixture's whole purpose, so the flag must permit it. `error_type` is a
classification token and is not gated. Consequently the request-side `input` also populates, as in the
flag-off case of the sibling format-assertion fixture. The flag's own gating of the message is covered by
fixture 159.
