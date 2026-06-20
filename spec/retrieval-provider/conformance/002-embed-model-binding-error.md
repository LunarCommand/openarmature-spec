# 002 — `EmbeddingProvider` model-binding error surfaces `provider_invalid_model`

Verifies the per-instance model-binding contract from retrieval-provider §3 plus the error-
category inheritance from llm-provider §7. An `EmbeddingProvider` bound to an unknown embedding
model identifier MUST surface `provider_invalid_model` on the readiness path.

**Spec sections exercised:**

- retrieval-provider §3 — `ready()` and `embed()` model-binding contract; `ready()` MUST
  surface `provider_invalid_model` for unrecognized bound models.
- retrieval-provider §7 — `provider_invalid_model` is one of the embedding-applicable
  error categories.
- llm-provider §7 — error-category enumeration (inherited).

**Cases:**

1. `embed_unknown_model_raises_provider_invalid_model` — `EmbeddingProvider` instantiated
   with model identifier `"nonexistent-embedding-model"`. Mocked provider returns HTTP 404
   with the provider-specific "model not found" shape. The implementation classifies the
   response as `provider_invalid_model` per llm-provider §7. Asserts the exception raises
   out of `embed()`.

**What passes:**

- `provider_invalid_model` raised, attributed to the calling node.
- The exception propagates per llm-provider §7's exception-flow contract.

**What fails:**

- A different §7 category is raised (e.g., `provider_invalid_request`) — the adapter's error
  classifier did not recognize the model-not-found signal.
- No exception raised — the adapter swallowed the error.
