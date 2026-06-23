# 066 — `LlmCompletionEvent.active_prompt_group` populated inside group context

Verifies graph-engine §6's `LlmCompletionEvent.active_prompt_group` field (per proposal
0057). The field carries a `{group_name}` record matching the prompt-group attribute family
per prompt-management §12 / observability §8.4.4 when the LLM call ran inside a
`PromptGroup` context.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.active_prompt_group` field (proposal 0057).
- prompt-management §10 — `PromptGroup` shape.
- prompt-management §12 — `openarmature.prompt.group_name` attribute.

**Cases:**

1. `active_prompt_group_populated_when_call_inside_group_context` — Graph with one
   LLM-calling node that renders a prompt inside a two-member `PromptGroup` context
   (`classify` + `summarize`, with `classify` active). The typed event's
   `active_prompt_group` carries `{group_name: "classification_pipeline"}`; `active_prompt`
   carries the active member's identity record.

**Per-directory directive (per conformance-adapter §3.2):**

- `renders_prompt_group: {group_name: <name>, members: [<prompt_name>, …], active_prompt: <prompt_name>}`
  (on a node) — the adapter constructs a `PromptGroup` from the explicit `members` list (an
  ordered sequence of at least two prompts defined in `prompt_backend.prompts`, per
  prompt-management §10), makes that group the active `PromptGroup` context, sets the named
  `active_prompt` member as the active `Prompt` context, then invokes the LLM. Both bindings
  are torn down when the node returns.

**What passes:**

- `active_prompt_group.group_name == "classification_pipeline"`.
- `active_prompt` carries the classify member's full identity record (also populated since
  the active prompt context was bound alongside the group).

**What fails:**

- `active_prompt_group` is null when the LLM call ran inside a group context.
- `active_prompt_group` is collapsed to a flat string (just the group_name) rather than a
  `{group_name}` record — the spec mandates record shape for future extensibility.
- `active_prompt_group` carries fields beyond `group_name` (the v0.51.0 spec carves only
  the one field; additions land via follow-on proposals).
