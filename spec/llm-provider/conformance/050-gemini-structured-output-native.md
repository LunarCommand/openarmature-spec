# 050 — Gemini native structured output

Verifies §8.3.5 — `response_schema` maps to `generationConfig.responseJsonSchema` +
`responseMimeType`, and the response text parses into `Response.parsed`.

**Spec sections exercised:**

- §8.3.5 — a supplied `response_schema` sets `responseMimeType: "application/json"` and
  `responseJsonSchema: <schema verbatim>` (the full-JSON-Schema field, not the lossy OpenAPI-subset
  `responseSchema`).
- §6 — the response text is parsed into `Response.parsed` and validated against the schema.

**What passes:**

- The schema appears under `generationConfig.responseJsonSchema` verbatim.
- `responseMimeType: "application/json"` is set alongside it.
- The JSON text `{"value":42}` parses into `parsed: {value: 42}`.

**What fails:**

- The schema emitted under `responseSchema` (the OpenAPI-subset field) instead of
  `responseJsonSchema`.
- `responseMimeType` omitted.
- The response text returned unparsed (no `Response.parsed`).
