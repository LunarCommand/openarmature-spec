# 013 — Prompt.sampling from Backend

Verifies §3 `Prompt.sampling` sub-record propagation. A backend that populates the new
typed field surfaces it on the returned Prompt; the manager propagates it through render
to PromptResult unchanged.

**Spec sections exercised:**

- §3 — `Prompt.sampling` field shape (seven declared fields mirroring llm-provider §6
  `RuntimeConfig` + extras mapping for vendor-specific keys).
- §4 — `PromptResult.sampling` propagation from source `Prompt.sampling`.

**Cases:**

1. `fetch + render with sampling populated` — backend supplies a Prompt with all seven
   declared sampling fields set plus one extras entry; harness verifies both `Prompt.sampling`
   and `PromptResult.sampling` carry the supplied values byte-for-byte.

**What passes:**

- `Prompt.sampling.temperature == 0.0`, `max_tokens == 256`, `top_p == 0.95`, `seed == 42`,
  `frequency_penalty == 0.1`, `presence_penalty == 0.2`,
  `stop_sequences == ["END"]`.
- `Prompt.sampling.extras == {"repetition_penalty": 1.05}` (extras pass through
  unmodified).
- `PromptResult.sampling` is bytewise identical to `Prompt.sampling` after render.

**What fails:**

- Any of the seven declared fields is missing on Prompt.sampling — backend's sub-record
  construction didn't follow §3's shape.
- `extras` contents are dropped or coerced (e.g., merged into the declared fields) —
  violates §3's "extras mapping for vendor-specific fields" rule.
- `PromptResult.sampling` differs from the source — manager modified the sub-record
  during render (violates §4 propagation contract).
- `Prompt.sampling` is collapsed into `Prompt.metadata` — backend didn't use the new
  typed field.
