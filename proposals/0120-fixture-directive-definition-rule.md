# 0120: Reconcile Where a Fixture Directive May Be Defined

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-15
- **Accepted:** 2026-08-26
- **Targets:**
  - spec/conformance-adapter/spec.md **§5 preamble, §3.2, §3.3, §8.2, §11**: reconcile six of the seven
    statements about where a directive's definition may live. They currently name four different candidate
    homes and disagree about which of them count, which leaves two conforming adapters able to reach opposite
    verdicts on the same shipped fixture. State one answer, and re-anchor §8.2's vocabulary reference to it.
    The seventh statement is **§5.9**, which is analyzed here but **deliberately left unamended and receives
    no cross-reference**; adding one would re-anchor its predicate delegation to a rule that excludes the
    fixture's own prose, which is the change this proposal withdrew. See *Detailed design*.
- **Related:** 0081 and 0107 (prior directive-vocabulary documentation passes), 0119 (documents
  `content_repeat` and `attribute_truncation`; its open question 1 is what surfaced this)

## Summary

The conformance-adapter spec says in seven places where a fixture directive may be defined, naming four
different candidate homes, and the statements contradict each other. For a directive defined only in a
harness note, §8.2 requires an adapter to raise and §3.2 requires the same adapter to implement it.
This proposal states one answer to "where may a definition live" and re-anchors the affected sections to it.
It resolves the **directive** surface; §5.9's invariant predicates carry the same contradiction and are left
for a proposal that can measure them on their own evidence.

It deliberately does **not** address what counts as a directive in the first place, which is a separate and
larger question deferred to a follow-on (see *Explicitly out of scope*).

## Motivation

### Seven statements, four candidate homes

| Section | What it says | Home it sanctions |
|---|---|---|
| §5 preamble | "This section is the authoritative enumeration of directives currently in use." | §5 |
| §11 (opening) | "The directive vocabulary §5 is the authoritative enumeration; this section is a navigational cross-reference." | §5 |
| §8.2 | "Parsing MUST be lossless against the §5 directive vocabulary; unknown directives MUST raise `fixture_directive_unknown` (per §9) rather than being silently skipped or treated as defaults." | §5 |
| §3.2 | A fixture-header comment block "is normative for the observability fixture suite even though it isn't part of this capability spec"; implementations "MUST honor per-directory harness notes"; per-directory specialization is "a permitted extension". | a fixture-header comment |
| §11 (closing) | "Each capability's `conformance/` directory MAY contain a per-directory README documenting specialized harness contracts (per §3.2). The general directive vocabulary lives here; the per-directory specialization lives there." | a per-directory README |
| §5.9 | "Fixture-specific predicates not listed here are documented in the originating fixture's prose per §3.2 per-directory harness notes; adapters MUST also implement those." | the originating fixture's prose |
| §3.3 | "The capability spec is the authoritative schema reference; per-directory READMEs are navigational aids at most." | §5 only, demoting the README |

Three of the seven say §5 is authoritative. Three sanction a second home, and they name three *different*
second homes: a fixture-header comment (§3.2), a per-directory README (§11), and the originating fixture's
own prose (§5.9). The seventh (§3.3) demotes one of those three while saying nothing about the other two.

### The contradiction is operative, not theoretical

Take a directive defined only outside §5, which §3.2, §5.9 and §11 all sanction in one form or another. It is
not in §5. So:

- **§8.2 requires an adapter to raise** `fixture_directive_unknown` on it, because §8.2's vocabulary is
  anchored to §5 and the directive is outside it.
- **§3.2 requires the same adapter to implement it**: "Implementations MUST honor per-directory harness
  notes when the fixture's YAML references them."

Both are MUSTs. Both are conforming readings. They cannot both be satisfied.

**Worked example.** `expected.span_tree` appears nowhere in §5. Its only occurrence in this capability spec
is §3.2's worked example, which lists it among the "expected-outcome shapes specific to observability"
documented in `spec/observability/conformance/001-otel-basic-trace.yaml`'s header comment, and which §3.2
declares "normative for the observability fixture suite even though it isn't part of this capability spec".
Fifty observability fixtures assert `expected.span_tree`. §3.2's MUST is conditional, binding "when the
fixture's YAML references them", and the reading this argument uses is that a fixture asserting
`expected.span_tree` is referencing the note that defines it, there being nowhere else the shape is defined.
Under that reading an implementer following §8.2 raises and fails all fifty, while an implementer following
§3.2 implements it and passes. Same fixtures, opposite verdicts, both defensible from the shipped text.

Two things about this example are worth stating rather than glossing. **A fifty-first fixture sits outside the
rule's reach**: `spec/sessions/conformance/012-session-observability.yaml` also asserts `expected.span_tree`,
and `spec/sessions/conformance/` has no harness note defining it. §3.2 scopes the observability note to "the
observability fixture suite", so after this proposal that fixture is in neither home and §8.2 still requires
an adapter to raise on it. A per-directory home cannot cover a cross-directory user, and this proposal does
not claim to fix that. **And by this proposal's own home-1 criterion, `span_tree` belongs in §5**, since two
capabilities' fixtures use it. That is the rule working as intended: it does not merely resolve the
contradiction, it names where the definition should live. The rule is prospective, so it does not force the
move; a later documentation pass promoting `span_tree` to §5 would close both points at once.

That is the defect. It needs no count to establish, and one example is enough to show two implementations can
diverge on shipped work today.

## Detailed design

### One answer to "where may a definition live"

Add to §5's preamble, and cross-reference it from §3.2, §3.3, §8.2 and §11 (**not** §5.9, per the
deferral below):

> **Definition homes.** A directive introduced or redefined after this proposal is accepted MUST have its
> definition in one of exactly two places:
>
> 1. **§5 of this capability spec**, for a directive used by more than one capability's fixtures, or whose
>    contract is general even if only one capability currently exercises it.
> 2. **A per-directory harness note**, for a directive whose contract is specific to one capability's
>    fixtures and does not generalize. A per-directory harness note is the fixture-header comment block or
>    per-directory README described in §3.2, belonging to the `conformance/` directory whose fixtures use the
>    directive.
>
> Together these are the **recognized vocabulary**. A definition in either home is normative and an adapter
> MUST honor it. §5 remains authoritative for the general surface and for this rule.
>
> Where §5 and a per-directory note both address the same directive, they are read together: §5 governs any
> point on which they conflict, and the note MAY supply detail §5 leaves to it. §5 naming a directive does
> not void a note that specifies its shape.

The two-home shape is what the spec already practises; this states it once instead of three times with three
different second homes.

**Directives already in use without a definition.** A body of directives currently in use has a definition in
neither home. This proposal neither creates nor resolves that condition. Such a directive sits outside §8.2's
vocabulary today, because that vocabulary is anchored to §5, and the re-anchoring below does not move it,
because it is in neither home. Identifying which keys are genuinely directives requires settling the
open-versus-closed vocabulary question this proposal puts out of scope, so closing them is the follow-on's
work. The rule above is stated prospectively so that it governs where a definition belongs without
retroactively invalidating directives it cannot yet identify.

### Consequential edits

- **§3.3** currently reads that per-directory READMEs are "navigational aids at most". Narrow it: a
  per-directory README that documents no directive is a navigational aid, while the harness-note content §3.2
  describes is normative for the directives it defines. As written, §3.3 contradicts both §3.2 and §11.
- **§11's closing paragraph** keeps its division ("the general directive vocabulary lives here; the
  per-directory specialization lives there") and gains a pointer to the definition-homes rule, so it reads as
  an instance of that rule rather than an independent sanction.
- **§5.9 is deliberately left unamended.** Its sentence delegates fixture-specific predicates to "the
  originating fixture's prose per §3.2 per-directory harness notes", naming a per-fixture home and a
  per-directory one in the same breath. An earlier revision of this proposal re-anchored it to the
  per-directory note, so that §5.9 would name the same second home as everything else. That is withdrawn:
  of the 934 distinct predicate names in shipped fixtures, 803 appear in exactly one file, so a predicate
  does not generalize to its directory; and where the corpus documents a predicate at all it does so per
  fixture, in the sidecar of a fixture that uses it, which accounts for 99 of the 934. The remaining ~9 in 10
  are documented nowhere. A per-directory anchor therefore matches neither the documented population nor the
  undocumented one. Expressing that here would require the definition-homes rule to admit the fixture's own
  prose (§3.1's `NNN-name.md`) as a third artifact form, which neither §3.2 nor §11 describes. That is a
  larger change than this proposal's scope, and the predicate surface should settle it on its own evidence.

  **The §8.2-versus-§5.9 contradiction therefore survives this proposal for invariant predicates.** A
  fixture-specific predicate documented only in its own fixture's prose remains outside the recognized
  vocabulary, so §8.2 still requires an adapter to raise while §5.9 still requires it to implement. This
  proposal resolves the directive surface and states the remaining gap rather than appearing to close both.
- **§8.2** is amended in exactly one respect: its vocabulary reference changes from "the §5 directive
  vocabulary" to "the recognized vocabulary" as defined above. Nothing else in §8.2 changes.

That §8.2 edit is the whole of the resolution. The unknown-directive rule, its trigger, and its error token
are untouched: §8.2 and §9 already require an adapter to raise rather than silently skip, and this proposal
neither strengthens nor weakens that. It only corrects which vocabulary decides whether a directive is
unknown.

### Explicitly out of scope

This proposal does **not** address **what counts as a directive**. That question is separate, larger, and
genuinely unsolved.

§2 already distinguishes a **Directive** (a named field declaring something the adapter must translate) from
an **Assertion shape** (a field under `expected:`) and an **Invariant** (a *name-keyed* boolean predicate).
What the spec never states is which of those name spaces are **closed** and which are **open**. Some are open
by design: an `invariants:` block is name-keyed, and the `capture_as` mechanism lets a fixture author mint an
arbitrary key that then appears under `expected:`. A rule that treated every key at a position as a directive
requiring a definition would therefore demand definitions for names that are, correctly, invented per fixture.

Resolving that requires deciding, per position, whether the vocabulary is closed (the adapter MUST implement
every name and a fixture MUST NOT invent one) or open (the fixture MUST define each name it uses and the
adapter MUST implement what the fixture defines). That is a follow-on proposal. Until it lands, §8.2's
unknown-directive rule stays as ambiguous in practice as it is today. This proposal removes one of the two
ambiguities rather than pretending to remove both.

No enforcement check ships with this proposal, for the same reason: a check cannot decide whether a key is an
undefined directive or a legitimate author-chosen name until the follow-on settles that.

## Conformance test impact

**No fixture file changes**, no new or changed directive, no new assertion. The change is to prose that tells
an adapter author where to look for a definition. Runnability does change for one population, which is the
point of the proposal rather than a side effect.

Three populations need distinguishing. A directive defined only in a per-directory harness note is in an
impossible position today, required to raise by §8.2 and to be implemented by §3.2; after this it is
unambiguously in the recognized vocabulary and an adapter implements it, so an adapter that raises today
gains those fixtures rather than failing them. `expected.span_tree` and the other shapes named in §3.2's note
are this population: an adapter built strictly against §8.2 gains **50 runnable observability fixtures** on
`span_tree` alone. The sessions fixture that also asserts it is not in this population, for the reason the
worked example gives. An **invariant predicate** documented only in its own fixture's prose is unchanged by this
proposal: it stays outside the recognized vocabulary, and the contradiction over it stays live pending the
predicate proposal. A directive defined nowhere is outside §8.2's vocabulary before and after, so its status
is unchanged and this proposal makes no claim to have fixed it.

## Alternatives considered

1. **Do nothing.** Rejected: the conflicting MUSTs are live in the shipped spec, and the worked example shows
   two conforming implementations reaching opposite verdicts on a shipped fixture.
2. **Resolve toward §5 only**, retiring per-directory notes as a definition home. Rejected: §3.2 exists
   because a genuinely capability-local harness contract does not belong in a cross-capability surface, and
   §5.9 deliberately scopes its enumeration "to keep this list maintainable". This would move a large body of
   definitions into §5 for no benefit.
3. **Resolve toward the notes only**, making §5 non-authoritative. Rejected: it discards the cross-capability
   surface that makes a directive portable, and §5 is what a new implementation reads first.
4. **Also settle the open-versus-closed vocabulary question here.** Rejected, and this is the substantive
   scoping decision. Two earlier drafts of this proposal attempted it and both failed: the first assumed the
   definition rule was missing when it already existed in three places, and the second proposed a
   position-based rule that would have required adapters to raise on `capture_as` labels, making 15 shipped
   prompt-management fixtures unrunnable. The two questions are separable, and the *where* question is
   bounded and verifiable on its own.
5. **Ship an enforcement check alongside.** Rejected: a check would have to classify every key as a directive
   or an author-chosen name, which is precisely the unsolved question. A check written now would encode a
   guess.

## Open questions

1. **Whether a per-directory README and a fixture-header comment should remain interchangeable.** This
   proposal treats both as "a per-directory harness note" because §3.2 and §11 already do. A per-directory
   note can hold a fixture-scoped entry: the note §3.2 uses as its worked example carries several, including
   `expected.log_records` for fixture 010 and `expected.no_openarmature_spans_on_global` for fixture 005. So
   the deferral of the predicate surface is about matching what the corpus actually does, documenting
   predicates in each fixture's own sidecar, rather than about what the note form permits. Whether §3.2
   should also describe the fixture's own prose (§3.1's `NNN-name.md`) as a note form is the question that
   surface will have to answer.
2. **Whether the read-together rule for §5 plus a note needs a worked example** in the spec text. §5.8's
   delegation of Langfuse assertion shapes to observability fixture headers is the natural candidate, since it
   is exactly the partial-definition case the rule exists to permit.
