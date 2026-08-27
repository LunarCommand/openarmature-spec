# 0123: Scope a Subgraph Declaration to the Graph Specification It Accompanies

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-21
- **Accepted:** 2026-08-27
- **Targets:**
  - spec/conformance-adapter/spec.md **§5.4 Composition directives**: state that a subgraph declaration
    (`subgraph:` or `subgraphs:`) is scoped to the **graph specification it accompanies**, and so appears
    wherever that specification does: at the document top level, inside a case, or inside a case's `graph:`
    block. §5.4 currently says "top level" three times and admits no other placement, while 20 shipped
    fixtures declare elsewhere and none of them carries a top-level block.
  - spec/conformance-adapter/spec.md **§5.4 preamble**: qualify the sentence introducing the section's
    directives, which scopes the whole section to `nodes.<node_name>:`. That is false for the declaration
    forms, which appear at none of the three sanctioned sites under a node. Left as is, §5.4 would state the
    placement rule and contradict it in the same section.
- **Related:** 0107 (documented the directive vocabulary these statements sit in)

## Summary

§5.4 documents subgraph declaration as a document-top-level construct, three times. Twenty shipped fixtures
across five capability areas declare it inside a case or inside a case's `graph:` block instead, and none of
them also declares at top level, so for those fixtures the documented location is empty. An adapter built
against §5.4 reads that location, finds nothing, and cannot construct them. This states all three
placements.

## Motivation

### The documented location is empty for twenty fixtures

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

Two fixtures settle it. Observability 008 declares `long_running_workflow` in two of its four cases, binding
it to a different body in each: the two bodies share a topology, and differ in the `step` node's behavior
directive (`update_pure` in one, `raises` in the other). Fixture 134 goes further, binding `leaf_sg` and `mid`
to structurally different bodies across two cases. A subgraph name bound to a different body per case cannot
be hoisted to one document-root declaration at all, in either direction, whether the difference is structural
or behavioral. The
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
> - at the fixture document's **top level**, where it is in scope for every case in the file;
> - inside an individual **case**, where it is visible to that case alone;
> - inside a case's **`graph:` block**, for a table fixture whose cases each carry a complete graph
>   specification.
>
> A top-level declaration alone suffices only when every case binds a given subgraph name to the same body,
> since one document-root declaration cannot express more than one body for a name. Where cases bind a name to
> different bodies, the differing bodies are declared at the narrower sites; a top-level declaration **MAY**
> still stand alongside them, and the resolution rule below decides which applies.
>
> Where a fixture declares the same subgraph name at more than one of these sites, an adapter **MUST** resolve
> that name using the innermost declaration that is in scope for the case being run, the three sites ranking
> from outermost to innermost in the order listed above: document top level, then case, then the case's
> `graph:` block. Where both declaration forms appear at the **same** site and bind the same name, the
> `subgraphs:` mapping entry governs, since it names the binding explicitly.

The resolution sentence is precautionary rather than descriptive: no shipped fixture declares at more than one
site, so it settles a collision the corpus does not contain. It is new behavior all the same, so it ships with
a fixture that exercises it (see *Conformance test impact*) rather than resting on the corpus being silent.
Two adapters left to choose would diverge on a fixture neither could be said to have failed.

### The §5.4 preamble

§5.4 introduces its directives with a sentence scoping the whole section to `nodes.<node_name>:`. That is
correct for the node-attached composition directives (`subgraph:` as a node's behavior, `fan_out:`,
`parallel_branches:`) and false for the declaration forms, which appear at none of the three sanctioned sites
under a node. Amending the placement rule while leaving that introduction intact would put the contradiction
inside one section rather than between two.
It is qualified so it introduces the node-attached composition directives without asserting where the
declaration forms go, deferring to *Subgraph declaration placement* for that.

## Conformance test impact

**One new fixture.** The precedence rule and the same-site tie-break are new behavior, so they are exercised
rather than asserted. A new conformance-adapter fixture carries three cases:

1. the same subgraph name declared at the **document top level** and inside a **case**, bound to a different
   body at each, asserting the case-level body executes;
2. the same name declared inside a **case** and inside that case's **`graph:` block**, bound to a different
   body at each, asserting the `graph:`-block body executes;
3. the same name declared at one site through both `subgraph:` and `subgraphs:`, asserting the `subgraphs:`
   mapping entry governs.

Cases 1 and 2 make both ranking steps observable; case 3 covers the tie-break the site ranking cannot decide.
Without them an adapter that ignored the ordering entirely would pass the suite.

**No existing fixture changes.** All 20 fixtures declaring outside the document root are correct as they stand
and none should move. The rest of the change is to the text that describes where the block may go.

**No new directive.** `subgraph:` and `subgraphs:` are unchanged in shape and meaning; only their permitted
placement is stated.

**§5.4 stops contradicting 20 shipped fixtures.** An adapter that already accepts the narrower placements,
which any adapter running the suite today must, is unaffected.

The claim is deliberately about the placement contradiction rather than about buildability, because for the
two `graph:`-block fixtures buildability needs one thing more: the per-case **`graph:` container** itself is
undocumented. §4.2's multi-case form puts `state:`, `entry:`, `nodes:` and `edges:` directly on the case, and
`graph:` appears nowhere in the conformance-adapter spec. This proposal states where a subgraph declaration
may sit, including inside that container; documenting the container is §4.2's business and is left to a
proposal that can survey the table-fixture shape as a whole. Observability 039 carries a related instance,
using `inner_subgraphs:` at case level and `fan_out.inner_subgraph:`, neither of which appears anywhere in
`spec/` outside a handful of observability fixtures. Both are undefined-directive instances of the kind
proposal 0120 scopes to a follow-on.

## Alternatives considered

1. **Do nothing.** Rejected: an adapter is entitled to build against §5.4, and one that does cannot
   construct 20 fixtures across five capability areas.
2. **Move the 20 fixtures to top-level declaration.** Rejected, and two of them make it impossible rather
   than merely undesirable: observability 008 binds `long_running_workflow` to two different bodies across
   two of its cases, and 134 binds `leaf_sg` and `mid` to structurally different bodies across two. One
   document-root declaration cannot express more than one body for a name. It would also churn shipped
   fixtures to match text rather than correcting text to match a deliberate shape.
3. **Sanction the narrower placements only**, retiring the top-level form. Rejected: 54 files use it, and it
   is the right shape when every case binds a given name to the same body.
4. **Scope the rule to two placements and defer the `graph:` block.** Rejected: it would leave §5.4 still
   contradicting graph-engine 007 and 041, which is the same defect this proposal exists to close, and the
   scoping rule that covers all three (the declaration belongs to the graph specification it accompanies) is
   no more complex than one enumerating two. Those two fixtures need §4.2's undocumented `graph:` container
   before an adapter can build them either way, but that is a separate gap and deferring the placement rule
   would add a second one.
5. **Leave §5.4 alone and document the case-level form in a per-directory note.** Rejected: the placement is
   used across five capability areas, so it is general rather than directory-local, and proposal 0120's
   definition-homes rule puts a general contract in §5.

## Open questions

1. **Whether the scoping rule should be stated once for every declaration form rather than for subgraphs
   alone.** "A declaration is scoped to the graph specification it accompanies" is a general principle, and
   §5.4 carries other composition forms. This proposal states it for the form whose misplacement is
   measured; whether the others share the shape is unmeasured and should not be assumed either way.
2. **Whether §4.2 should document the per-case `graph:` container.** This proposal sanctions a subgraph
   declaration inside a case's `graph:` block, but §4.2's multi-case form puts `state:`, `entry:`, `nodes:`
   and `edges:` directly on the case and never says a case may nest them under `graph:` instead. The key
   appears nowhere in the conformance-adapter spec. Six shipped fixtures use the container: graph-engine
   007, 041 and 042, and pipeline-utilities 065, 077 and 078. Two of those, graph-engine 007 and 041, also
   declare a subgraph inside it, which is the subset this proposal measures. The gap is a **schema**
   question rather than a vocabulary one: an adapter cannot parse such a case into a shape at all without
   knowing the container exists, so it is answerable on its own and does not wait on the open-versus-closed
   vocabulary question that proposal 0120 defers. It is a candidate for a small proposal against §4.2.
3. **Undefined composition keys adjacent to this one.** Observability 039 uses `inner_subgraphs:` at case
   level and `fan_out.inner_subgraph:`, neither of which appears anywhere in `spec/` outside a handful of
   observability fixtures. Unlike the `graph:` container these are vocabulary rather than schema, so they
   belong to the follow-on proposal 0120 scopes for directives with no definition in either home. Recorded
   here because they surfaced alongside the container and share its diagnosis: the fixture corpus uses
   composition shapes the spec never wrote down.
