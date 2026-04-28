# 0002: Subgraph Explicit Input/Output Mapping

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-04-16
- **Accepted:** 2026-04-27
- **Targets:** spec/graph-engine/spec.md (modifies §2 Subgraph)
- **Related:** 0001
- **Supersedes:**

## Summary

Add an optional explicit input/output mapping to subgraph composition, allowing graph authors to declare
which parent fields feed which subgraph fields on entry, and which subgraph fields merge back into which
parent fields on exit. When no mapping is declared, the §2 defaults established by proposal 0001 apply
unchanged: no projection in (the subgraph runs from its own schema defaults), and field-name matching for
projection out.

## Motivation

Proposal 0001 established two defaults for subgraph composition: **no projection in** (subgraphs run from
their own schema's field defaults, independent of the parent), and **field-name matching for projection
out** (subgraph fields whose names match parent fields merge back via the parent's reducers; non-matching
subgraph fields are discarded). Those defaults are simple and predictable, but they leave several real
composition needs unaddressed. Three cases that break down under the name-matching-only defaults:

1. **Reusable subgraphs.** A subgraph designed to be instantiated in multiple parent graphs becomes
   dependent on each parent using identical field names. If one parent calls its message field `message`
   and another calls it `chat_input`, the subgraph can serve only one without renaming its own schema —
   which defeats reuse.
2. **Same subgraph, two sites in one parent.** If a parent graph embeds the same subgraph twice (e.g.,
   a research subgraph run once per candidate in a list), both instances would read from and write to the
   same parent fields under name matching. The author needs a way to point each instance at different
   parent fields.
3. **Field-name collision on output.** A subgraph may declare internal scratch fields that happen to share
   names with parent fields. Under default name-matching projection-out, those scratch values would leak
   back into the parent. The subgraph author can avoid this only by renaming internal fields to be globally
   unique across every parent that uses the subgraph — burdensome and brittle.

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
> The two directions are independent: a subgraph-as-node MAY declare `inputs` only, `outputs` only, both,
> or neither.
>
> - When `inputs` is absent, the default from §2 applies: no projection in. The subgraph runs from its own
>   schema defaults.
> - When `inputs` is present, named parent fields are copied to their mapped subgraph fields at entry; all
>   other subgraph fields receive their schema-declared defaults.
> - When `outputs` is absent, the default from §2 applies: subgraph fields whose names match parent fields
>   are merged back via the parent's reducers; non-matching subgraph fields are discarded.
> - When `outputs` is present, it **replaces** field-name matching for projection-out: only the
>   parent/subgraph field pairs named in `outputs` are merged, via the parent's reducer for the named
>   parent field. All other subgraph fields are discarded.
>
> This asymmetry — `inputs` additive, `outputs` replacement — is intentional. It reflects the asymmetry in
> the §2 defaults themselves: projection-in is off by default (so `inputs` turns it on for listed fields),
> while projection-out is on by default via field-name matching (so `outputs` replaces it to avoid
> ambiguous mixed rules).
>
> Compilation MUST fail if an `inputs` mapping names a parent field that is not declared in the parent's
> state schema, or a subgraph field that is not declared in the subgraph's state schema. The same rule
> applies symmetrically to `outputs`.

**Precedence rationale (`outputs`).** Replace rather than extend. Falling through from `outputs` to
field-name matching for unlisted subgraph fields would produce confusing hybrid behavior where some
fields follow the explicit mapping and some follow the default, and authors would have to reason about
which fields they "forgot" to list. Clean replacement keeps the behavior predictable: if you declare an
`outputs` mapping, what you see is what you get.

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
