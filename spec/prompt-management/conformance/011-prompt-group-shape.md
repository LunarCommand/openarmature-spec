# 011 — Prompt Group Shape (N>2)

Construct a `PromptGroup` with three `PromptResult` members and a
`group_name`. Assert the group exposes the ordered `members` sequence
and the `group_name`. Tests the N>2 case explicitly (not just the
charter's classifier+follow-up pair) per §9.

**Spec sections exercised:**

- §9 PromptGroup — group structure: `group_name` + ordered `members`.
- §9 N>2 support — multi-stage classification example is one of the
  enumerated patterns; the group primitive handles it under the same
  shape as N=2.
- §9 member ordering — order matches the application's intended call
  sequence; spec doesn't require sequential execution but observability
  tools MAY use member order to lay out the group visually.

**What passes:**

- The group exposes `group_name == "multi_stage_classification"`.
- The group has 3 members.
- Member order matches construction order (m1 first, m2 second, m3
  third).

**What fails:**

- The group accepts only N=2 (would mean the primitive was
  pair-specialized in implementation; spec mandates N>=2 with N>2
  supported).
- Member order is lost (alphabetized, sorted, etc.) — would violate
  §9's order-preservation rule.
- Empty group accepted (would mean §9's "Empty groups are
  spec-invalid" rule is missing).
