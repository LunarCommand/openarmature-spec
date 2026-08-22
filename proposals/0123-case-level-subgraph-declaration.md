# 0123: Sanction Case-Level Subgraph Declaration

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-21
- **Accepted:**
- **Targets:**
  - spec/conformance-adapter/spec.md **§5.4 Composition directives**: state that a subgraph declaration
    (`subgraph:` or `subgraphs:`) is scoped to the **graph specification it accompanies**, and so appears
    wherever that specification does: at the document top level, inside a case, or inside a case's `graph:`
    block. §5.4 currently says "top level" three times and admits no other placement, while 20 shipped
    fixtures declare elsewhere and none of them carries a top-level block.
  - spec/conformance-adapter/spec.md **§5.4 preamble**: qualify the sentence introducing the section's
    directives, which asserts the placement the rule above corrects. Left as is, §5.4 would state the
    placement rule and contradict it in the same section.
- **Related:** 0107 (documented the directive vocabulary these statements sit in)

## Summary

§5.4 documents subgraph declaration as a document-top-level construct, three times. Eighteen shipped
fixtures across four capability areas declare it inside a case instead, and none of them also declares at
top level, so for those fixtures the documented location is empty. An adapter built against §5.4 reads that
location, finds nothing, and cannot construct them. This states both placements.

## Motivation

### The documented location is empty for eighteen fixtures

§5.4 says, in three separate statements: a node "executes a named subgraph (declared at fixture top level
via `subgraph:` or `subgraphs:` mapping)"; "**Subgraph declaration via top-level `subgraph:`**"; and
"**Subgraph declaration via top-level `subgraphs:`**".

Sweeping every fixture file positionally, for a `subgraph` or `subgraphs` key at any structural site:

| Site | Declarations | Files |
|---|---|---|
| Document top level | 54 | 54 |
| Inside a case | 24 | 18 |
| Inside a case's `graph:` block | 3 | 2 |
| Any file using more than one site | | 0 |

The 18 case-level files span four capability areas: observability (9), suspension (5), pipeline-utilities (2),
sessions (2). The two `graph:`-block files are graph-engine 007 and 041, table fixtures whose every case
carries a complete graph definition under `graph:` because the case *is* the graph under test.

Because no file uses more than one site, an adapter that reads only the documented location finds nothing for
all 20 and cannot build them. That is a portability break rather than a wording nit: the failure surfaces as a
missing-key error that reads like an absent directive rather than a placement difference, which is how it was
found downstream.

### The other placements are correct, not drift

Two fixtures settle it. Observability 008 declares `long_running_workflow` in four cases with a different body
in each, and 134 does the same for `leaf_sg` and `mid` across two. A subgraph name bound to different
topologies per case cannot be hoisted to one document-root declaration at all, in either direction. The
`graph:`-block form is the same principle one level further in: the declaration belongs to the graph
specification it accompanies, and in a table fixture that specification is per-case.

The fixtures are right and the spec never caught up.

This is the same class of defect proposal 0120 addresses for a directive's **definition**, one level over:
there the question was where a definition may live, here it is where a usage may be placed. Both were
settled in practice by the corpus and left unstated in the text.

## Detailed design

Amend §5.4's three statements so placement is stated once and covers both forms:

> **Subgraph declaration placement.** A subgraph declaration (`subgraph:` for a single inline subgraph,
> `subgraphs:` for a named mapping) is scoped to the graph specification it accompanies, and an adapter
> **MUST** accept it wherever that specification appears:
>
> - at the fixture document's **top level**, where it is visible to every case in the file;
> - inside an individual **case**, where it is visible to that case alone;
> - inside a case's **`graph:` block**, for a table fixture whose cases each carry a complete graph
>   specification.
>
> The top-level placement is available when every case in the file shares one topology. The narrower
> placements are required when it does not, since a subgraph name bound to a different topology per case
> cannot be expressed by one document-root declaration.
>
> Where a fixture declares the same subgraph name at more than one of these sites, an adapter **MUST**
> resolve that name to the narrowest declaration in scope for the case being run.

The resolution sentence is precautionary rather than descriptive: no shipped fixture declares at more than one
site, so it settles a collision the corpus does not contain. It ships **unexercised by any fixture**, which is
stated here rather than left for a reader to discover. That is acceptable for a rule whose only job is to give
an adapter a determinate answer where the corpus is silent, and a fixture can be added by the first proposal
that needs the shape. What it must not be is unstated, since two adapters left to choose would diverge on a
fixture neither could be said to have failed.

### The §5.4 preamble

§5.4 introduces its directives with a sentence asserting the top-level placement. Amending the placement rule
while leaving that introduction intact would put the contradiction inside one section rather than between two.
It is qualified so it introduces the node-behavior directives without asserting where the declaration forms
go, deferring to *Subgraph declaration placement* for that.

## Conformance test impact

**No fixture changes.** All 20 fixtures declaring outside the document root are correct as they stand and none
should move. The change is to the text that describes where the block may go.

**No new directive.** `subgraph:` and `subgraphs:` are unchanged in shape and meaning; only their permitted
placement is stated.

**An adapter built strictly against the current §5.4 gains 20 buildable fixtures.** An adapter that already
accepts the narrower placements, which any adapter running the suite today must, is unaffected.

## Alternatives considered

1. **Do nothing.** Rejected: an adapter is entitled to build against §5.4, and one that does cannot
   construct 18 fixtures across four capability areas.
2. **Move the 20 fixtures to top-level declaration.** Rejected, and two of them make it impossible rather
   than merely undesirable: observability 008 binds `long_running_workflow` to a different topology in each
   of four cases, and 134 does the same for two names. One document-root declaration cannot express that. It
   would also churn shipped fixtures to match text rather than correcting text to match a deliberate shape.
3. **Sanction the narrower placements only**, retiring the top-level form. Rejected: 54 files use it, and it
   is the right shape when every case shares a topology.
5. **Scope the rule to two placements and defer the `graph:` block.** Rejected: it would leave graph-engine
   007 and 041 unbuildable by an adapter following the amended text, which is the same defect this proposal
   exists to close, and the scoping rule that covers all three (the declaration belongs to the graph
   specification it accompanies) is no more complex than one enumerating two.
4. **Leave §5.4 alone and document the case-level form in a per-directory note.** Rejected: the placement is
   used across four capability areas, so it is general rather than directory-local, and proposal 0120's
   definition-homes rule puts a general contract in §5.

## Open questions

1. **Whether the scoping rule should be stated once for every declaration form rather than for subgraphs
   alone.** "A declaration is scoped to the graph specification it accompanies" is a general principle, and
   §5.4 carries other composition forms. This proposal states it for the form whose misplacement is
   measured; whether the others share the shape is unmeasured and should not be assumed either way.
