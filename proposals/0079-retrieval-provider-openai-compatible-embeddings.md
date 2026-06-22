# 0079: OpenAI-Compatible Embeddings Wire Mapping

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-22
- **Accepted:**
- **Targets:** spec/retrieval-provider/spec.md **§8 Wire-format mappings** (the section introduced by
  0077) — add **§8.3 OpenAI-compatible embeddings** covering `POST /v1/embeddings`, with a
  **configurable `base_url`** so the one mapping serves OpenAI *and* the broad OpenAI-compatible
  ecosystem (vLLM, LocalAI, Together, TEI's own OpenAI-compatible endpoint, …) — the retrieval-provider
  analogue of llm-provider §8.1 (OpenAI-compatible *chat*). **Embeddings-only** (OpenAI exposes no
  rerank API). **No protocol change, no renumber** (appends §8.3; `input_type` is 0077's — not
  realized on the symmetric base wire, with 0077 §8.1's optional client-side prefix reused for
  asymmetric models behind a compatible endpoint). Plus new conformance fixtures under
  `spec/retrieval-provider/conformance/`.
- **Related:** 0077 (introduces §8 *Wire-format mappings* + the `input_type` knob — 0079 reuses the §8
  section and exercises 0077's graceful `input_type`-absent degradation; accepted after 0077), 0059
  (embedding protocol — this realizes it), 0006 (llm-provider §8.1 OpenAI-compatible *chat* mapping —
  the `base_url`-configurable ecosystem precedent this mirrors for embeddings), 0078 (Jina — sibling
  hosted mapping in the same batch)
- **Supersedes:**

## Summary

The third retrieval-provider wire mapping, and the **highest-leverage** one: the OpenAI-compatible
`/v1/embeddings` surface. Two properties make it punch above its size:

1. **One mapping, the whole ecosystem.** OpenAI's `/v1/embeddings` (`{model, input, dimensions, encoding_format}`)
   is the de-facto-standard embedding wire — vLLM and TEI's *own* OpenAI-compatible endpoint expose it
   (verified), as do other OpenAI-compatible servers (LocalAI, Together, …). A `base_url`-configurable mapping (default
   `https://api.openai.com`, override for any compatible backend) covers all of them in one
   proposal — exactly the play llm-provider §8.1 made for chat completions.

2. **Symmetric — it exercises 0077's graceful degradation, not a new knob.** OpenAI embeddings have
   **no** query/document distinction (the verified request schema has no `input_type` / `task` field),
   so 0077's `input_type` simply **isn't realized** on this wire: `input_type` absent is the correct,
   symmetric default, and a symmetric model ignores it. No protocol change; this is precisely the
   "absent ⇒ symmetric" path 0077 designed for. (For an *asymmetric* model served behind an
   OpenAI-compatible endpoint, the optional client-side prefix mechanism from 0077 §8.1 applies — see
   *Open questions*.)

Embeddings-only: OpenAI has no rerank API, and "OpenAI-compatible rerank" is not a standardized
surface, so §8.3 maps `/v1/embeddings` only (no `RerankProvider`).

## Motivation

**Single highest-leverage mapping in the retrieval batch.** Just as `/v1/chat/completions` is the
lingua franca that llm-provider §8.1 rode to cover OpenAI + every compatible runtime, `/v1/embeddings`
is the embedding equivalent. One `base_url`-configurable mapping turns "OA supports OpenAI embeddings"
into "OA supports OpenAI **and** vLLM / TEI-via-OpenAI-endpoint / LocalAI / Together /
any `/v1/embeddings` server" — far more reach per proposal than a single hosted vendor.

**Validates the 0077 `input_type` design.** A symmetric provider should require *zero* special-casing:
it just doesn't realize `input_type`, and the absent default is already correct. 0079 demonstrates that
— evidence the knob was specced at the right layer (a per-mapping realization, optional, absent-safe).

**Completes the embedding coverage across the three archetypes.** Self-hosted-native (TEI, 0077),
hosted-asymmetric (Jina, 0078), and the symmetric OpenAI-compatible ecosystem (0079) — the three shapes
a real retrieval stack draws from.

## Proposed change

Add **§8.3 OpenAI-compatible embeddings** to the §8 *Wire-format mappings* section (0077).
`gen_ai.system` is `"openai"` — identifying the **wire surface**, not the backing deployment (per the
observability §5.5.8 / §5.5.13 convention and consistent with llm-provider §8.1's OpenAI-compatible
treatment); a vLLM/LocalAI backend reached through this wire is still the OpenAI wire surface. Wire
shapes below were **verified against the OpenAI OpenAPI on 2026-06-22**; recorded in
`docs/compatibility.md` at Accept.

- **Construction.** An OpenAI-compatible `EmbeddingProvider` binds an **API key** (sent as
  `Authorization: Bearer <key>`) + the bound model identifier (§3 / §5 per-instance binding), with
  **`base_url` defaulting to `https://api.openai.com`** and overridable for any OpenAI-compatible
  backend (origin only — the `/v1` version stays in the route, consistent with §8.1 / §8.2; mirrors
  llm-provider §8.1's construction). It MAY additionally bind the optional client-side
  `query_prefix` / `document_prefix` from 0077 §8.1 — off by default (pure-symmetric OpenAI), set only
  for an asymmetric model served behind a compatible endpoint (see *`input_type`* below).
  **Embeddings-only** — no `RerankProvider` counterpart in this mapping.
- **`/v1/embeddings`** — `POST {base_url}/v1/embeddings` with `{"model": str, "input": [str], "dimensions"?: int, "encoding_format"?: "float"|"base64"}`.
  `input` is always the array form (§3's "always a list"); `EmbeddingRuntimeConfig.dimensions` → wire
  `dimensions` (Matryoshka, on models that support it) when set; `encoding_format` defaults to `float`
  (base64 rides the extras bag). Response
  `{data: [{index, embedding}], model, usage: {prompt_tokens, total_tokens}}` → the `EmbeddingResponse`
  vectors in input order; `usage.prompt_tokens` → `EmbeddingUsage.input_tokens` (embedding has no
  output tokens, so `total_tokens` == `prompt_tokens`).
- **`input_type` (symmetric base wire; client-side prefix for asymmetric).** The OpenAI
  `/v1/embeddings` wire has no query/document parameter, so on the base wire `input_type` is **not
  realized** — an absent `input_type` is the correct symmetric default for OpenAI's symmetric models
  (e.g. `text-embedding-3`), and the mapping does not error on it. For an **asymmetric** model served
  behind a compatible endpoint (e.g. a BGE / E5 model on vLLM), the mapping applies the **client-side
  prefix** from 0077 §8.1: when `query_prefix` / `document_prefix` are bound at construction,
  `input_type` selects which to prepend before sending — the only way to express the distinction on a
  wire that has no `input_type` field. A server that *extends* the wire with its own `input_type`-style
  field instead takes it through the extras-pass-through bag.
- **Errors** — HTTP failures map to the §7 categories per the shared enumeration: `401` →
  `provider_authentication`; `429` (rate limit) → `provider_rate_limit`; `5xx` → `provider_unavailable`; unknown model
  (`404` / `400`) → `provider_invalid_model`; malformed / oversized request (`400`) →
  `provider_invalid_request`; malformed response → `provider_invalid_response`.

## Conformance test impact

New fixtures under `spec/retrieval-provider/conformance/` (numbers assigned at Accept; appended after
the 0078 Jina set):

- **OpenAI-compatible `/v1/embeddings` mapping** — request carries `Authorization: Bearer`, `model`,
  `input` (array form); response `data` assembles to vectors in input order;
  `usage.prompt_tokens` → `EmbeddingUsage.input_tokens`.
- **`base_url` override** — the same mapping issues against a non-OpenAI `base_url` (the
  ecosystem-compatibility case).
- **`dimensions` passthrough** — `EmbeddingRuntimeConfig.dimensions` → wire `dimensions`.
- **`input_type` is a no-op (symmetric)** — `embed(config={input_type: "query"})` produces a wire
  request with **no** query/document parameter (byte-identical to the no-`input_type` request); the
  symmetric mapping does not error and does not alter the wire.

## Versioning

**MINOR bump** (pre-1.0), additive only: §8.3 is a new wire mapping; no protocol surface changes (the
`input_type` knob and §8 are 0077's), no renumber. The reference implementation gains an
OpenAI-compatible embeddings provider (HTTP client + API-key auth + `base_url` config). Tentative spec
version target deferred to Accept (sequenced last in the retrieval batch — after 0077 and 0078, since
§8 must exist first).

## Alternatives considered

1. **"OpenAI" only (fixed endpoint) vs. "OpenAI-compatible" (configurable `base_url`).** Choose
   OpenAI-compatible — the configurable `base_url` is the entire leverage (one mapping, whole
   ecosystem), exactly as llm-provider §8.1 is "OpenAI-compatible," not "OpenAI."
2. **Include a rerank half.** Reject — OpenAI has no rerank API, and OpenAI-compatible rerank
   (`/rerank`, `/score`) is not a standardized surface across the compatible servers. Embeddings-only;
   rerank-capable runtimes use their own mapping (TEI §8.1, Jina §8.2, or a future one).
3. **Synthesize an `input_type` wire field.** Reject — base OpenAI `/v1/embeddings` has none, and
   inventing one would diverge from the de-facto standard. Symmetric models don't need it; asymmetric
   models behind a compatible endpoint use the 0077 §8.1 client-side prefix mechanism.
4. **A dedicated `openai-embeddings` capability.** Reject — it's a §8.x wire mapping of the existing
   `EmbeddingProvider` contract, mirroring llm-provider §8.1.

## Open questions

None blocking — resolved during drafting:

- **Asymmetric model behind an OpenAI-compatible endpoint** — RESOLVED: §8.3 reuses 0077 §8.1's
  optional client-side `query_prefix` / `document_prefix` construction; `input_type` selects the
  prefix, prepended client-side. Off by default (pure-symmetric OpenAI). Verified 2026-06-22 that this
  is a real case — vLLM serves OpenAI-compatible `/v1/embeddings` for asymmetric models
  (e.g. `jina-embeddings-v3`, `e5-small`).

Deferred to Accept (alignment, not design):

- **`gen_ai.system`** — `"openai"` identifies the wire surface; confirm the exact match to
  llm-provider §8.1's treatment (fixed `"openai"` vs. an override knob) when writing §8.3.

## Out of scope

- **Rerank** — OpenAI has no rerank API (see Alternatives).
- **Multi-modal / non-text embeddings** — text + dense vectors only, per 0059.
- **`encoding_format: base64` / binary as declared fields, the `user` field, and other
  OpenAI-specific knobs** — ride the extras-pass-through bag; `float` is the default.
- **Other vendors** — Cohere, Voyage AI mappings remain deferred (retrieval-provider §11 *Out of
  scope*).
