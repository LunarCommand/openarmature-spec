# 026 — Chat-Prompt Observability Entities Propagation

Verifies §12's "§8.4.4 linkage unaffected by Prompt variant" clarification: a Chat-prompt
carrying `observability_entities['langfuse_prompt']` flows through the §8.4.4 Langfuse
Prompt-entity lookup exactly as a Text-prompt does (cf. fixture 016). The linkage is keyed
on prompt identity (`name + version + label`), not on rendered message count or Prompt
variant.

**Spec sections exercised:**

- §3.1 — Chat-prompt variant; `chat_template`.
- §3 — `Prompt.observability_entities` field; spec-normative key `langfuse_prompt`.
- §4 — `PromptResult.observability_entities` propagation.
- §12 — observability §8.4.4 cross-spec touchpoint; "unaffected by Prompt variant"
  confirmation.

**Cases:**

1. `chat_prompt_observability_entities_propagate` — Chat-prompt backend supplies
   `observability_entities = {"langfuse_prompt": "<sentinel>"}`; both Prompt and
   PromptResult carry the sentinel unchanged after render; the rendered messages match the
   expected per-segment substitution.

**Harness extensions:** none new (same primitives as fixtures 016, 017, 023).

**What passes:**

- `Prompt.observability_entities['langfuse_prompt']` equals the sentinel.
- `PromptResult.observability_entities['langfuse_prompt']` equals the same sentinel after
  render — rendering does NOT modify the mapping (per §4 propagation rule).
- `PromptResult.messages` matches the expected per-segment substitution (length 2; system +
  user with substituted variables).

**What fails:**

- The sentinel was dropped during render — render mutated the field. Violates §4
  propagation rule.
- The Chat-prompt variant was treated differently from Text-prompt in the propagation
  path (e.g., observability_entities was reset to `None` when the variant was Chat-prompt)
  — implementation differentiated where the spec mandates uniform propagation.
- The rendered messages don't match the expected substitution — orthogonal to the
  observability propagation but verified together so failure modes don't conflate.
