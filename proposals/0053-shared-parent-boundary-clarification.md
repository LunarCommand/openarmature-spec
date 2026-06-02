# 0053: §3.4 Shared-Parent Boundary Clarification (Invocation Span)

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-01
- **Accepted:** 2026-06-01
- **Targets:** spec/observability/spec.md (§3.4 *Shared-parent boundary (MUST NOT)* paragraph — tightens the structural-shared-parent classification to explicitly carve out the invocation span as a conditional shared parent rather than an unconditional one; the invocation span is structurally a shared parent ONLY when at least one fan-out or parallel-branches dispatch is on the augmenter's call-stack path. The §3.4 *Three-step boundary decision tree* rule 3 picks up matching wording. No conformance fixture impact — existing fixtures 034 (outermost-serial augmentation) and 039 (nested-lineage cases) already exercise the predicate-derived behavior; this proposal closes the spec-text ambiguity that previously made the two fixtures' apparent contradiction unresolvable from §3.4's text alone.
- **Related:** 0040 (mid-invocation augmentation open-span update — established the §3.4 augmentation mechanism and the initial ancestor / sibling boundary rule), 0045 (nested-lineage augmentation containment scope — rewrote §3.4's boundary as the three lineage-aware rules this proposal tightens)
- **Supersedes:**

## Summary

Proposal 0045 (nested-lineage augmentation containment scope)
rewrote observability §3.4's ancestor / sibling boundary into
three lineage-aware rules: augmenter's call-stack ancestor chain
MUST update, sibling MUST NOT update, shared-parent MUST NOT
update. The shared-parent rule classifies the invocation span as
a structural shared parent "regardless of runtime cardinality" —
intending to capture the case where the invocation span sits above
a fan-out fork and is visible to multiple sibling instances.

But in the **pure-serial case** (an augmenter inside a node that
runs in the outermost serial context, with no fan-out or
parallel-branches dispatch on the call-stack path), the invocation
span has no sibling instances to leak to. The original 0040
boundary rule treated this case as "update the invocation span"
(per fixture 034). 0045's text — by phrasing the shared-parent
classification as unconditional on the invocation span — created
a tension: a strict reading of §3.4 says "never update the
invocation span," but fixture 034 expects it to be updated in the
outermost-serial case.

The reconciliation is an explicit `outermost_serial` predicate:
the invocation span is treated as a shared parent ONLY when at
least one fan-out or parallel-branches dispatch is on the
augmenter's call-stack path. When the augmenter's lineage chain
has only `null` entries (pure-serial descent through subgraph
wrappers, no fork), the invocation span is on the call-stack
ancestor path and gets updated per rule 2.

This proposal tightens §3.4's *Shared-parent boundary* paragraph
to make the predicate explicit. The change is documentary — it
records the predicate that fixture 034 + fixture 039 already
exercise, removing the spec-text ambiguity for future readers.
No conformance fixture impact.

## Motivation

0045's text intent was sound — the rule it added covers the
common nested case correctly. But the "regardless of runtime
cardinality" framing over-applied to the invocation span. When
read strictly:

- The fan-out node span IS a shared parent regardless of
  cardinality (degenerate single-instance fan-outs still have the
  structural risk of being a dispatcher — siblings could exist
  even if they don't at runtime). ✓
- The parallel-branches node span IS a shared parent regardless
  of cardinality (same logic). ✓
- The invocation span IS the root of every invocation. The
  "regardless of cardinality" framing implies it's always a
  shared parent — but there's nothing to share with when no
  fan-out or parallel-branches dispatch has occurred. The pure-
  serial case has only one async context, one path through the
  graph, no siblings. The structural-shared-parent classification
  doesn't fit.

The ambiguity surfaced when the spec text said one thing (don't
update invocation span) but the fixture set said another (do
update it in outermost-serial). The predicate-derived reading is
the resolution — fixture 034 + 039 are correct; the spec text
needs tightening.

This proposal tightens the spec text to match the predicate
without changing the rule's substance. Future readers see the
conditional-shared-parent framing explicitly and don't have to
reconcile fixture 034 against §3.4's "regardless of cardinality"
wording.

## Proposed change

### observability §3.4 — *Shared-parent boundary (MUST NOT)* paragraph

The §3.4 *Shared-parent boundary (MUST NOT)* paragraph currently
reads (per spec v0.37.0 from proposal 0045):

> **Shared-parent boundary (MUST NOT).** Spans for a SHARED parent
> (the fan-out node itself, the parallel-branches node itself, the
> invocation span) MUST NOT be updated. A shared parent is by
> definition visible to multiple sibling instances / branches;
> updating it would propagate the augmentation to siblings
> indirectly. Identify a shared parent structurally by dispatch-
> node type — any span representing a fan-out node, any span
> representing a parallel-branches node, and the invocation span —
> regardless of runtime cardinality. The rule applies even in
> degenerate cases (a fan-out over a single-element list, a
> parallel-branches dispatcher with one branch) where no sibling
> exists at runtime: the structural classification governs, not
> the live sibling count.

This proposal replaces the paragraph with:

> **Shared-parent boundary (MUST NOT).** Spans for a SHARED parent
> MUST NOT be updated. A shared parent is by definition visible to
> multiple sibling instances / branches; updating it would
> propagate the augmentation to siblings indirectly.
>
> Identify a shared parent structurally:
>
> - **Fan-out node span** — always a shared parent. Identified
>   structurally by dispatch-node type; the rule applies even in
>   degenerate cases (a fan-out over a single-element list) where
>   no sibling instance exists at runtime — the structural
>   classification governs, not the live sibling count.
> - **Parallel-branches node span** — always a shared parent. Same
>   structural-classification rule; applies even in degenerate
>   cases (a parallel-branches dispatcher with one branch).
> - **Invocation span** — a shared parent **only when at least one
>   fan-out or parallel-branches dispatch is on the augmenter's
>   call-stack path**. Concretely: the augmenter's lineage chain
>   (per the *Per-depth lineage tracking* paragraph below) contains
>   at least one non-`null` `fan_out_index` or `branch_name` entry.
>   When the chain has only `null` entries (pure-serial descent —
>   no fork occurred between the invocation entry and the
>   augmenter), the invocation span is on the augmenter's
>   call-stack ancestor path and is NOT a shared parent; it gets
>   updated per the *Augmenter's call-stack ancestor chain (MUST)*
>   rule above.
>
> The structural framing applies to the fan-out and parallel-
> branches node spans (whose dispatcher nature is intrinsic to
> their identity); the invocation span's classification is
> conditional on whether any dispatcher has fired on the
> augmenter's path. This matches the existing fixture 034
> behavior (outermost-serial augmentation reaches the invocation
> span) and the fixture 039 behavior (nested cases do not reach
> the invocation span because at least one fan-out or
> parallel-branches dispatch is on the path).

### observability §3.4 — *Three-step boundary decision tree* rule 3

The decision tree's rule 3 currently reads:

> 3. Is the span's opening context a sibling of any context on the
>    augmenter's call-stack path, OR a shared parent at any depth?
>    → **Do not update.**

This proposal leaves the rule's text unchanged but adds a short
trailing parenthetical pointing readers at the tightened
classification:

> 3. Is the span's opening context a sibling of any context on the
>    augmenter's call-stack path, OR a shared parent at any depth
>    (per the conditional invocation-span classification above)?
>    → **Do not update.**

The "shared parent at any depth" phrasing already reads correctly
under the tightened *Shared-parent boundary* paragraph above — in
the pure-serial case, no fork exists and therefore no shared
parent exists at any depth. The added parenthetical is purely a
navigation hint so a reader of just the decision tree knows where
the "shared parent" classification is defined.

## Conformance test impact

**None.** Existing fixtures already exercise the predicate-
derived behavior:

- **Fixture 034** (`observability/conformance/034-caller-metadata-open-span-update-serial`)
  exercises the outermost-serial case where the invocation span
  receives the augmentation. Under the tightened §3.4 wording,
  this is rule 2 (call-stack ancestor) applying — the augmenter's
  lineage chain has only `null` entries, so the invocation span
  is NOT a shared parent and IS on the call-stack path.
- **Fixture 039** (`observability/conformance/039-nested-lineage-augmentation`)
  exercises the three nested cases (fan-out-in-fan-out-instance,
  parallel-branches-in-fan-out-instance, fan-out-in-serial-
  subgraph) where the invocation span is NOT updated. Under the
  tightened §3.4 wording, this is rule 3 (shared parent at any
  depth) applying — each case has at least one fan-out or
  parallel-branches dispatch on the call-stack path, so the
  invocation span IS a shared parent.

Both fixtures pass under the predicate-derived behavior without
modification. The tightened spec text retroactively explains why
their apparent contradiction (one updates invocation span, the
other doesn't) is consistent with §3.4's intent.

### Optional future fixture

An explicit positive-control fixture for the "pure-serial through
nested subgraph wrappers" case (the §3.4 *Augmenter's call-stack
ancestor chain (MUST)* rule applying to a serial-subgraph wrapper
on the augmenter's path) MAY be added as a follow-on if cross-
impl coverage warrants. The behavior is already exercised by the
v0.37.0 fixture 039 case 3 (fan-out-in-serial-subgraph), but a
dedicated pure-serial fixture would tighten the cross-impl story.
Out of scope for this proposal.

## Versioning

**MINOR bump** (pre-1.0). The change is purely documentary —
tightens the existing §3.4 *Shared-parent boundary (MUST NOT)*
paragraph without modifying the normative behavior fixtures 034
and 039 already exercise. Precedent: 0019 (multi-provider
extension reframe), 0026 (§8.X template), 0030 (drain-snapshot
timing clarification), 0051 (Langfuse SDK caveat) all landed as
MINOR bumps for documentary / textual changes without behavioral
impact.

The whole-spec SemVer increments with:

- Tightened §3.4 *Shared-parent boundary (MUST NOT)* paragraph
  (rewritten to bullet form with explicit invocation-span
  conditional clause).
- No new conformance fixtures (existing 034 + 039 exercise the
  predicate-derived behavior).
- No public-type / interface changes.
- No new error categories, attributes, or events.

Listed as `Textual` impl-tracking status (no module-level
implementation change required) when adopted by an implementation;
per the existing `docs/proposals.md` convention, this signals
impls update their spec-version pin without code changes. This
proposal's spec-text tightening retroactively matches the
predicate-derived behavior implementations adopted when working
through 0045's nested-cases coverage.

## Alternatives considered

1. **Re-litigate the §3.4 boundary by allowing the strict
   "invocation span never updates" reading and adjusting fixture
   034.** Treat the strict-shared-parent reading as canonical;
   modify fixture 034 to assert the invocation span is NOT
   updated in the outermost-serial case. Rejected: fixture 034
   has been shipping for multiple spec versions, and modifying it
   would break the established conformance contract that
   implementations have built against. Tightening the spec text
   to match the fixture's normative behavior is the lower-risk
   shape.

2. **Tighten the decision tree's rule 3 wording instead of the
   *Shared-parent boundary* paragraph.** Reframe rule 3's "shared
   parent at any depth" to add an explicit invocation-span
   carve-out (something like "or a shared parent at any depth,
   except the invocation span when no fork is on the augmenter's
   path"). Rejected: the rule 3 phrasing already reads correctly
   under the tightened paragraph definition of "shared parent" —
   pushing the carve-out into the rule itself is redundant and
   makes the decision-tree harder to scan. Better to fix the
   classification rule's definition; the decision tree consumes
   the cleaner definition.

3. **Add new conformance fixtures explicitly exercising the
   `outermost_serial` predicate.** Land one or more new positive-
   control fixtures (e.g., pure-serial-through-subgraph-wrapper)
   to lock down the predicate at the fixture layer. Rejected for
   this proposal: existing fixtures 034 + 039 already exercise
   the predicate-derived behavior end-to-end. A dedicated pure-
   serial-with-subgraph fixture is captured as an optional
   follow-on (per *Conformance test impact* above) if cross-impl
   coverage gaps emerge.

4. **Introduce a new helper construct in §3.4 (e.g., a typed
   `LineageChain` record).** Define an explicit data structure
   for the per-depth lineage tracking that's currently described
   prose-only in §3.4's *Per-depth lineage tracking* paragraph.
   Rejected for this proposal: out of scope. The lineage chain
   is impl-side data per 0045's framing; introducing a spec-level
   typed record is a separate concern that would conflate
   wording-clarification (this proposal) with new-surface-area
   addition (a follow-on if a use case surfaces).

## Open questions

None at draft time. The design choices are settled in the
proposal text above:

- **Boundary paragraph rewrite vs decision-tree rule rewrite**
  (alternative 2) — rewrite the *Shared-parent boundary*
  paragraph's classification, leave the decision-tree rule
  text unchanged; the rule reads correctly under the tightened
  classification.
- **Fixture additions** (alternative 3) — none for this
  proposal; existing 034 + 039 are sufficient. An optional
  follow-on may add a dedicated pure-serial fixture if cross-
  impl coverage warrants.
- **Per-depth lineage typed record** (alternative 4) — out of
  scope; separate concern from wording clarification.

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **Re-litigating the invocation-span behavior.** This proposal
  tightens the spec text to match the predicate-derived behavior
  fixtures 034 + 039 already exercise. It does NOT propose
  changing what the invocation span actually receives in any
  case; the fixtures are the normative behavior surface.
- **Introducing a typed `LineageChain` data structure** for the
  per-depth lineage tracking (alternative 4). Out of scope;
  separate concern.
- **Adding new conformance fixtures** for cases the existing 034
  + 039 fixtures don't cover (e.g., dedicated pure-serial-through-
  subgraph-wrapper fixture). Out of scope for this proposal;
  captured as an optional follow-on if cross-impl coverage gaps
  emerge in practice.
- **Reframing the *Augmenter's call-stack ancestor chain (MUST)*
  or *Sibling boundary (MUST NOT)* rules.** Those rules are
  unchanged; only the *Shared-parent boundary (MUST NOT)*
  paragraph is rewritten.
- **Decision-tree rule renumbering.** The three-step decision
  tree's rule numbering and structure remain unchanged.
