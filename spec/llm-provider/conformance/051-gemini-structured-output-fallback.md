# 051 — Gemini structured-output fallback

Verifies §8.3.5.1 — for a model without native `responseJsonSchema` support, the mapping falls back
to prompt augmentation (per §8.1.5.1's pattern).

**Spec sections exercised:**

- §8.3.5.1 — when the model lacks native structured-output support, the mapping appends a schema
  directive to `systemInstruction` (impl-derived text) and parses the text response; the wire
  request carries no `responseJsonSchema` / `responseMimeType`.
- §6 — the response text parses into `Response.parsed`.

**What passes:**

- The wire request carries a `systemInstruction` directive (impl-derived) and no native
  structured-output fields.
- The response JSON `{"value":42}` parses into `parsed: {value: 42}`.

**What fails:**

- The native `responseJsonSchema` / `responseMimeType` emitted despite no native support.
- The response text returned unparsed.

(The appended directive text is implementation-derived per §8.3.5.1; the harness wildcard `"*"`
matches any present non-empty string.)
