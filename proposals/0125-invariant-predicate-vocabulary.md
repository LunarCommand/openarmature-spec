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
recursive scan of the corpus finds 934 distinct predicate names, of which 924 are outside the §5 vocabulary
and 835 are defined nowhere at all. This gives the obligation a failure mode and requires the delegated
definitions to exist.

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
| Named in the §5 vocabulary | 10 |
| Not in §5, but named in their own fixture's prose | 89 |
| Named in neither | **835** |

The two figures answer different questions and should not be conflated. **924** are outside the §5 vocabulary,
which is where §5.9 delegates them to fixture prose, so being outside it is expected rather than a defect.
**835** appear in neither §5 nor the prose of any fixture that uses them, and those are the ones with no
definition anywhere.

The 89 matter as much as the 835: they show §5.9's delegation working when it is used. The mechanism is not
broken, it is unenforced. (The 89 is an upper bound: a name appearing in a sidecar is not necessarily
*defined* there, in the sense of stating what the adapter must check.)

**A worked instance.** Observability fixture 038 asserts
`invariants.dispatch_spans_close_before_node_span: true`, a relation about the order in which spans close. No
`expected.span_tree` assertion can express close ordering, so nothing else in the fixture carries that claim.
The predicate is documented in the fixture's own sidecar, exactly where §5.9 directs, so an adapter is
obliged to implement it. An adapter that does not implement it skips it, and the fixture reports a pass having
checked nothing about close ordering.

That is the shape: not an undefined name, but a defined one whose obligation has no failure mode.

### Why this is not proposal 0120

0120 settles where a **directive's definition** may live, and its out-of-scope section names this surface
explicitly as the follow-on. The two differ in what is unresolved. For directives, the homes disagreed and
0120 reconciled them. For predicates, §5.9's structure is already right: canonical names in the spec,
fixture-specific names in fixture prose, both obligatory. What is missing is a consequence and an
enforceable definition requirement, not a decision about where definitions live.

## Detailed design

### §5.9: an unimplemented predicate fails the fixture

Two forms are drafted, because the choice between them is a release-timing decision and the accept should pick
between texts rather than compose one.

**Immediate form:**

> An adapter that encounters an invariant predicate name it does not implement **MUST** fail the fixture with
> `fixture_predicate_unknown` (§9), reporting the predicate name and the fixture location. It **MUST NOT**
> skip the predicate and report a pass. A predicate an adapter cannot evaluate is a failure to evaluate the
> fixture, not an assertion that holds.

**Staged form**, identical but with the obligation dated:

> An adapter that encounters an invariant predicate name it does not implement **MUST** fail the fixture with
> `fixture_predicate_unknown` (§9), reporting the predicate name and the fixture location, from spec version
> `<TARGET>` onward. Before that version an adapter **SHOULD** fail, and **MUST** report the skipped predicate
> name in its conformance output so an unimplemented predicate is visible rather than silent. Under neither
> form may an adapter skip the predicate and report an unqualified pass.

Either shape is the same as §8.2's rule for an unrecognized directive, and for the same reason: silent skipping
masks conformance gaps. The staged form differs only in when the failure becomes mandatory, and in requiring
interim visibility so the gap stays measurable while it is closed.

**This proposal does not claim neutrality between them.** The immediate form is preferable on the merits,
because the staged form's interim state is a conformance report that passes while naming what it did not
check. The staged form exists for the case where the size of the drop needs a scheduled window, which is a
release-management judgment rather than one about the rule.

### §5.9: a fixture-specific predicate must be defined

> A fixture-specific predicate name **MUST** be defined in the prose of the fixture that uses it. A
> **definition** states what the adapter must check and what outcome satisfies the predicate. A name that
> appears in prose without both is a mention, not a definition, and a fixture **MUST NOT** depend on a
> predicate that is undefined in this sense.

The definition test is stated here rather than borrowed. An earlier draft cited a three-part test from proposal
0120, which that proposal carried until it was narrowed to the definition-homes contradiction alone; the test
is not in its merged text, so citing it would point at nothing.

### Reconciling with proposal 0120

0120 re-anchors §5.9's sentence about "the originating fixture's prose" to mean a **per-directory harness
note**, so that §5.9 names the same second home as every other definition rather than a third one. This
proposal requires a predicate to be defined in **the prose of the fixture that uses it**. Those are different
places, and both proposals are amending the same sentence.

The corpus settles which is right for predicates: 89 predicate names are documented in the sidecar of the
fixture that uses them, and a predicate is by construction fixture-specific, so a per-directory note is the
wrong granularity for it. A close-ordering claim about one fixture's span tree does not generalize to its
directory.

So 0120's re-anchoring is correct for directives and over-broad for predicates, which it swept in without
measuring what the corpus does with them. **Whichever of the two accepts second reconciles the sentence**, and
the reconciliation is to scope 0120's re-anchoring to directives and leave §5.9's predicate delegation
pointing at fixture prose. Both are still Draft, so either can carry the wording; this proposal states the
conflict rather than leaving the second accept to discover it.

### §9: the error token

> **`fixture_predicate_unknown`**: an adapter encountered an invariant predicate name it does not implement.
> Silent skipping would report coverage that does not exist, so the adapter **MUST** raise and surface the
> predicate name plus the fixture location.

### The definition requirement is an authoring rule, not an adapter obligation

The definition requirement above binds **fixture authors**, and it has no adapter-observable consequence. An
adapter cannot tell whether a predicate it implements was documented, and it should not have to: it implements
the name either way. So no error token attaches to it, and no conformance run detects a breach.

That is worth stating plainly rather than leaving a reader to infer an enforcement that does not exist,
particularly in a proposal arguing that an obligation without a failure mode is not an obligation. The
requirement is not self-defeating for the same reason a style rule is not: it constrains what may be written,
and what enforces it is review of the fixture rather than execution of it. A repository check could enforce it
mechanically, which *Open questions* records rather than proposes, because it depends on the definition test
being machine-decidable and proposal 0120 found that it is not.

## Conformance test impact

**This is the largest conformance change in the current batch, and it should be sized honestly.** After this,
an adapter that does not implement a predicate fails the fixture using it. No adapter implements all 934
names. So on the day this is accepted, every adapter's conformance numbers drop, and they drop by the amount
of coverage that was never real.

That is the intended effect and it is why the change is worth making, but it makes the accept a decision about
timing as well as wording. Both candidate texts are drafted in *Detailed design*:

1. **Immediate.** The numbers become true at once, and the gap is visible and worked down. Preferred on the
   merits, because the alternative's interim state is a conformance report that passes while naming what it
   did not check.
2. **Staged.** The definition requirement and the error token land now, and the failure obligation takes
   effect at a named future spec version, with the skipped predicate names reported in the interim so the gap
   stays measurable.

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

1. **Immediate or staged.** Both forms are drafted in *Detailed design*, so the accept chooses between texts
   rather than composing one. This proposal prefers the immediate form on the merits and says so; the staged
   form exists for the case where the conformance drop needs a scheduled window, and it needs a target version
   substituted for `<TARGET>`.
2. **Whether a repository check should enforce the definition requirement.** It would have to decide whether
   prose states an obligation, which proposal 0120 established is not machine-decidable, so a check would
   either under-enforce or encode a guess. Left out of scope, and recorded because the alternative is that
   someone writes it and discovers the same wall.
2. **Whether the same treatment is owed to the `carries` assertion surface** and any other name-keyed
   vocabulary, which have not been swept. This proposal covers the three invariant blocks it measured;
   whether other surfaces share the shape is unmeasured and should not be assumed either way.
