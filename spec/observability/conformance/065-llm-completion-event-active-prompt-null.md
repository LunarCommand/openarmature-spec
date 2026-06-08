# 065 — `LlmCompletionEvent.active_prompt` null outside prompt-context

Verifies graph-engine §6's `LlmCompletionEvent.active_prompt` nullability semantics (per
proposal 0057). When the LLM call ran outside any prompt-context binding, the field is null
— paralleling the case where no `openarmature.prompt.*` attributes would have been emitted
on the OTel span.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.active_prompt` nullability (proposal 0057).
- observability §8.4.4 — `openarmature.prompt.*` absence when no prompt-context active.

**Cases:**

1. `active_prompt_null_when_call_outside_prompt_context` — Graph with one LLM-calling node
   that does NOT render a prompt first. The typed event's `active_prompt` is null. Companion
   assertion: `active_prompt_group` is also null (no group was active either).

**What passes:**

- `active_prompt == null` and `active_prompt_group == null`.

**What fails:**

- `active_prompt` is an empty record `{}` rather than null (the spec distinguishes:
  null means "no prompt-context binding"; empty record would be ambiguous).
- `active_prompt` is fabricated with default values (e.g.,
  `{name: "", version: "", ...}`) — the field MUST be null when no prompt-context was active.
