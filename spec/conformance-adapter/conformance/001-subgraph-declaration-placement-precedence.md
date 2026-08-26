# 001 — Subgraph Declaration Placement and Precedence

Verifies **conformance-adapter §5.4 *Subgraph declaration placement*** (proposal 0123): a subgraph
declaration is scoped to the graph specification it accompanies, so it may sit at the fixture document's
top level, inside an individual case, or inside a case's `graph:` block. Where the same subgraph name is
declared at more than one of those sites, an adapter resolves it using the **innermost** declaration in
scope for the case being run, the three sites ranking outermost to innermost as document top level, then
case, then the case's `graph:` block. Where **both declaration forms** appear at one site and bind the same
name, the `subgraphs:` mapping entry governs.

**This is the first fixture whose subject is the fixture format itself.** §5.4's rule binds *an
adapter*, and every assertion here turns on which declaration the adapter resolved while constructing
the graph. That choice is made before the engine runs. Subgraph composition is only the instrument
that makes it observable: any construct able to carry a distinguishable marker out of a resolved body
would serve, and nothing here can fail for a reason internal to graph-engine.

That is why `spec/conformance-adapter/conformance/` exists as of v0.114.0 and why this fixture opens
it. Every case runs an identical graph (one node, `{subgraph: pick, outputs: {resolved: which}}`) over
identically shaped subgraph bodies; only the marker each body writes and the site it is declared at
differ. A defect in subgraph composition would fail all four cases uniformly and identify nothing,
which is what distinguishes an instrument from a subject. The machinery itself is covered by
graph-engine fixtures 006, 011, 019 and 040, which vary it deliberately.

Before 0123, §5.4 stated the top-level placement three times and admitted no other, while 20 shipped
fixtures declared elsewhere. This fixture exercises the placement rule that replaced those statements, and
the precedence rule that placement makes necessary.

## How the assertions work

Each declaration of `pick` writes a distinct marker into its own `which` field. The subgraph-as-node
projects that field out through the explicit `outputs:` map (per fixture 011), so the parent's `resolved`
field records **which declaration the adapter actually resolved** rather than merely that one was found.

The document-level declaration stays in scope for all three cases and is shadowed in each. That is what
makes case 1 load-bearing: without an outer declaration to shadow, the case would only prove a case-level
declaration is accepted, not that it wins.

## Cases

1. **`case_level_declaration_shadows_top_level`** — `pick` is declared at the document top level
   (`which: "top-level"`) and inside the case (`which: "case-level"`). Asserts `resolved == "case-level"`.
   An adapter resolving outermost-first yields `"top-level"`.

2. **`graph_block_declaration_shadows_case_level`** — `pick` is declared at all three sites: document top
   level, case level (`which: "case-level"`), and inside the case's `graph:` block
   (`which: "graph-block"`). Asserts `resolved == "graph-block"`. An adapter that stops at the case level
   yields `"case-level"`; one resolving outermost-first yields `"top-level"`. This is the only case that
   exercises the full three-site ranking.

3. **`inline_declaration_at_inner_site_beats_mapping_at_outer_site`** — `pick` is declared at the document
   top level through the `subgraphs:` mapping (`which: "top-level"`) and inside the case through the
   **inline** form (`which: "case-inline"`), with no case-level mapping. Site ranks before form, so the
   inner declaration wins despite being the inline one. Asserts `resolved == "case-inline"`. An adapter
   that prefers any in-scope mapping over any inline declaration yields `"top-level"`.

4. **`subgraphs_mapping_governs_over_inline_subgraph_at_one_site`** — `pick` is declared twice at the same
   (case) site, once through the `subgraphs:` mapping (`which: "mapping"`) and once through inline
   `subgraph:` (`which: "inline"`). The site ranking cannot decide this, so the tie-break applies. Asserts
   `resolved == "mapping"`. An adapter preferring the inline form yields `"inline"`.

## Which wrong strategies each case catches

| Strategy | Caught by |
| --- | --- |
| Outermost-wins | all four |
| Stop at the case level, ignoring the `graph:` block | case 2 |
| Prefer the inline form where two forms meet | case 4 |
| Prefer any in-scope mapping over any inline form, ignoring site | case 3 |
| Flatten every declaration into one mapping, first write wins | all four |
| Flatten every declaration into one mapping, last write wins | case 4 |

Two of those need the cases arranged deliberately, and both arrangements look arbitrary until you know
why.

**Case 4 writes `subgraphs:` before the inline `subgraph:`.** Without that ordering the declaration that
must win is also the last one in document order in every case, so a resolver with no scoping model at
all, flattening every declaration into one mapping and letting the last write win, passes them all while
implementing neither the site ranking nor the tie-break. Document order carries no meaning for a
conforming adapter, which is what makes the ordering free to spend on denying that shortcut a pass. An
author tidying case 4 into `subgraph:`-then-`subgraphs:` order would silently reopen the hole.

**Case 3 makes the inner declaration the inline form.** Every other case puts the winning declaration in
a `subgraphs:` mapping, which never separates the site ranking from the form tie-break. An adapter
implementing "use the innermost in-scope mapping, falling back to an inline declaration only if no
mapping binds the name" passes the other three and is a different rule: it answers the outer mapping
where §5.4 answers the inner inline declaration. Case 3 is the only arrangement that tells the two
apart.

## Spec coverage

- **conformance-adapter §5.4** — *Subgraph declaration placement*, the sole subject: the three
  sanctioned sites, the innermost-in-scope resolution rule and its outermost-to-innermost site
  ranking, and the same-site tie-break between `subgraph:` and `subgraphs:`.
- **conformance-adapter §4.2** — *The `graph:` container*, exercised by case 2, which is the first
  container case in the corpus that executes rather than only compiling.

Graph-engine §2 subgraph composition and §5.4's `outputs:` projection are the **instruments** rather
than the subject. They carry the marker out of the resolved body; they are not what this fixture can
find a defect in.

## Notes

Case 2 uses a per-case `graph:` block. Six other fixtures use that container (graph-engine 007, 041
and 042; pipeline-utilities 065, 077 and 078), but **every one of their cases only compiles**: each is
`{name, graph, expected_compile_error}` or its warning variant, and none is ever invoked. Case 2 is the
first container case anywhere with `initial_state:` and `expected:` as case-level siblings of `graph:`,
and so the first that must execute.

That is why the same accept added **The `graph:` container** to §4.2. An adapter that implemented
`graph:` from the shipped corpus alone would have wired it into a compile-diagnostic path and had no
code path that runs such a case, and case 2 is the sole coverage of the newly normative third site, so
leaving the container undefined would have shipped that site with coverage no spec-derived adapter
could run. §4.2 now states that a container case asserting a runtime outcome MUST be executed.
