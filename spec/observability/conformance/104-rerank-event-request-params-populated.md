# 104 — `RerankEvent.request_params` populated

Verifies graph-engine §6's `request_params` contract for `RerankEvent`. The field carries the
rerank-specific runtime-config fields the caller supplied (initially `return_documents` per
retrieval-provider §2), with absence-is-meaningful semantics for unsupplied params.

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent.request_params` absence-is-meaningful semantics.
- retrieval-provider §2 — `RerankRuntimeConfig` shape (initially `return_documents`).

**Cases:**

1. `request_params_populates_return_documents_when_supplied` — `config.return_documents=True`; the
   event's `request_params` carries `{return_documents: true}` and no other keys.
2. `request_params_empty_when_no_config_supplied` — no config; `request_params` is an empty mapping.

**What passes:**

- Supplied params appear in `request_params`; unsupplied params are absent (empty mapping when none).

**What fails:**

- An unsupplied param appears with a default value — absence-is-meaningful semantics broken.
- `return_documents` is dropped when the caller supplied it.
