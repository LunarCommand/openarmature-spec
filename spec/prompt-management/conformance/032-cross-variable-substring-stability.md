# 032 — Cross-variable substring stability

Verifies §13 *Cross-variable substring stability* — two renders of the same `Prompt` that
differ only in unrelated variable bindings MUST produce rendered output whose non-variable
substrings are byte-identical. Variable substitution is in-place and MUST NOT introduce
position-dependent transformations (variable indexing, per-variable salts, whole-template
normalization) that shift bytes earlier in the rendered output based on later content.

This is the substrate that downstream **automatic prefix caching** (per llm-provider §6 / §8
*Wire-byte stability*) relies on to recognize cache-eligible prefixes across requests.

**Spec sections exercised:**

- §13 *Determinism* — *Cross-variable substring stability* paragraph.

**Cases:**

1. `text_prompt_substring_stability` — A Text-prompt with two variables (`{{ persona }}` and
   `{{ user_question }}`, in that order). Render twice with the same `persona` but different
   `user_question`. The leading portion of the rendered text (everything up through the persona
   substitution) MUST be byte-identical.

2. `chat_prompt_substring_stability` — A Chat-prompt with a fixed system segment and a
   user segment containing `{{ query }}`. Render twice with different `query` values; the
   system Message's rendered bytes MUST be identical across the two renders.

**Harness extensions:** none new.

**What passes:**

- The two renders' shared-prefix substrings (everything up to the first divergent variable) are
  byte-identical.
- The variable-derived substrings differ as expected (per the changed binding).

**What fails:**

- The leading prefix differs because the implementation runs a whole-template post-processor
  that reflows text based on whole-template state.
- A variable-indexing scheme (e.g., numbering variable expansions) introduces position-dependent
  numbers into the rendered text.
- A per-render salt or timestamp is injected into the rendered output.
