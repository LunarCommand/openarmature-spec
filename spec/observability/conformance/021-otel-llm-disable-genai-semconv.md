# 021 — disable_genai_semconv Opt-Out

Verifies §5.5.4 `disable_genai_semconv = True`: when set, the §5.5.2 request-parameter
attributes and the §5.5.3 response-attribute set are NOT emitted. The v0.7.0 OA-namespaced
baseline attributes continue to emit — the opt-out is GenAI-specific and does not affect the
baseline.

**Spec sections exercised:**

- §5.5.4 `disable_genai_semconv = True` — suppresses §5.5.2 and §5.5.3 emission.
- §5.5.4 independence rule — the three opt-out flags are independent; the GenAI opt-out does
  NOT suppress the v0.7.0 baseline OA attributes.

**Cases:**

1. `genai_opt_out` — observer constructed with `disable_genai_semconv = True`. `RuntimeConfig`
   supplies `temperature: 0.7`. The span carries the v0.7.0 baseline OA attributes; none of the
   `gen_ai.*` attributes appear (including the request parameter attribute, which §5.5.4 ties to
   the same flag as §5.5.3's response attributes).

**What passes:**

- The v0.7.0 baseline attributes (`openarmature.llm.{model, finish_reason, usage.*}`) are
  present with the right values.
- No `gen_ai.*` attribute appears on the span — including request parameters (per §5.5.4's
  pairing of §5.5.2 and §5.5.3 under the same opt-out).

**What fails:**

- A `gen_ai.*` attribute is emitted — implementation didn't gate emission on the flag.
- The baseline OA attributes are missing — implementation incorrectly tied the baseline to the
  GenAI opt-out (the baseline emits regardless of GenAI opt-out; only `disable_llm_spans`
  suppresses it, by suppressing the span entirely).
