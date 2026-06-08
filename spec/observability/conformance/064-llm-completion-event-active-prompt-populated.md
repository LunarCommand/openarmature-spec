# 064 — `LlmCompletionEvent.active_prompt` populated when call inside prompt-context

Verifies graph-engine §6's `LlmCompletionEvent.active_prompt` field (per proposal 0057). The
field carries a 5-field identity record (`name`, `version`, `label`, `template_hash`,
`rendered_hash`) matching the prompt-identity attribute family per prompt-management §12 /
observability §8.4.4.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.active_prompt` field (proposal 0057).
- prompt-management §12 — `openarmature.prompt.*` attribute family (the same data surfaced
  on the typed event).
- observability §8.4.4 — prompt-identity attribute family mapping.

**Cases:**

1. `active_prompt_populated_when_call_inside_prompt_context` — Graph with one LLM-calling
   node that renders a prompt first and then calls the LLM with that prompt active. The
   typed event's `active_prompt` carries the 5-field identity record matching the rendered
   prompt.

**Harness extensions:** uses the established `renders_prompt:`, `prompt_backend:`, and
`render_variables:` directives from fixture 024.

**What passes:**

- `active_prompt.name == "classify"`, `version == "v7"`, `label == "production"`,
  `template_hash == "abc123"`.
- `active_prompt.rendered_hash` is a non-empty string (computed by prompt-management §4
  during render).

**What fails:**

- `active_prompt` is null when the LLM call ran inside a prompt-context binding.
- `active_prompt` collapses the 5-field record to flat keys (e.g., `active_prompt_name`).
- `active_prompt.rendered_hash` is missing (mandatory per prompt-management §4 / proposal
  0033).
