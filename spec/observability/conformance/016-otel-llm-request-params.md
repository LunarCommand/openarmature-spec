# 016 — LLM Request Parameters

Verifies §5.5.2: `RuntimeConfig` fields (temperature, max_tokens, top_p, seed) are emitted under
the GenAI semconv namespace (`gen_ai.request.*`) on the LLM provider span. No
`openarmature.llm.request.*` parallels are emitted for these cross-vendor parameters.

**Spec sections exercised:**

- §5.5.2 `gen_ai.request.temperature` — double, mapped from `RuntimeConfig.temperature`.
- §5.5.2 `gen_ai.request.max_tokens` — int, mapped from `RuntimeConfig.max_tokens`.
- §5.5.2 `gen_ai.request.top_p` — double, mapped from `RuntimeConfig.top_p`.
- §5.5.2 `gen_ai.request.seed` — int, mapped from `RuntimeConfig.seed`.
- §5.5.2 OA-prefix non-emission rule — implementations MUST NOT emit
  `openarmature.llm.request.{temperature, max_tokens, top_p, seed}` parallels.

**Cases:**

1. `all_params` — `RuntimeConfig` supplies all four fields. The LLM span carries all four
   `gen_ai.request.*` attributes with the right values; no OA-prefixed parallels appear.

**Harness extensions:**

- `config` block under `calls_llm` — passes `RuntimeConfig` fields through to `Provider.complete()`.

**What passes:**

- All four `gen_ai.request.*` attributes are present with the supplied values.
- Types match: `temperature` and `top_p` as floating-point; `max_tokens` and `seed` as int.
- No `openarmature.llm.request.{temperature, max_tokens, top_p, seed}` attributes appear.

**What fails:**

- An attribute is missing or has a wrong value.
- An attribute is emitted with the OA prefix (e.g., `openarmature.llm.request.temperature`) —
  implementation duplicated the namespace.
- `gen_ai.request.temperature` is emitted as an integer (`1`) when supplied as a float (`1.0`) —
  type narrowing bug.
