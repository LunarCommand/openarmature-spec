# 019 — LLM GenAI Semconv Response Attributes

Verifies §5.5.3: the full minimum set of GenAI semantic-convention response attributes is
emitted on the LLM provider span by default (no `disable_genai_semconv` override), alongside the
v0.7.0 OA-namespaced baseline attributes. Additions, not renames — both the OA and GenAI sets
appear.

**Spec sections exercised:**

- §5.5.3 `gen_ai.system` — defaults to `"openai"` for the OpenAI-compatible provider when no
  override is supplied.
- §5.5.3 `gen_ai.request.model` — mirrors `openarmature.llm.model`.
- §5.5.3 `gen_ai.response.model` — populated from the response body when the provider returns a
  non-null model.
- §5.5.3 `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` — mirror
  `openarmature.llm.usage.prompt_tokens` / `completion_tokens`.
- §5.5.3 `gen_ai.response.finish_reasons` — string array (length 1 for OA's single-choice §6
  shape), distinct from the scalar `openarmature.llm.finish_reason`.
- §5.5.3 `gen_ai.response.id` — populated when the provider returns a non-null id.
- Backwards compatibility — v0.7.0 `openarmature.llm.*` baseline attributes continue to emit.

**Cases:**

1. `full_genai_set` — single LLM call. Mock provider returns `id: cc-19` and
   `model: "test-model-2026-05-22"` (distinct from the bound `model: "test-model"`); usage carries
   non-null token counts; finish_reason is `stop`. The span carries the full GenAI semconv minimum
   set plus the v0.7.0 baseline.

**What passes:**

- All seven GenAI semconv attributes are present with the right values and types.
- `gen_ai.response.finish_reasons` is emitted as `["stop"]` (one-element array), NOT as `"stop"`
  (scalar).
- `gen_ai.request.model` and `gen_ai.response.model` differ (`"test-model"` vs
  `"test-model-2026-05-22"`).
- The v0.7.0 baseline (`openarmature.llm.{model, finish_reason, usage.*}`) is still emitted —
  this is the "additions, not renames" rule.

**What fails:**

- A GenAI attribute is missing — implementation didn't extend §5.5 with §5.5.3 emission.
- `gen_ai.response.finish_reasons` is emitted as a scalar string — implementation didn't wrap in
  array per the semconv contract.
- The v0.7.0 baseline attribute set is missing or renamed — implementation incorrectly treated
  GenAI as a rename rather than an addition.
- `gen_ai.system` is anything other than `"openai"` without a caller-set override — implementation
  inferred from `base_url` or defaulted to the wrong value.
