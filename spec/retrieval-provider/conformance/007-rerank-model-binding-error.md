# 007 — `RerankProvider` model-binding error surfaces `provider_invalid_model`

Verifies the per-instance model-binding contract from retrieval-provider §5 plus the error-category
inheritance from llm-provider §7. A `RerankProvider` bound to an unknown rerank model identifier MUST
surface `provider_invalid_model` on the readiness path.

**Spec sections exercised:**

- retrieval-provider §5 — `ready()` MUST surface `provider_invalid_model` for unrecognized bound
  models.
- retrieval-provider §7 — `provider_invalid_model` is one of the rerank-applicable error categories.
- llm-provider §7 — error-category enumeration (inherited).

**Cases:**

1. `rerank_unknown_model_raises_provider_invalid_model` — `RerankProvider` instantiated with model
   identifier `"nonexistent-rerank-model"`. Mocked provider returns HTTP 404 with the
   provider-specific "model not found" shape. The implementation classifies the response as
   `provider_invalid_model`. Asserts the exception raises out of the call.

**What passes:**

- `provider_invalid_model` raised, attributed to the calling node.
- The exception propagates per llm-provider §7's exception-flow contract.

**What fails:**

- A different §7 category is raised (e.g., `provider_invalid_request`) — the classifier did not
  recognize the model-not-found signal.
- No exception raised — the adapter swallowed the error.
