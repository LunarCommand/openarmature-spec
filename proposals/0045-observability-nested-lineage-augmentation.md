# 0045: Observability — Nested-Lineage Augmentation Containment Scope

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-29
- **Accepted:** 2026-05-30
- **Targets:** spec/observability/spec.md (§3.4 *Mid-invocation augmentation* — rewrite the ancestor / sibling boundary rule to be lineage-aware in nested cases; §3.4 *Per-async-context scoping* — add a per-depth lineage clarification covering nested fan-out / parallel-branches / fan-out-inside-subgraph variants; new conformance fixture exercising the nested cases)
- **Related:** 0040 (mid-invocation augmentation open-span update — this proposal extends the boundary rule from single-level to nested), 0034 (caller-supplied invocation metadata), 0011 (parallel branches), 0009 (per-instance fan-out resume), 0044 (parallel-branches dispatch span synthesis — adjacent observer-side surface)
- **Supersedes:**

## Summary

0040 introduced mid-invocation metadata augmentation with a per-async-
context boundary rule (§3.4) that is well-defined for single-level cases
(one fan-out instance, one parallel branch). The current boundary text
conflates "ancestor async context" with "sibling context": its example
explicitly says "relative to a fan-out instance's augmentation: the
invocation span and the shared fan-out-node span" MUST NOT be updated.
This is the correct behavior for single-level. In **nested** cases
(inner fan-out inside outer fan-out instance, parallel-branch inside
fan-out, fan-out inside serial subgraph), the outer-instance dispatch
span is an ancestor async context but is *specifically the augmenter's
own call-stack ancestor* — not a sibling.

This proposal clarifies §3.4 to be **lineage-aware**: a mid-invocation
augmentation applies to every span on the augmenter's call-stack
ancestor chain (including outer-instance dispatch spans, outer
parallel-branches dispatch spans, outer serial-subgraph wrapper spans),
and MUST NOT apply to siblings at any depth. The single-level behavior
is unchanged (the existing fixtures 029 / 030 / 034 stay correct); the
clarification settles what happens at nested boundaries.

## Motivation

Concrete case — inner fan-out inside outer fan-out instance:

```
outer_fan_out (items=[A, B, C])
└── inner_subgraph
    └── inner_fan_out (items=[x, y])
        └── inner_subgraph
            └── leaf  ← augments productId="A-x"
```

When the leaf in outer-instance #1 ("A") / inner-instance #0 ("x")
augments `productId="A-x"`, which spans should the augmentation
update?

| Span | Should update? | Why |
|---|---|---|
| The leaf's own span | YES | Augmenter's own context. |
| The inner-fan-out instance #0 dispatch span | YES | Augmenter's immediate dispatch ancestor. Matches the accepted single-level §3.4 rule. |
| The **outer-fan-out instance #1 dispatch span** | YES (under this proposal) | Augmenter's *next-outer* call-stack ancestor; specific to "A"; NOT shared with siblings ("B", "C"). |
| The outer-fan-out NODE span (shared across A/B/C) | NO | Shared parent; updating it would leak the per-A augmentation across siblings. |
| Inner-fan-out instance #1's dispatch span ("y") | NO | Sibling at the inner depth; not on the augmenter's call-stack path. |
| Outer-fan-out instance #0 / #2 dispatch spans ("B", "C") | NO | Siblings at the outer depth. |
| Invocation span | NO | Above the outer fan-out node; updating it would leak across all instances. |

The current §3.4 boundary text is ambiguous on the outer-instance
dispatch span row — its strict "ancestor async context MUST NOT be
updated" wording reads as forbidding the update, but the *intent* (per
the existing "no sibling leakage" framing) supports it.

The same pattern repeats for parallel-branch-inside-fan-out (the
augmenter's outer fan-out instance dispatch span is in scope; sibling
branches and sibling instances are NOT) and fan-out-inside-serial-
subgraph (the augmenter's outer serial-subgraph wrapper span is in
scope, since the wrapper is on the call-stack path and is not shared
with siblings — there are no siblings of a serial wrapper).

## Detailed design

The proposed normative changes are below. Anticipated bump: **MINOR**
(pre-1.0).

### observability §3.4 — *Mid-invocation augmentation*: rewrite the ancestor / sibling boundary text

The current "Ancestor / sibling boundary (MUST NOT)" paragraph is
replaced with a **lineage-aware** rule:

> **Augmenter's call-stack ancestor chain (MUST).** Spans opened in
> async contexts that are ANCESTORS of the augmenting async context **on
> the augmenter's specific call-stack path** MUST be updated by the
> augmentation, where the backend SDK supports in-place attribute /
> metadata update. The augmenter's call-stack ancestor chain is the
> sequence of dispatch-context boundaries the augmenter crossed to reach
> the augmenting context — each outer fan-out instance dispatch, each
> outer parallel-branches branch dispatch, each outer serial-subgraph
> wrapper. Each such ancestor context's open spans (the corresponding
> dispatch / wrapper span and any open node spans within it that share
> the same call-stack path) MUST be updated.
>
> **Sibling boundary (MUST NOT).** Spans opened in a **sibling**
> async context — another fan-out instance at any depth, another
> parallel-branches branch at any depth — MUST NOT be updated by the
> augmentation. The augmentation is per-call-stack-path, not
> per-fan-out-node and not per-invocation: siblings get their own copies
> of the metadata mapping at dispatch time (see *Per-async-context
> scoping* below), and the augmenter's mutation does not leak across
> the sibling boundary.
>
> **Shared-parent boundary (MUST NOT).** Spans for a SHARED parent (the
> fan-out node itself, the parallel-branches node itself, the
> invocation span) MUST NOT be updated. A shared parent is by definition
> visible to multiple sibling instances / branches; updating it would
> propagate the augmentation to siblings indirectly. Identify a shared
> parent by: a span whose async context is an ancestor of MULTIPLE
> sibling instance / branch contexts (i.e., the fork point above the
> dispatch).
>
> The decision tree, applied to each open span at augmentation time:
>
> 1. Is the span's opening context the augmenting context itself, or a
>    descendant of it? → **Update** (per the existing same-context rule).
> 2. Is the span's opening context on the augmenter's call-stack
>    ancestor path (a strict dispatch ancestor, not a shared parent)?
>    → **Update.**
> 3. Is the span's opening context a sibling of any context on the
>    augmenter's call-stack path, or a shared parent at any depth?
>    → **Do not update.**

### observability §3.4 — *Per-async-context scoping*: per-depth lineage clarification

A clarifying paragraph follows the existing per-async-context scoping
text:

> **Per-depth lineage tracking.** Implementations track the metadata
> mapping per async context, but the per-call-stack-ancestor update
> requirement above means implementations MUST also track the *lineage*
> of dispatch contexts the augmenter has crossed (the chain of outer
> fan-out instances, outer parallel-branches branches, and outer serial
> subgraphs on the augmenter's path). This lineage is naturally
> available to the engine's dispatch machinery: each `descend_into_*`
> step pushes a new dispatch boundary onto the active call stack and
> the boundary's identity is observable from the engine's internal
> state. Implementations MUST NOT overwrite per-depth identifiers (e.g.,
> a single scalar `fan_out_index` ContextVar that gets clobbered at each
> nested descent) — when applying an augmentation, the observer needs
> the full call-stack ancestor chain to find the right open spans.

### observability §3.4 — backward compatibility note

The single-level behavior (one fan-out instance OR one parallel branch,
no nested dispatch) is unchanged: the existing fixtures 029 / 030 / 034
exercise single-level scope and their assertions remain correct under
the lineage-aware rule (when there is only one dispatch on the
augmenter's path, the call-stack ancestor chain has length one — the
augmenter's immediate dispatch context — and the update set is
identical to the single-level rule).

## Conformance test impact

### New fixture

A new fixture under `observability/conformance/` (number assigned at
acceptance) exercises three nested-case variants:

1. **Inner fan-out inside outer fan-out instance.** Two-level fan-out
   nesting. Augmenter at the leaf in outer-instance #1 / inner-instance
   #0 augments `productId="A-x"`. Asserts:
   - Leaf's own span carries the augmented metadata.
   - Inner-instance #0 dispatch span carries the augmented metadata.
   - **Outer-instance #1 dispatch span carries the augmented metadata**
     (the new lineage-aware-scope requirement).
   - Outer-fan-out NODE span does NOT carry the augmented metadata
     (shared parent).
   - Outer-instance #0 / #2 dispatch spans (siblings) do NOT carry it.
   - Inner-instance #1 of outer-instance #1 (sibling at inner depth)
     does NOT carry it.
   - Invocation span does NOT carry it.

2. **Parallel-branch inside fan-out instance.** A fan-out instance
   contains a parallel-branches node; augmenter is a leaf inside
   branch X of inner parallel-branches inside outer-instance #1.
   Asserts:
   - Leaf's own span + branch-X dispatch span + outer-instance #1
     dispatch span all carry the augmented metadata.
   - Branch Y dispatch span (sibling) does NOT.
   - Other outer-instance dispatch spans (siblings) do NOT.
   - Parallel-branches NODE span, outer fan-out NODE span,
     invocation span do NOT.

3. **Fan-out inside serial subgraph.** A serial subgraph wrapper
   contains a fan-out node; augmenter is a leaf inside fan-out
   instance #1 of that inner fan-out. Asserts:
   - Leaf's own span + inner-instance #1 dispatch span + outer serial
     subgraph wrapper span all carry the augmented metadata.
   - Inner-instance #0 / #2 dispatch spans (siblings of #1) do NOT.
   - The inner fan-out NODE span does NOT (shared parent of all
     instances).
   - Invocation span does NOT.

### Unaffected

Existing single-level augmentation fixtures (`029-caller-metadata-fan-out-per-instance`,
`030-caller-metadata-parallel-branches-per-branch`, `034-caller-metadata-open-span-update-serial`)
remain unchanged — the lineage-aware rule reduces to the single-level
rule when the call-stack ancestor chain has length one.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments:

- §3.4 *Mid-invocation augmentation* boundary text rewritten to be
  lineage-aware (loosening — outer-instance dispatch spans now
  updated where the current text was ambiguous-or-not-updated).
- §3.4 *Per-async-context scoping* extended with a per-depth lineage
  tracking clarification.
- New conformance fixture exercising three nested variants.

Single-level fixtures and emission behavior are unchanged. The
loosening expands the set of spans that carry augmented metadata in
nested cases — backwards-compatible for observers / backends that
already handle the metadata (more spans now carry it; none get less).
Implementations that internally use a single scalar FI / BN ContextVar
that gets overwritten on nested descent need to track per-depth
lineage instead; this is internal mechanics, not an observable API
break.

## Out of scope

- **New `openarmature.*` lineage attributes.** Augmentation continues to
  propagate via the existing `openarmature.user.*` family (§5.6); no
  new attribute family is introduced. The new conformance fixture
  asserts the `openarmature.user.<key>` family appears on the right
  set of open spans, not a new attribute name.
- **Specific implementation data structure for the lineage chain.** A
  python `MetadataAugmentationEvent` carrying tuple-typed lineage
  fields, a TypeScript per-`AsyncLocalStorage` chain, or any other
  equivalent satisfies the per-depth lineage tracking requirement —
  per-language idiomatic.
- **Re-applying augmentation to already-closed ancestor spans.** The
  existing closed-spans rule (§3.4: "Spans already closed are NOT
  retroactively updated") still applies. The lineage-aware rule
  expands which OPEN spans get the update; closed-span behavior is
  unchanged.
- **Detached subgraph / fan-out propagation.** Detached children
  already get their own context copy per the existing §3.4 rule;
  this proposal does not change detached propagation.

## Alternatives considered

- **Strict per-async-context copy-on-write extends to nested cases
  unchanged.** The outer-instance dispatch span is NOT updated (per
  the current text's literal reading). Rejected: less useful for
  filtering ("show me all spans for this specific outer instance"
  doesn't work at the augmented-metadata level), and the rule's
  intent (per the "no sibling leakage" framing) supports updating
  the augmenter's own call-stack ancestor.
- **Specify only the event shape; defer the scope decision.**
  Extend the augmentation event to carry per-depth lineage
  information but leave the scope rule (which spans update) for a
  future proposal. Rejected: kicks the actual design question down
  the road. The event-shape extension is a *consequence* of the
  scope decision, not an independent choice — without settling the
  scope, implementations don't know what to do with the chain.
- **Do nothing.** Leave the nested case under-specified. Rejected:
  the v0.11.0 batch deliberately addresses the gap so downstream
  implementations have a defined contract for nested fan-out /
  parallel-branches usage.
- **Apply augmentation to ALL ancestor contexts including shared
  parents and invocation.** Maximally inclusive. Rejected: shared
  parents are by definition visible to multiple sibling instances;
  updating them would leak the per-instance augmentation across
  siblings indirectly — exactly what the per-async-context scoping
  is designed to prevent.
