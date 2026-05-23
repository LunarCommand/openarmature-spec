# 020 — gen_ai.system Caller-Set Override

Verifies §5.5.3's caller-set-override clause for `gen_ai.system`: the OpenAI-compatible provider
defaults to `"openai"` but MUST allow callers to override the value to reflect a non-OpenAI
endpoint (vLLM, LM Studio, llama.cpp server, etc.). The override mechanism's specific shape is
implementation-defined; the behavioral contract is that the override is available and effective.

**Spec sections exercised:**

- §5.5.3 `gen_ai.system` configurability — "Implementations MUST allow this value to be
  configurable per provider instance."
- §5.5.3 OpenAI-compatible provider default — `"openai"` when no override is supplied
  (verified by fixture 019); overridden here.

**Cases:**

1. `vllm_override` — provider instance configured with `gen_ai.system = "vllm"`. The LLM span
   carries `gen_ai.system: "vllm"`. The bound model remains `"test-model"`; the override applies
   only to `gen_ai.system`.

**Harness extensions:**

- `provider` block at the case level — configures the provider type and override fields.
  `genai_system: "vllm"` sets the `gen_ai.system` value the provider emits. Specific
  constructor/factory shape is per-implementation; the fixture's `genai_system` field maps to
  whatever surface the implementation exposes.

**What passes:**

- `gen_ai.system: "vllm"` is present on the LLM span (not `"openai"`).
- `gen_ai.request.model: "test-model"` is unchanged — the override applies only to
  `gen_ai.system`.

**What fails:**

- `gen_ai.system` is `"openai"` — implementation didn't honor the override (hardcoded the
  default).
- `gen_ai.system` is missing entirely — implementation incorrectly suppressed the attribute
  when overridden.
- An OA-prefixed attribute parallels the GenAI system (e.g., `openarmature.llm.system`) —
  implementation duplicated the namespace for what is normatively a GenAI-only attribute.
