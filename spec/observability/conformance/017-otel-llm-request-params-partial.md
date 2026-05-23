# 017 — LLM Request Parameters (Partial)

Verifies §5.5.2's absence semantics: `RuntimeConfig` fields that are NOT supplied on the call
MUST NOT be emitted as `gen_ai.request.*` attributes. Specifically, supplying
`temperature: 0.0` does NOT cause `max_tokens`, `top_p`, or `seed` to default-emit as zero.

The key distinction this fixture pins down: **attribute absence means "field not supplied"**,
NOT "field supplied with a zero value." A `temperature: 0.0` is a real user choice (deterministic
sampling) and emits as `0.0`; a `max_tokens` left unset just doesn't emit at all.

**Spec sections exercised:**

- §5.5.2 absence rule — "the absence of an attribute means 'the field was not supplied for this
  call,' distinct from 'the field was supplied with a zero value.'"

**Cases:**

1. `temperature_only` — `RuntimeConfig` supplies only `temperature: 0.0`. The span carries
   `gen_ai.request.temperature: 0.0`; `gen_ai.request.max_tokens`, `gen_ai.request.top_p`, and
   `gen_ai.request.seed` MUST NOT appear.

**What passes:**

- `gen_ai.request.temperature: 0.0` is present.
- None of `gen_ai.request.{max_tokens, top_p, seed}` appear on the span.

**What fails:**

- A non-supplied field is emitted as `0` or `null` — implementation defaulted absent fields
  rather than omitting the attribute.
- `gen_ai.request.temperature` is missing — implementation skipped emit because the value
  equals zero (incorrect — zero is a real choice that MUST emit).
