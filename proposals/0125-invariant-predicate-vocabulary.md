# 0125: Make an Unimplemented Invariant Predicate Fail Loudly

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-21
- **Accepted:**
- **Targets:**
  - spec/conformance-adapter/spec.md **§5.9 Invariant assertions**: state the consequence of encountering a
    predicate name an adapter does not implement. §5.9 says adapters MUST implement both the canonical names
    and the fixture-specific ones, but says nothing about what happens when one is not implemented, so the
    universal outcome is that it is silently skipped and the fixture reports a pass.
  - spec/conformance-adapter/spec.md **§5.9**: require that a fixture-specific predicate be **defined** in
    the fixture's prose, applying the same three-part test proposal 0120 sets for a directive definition.
    §5.9 already directs them there; 924 of the 934 predicate names in the corpus have no definition anywhere.
  - spec/conformance-adapter/spec.md **§9**: add `fixture_predicate_unknown` to the error catalogue, the
    predicate-surface analogue of `fixture_directive_unknown`.
- **Related:** 0120 (settled where a directive's definition may live and scoped this surface out explicitly),
  0081 and 0107 (prior vocabulary documentation passes)

## Summary

§5.9 obliges adapters to implement every invariant predicate name a fixture uses, both the canonical ones it
enumerates and the fixture-specific ones it delegates to fixture prose. It states no consequence for failing
to, so an unimplemented name is silently skipped and its fixture goes green having checked nothing. A
recursive scan of the corpus finds 934 distinct predicate names, of which 924 appear nowhere in the §5
vocabulary. This gives the obligation a failure mode and requires the delegated definitions to exist.

## Motivation

### An obligation with no observable failure

§5.9 states the requirement twice. Generally: "the adapter MUST ship logic that interprets each predicate name
and runs the corresponding check against the executed outcome." And for the split it defines: "Adapters MUST
ship logic that interprets each canonical predicate name in this section. Fixture-specific predicates not
listed here are documented in the originating fixture's prose per §3.2 per-directory harness notes; adapters
MUST also implement those."

Nothing says what happens when an adapter meets a name it has not implemented. Because `invariants` is itself
a recognized key, no unknown-directive rule fires: the block parses, the adapter iterates the names it knows,
and the rest are skipped. The fixture reports a pass.

That is a MUST with no observable failure mode, which is the worst shape a conformance requirement can take.
It is also the shape that produces false confidence rather than a visible gap: a conformance report says the
behaviour is covered, and nothing was checked.

### The scale

A recursive scan of all 497 fixture files, collecting every key under `invariants`,
`observer_event_invariants` and `node_accumulator_snapshot_invariants`:

| | Count |
|---|---|
| Distinct predicate names | 934 |
| Word-matched anywhere in the §5 vocabulary | 10 |
| Absent from it | 924 |

§5.9 delegates the 924 to fixture prose. A downstream report supplies a worked instance: fixture 148 asserts
that a Generation's fixed `usage` record omits `input` when the provider reports no prompt tokens, and the
claim rests entirely on two predicate names, `generation_usage_input_omitted_when_prompt_tokens_null` and
`generation_usage_output_and_total_present_when_sound`. Each appears in exactly one fixture and in no spec
file. Neither is implemented by any adapter the corpus reflects. The fixture passes with no harness work at
all, which is what prompted the check.

The reporter's phrase for it is the general case: the assertion the fixture exists to make is currently made
by nothing.

### Why this is not proposal 0120

0120 settles where a **directive's definition** may live, and its out-of-scope section names this surface
explicitly as the follow-on. The two differ in what is unresolved. For directives, the homes disagreed and
0120 reconciled them. For predicates, §5.9's structure is already right: canonical names in the spec,
fixture-specific names in fixture prose, both obligatory. What is missing is a consequence and an
enforceable definition requirement, not a decision about where definitions live.

## Detailed design

### §5.9: an unimplemented predicate fails the fixture

> An adapter that encounters an invariant predicate name it does not implement **MUST** fail the fixture with
> `fixture_predicate_unknown` (§9), reporting the predicate name and the fixture location. It **MUST NOT**
> skip the predicate and report a pass. A predicate an adapter cannot evaluate is a failure to evaluate the
> fixture, not an assertion that holds.

This is deliberately the same shape as §8.2's rule for an unrecognized directive, and for the same reason:
silent skipping masks conformance gaps.

### §5.9: a fixture-specific predicate must be defined

> A fixture-specific predicate name **MUST** be defined in the prose of the fixture that uses it. A definition
> states what the adapter must check and what outcome satisfies it. A name appearing only in a fixture's YAML
> is **undefined**, and a fixture MUST NOT depend on an undefined predicate.

The definition test is the one proposal 0120 sets for directives: a name mentioned without a stated obligation
is not a definition. That test is what makes this checkable rather than aspirational.

### §9: the error token

> **`fixture_predicate_unknown`**: an adapter encountered an invariant predicate name it does not implement.
> Silent skipping would report coverage that does not exist; the adapter MUST raise and surface the predicate
> name plus the fixture location.

## Conformance test impact

**This is the largest conformance change in the current batch, and it should be sized honestly.** After this,
an adapter that does not implement a predicate fails the fixture using it. No adapter implements all 934
names. So on the day this is accepted, every adapter's conformance numbers drop, and they drop by the amount
of coverage that was never real.

That is the intended effect and it is why the change is worth making, but it makes the accept a decision about
timing rather than only about wording. Two mitigations are available and this proposal does not choose between
them, because the choice belongs to whoever schedules the release:

1. **Accept the drop.** The numbers become true immediately, and the gap is visible and worked down.
2. **Stage it.** Accept the definition requirement and the error token now, and set the failure obligation to
   a stated future spec version, so implementations have a window to close the gap against a fixed date.

**No fixture YAML changes.** The corpus already uses every predicate name; this makes the obligation
enforceable and requires the delegated definitions to exist.

**The definition requirement lands on fixture authors**, and 924 names currently lack a definition. Writing
them is not this proposal's work and cannot be, since each definition states what a specific check does. What
this proposal does is make an undefined predicate detectable rather than invisible.

## Alternatives considered

1. **Do nothing.** Rejected: an obligation with no failure mode is not an obligation, and the corpus contains
   roughly nine hundred instances of it. The downstream report is one worked example of a fixture that passes
   while asserting nothing.
2. **Make an unimplemented predicate a warning.** Rejected: a warning in a conformance run is a pass, and
   unearned passes are the entire defect.
3. **Enumerate all 934 names in §5.9.** Rejected: §5.9 explicitly scopes its enumeration "to keep this list
   maintainable", and that judgment is right. A cross-capability surface should not carry nine hundred
   fixture-local check names.
4. **Drop the fixture-specific tier and require every predicate to be canonical.** Rejected: it would force
   every local check into a cross-capability list, which is the outcome alternative 3 rejects, and it
   contradicts §5.9's deliberate split.
5. **Fold this into proposal 0120.** Rejected: 0120 resolves a contradiction between sections and changes no
   implementation behaviour. This changes what every adapter must do and moves conformance numbers. Keeping
   them separate keeps 0120 mergeable on its own merits and makes this decision visible rather than carried
   in on another proposal's back.

## Open questions

1. **Immediate or staged (the two options in *Conformance test impact*).** This is a release-timing decision
   rather than a design one, and it should be made deliberately rather than by whichever wording ships. The
   staged form needs a target version named in the text.
2. **Whether the same treatment is owed to the `carries` assertion surface** and any other name-keyed
   vocabulary, which have not been swept. This proposal covers the three invariant blocks it measured;
   whether other surfaces share the shape is unmeasured and should not be assumed either way.
