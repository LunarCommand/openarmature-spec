# 106 — `RerankEvent.active_prompt` populated inside prompt context

Verifies graph-engine §6's `active_prompt` contract for `RerankEvent`. When a rerank call runs with
an active prompt (a RAG retrieval scenario — render the query template, then rerank candidate
documents against the rendered query), the typed event carries a snapshot of the prompt identity.

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent.active_prompt` snapshot field.
- prompt-management §12 — the prompt-identity attribute set the snapshot mirrors.

**Cases:**

1. `active_prompt_populated_when_rerank_inside_prompt_context` — a node renders `rag_query` then
   reranks with that prompt active. The `RerankEvent.active_prompt` carries the 5-field identity
   record (`name`, `version`, `label`, `template_hash`, `rendered_hash`) matching the rendered prompt.

**What passes:**

- `active_prompt` carries the prompt-identity snapshot matching the rendered prompt.

**What fails:**

- `active_prompt` is null when a prompt was active at rerank time.
- The snapshot identity fields mismatch the rendered prompt.
