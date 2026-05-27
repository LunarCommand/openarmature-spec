# 016 — Prompt.observability_entities Propagation

Verifies §3 `Prompt.observability_entities` propagation through fetch → render → PromptResult.
Two cases: a backend that attaches a Langfuse Prompt entity reference under
`observability_entities['langfuse_prompt']` (case A); a backend with no observability
entities at all (case B, absent semantic).

**Spec sections exercised:**

- §3 — `Prompt.observability_entities` field (optional `dict[str, Any] | None`,
  backend-keyed entries following `<backend>_<entity>` naming convention).
- §3 — spec-normative key `langfuse_prompt` for the Langfuse SDK Prompt-entity reference.
- §4 — `PromptResult.observability_entities` propagation; rendering does NOT modify the
  mapping.
- §12 cross-spec touchpoint: this is the lookup target observability §8.4.4 reads for
  Langfuse Generation linkage.

**Cases:**

1. `observability_entities_propagates` — backend populates
   `observability_entities = {"langfuse_prompt": "<sentinel>"}`; both Prompt and
   PromptResult carry it unchanged after render.
2. `observability_entities_absent` — backend supplies no observability entities; both
   Prompt and PromptResult carry `observability_entities = None`.

**Harness extensions:**

- `observability_entities: {key: value, ...}` on a backend's prompt definition — populates
  the typed mapping on the returned Prompt. Values are opaque sentinel strings for
  fixture-level equality assertion (no real Langfuse SDK objects are constructed at
  fixture time).
- `expected.rendered.observability_entities_absent: true` — harness asserts the field is
  null / None / undefined per language idiom.

**What passes:**

- Case A: `Prompt.observability_entities['langfuse_prompt'] == "lf-prompt-sentinel-7a3e"`;
  same value on `PromptResult.observability_entities['langfuse_prompt']` after render.
- Case B: both Prompt and PromptResult have `observability_entities == None`.
- Rendering does NOT modify the mapping (case A's after-render value equals the
  before-render value).

**What fails:**

- Case A: the sentinel reference is dropped during render — render mutated the field.
  Violates §4 propagation rule.
- Case A: the reference is stuffed into `Prompt.metadata` instead of the new typed field —
  backend didn't follow the v0.26.0 spec-defined location.
- Case B: the field is defaulted to an empty dict `{}` instead of None — implementation
  synthesized a default; should remain absent entirely per the §3 "opt-in per backend"
  semantic.
- Either case: the Langfuse observer reads from `Prompt.metadata` instead of
  `Prompt.observability_entities['langfuse_prompt']` — that's an observability-spec
  fixture concern (027 + the Langfuse linkage fixtures cover §8.4.4 directly), but the
  cross-spec connection is that the prompt-management layer MUST surface the reference at
  this normative location.
