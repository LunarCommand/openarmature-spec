# 081 — `EmbeddingEvent.active_prompt` snapshot populated under prompt context

Verifies graph-engine §6's `active_prompt` field population on `EmbeddingEvent` (per proposal
0059). When `embed()` is called inside an active prompt-context binding (typical RAG
retrieval-template scenario), the typed event MUST carry a snapshot of the `Prompt` identity.
Mirrors fixture 064 for the LLM-side variant.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent.active_prompt` field population from prompt-context binding.
- prompt-management §12 — prompt-context binding mechanism.

**Cases:**

1. `active_prompt_populated_when_embed_inside_prompt_context` — Graph node renders a prompt
   template (RAG retrieval template), then calls `embed()` with that prompt active. Asserts
   the typed event's `active_prompt` carries the 5-field identity record.

**What passes:**

- `active_prompt` populated with `name`, `version`, `label`, `template_hash`, `rendered_hash`.

**What fails:**

- `active_prompt` is null even though the call ran inside an active prompt-context binding —
  the prompt-context wiring is broken for the embedding path.
- The identity fields are missing or mismatched against the rendered prompt.
