# 0123: Sanction Case-Level Subgraph Declaration

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-21
- **Accepted:**
- **Targets:**
  - spec/conformance-adapter/spec.md **§5.4 Composition directives**: state that a subgraph declaration
    (`subgraph:` or `subgraphs:`) MAY appear at the document top level **or** inside a case, and that the
    case-level placement is the one to use when the topology differs per case. §5.4 currently says "top
    level" three times and admits no other placement, while 18 shipped fixtures declare inside a case and
    none of them carries a top-level block.
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

Sweeping every fixture file for a `subgraph` or `subgraphs` key:

| Placement | Files |
|---|---|
| Document top level | 54 |
| Inside a case | 18 |
| Both in one file | 0 |

The 18 span four capability areas: observability (9), suspension (5), pipeline-utilities (2), sessions (2).
Because no file uses both placements, an adapter that reads only the documented location finds nothing for
all 18 and cannot build them. That is a portability break rather than a wording nit: the failure surfaces as
a missing-key error that reads like an absent directive rather than a placement difference, which is how it
was found downstream.

### The case-level shape is correct, not a drift

Several of the 18 are multi-case files with the block on only some cases. A topology that differs per case
cannot be hoisted to the document root without either duplicating every case's graph or inventing a
per-case override. The fixtures are right and the spec never caught up.

This is the same class of defect proposal 0120 addresses for a directive's **definition**, one level over:
there the question was where a definition may live, here it is where a usage may be placed. Both were
settled in practice by the corpus and left unstated in the text.

## Detailed design

Amend §5.4's three statements so placement is stated once and covers both forms:

> **Subgraph declaration placement.** A subgraph declaration (`subgraph:` for a single inline subgraph,
> `subgraphs:` for a named mapping) MAY appear at the fixture document's top level, where it is visible to
> every case in the file, **or** inside an individual case, where it is visible to that case alone. An
> adapter MUST accept both placements.
>
> Use the case-level placement when the topology differs per case; a per-case topology cannot be hoisted to
> the document root. Use the top-level placement when every case in the file shares one topology. A fixture
> SHOULD NOT declare the same subgraph name in both places in one file, and where it does, the case-level
> declaration governs for that case.

The last sentence is precautionary rather than descriptive: no shipped fixture uses both placements, so it
resolves a collision the corpus does not currently contain, and it is stated so that an adapter has an answer
if one appears.

## Conformance test impact

**No fixture changes.** All 18 case-level fixtures are correct as they stand and none should move. The
change is to the text that describes where they may put the block.

**No new directive.** `subgraph:` and `subgraphs:` are unchanged in shape and meaning; only their permitted
placement is stated.

**An adapter built strictly against the current §5.4 gains 18 buildable fixtures.** An adapter that already
accepts either placement, which any adapter running the suite today must, is unaffected.

## Alternatives considered

1. **Do nothing.** Rejected: an adapter is entitled to build against §5.4, and one that does cannot
   construct 18 fixtures across four capability areas.
2. **Move the 18 fixtures to top-level declaration.** Rejected: several are multi-case with per-case
   topologies, which cannot be hoisted without duplicating each case's graph. It would also churn shipped
   fixtures to match text rather than correcting text to match a deliberate shape.
3. **Sanction case-level only**, retiring the top-level form. Rejected: 54 files use it, and it is the right
   shape when every case shares a topology.
4. **Leave §5.4 alone and document the case-level form in a per-directory note.** Rejected: the placement is
   used across four capability areas, so it is general rather than directory-local, and proposal 0120's
   definition-homes rule puts a general contract in §5.

## Open questions

None. The corpus settles which placements are in use, the multi-case fixtures settle why the case-level form
exists, and the collision rule is stated for a case that does not yet occur.
