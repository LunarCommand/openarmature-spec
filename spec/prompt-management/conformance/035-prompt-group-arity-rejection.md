# 035 — PromptGroup arity rejection (§10 / §11)

Verifies proposal 0080: prompt-management §10 marks empty and single-member
`PromptGroup`s spec-invalid (`members` MUST contain at least two elements), and
§11 adds the `prompt_group_invalid` error category. Constructing a group with
fewer than two members MUST raise `prompt_group_invalid` **at construction time**.
Complements `011` (valid N>2 construction).

**Spec sections exercised:**

- §10 PromptGroup — the two-or-more-members rule and its construction-time
  enforcement.
- §11 Errors — the `prompt_group_invalid` category (raised at construction).

**Cases:**

1. `single_member_group_rejected` — constructing a group with exactly one
   member raises `prompt_group_invalid`.
2. `empty_group_rejected` — constructing a group with zero members raises
   `prompt_group_invalid`.

**What passes:**

- Each construction raises an error whose `category` is `prompt_group_invalid`.
- The raise occurs at construction — no render or LLM call is reached.

**What fails:**

- Construction succeeds (a fewer-than-two-member group is accepted) — violates
  §10's MUST.
- The raise carries a different `category` (e.g. a generic validation error);
  the spec mandates the `prompt_group_invalid` category for cross-impl
  uniformity.
