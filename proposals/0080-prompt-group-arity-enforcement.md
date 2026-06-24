# 0080: PromptGroup Arity Enforcement

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-23
- **Targets:** prompt-management/spec.md **§10 PromptGroup** (pin the enforcement point —
  constructing a group with fewer than two members MUST raise, at construction) + **§11 Errors**
  (add a `prompt_group_invalid` category). Plus new conformance fixtures under
  `spec/prompt-management/conformance/` asserting the rejection.
- **Related:** 0017 (prompt-management core — introduced the `PromptGroup` §10 primitive and the
  two-or-more-members rule), 0033 (prompt-management surface refinements), 0057
  (LlmCompletionEvent field set — its observability fixture `066` built the group-of-one that
  exposed this gap; corrected in spec v0.74.1), 0055 (conformance-adapter — the categorized
  `raises: {category}` assertion shape these fixtures use)
- **Supersedes:**

## Summary

prompt-management §10 requires a `PromptGroup` to hold **two or more** members ("empty groups and
single-member groups are both spec-invalid; `members` MUST contain at least two elements"), but it
specifies **neither the enforcement point** (must the implementation actively reject an invalid
group, or is the behavior undefined?) **nor an error category**, and **no conformance fixture pins
it**. This proposal closes that loop: it pins rejection at **construction time**, adds a
`prompt_group_invalid` error category (§11), and adds rejection fixtures so the rule is enforced
uniformly across implementations.

## Motivation

The gap is not hypothetical — it just bit. Observability conformance fixture `066`
(`LlmCompletionEvent.active_prompt_group`) was authored with a **single-member** group, directly
contradicting §10's two-or-more-members rule. It went undetected through authoring and acceptance;
the only thing that surfaced it was a reference implementation wiring the fixture into its harness
and finding its own `PromptGroup` constructor (which enforces ≥2) rejected the fixture's group. The
fixture was corrected in spec v0.74.1.

That episode is the argument for this proposal. A normative `MUST` with **no conformance fixture and
no defined error** is a latent cross-implementation divergence:

- An implementation that *doesn't* enforce ≥2 would pass the entire suite, because nothing tests
  rejection — the §10 rule is real but toothless.
- Worse, a fixture can silently violate the rule (as `066` did) without any guard catching it.

Closing the gap needs three things the spec lacks: (1) a pinned enforcement point, (2) an error the
conformance harness can assert against (prompt-management's error model is fully categorized — every
`raises:` assertion names a `category`), and (3) a fixture that exercises rejection.

## Proposed change

**§10 PromptGroup** — add an enforcement sentence alongside the existing two-or-more rule:

> Constructing a `PromptGroup` whose `members` contains fewer than two elements (an empty or
> single-member group) MUST raise `prompt_group_invalid` (§11). Enforcement is at **construction
> time** — the earliest point at which the member set is known — so an invalid group never reaches
> rendering, an LLM call, or observability emission.

**§11 Errors** — add a fourth canonical category, modeled on the existing `prompt_render_error` shape
(one coarse category with a list of triggers):

> - `prompt_group_invalid` — `PromptGroup` construction violated a §10 group-validity rule. Raised at
>   `PromptGroup` construction. Currently raised when:
>   - `members` contains fewer than two elements (an empty or single-member group), violating §10's
>     two-or-more-members rule.
>
>   Non-transient (a caller contract violation; constructing again with the same members will not
>   succeed without changing them). Future group-validity rules (e.g. duplicate or null members)
>   extend this trigger list under the same category rather than minting new ones.

**Conformance** — new fixtures under `spec/prompt-management/conformance/` exercising
`construct_prompt_group` (the existing group-construction directive, per fixture `011`) with an
invalid member count and asserting the raise.

## Conformance test impact

New fixtures (numbers assigned at Accept; appended after `034`), complementing `011`
(which covers only the valid N>2 case):

- **Single-member group rejected** — `construct_prompt_group` with one member asserts
  `raises: {category: prompt_group_invalid}` at construction.
- **Empty group rejected** — `construct_prompt_group` with zero members asserts the same.

No change to existing fixtures (`011`'s valid-group assertions are unaffected; the corrected `066`
already holds a valid two-member group).

## Versioning

**MINOR bump** (pre-1.0), additive: a new public error category (`prompt_group_invalid`), the pinned
enforcement of an already-stated `MUST`, and new fixtures. The valid-group contract is unchanged — no
existing conforming construction starts failing.

## Alternatives considered

1. **Leave construction rejection undefined (status quo).** Reject — that is precisely the gap that
   let `066` slip; cross-impl uniformity requires the error pinned and a fixture testing it.
2. **Reuse an existing §11 category.** Reject — `prompt_not_found` / `prompt_render_error` /
   `prompt_store_unavailable` are operational/runtime errors with no semantic fit for a construction
   precondition violation.
3. **A category-agnostic "construction raises" assertion shape instead of a named category.** Reject
   — prompt-management's error model is fully categorized (every `raises:` asserts a `category`); a
   one-off uncategorized raise would be the lone exception and would give no stable cross-impl signal
   to assert on.
4. **Enforce at render / first use rather than construction.** Reject — construction is the earliest
   point the member set is known and gives the fastest, clearest feedback; deferring to use permits an
   invalid group to exist transiently and pushes the error further from its cause.

## Open questions

None blocking — resolved during drafting:

- **Category name & generality — RESOLVED.** `prompt_group_invalid` (not the narrower
  `prompt_group_arity_invalid`), defined as a **general group-construction-validity category** with
  member-count (arity) as the currently-specified trigger — mirroring §11's existing
  `prompt_render_error` (one coarse category, a list of triggers). Future group-validity rules
  (duplicate / null members) add triggers under the same category rather than minting new ones. A
  dedicated category (vs. a category-agnostic construction-raises assertion shape) keeps the
  conformance harness asserting on a stable `category`, consistent with prompt-management's
  fully-categorized error model.

## Out of scope

- **The two-or-more-members rule itself** — it stands per §10; this proposal *enforces* it, it does
  not change it.
- **Construction-precondition validation for other spec objects** (`RuntimeConfig`, etc.) — scoped to
  `PromptGroup` here.
- **Member-content validation beyond count** (duplicate members, null members) — a future proposal if
  a need arises.
