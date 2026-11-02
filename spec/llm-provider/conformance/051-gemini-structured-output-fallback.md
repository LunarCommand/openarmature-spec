# 051 — Gemini structured-output fallback

Verifies §8.3.5.1 — for a model without native `responseJsonSchema` support, the mapping falls back
to prompt augmentation (per §8.1.5.1's pattern).

**Spec sections exercised:**

- §8.3.5.1 — when the model lacks native structured-output support, the mapping appends a schema
  directive to `systemInstruction` or the message list and parses the text response; the wire
  request carries no `responseJsonSchema` / `responseMimeType`.
- §6 — the response text parses into `Response.parsed`.

**What passes:**

- The wire request carries the bound `model` and `generationConfig.maxOutputTokens`, and no native
  structured-output fields under `generationConfig`.
- The response JSON `{"value":42}` parses into `parsed: {value: 42}`.

**What fails:**

- The native `responseJsonSchema` / `responseMimeType` emitted despite no native support.
- The response text returned unparsed.

The directive's text is implementation-derived, and §8.3.5.1 lets it go in `systemInstruction` or
the message list, so the wire assertion (`expected_wire_request_includes`) asserts neither
`systemInstruction` nor `contents`.
