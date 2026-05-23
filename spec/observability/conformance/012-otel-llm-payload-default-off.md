# 012 — LLM Payload Default-Off

Verifies §5.5.4 default opt-out flags: `disable_llm_payload = True` (default) suppresses the
§5.5.1 payload attributes; `disable_genai_semconv = False` (default) keeps the §5.5.2 / §5.5.3
GenAI semconv attributes emitting.

**Spec sections exercised:**

- §5.5 baseline attributes — `openarmature.llm.model`, `openarmature.llm.finish_reason`,
  `openarmature.llm.usage.*` MUST emit on the LLM provider span.
- §5.5.2 request parameters — none in this case (no `RuntimeConfig` supplied), so no
  `gen_ai.request.*` parameter attributes emit; `gen_ai.request.model` (per §5.5.3) does emit.
- §5.5.3 GenAI semconv response attributes — full set emits by default.
- §5.5.4 `disable_llm_payload = True` default — `openarmature.llm.input.messages`,
  `openarmature.llm.output.content`, `openarmature.llm.request.extras` MUST NOT emit.

**Cases:**

1. `default_payload_off` — single user message, mock OpenAI-compatible response. Default observer
   config (no `disable_llm_payload` or `disable_genai_semconv` overrides). LLM span carries the
   baseline OA attributes plus the GenAI semconv set; the payload attributes are absent.

**Harness extensions:**

- `attributes_absent` — list of attribute names that MUST NOT appear on the span. Implementations
  assert by checking the attribute key is not present on the emitted span.

**What passes:**

- Span tree shows `invocation → ask_llm → openarmature.llm.complete`.
- LLM span carries the listed `attributes` with the listed values (exactly; not as a subset rule).
- LLM span carries NO key matching any entry in `attributes_absent`.

**What fails:**

- Any `attributes_absent` key appears on the span — implementation forgot to gate payload
  attributes under `disable_llm_payload`.
- Any listed `attributes` entry is missing or has a wrong value.
- `gen_ai.response.finish_reasons` is emitted as a scalar string instead of a one-element array.
