# 024 — Langfuse Prompt Linkage

Verifies §8.4.4's capability-based linkage trigger: a Generation observation links to a Langfuse
Prompt entity when the prompt's source exposes a reference, regardless of which specific
PromptBackend produced the prompt. When no reference is exposed, identity surfaces via
`generation.metadata.prompt` only.

**Spec sections exercised:**

- §8.4.4 prompt linkage trigger — capability-based, not backend-identity-based.
- §8.4.4 metadata.prompt block — normative nested shape (`name`, `version`, `label`,
  `template_hash`, `rendered_hash`).
- §8.8 prompt linkage (cross-references §8.4.4).
- Prompt-management §11 — `openarmature.prompt.*` attributes on the LLM provider span.

**Cases:**

1. `langfuse_prompt_reference_present` — mock PromptBackend that attaches a Langfuse Prompt
   reference (`"lf-prompt-7a3e"`) to the rendered prompt. Verifies the Generation observation
   is linked to that entity AND has the metadata.prompt block.
2. `no_langfuse_prompt_reference` — filesystem PromptBackend with no Langfuse reference.
   Verifies NO Prompt-entity link is established; metadata.prompt block is still present.

**Harness extensions:**

- `prompt_backend.type` — selects the mock PromptBackend shape. Two recognized values:
  - `mock_with_langfuse_reference`: a mock backend that attaches a `langfuse_prompt_reference`
    field on each Prompt record; the Langfuse-observer recorder verifies the resulting
    Generation observation is linked.
  - `filesystem`: a mock backend that does NOT attach the reference field (or any equivalent
    Langfuse-compatible reference).
- `prompt_entity_link` — the expected reference value the harness verifies was passed to the
  Langfuse SDK's Generation prompt-link mechanism.
- `prompt_entity_link_absent` — the harness verifies no prompt-link was passed to the SDK.
- `renders_prompt` (in node spec) — the prompt name to fetch + render via the configured
  backend before the LLM call.
- `render_variables` — the variables to inject into the rendered template.

**What passes:**

- Case 1 (`langfuse_prompt_reference_present`): the Generation observation is linked to Prompt
  entity `"lf-prompt-7a3e"` AND `generation.metadata.prompt` carries the full nested map (name,
  version, label, template_hash, rendered_hash). Both link and metadata are present (the
  redundant-metadata rule per §8.4.4).
- Case 2 (`no_langfuse_prompt_reference`): no Prompt-entity link is established
  (`prompt_entity_link_absent`); `generation.metadata.prompt` is the only identity surface.

**What fails:**

- Case 1: implementation classifies the trigger by backend type rather than reference presence,
  e.g., refuses to link a Langfuse reference from a non-LangfusePromptBackend (mock backend).
  Violates the capability-based trigger rule in §8.4.4.
- Case 2: implementation fabricates a Prompt-entity link when no reference is present
  (e.g., synthesizes a reference from the metadata fields). §8.4.4 mandates "MUST NOT fabricate
  one when absent."
- Either case: `generation.metadata.prompt` is collapsed to flat keys
  (`metadata.prompt_name`, etc.) instead of the nested shape. §8.4.4 prohibits collapsing.
- Either case: `metadata.prompt.rendered_hash` is missing (computed by prompt-management §4
  during render; MUST propagate to Generation observation metadata).
