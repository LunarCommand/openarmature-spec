# 0002: Subgraph Explicit Input/Output Mapping

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-16
- **Accepted:**
- **Targets:** spec/graph-engine/spec.md (modifies §2 Subgraph)
- **Related:** 0001
- **Supersedes:**

## Summary

Add an optional explicit input/output mapping to subgraph composition, allowing graph authors to declare
which parent fields feed which subgraph fields on entry, and which subgraph fields merge back into which
parent fields on exit. When no mapping is declared, field-name matching (the default established by
proposal 0001) applies unchanged.

## Motivation

Proposal 0001 established field-name matching as the default projection rule between parent and subgraph
state. That default is ergonomic when schemas align by name, but it forces tight coupling between a
subgraph's field names and every parent that wants to use it. Three real cases break down under
name-matching-only:

1. **Reusable subgraphs.** A subgraph designed to be instantiated in multiple parent graphs becomes
   dependent on each parent using identical field names. If one parent calls its message field `message`
   and another calls it `chat_input`, the subgraph can serve only one without renaming its own schema —
   which defeats reuse.
2. **Same subgraph, two sites in one parent.** If a parent graph embeds the same subgraph twice (e.g.,
   a research subgraph run once per candidate in a list), both instances would read from and write to the
   same parent fields under name matching. The author needs a way to point each instance at different
   parent fields.
3. **Partial projection.** A subgraph may declare fields that the parent should *not* supply (e.g.,
   internal scratch state the subgraph initializes itself). Name matching either over-shares or forces
   the subgraph to rename its internal fields to avoid collision.

Without explicit mapping, authors work around these by inserting pre/post-processing nodes that shuffle
state, which is boilerplate that belongs in graph composition, not in user code.

## Detailed design

Add the following to §2 Subgraph of `spec/graph-engine/spec.md`, after the field-name-matching paragraph
introduced by proposal 0001:

> **Explicit input/output mapping.** A subgraph-as-node MAY declare an `inputs` mapping, an `outputs`
> mapping, or both:
>
> - `inputs`: a mapping from subgraph field name → parent field name. For each entry, the parent field's
>   current value is copied to the subgraph's corresponding field at entry. Subgraph fields not named in
>   `inputs` receive their schema-declared default — they are NOT filled by field-name matching as a
>   fallback.
> - `outputs`: a mapping from parent field name → subgraph field name. For each entry, the subgraph's
>   final value for the named subgraph field is merged into the corresponding parent field via the
>   parent's reducer for that field. Subgraph fields not named in `outputs` are discarded — they do NOT
>   fall through to field-name matching.
>
> When `inputs` is present, it **replaces** field-name matching for projection-in. When `outputs` is
> present, it **replaces** field-name matching for projection-out. The two directions are independent:
> a subgraph-as-node MAY declare `inputs` only, `outputs` only, both, or neither (in which case the
> default field-name-matching rule from §2 applies to both directions).
>
> Compilation MUST fail if an `inputs` mapping names a parent field that is not declared in the parent's
> state schema, or a subgraph field that is not declared in the subgraph's state schema. The same rule
> applies symmetrically to `outputs`.

**Precedence rationale.** Replace rather than extend. Falling through from explicit mapping to field-name
matching would produce confusing hybrid behavior where some fields follow one rule and some follow
another, and authors would have to reason about which fields they "forgot" to list. Making explicit
mapping a clean replacement keeps the behavior predictable: if you declare a mapping, what you see is
what you get.

**Type compatibility.** Implementations SHOULD validate at compile time that the types of mapped
parent/subgraph field pairs are compatible (per the language's type system's notion of compatibility).
This is SHOULD rather than MUST because type-system expressiveness varies across languages.

## Conformance test impact

Add one new fixture:

**`011-subgraph-explicit-mapping`** — a subgraph reused twice in one parent graph, each instance with a
different `inputs`/`outputs` mapping. Verifies:

- Input mapping copies only named parent fields into the subgraph; non-mapped subgraph fields receive
  their schema defaults (no field-name fallback).
- Output mapping merges only named subgraph fields back into the parent; non-mapped subgraph fields are
  discarded.
- The same subgraph instance produces different contributions to parent state under different mappings.
- `inputs`-only and `outputs`-only cases behave as documented.

One new compile-error case is added to fixture `007-compile-errors`:

- `mapping_references_undeclared_field` — an `inputs` or `outputs` mapping names a field that is not
  declared in either the parent or subgraph state schema.

## Alternatives considered

**Do nothing.** Leaves reusable and multiply-embedded subgraphs dependent on parent naming; forces users
to write pre/post-shuffle nodes. Rejected for the reasons in Motivation.

**Allow mapping with field-name-matching fallback for unlisted fields.** Considered and rejected because
the behavior of "fields that appear by name in both schemas but weren't listed" becomes subtle — authors
would need to remember which fields they declared to mean "don't project" vs. which they forgot. Clean
replacement is easier to reason about.

**Subgraph-level rename (let the subgraph declare aliases for its own fields).** Would help the
reusable-subgraph case but not the same-subgraph-in-two-places case, because the subgraph's schema is
fixed at compile time and can't express "this instance reads from `x`, that instance reads from `y`."
Wrong layer.

**Wire-level projection DSL.** A richer transformation language (project, rename, filter, compute) would
cover more cases but drags in expression semantics and would need its own spec surface. Out of proportion
for the current need. If composition pressures warrant it later, a follow-on proposal can introduce it;
this proposal keeps the mechanism small.

## Open questions

None at time of submission.
