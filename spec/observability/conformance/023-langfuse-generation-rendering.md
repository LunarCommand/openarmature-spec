# 023 — Langfuse Generation Rendering

Verifies §8.4.3 Generation-specific fields (model, modelParameters, usage, metadata.{system,
response_model, response_id, finish_reason}) AND §8.7 input/output rendering when the Langfuse
observer's `disable_llm_payload = False`. Includes a second case for §8.7's truncation-fallthrough
rule.

**Spec sections exercised:**

- §8.3 LLM provider span → Generation observation.
- §8.4.3 Generation-specific mapping table:
  - `openarmature.llm.model` (and `gen_ai.request.model`) → `generation.model`
  - Each `gen_ai.request.*` param (per §5.5.2) → `generation.modelParameters.<suffix>` —
    `temperature`, `max_tokens` exercised here.
  - `openarmature.llm.usage.*` (and `gen_ai.usage.*`) → `generation.usage.{input, output, total}`
  - `openarmature.llm.finish_reason` (and `gen_ai.response.finish_reasons[0]`) →
    `generation.metadata.finish_reason`
  - `gen_ai.system` → `generation.metadata.system`
  - `gen_ai.response.model` → `generation.metadata.response_model`
  - `gen_ai.response.id` → `generation.metadata.response_id`
- §8.7 Generation rendering — input/output set from §5.5.1 attributes; `generation.input` parses
  back to the §3 message structure originally sent to the provider.
- §8.7 Truncation contract — when the §5.5.1 source attribute is truncated, the Langfuse observer
  sets `generation.input` to the raw truncated string (preserving the marker), NOT a
  best-effort JSON parse of partial bytes.

**Cases:**

1. `generation_rendering` — two-turn conversation with `temperature=0.0, max_tokens=32`. Mock
   returns assistant content `"hello back"`, finish_reason `stop`. Verifies all §8.4.3 fields
   and §8.7 normal-path rendering.
2. `generation_rendering_truncated` — long user content forces truncation at the 256-byte cap
   (the §5.5.5 minimum). Verifies `generation.input` is set to the raw truncated string with
   the marker, not omitted or partially parsed.

**Harness extensions:**

- `langfuse_observer.payload_byte_cap` — configures the per-attribute byte cap (default 64 KiB
  per §5.5.5). Set to 256 in the truncation case to force truncation with a small payload.
- `input_parses_as_messages` — mapping equivalent: harness asserts that `generation.input`
  parses as a JSON array of message records matching the supplied list (parallel to fixture
  013's `attribute_parses_as_messages`).
- `input_is_raw_string_with_marker` — harness asserts that `generation.input` is a string ending
  with the §5.5.5 truncation marker `…[truncated, M bytes total]` and is NOT parseable JSON.

**What passes:**

- `generation_rendering` case: `generation.model == "test-model"`, `modelParameters.temperature
  == 0.0` and `modelParameters.max_tokens == 32`, `usage.input == 7` / `usage.output == 2` /
  `usage.total == 9`, `metadata.finish_reason == "stop"`, `metadata.system == "openai"`,
  `metadata.response_model == "test-model-v2"`, `metadata.response_id == "cc-23"`,
  `generation.input` parses as the supplied message list, `generation.output == "hello back"`.
- `generation_rendering_truncated` case: `generation.input` is a raw string ending with the
  §5.5.5 truncation marker; `generation.output == "k"` (short enough not to trigger truncation).

**What fails:**

- `generation.model` is missing → §8.4.3 model-field mapping not implemented.
- `modelParameters` is missing temperature/max_tokens that were supplied on the request →
  §8.4.3 §5.5.2-by-inclusion rule not implemented.
- `generation.input` is omitted in the rendering case → payload gating logic ignores the
  observer's `disable_llm_payload = False`.
- `generation.input` is omitted in the truncated case → observer dropped on JSON parse failure
  instead of preserving the truncated string per §8.7.
- The `modelParameters` set is hard-coded to only the four pre-0032 fields (temperature,
  max_tokens, top_p, seed) rather than driven by what §5.5.2 currently defines (the inclusion
  reference per §8.4.3).
