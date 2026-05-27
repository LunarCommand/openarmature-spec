# 025 — OTel LLM Request Params Extended

Verifies §5.5.2's extended request-parameter attribute list (proposal 0032). All seven §6
declared `RuntimeConfig` fields set on a single call MUST surface as the corresponding seven
`gen_ai.request.*` attributes on the LLM provider span: the four pre-0032 (`temperature`,
`max_tokens`, `top_p`, `seed`) plus the three new ones (`frequency_penalty`, `presence_penalty`,
`stop_sequences`).

**Spec sections exercised:**

- §5.5.2 — each `gen_ai.request.*` attribute is emitted when the corresponding `RuntimeConfig`
  field is set.
- §5.5.2 — `gen_ai.request.stop_sequences` is a string array, sourced from
  `RuntimeConfig.stop_sequences` (same name on both sides — the OpenAI body's `stop` field is the
  outlier and lives at the wire layer per §8.1 of llm-provider).
- §5.5.6 — cross-implementation consistency on attribute names and value types.

**Cases:**

1. `all_request_params_emitted` — all seven declared `RuntimeConfig` fields set;
   `gen_ai.request.temperature`, `gen_ai.request.max_tokens`, `gen_ai.request.top_p`,
   `gen_ai.request.seed`, `gen_ai.request.frequency_penalty`,
   `gen_ai.request.presence_penalty`, `gen_ai.request.stop_sequences` are all emitted with the
   supplied values.

**What passes:**

- LLM provider span carries all seven `gen_ai.request.*` attributes with the supplied values.
- `gen_ai.request.stop_sequences` is a JSON string array preserving order
  (`["END", "STOP"]`).

**What fails:**

- Any of the three new attributes is missing — the §5.5.2 expansion isn't implemented.
- `gen_ai.request.stop_sequences` is emitted as a scalar string or with a vendor-specific name
  (e.g., `gen_ai.request.stop`) — violates §5.5.2's name + type contract.
- The fixture's seven attributes are emitted under the OA-namespaced names (e.g.,
  `openarmature.llm.frequency_penalty`) instead of the GenAI semconv namespace — violates
  §5.5.2's "use the GenAI semconv namespace directly" precedent.
