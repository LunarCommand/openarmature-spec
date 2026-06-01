# 0051: Langfuse Trace Input/Output Implementation-Surface Caveat

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-01
- **Accepted:**
- **Targets:** spec/observability/spec.md (§8.4.1 *Trace input/output sourcing* — adds a single *Implementation surface caveat* paragraph noting that the vendor SDK method which currently delivers the §8.4.1 contract's UI-visible projection is marked deprecated by the upstream vendor, with the §8.4.1 normative contract (three-lever decision tree, hook contract, status enum, resume semantics) decoupled from any specific SDK-method binding). No conformance fixture impact.
- **Related:** 0043 (observability §8.4.1 Langfuse trace.input/trace.output sourcing — established the §8.4.1 contract this proposal documents an implementation-surface caveat for)
- **Supersedes:**

## Summary

The §8.4.1 *Trace input/output sourcing* normative contract — the
three-lever decision tree, `disable_state_payload` privacy knob,
caller-hook signatures, status enum, and resume semantics —
specifies *what* trace-level input/output should look like in
Langfuse, decoupled from *how* implementations get the values
there via the vendor SDK.

Empirical verification against the current Langfuse SDK surface
(Langfuse Python SDK v4.7.1, verified 2026-05-30) finds that the
SDK method which delivers the §8.4.1 contract's UI-visible value
to the Langfuse Traces list view (`set_current_trace_io` /
`Span.set_trace_io`) is marked **deprecated** by the upstream
vendor, with stated removal in a future major version. The non-
deprecated replacement method (`propagate_attributes`) does NOT
project trace-level input/output values to the headline UI
columns the §8.4.1 motivation targets.

This proposal adds a single short paragraph to §8.4.1 — an
*Implementation surface caveat* — recording the SDK-surface state
at a specific verification date, decoupling the §8.4.1 normative
contract from the specific SDK method binding. The §8.4.1
contract stays stable across SDK migrations; implementations
track vendor SDK releases for migration-path updates.

The change is purely documentary. No behavior change. No
conformance impact.

## Motivation

When a normative spec contract binds (at the operational level)
to a vendor SDK method, and that vendor method gets deprecated,
the spec's durability is at risk if readers conclude the spec
contract itself is deprecated. The §8.4.1 contract is sound
(operators DO scan the Traces list view headline columns; the
three-lever decision tree resolves correctly); only the
implementation surface is affected by vendor churn.

A short caveat paragraph in the spec text recording the
verification-date state of the vendor SDK serves three purposes:

1. **Future readers see the SDK-surface state at a point in time.**
   The Langfuse v4 deprecation isn't a secret — implementations
   have to navigate it. Recording the date + the deprecated /
   replacement method names makes the navigation discoverable
   from spec text rather than burying it in implementation-side
   release notes.

2. **Spec text makes the contract / implementation split explicit.**
   The §8.4.1 contract (decision tree, hook signatures, status
   enum) is stable; the SDK-method binding migrates over time.
   Calling out the split prevents readers from misreading SDK
   deprecation as spec deprecation.

3. **Verification cadence becomes self-documenting.** The "as of
   2026-05-30" date sets a maintenance trigger — a future reader
   encountering this caveat at a much later date knows to
   re-verify the vendor SDK state before relying on the binding.

The paragraph is short and one-time-only — when Langfuse
publishes a concrete v5 migration guide, a follow-on proposal MAY
expand the caveat into a full §8.4.1 reframe specifying the v5
binding. Until that happens, the caveat is the right scope.

## Proposed change

### observability §8.4.1 — *Implementation surface caveat* paragraph

Add a single short paragraph to the end of §8.4.1's *Trace
input/output sourcing* block, after the existing
`disable_state_payload` / decision-tree / status-enum /
caller-hook / resume-semantics content:

> **Implementation surface caveat.** Implementations bind the
> §8.4.1 contract to whichever vendor SDK method projects trace-
> level input / output values into the Langfuse UI's headline
> Input / Output columns. As of Langfuse SDK v4 (empirically
> verified 2026-05-30), this is the `set_current_trace_io` /
> `Span.set_trace_io` family, which the SDK marks as deprecated
> with stated removal in a future major version. The non-
> deprecated `propagate_attributes` method does not currently
> project trace-level input / output values to the headline
> columns. The §8.4.1 contract (three-lever decision tree, hook
> contract, status enum, resume semantics) is independent of
> which SDK method populates the values and remains stable
> across SDK migrations; implementations track vendor SDK
> releases for migration-path updates. The operational tracking
> record — verified-against SDK version, per-row re-verification
> cadence — lives at `docs/compatibility.md` per the
> *External-dependency adoption* policy (`GOVERNANCE.md`); the
> caveat above and the compatibility-page row are kept in sync
> when re-verification updates either.

The paragraph is vendor-neutral in voice (talks about "the
vendor SDK" rather than naming a specific language SDK), records
the verification date explicitly so future readers know the
context, and frames the contract / implementation split clearly.

The paragraph deliberately does NOT:

- Recommend or prescribe a specific SDK-version migration
  strategy.
- Speculate about what the v5 replacement might look like.
- Reference any specific implementation's CHANGELOG or release
  notes.

When Langfuse publishes a concrete v5 migration guide
(timeline-uncertain), a follow-on proposal can expand the caveat
into a full §8.4.1 reframe specifying the new binding. The caveat
paragraph is the v1 scope.

## Conformance test impact

**None.** This proposal adds documentary text to §8.4.1 without
changing the normative contract, the conformance fixture set, or
any observable behavior. The existing §8.4.1 fixture (per proposal
0043's *Conformance test impact* section) remains valid
unchanged — it exercises the three-lever decision tree, hook
signatures, status enum, and resume semantics; none of those are
affected by which SDK method an implementation uses to project
the values.

## Versioning

**MINOR bump** (pre-1.0). The change is purely documentary — adds
a single paragraph to existing spec text without modifying
normative behavior. Precedent: 0019 (multi-provider extension
reframe), 0026 (§8.X template), 0030 (drain-snapshot timing
clarification) all landed as MINOR bumps for documentary /
textual changes without behavioral impact.

The whole-spec SemVer increments with:

- A new *Implementation surface caveat* paragraph in
  observability §8.4.1.
- No conformance fixture changes.
- No public-type / interface changes.

Listed as `Textual` impl-tracking status (no module-level
implementation change required) when adopted by an
implementation; per the existing `docs/proposals.md` convention,
this signals impls update their spec-version pin without code
changes.

## Alternatives considered

1. **Do nothing (defer entirely).** Leave the spec untouched;
   let implementations handle the migration in their own release
   cadences when Langfuse v5 ships. Rejected: silent drift across
   implementations is a risk — each implementation would
   independently rediscover the deprecation, potentially making
   divergent migration choices. The spec text serves as a single
   source of truth for "here's what we know about the vendor SDK
   surface state at this date"; without it, the cross-impl
   coordination story is weaker.

2. **Pre-stage a placeholder migration proposal as Draft.**
   Reserve a proposal number (e.g., 004X) with `Status: Draft` and
   empty body to be populated when v5 ships. Rejected: empty
   drafts sit awkwardly in the proposals index; the proposals
   table is read as "what's in flight" and an empty placeholder
   muddies that. A targeted caveat in §8.4.1 is the lighter
   touch that delivers more value — the spec text records what's
   known now.

3. **Expand the caveat into a full §8.4.1 reframe.** Use this
   proposal to design the v5 migration path rather than just
   documenting the current state. Rejected: speculating on v5's
   shape ahead of vendor publication is exactly the kind of
   premature design the *Stable-only upstream adoption* policy
   (per `docs/compatibility.md`) steers away from. The caveat
   records what's known; a future proposal handles the actual
   migration when vendor v5 publishes a concrete shape.

4. **Pin the caveat in `docs/compatibility.md` instead of
   §8.4.1 spec text.** The compatibility tracking page exists for
   exactly this kind of external-dependency state recording; put
   the caveat there rather than in normative spec text. Partial
   rejection: the compatibility page ALREADY records the Langfuse
   SDK v4.7.1 verification and the deprecation note (per the
   *Langfuse SDK* row + per-dependency section). The §8.4.1
   spec-text caveat is the cross-pointer — readers of §8.4.1 see
   the SDK-surface state inline rather than having to look up the
   compatibility page. The two artifacts work together: the
   compatibility page tracks the version + verification date;
   the §8.4.1 caveat ensures readers of the normative contract
   text see the SDK-surface context.

## Open questions

None at draft time. The design choices are settled in the
proposal text above:

- **Caveat scope** (alternatives 1-3) — single paragraph in
  §8.4.1; no proposal for v5 migration ahead of vendor
  publication; no placeholder Draft.
- **Caveat location** (alternative 4) — §8.4.1 spec text with
  the cross-pointer relationship to `docs/compatibility.md`
  documented at acceptance time.
- **Vendor-neutral voice** — the caveat says "the vendor SDK"
  rather than naming Python / TypeScript SDKs specifically; the
  deprecation applies at the wire/API layer across language
  ports, so the language-agnostic voice is correct.

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **Designing the v5 migration path.** Speculating on the v5
  replacement surface ahead of vendor publication is premature
  per the stable-only adoption policy
  (`docs/compatibility.md`). A follow-on proposal handles the
  v5 reframe when vendor v5 ships with a concrete migration
  guide.
- **Other vendor SDK deprecations.** This proposal scopes to the
  specific Langfuse v4 `set_current_trace_io` deprecation
  affecting §8.4.1; future vendor SDK changes affecting other
  spec sections warrant their own caveat-style proposals as they
  surface.
- **Changes to the §8.4.1 normative contract.** The three-lever
  decision tree, hook contract, status enum, and resume
  semantics remain unchanged. This proposal documents the
  implementation-surface context around the existing contract;
  the contract itself is not modified.
- **Conformance fixture additions.** No behavioral change; the
  existing §8.4.1 fixture set remains valid unchanged.
