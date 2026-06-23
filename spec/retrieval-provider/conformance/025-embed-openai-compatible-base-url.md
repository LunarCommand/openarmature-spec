# 025 — OpenAI-compatible `/v1/embeddings` `base_url` override

Verifies the retrieval-provider §8.3 `base_url` override — the entire leverage of the mapping: one
OpenAI-compatible mapping serves OpenAI **and** the broad OpenAI-compatible serving ecosystem (vLLM,
LocalAI, Together, TEI's own OpenAI-compatible endpoint, …). Bound to a non-OpenAI `base_url`, the
mapping MUST still route to `{base_url}/v1/embeddings` with `Authorization: Bearer` and produce the
identical request/response contract — because `gen_ai.system` `"openai"` names the **wire surface**, not
the backing deployment.

**Spec sections exercised:**

- retrieval-provider §3 — `embed()` preserves input order; array-form request.
- retrieval-provider §4 — `EmbeddingResponse` shape invariants.
- retrieval-provider §8.3 OpenAI-compatible embeddings — *Construction*: `base_url` defaults to
  `https://api.openai.com` (origin only — the `/v1` version stays in the route) and is **overridable for
  any OpenAI-compatible backend**; `gen_ai.system` is `"openai"` identifying the wire surface, not the
  backing deployment.

**Cases:**

1. `base_url_override_routes_to_compatible_backend` — provider bound to a vLLM-style origin
   `http://vllm.invalid`. `embed()` over 2 inputs, no config. The mapping MUST POST to
   `http://vllm.invalid/v1/embeddings` (origin + the fixed `/v1/embeddings` route) with
   `Authorization: Bearer` present and body `{model, input: [s0, s1]}` (array form, no `input_type` /
   `dimensions`). The `{object, data, model, usage}` response maps to vectors in input order — the
   byte-identical contract to the OpenAI-host case (023). Distinct first components keep input order
   load-bearing.

**What passes:**

- The resolved request URL is `{base_url}/v1/embeddings` against the overridden origin (the mapping
  appends the same `/v1/embeddings` route to any origin).
- The `Authorization: Bearer <api_key>` header is present regardless of backend (auth is mapping-level).
- The request/response contract is identical to the OpenAI-host case — vectors in input order,
  `usage.prompt_tokens` → `input_tokens`, `response_id` null.

**What fails:**

- The request routes to the default `https://api.openai.com` (or any host other than the bound
  `base_url`), or the `/v1/embeddings` route is altered when the origin is overridden.
- The `base_url` is treated as including the route (double `/v1`), or the `Authorization: Bearer` header
  is dropped for a non-OpenAI backend.
