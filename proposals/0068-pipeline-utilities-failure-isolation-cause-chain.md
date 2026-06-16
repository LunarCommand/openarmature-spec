# 0068: Pipeline Utilities — Failure-Isolation Event Structured Cause Chain

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-15
- **Accepted:** 2026-06-15
- **Targets:** spec/pipeline-utilities/spec.md (§6.3 — the failure-isolation event's `caught_exception` record gains a structured **`chain`** field: an ordered list of cause links `{category, message, carrier}` from the caught exception down to the originating raise, outermost→innermost, carriers included and flagged; the existing `category` / `message` fields are **retained and redefined** as a derivation over the chain — the outermost non-carrier link carrying a category (else `category` is `null` and `message` is the outermost non-carrier link's). Supersedes 0065's "resolve through the carrier wrapper to the originating cause" prose, which is ambiguous when the post-carrier chain has multiple non-carrier links; plus a conformance fixture covering a nested-carrier chain. §6.1 retry classification is explicitly unchanged.)
- **Related:** 0050 (introduced §6.3 `FailureIsolationMiddleware` + the failure-isolation event and its `caught_exception` record), 0065 (the cause-fidelity carrier-unwrap clause this extends/supersedes), 0009 / 0036 (fan-out — the §9.7 instance-middleware site), 0011 (parallel branches — the §11.7 branch-middleware site), graph-engine §4 (`node_exception` carrier wrapper + `__cause__`), graph-engine §6 (observer delivery queue the event rides)
- **Supersedes:** 0065 (the §6.3 `caught_exception` cause-representation clause only; 0065's wrapped-instance/branch **lineage** SHOULD is unaffected and stands)

## Summary

0065 tightened §6.3 so the failure-isolation event's `caught_exception.category`
reports the *originating* failure rather than the masking graph-engine §4
`node_exception` carrier — "resolve through the carrier wrapper to the
originating cause and report that category," and "resolution walks nested
carrier wrappers to the originating cause."

That wording assumes the structure is `[carriers…] → one originating cause`. It
is **underspecified when the post-carrier cause chain has more than one
non-carrier link** — e.g. a `provider_unavailable` deliberately re-raised as a
domain error, or an uncategorized surface error wrapping a categorized cause.
"The originating cause" then has no single referent: nearest-categorized,
deepest/root, and first-non-carrier all diverge, and 0065's only fixture
covers single-carrier cases — so two conformant implementations can report
**different** categories for the same nested failure, defeating the very
fidelity guarantee 0065 exists to provide.

This proposal stops making the fidelity *contract* hinge on a single adjudicated
cause and instead makes the event **carry the whole resolved chain** (with the
single-value `category` kept as a labeled derivation over it). `caught_exception`
gains a structured `chain` — every link from the caught exception down to the
originating raise,
each `{category, message, carrier}`, carriers included and flagged. The
existing `category` / `message` fields are kept as a precisely-defined
*derivation* over the chain (a convenience for the common single-value
consumer and the bundled observers), so nothing is hidden and no consumer is
forced to walk the chain. Conformance becomes "produce this exact chain" —
mechanical and deterministic — rather than "pick the right single category per
a heuristic."

## Motivation

The failure-isolation event exists to tell a consumer **why** an instance or
branch was isolated. 0065 made that actionable by unwrapping the carrier. But
collapsing the cause to one category re-introduces a smaller version of the same
problem one level down: the spec has to *choose* which non-carrier cause wins,
and any choice is a heuristic that (a) can map distinct failures to the same
reported category with no way to tell them apart, and (b) is the kind of
implicit, lossy rule OA otherwise avoids.

A structured chain resolves this in OA's idiom — **explicit, structured, nothing
hidden**:

- **It subsumes every single-pick policy.** A consumer that wants
  nearest-categorized derives it; one that wants the root cause derives it. The
  spec no longer ordains one.
- **It is the actionable signal *and* the full diagnostic.** Telemetry that
  groups by a single category uses the derived `category`; a human debugging a
  nested failure reads the chain (`branch carrier → instance carrier →
  provider_unavailable`) — strictly more than a lone category.
- **It is more conformable, not less.** Producing the chain is a mechanical
  cause-chain walk; comparing chains is structural equality. That is a sharper
  conformance contract than "did you apply the resolution heuristic correctly,"
  and it pins the nested case 0065 left open.
- **It matches OA's typed-event direction** (0049 / 0058 / 0065) — structured
  over collapsed.

This is an **underspecified-interaction refinement, not a conformance bug**: an
implementation reporting any reasonable single category conforms to 0065's
prose today. The chain makes the contract exhaustive so implementations
converge.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0); concrete version assigned at acceptance.
All changes are in pipeline-utilities §6.3's `caught_exception` definition.

### pipeline-utilities §6.3 — `caught_exception.chain`

The §6.3 `caught_exception` record gains a required structured field:

> **`chain`** — an ordered list of **cause links** describing the caught
> exception and its **cause chain** (the language's exception-cause linkage —
> Python `__cause__`, TypeScript `Error.cause`), from the caught exception
> (**outermost**, index 0) down to the originating raise (**innermost**). Each
> cause link is a structured record:
>
> - **`category`** — the link's failure category (per its carrying spec, e.g.
>   llm-provider §7 / graph-engine §4) as a string, or `null` when the link
>   carries no category.
> - **`message`** — the link's own message.
> - **`carrier`** — `true` when the link is a graph-engine §4 `node_exception`
>   carrier wrapper (including subtypes such as the §11.9
>   `parallel_branches_branch_failed`), `false` otherwise.
>
> The chain is built by walking the cause chain from the caught exception to
> its end, recording one link per exception. Implementations MUST terminate the
> walk on a repeated reference (a cyclic cause chain MUST NOT hang or crash the
> degrade path) and MUST stop at the first link whose cause is not itself an
> exception. At **node-level** placement the caught exception is the raw
> error, so the chain is a single non-carrier link; at a non-node placement
> (§9.7 instance, §11.7 branch, §9.6 / §11.6 parent-node middleware) the
> outermost link(s) are the engine's carrier wrapper(s), `carrier = true`.

### pipeline-utilities §6.3 — `category` / `message` as a derivation

The existing `category` and `message` fields are **retained** (so simple
consumers and the bundled OTel / Langfuse observers keep a single value to
group and render) and **redefined as a derivation over `chain`**, replacing
0065's "originating cause" prose:

> `caught_exception.category` MUST be the `category` of the **outermost
> non-carrier** link in `chain` whose `category` is a non-empty string. When no
> non-carrier link carries a category, `category` MUST be `null`.
> `caught_exception.message` MUST be the `message` of that same link; when no
> non-carrier link carries a category, it MUST be the `message` of the
> **outermost non-carrier** link (the surface error — the first non-carrier beneath any engine carriers). The derived
> `category` and `message` therefore always describe **one** link of the chain.

"Outermost non-carrier carrying a category" makes a **deliberate re-categorization
win** — if an intermediate layer re-raised a `provider_unavailable` as a domain
error with its own category, that intentional surface category is reported,
while the full provenance remains visible in `chain`. This derivation reproduces
0065's single-carrier results exactly (the existing fixtures are unchanged), and
gives the nested case a single, stated answer instead of an ambiguous one.

### Why §6.1 retry classification is out of scope (not deferred)

§6.1's default classifier is a **single-level** check (the exception's category
or its direct cause's). That is the **correct boundary** for retry's semantics,
not a compromise: retry decides "re-run this node," and re-running an entire
outer subgraph because of a deeply-nested transient is the **wrong grain** — it
re-executes unrelated work, independent of whether an inner retry is configured.
The place to retry a specific failing call is at or near that call, not at a
wrapping site several carriers up. The structured chain makes the **event**
fully transparent regardless, so there is no hidden
behavior: the event reports what was caught in full, and retry independently
answers a different question. Unifying the two resolutions would change retry's
behavior and is a separate proposal on its own merits, not part of this one.

## Conformance test impact

### Extended / new fixture

The 0065 fixture (`pipeline-utilities/conformance/064-…`) is **extended** (or a
sibling added; number assigned at acceptance) to assert `caught_exception.chain`
in addition to the derived `category` / `message`:

- **Single-carrier cases (existing 064 Cases 1–2).** Add a `chain` assertion:
  `[ {carrier: true, category: …(node_exception)…}, {carrier: false, category:
  "provider_unavailable"} ]`, and the derived `category == "provider_unavailable"`
  (unchanged from 0065). Confirms the chain is exhaustive and the derivation
  reproduces 0065.
- **Node-level case (existing Case 3).** `chain` is a single non-carrier link;
  derived `category` equals it. Guards the single-link shape.
- **Uncategorized cause (existing Case 4).** The lone non-carrier link has
  `category: null`; derived `category == null`, `message` from that link.
- **New — nested-carrier chain.** A failure isolated at a placement where the
  cause chain is `carrier → carrier → categorized cause` (e.g. a fan-out
  instance with inner retry, wrapped by a branch). Assert `chain` records **both**
  carriers (`carrier: true`) then the categorized originating link, and the
  derived `category` is that originating category. This is the case 0065 left
  unpinned.
- **New (optional) — re-categorized surface.** A categorized originating cause
  re-raised by an intermediate non-carrier with a *different* category. Assert
  `chain` carries both non-carrier links and the derived `category` is the
  **outermost** (surface) one — pinning the "deliberate re-categorization wins"
  derivation.

Asserting `chain` is an additive structural comparison on the existing
`expected_failure_isolation_event` assertion; no conformance-adapter directive
vocabulary change is anticipated.

### Unaffected

0050's catch/degrade fixtures and 0065's single-carrier `category` assertions
continue to pass — the derivation reproduces 0065's values; this proposal adds
the `chain` and pins the nested case.

## Versioning

**MINOR bump** (pre-1.0):

- §6.3's `caught_exception` record gains the required `chain` field, and
  `category` / `message` are redefined as a derivation over it (superseding
  0065's "originating cause" prose).
- A conformance fixture pins the chain, including the nested-carrier case.

**Behavior-change note.** The `caught_exception` shape grows a `chain` field
(additive). Derived `category` / `message` are unchanged for single-carrier
chains (0065's results stand); for multi-non-carrier chains they become
well-defined where 0065 was ambiguous. 0065's `caught_exception.message` SHOULD
is tightened to a **MUST** (the chain makes the derivation unambiguous) — a
conformance tightening for any implementation that previously diverged on the
message. Catch/degrade behavior and graph execution outcomes are untouched. Classified MINOR (an additive event-shape
change plus a pinned conformance expectation); a PATCH reading is defensible
since the derived values are unchanged in the cases 0065 fixtured — the
maintainer's call at acceptance.

## Out of scope

- **§6.1 retry classification.** Stays single-level — the correct boundary for
  retry semantics (see Detailed design); not deferred, not part of this change.
- **The middleware's catch / degrade behavior.** Untouched; this proposal
  changes only what the event *reports*, not recovery.
- **0065's wrapped-instance / branch lineage SHOULD.** Unaffected and stands.
- **Promoting the failure-isolation event to a typed observer-union variant.**
  Independent of cause representation; remains the deferred 0050 carve-out.
- **Exposing exception *type* names in a cause link.** Deliberately omitted —
  `{category, message, carrier}` is language-agnostic; a concrete class name
  would leak per-language detail into the cross-impl event.
- **How the bundled observers surface the `chain`.** The OTel / Langfuse
  observers render the derived `category` for their single-value attribute;
  whether they additionally expose the full `chain` (e.g. as structured event
  detail) is an observability-spec concern, out of scope here — the event
  carries the chain for custom observers regardless.

## Alternatives considered

- **Single resolved category, "nearest-categorized" rule (no chain).** The
  minimal fix: keep `caught_exception.{category, message}` and define the
  resolution as nearest-categorized. Rejected as the primary design: it still
  bakes a lossy heuristic into the spec, can collapse distinct failures to one
  reported category, and hides the provenance — the chain subsumes it (the
  derived `category` *is* this rule, now with the full chain beside it).
- **Single resolved category, deepest/root rule.** Same lossiness; also reports
  a deep cause even when an intermediate layer deliberately re-categorized,
  which is usually the *less* actionable signal. Rejected for the same reason;
  available as a derivation over `chain` for consumers who want it.
- **Carrier category propagation at wrap time.** Have the engine stamp the
  originating category onto the `node_exception` carrier so everyone reads it
  single-level. Rejected: a graph-engine §4 carrier-semantics change that still
  needs a "which category when re-wrapping" rule — the same hard question moved
  earlier, for more blast radius.
- **Pure chain, drop derived `category` / `message`.** Maximally explicit, but
  forces every consumer (and both bundled observers, which need one value) to
  walk the chain. Rejected in favor of keeping the derivation as a stated,
  verifiable convenience — transparent because the chain sits beside it.
- **Do nothing.** Rejected: leaves the nested case ambiguous, so conformant
  implementations diverge on the reported category for the same failure.
