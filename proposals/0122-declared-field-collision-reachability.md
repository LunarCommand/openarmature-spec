# 0122: Settle the Shape of the Extras Surface

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-19
- **Accepted:**
- **Targets:**
  - spec/llm-provider/spec.md **§6 Extras pass-through**: state the shape of the extras surface. It is a
    **named container on the config record**, distinct from the declared fields, which is what
    retrieval §10, every §8.x mapping, and all 24 fixtures that use it already assume. §6's current wording
    ("fields beyond the declared set", "preserved on the config record") reads equally well as undeclared
    fields sitting alongside the declared ones, and an implementation has read it that way and concluded that
    a shipped fixture pins an unreachable case. Fix the container's **name** as `extras`, normative for
    cross-implementation consistency on the §5.5.4 precedent, while leaving its ergonomics
    implementation-defined.
  - spec/retrieval-provider/spec.md **§8.1, §8.3 and §8.4**: give each mapping the clause-(b) realization
    enumeration §6 requires. §10 names three retrieval realization sites for the declared `dimensions`
    (`dimensions` on §8.1 TEI and §8.3 OpenAI, `output_dimension` on §8.4 Cohere) and none of the three
    mappings enumerates it. §8.4 is the sharpest case, stating it manages exactly two keys and that "every
    other undeclared extras key keeps §6's untouched pass-through", which contradicts §10 outright. These
    enumerations date from proposal 0105, which deferred the declared-field realizations to a follow-on, and
    0108 extended llm-provider's three mappings but not retrieval's.
  - spec/retrieval-provider/spec.md **§8.4**: change the malformed-`embedding_types` element test from "not a
    precision string" to "not a string". The current wording reads as a vocabulary check, which the general
    §6 rule it inherits explicitly is not, and an implementation has already read it that way.
  - spec/retrieval-provider/conformance/053-embed-cohere-embedding-types-malformed.{yaml,md}: add a case
    pinning a well-typed but provider-unrecognized element, including the empty string, as **merging** rather
    than being treated as malformed.
  - spec/retrieval-provider/conformance/ **new fixture**: pin the Cohere clause-(b) rename arm (declared
    `dimensions` set, `output_dimension` supplied in the extras container) across the reject and no-op
    outcomes. The §8.4 enumeration correction is a behavior change, since that key rides untouched today, so
    it needs a fixture rather than inheriting coverage. Retrieval 052 already pins the same-name arm that
    §8.1 and §8.3 share, so those two need no new fixture once their enumerations name the realization.
- **Related:** 0099 (settled the adjacent *value* case), 0105 (introduced the managed-key enumeration
  requirement), 0108 (introduced clause (b), which §8.4's enumeration was never extended for), 0113 (the
  malformed-merge rule whose wording this tightens), 0120 (same defect shape: two sections assuming
  incompatible models with nothing settling which governs)

## Summary

§6 never states what the extras surface *is*. Read one way it is a named container on the config record
alongside the declared fields; read the other it is undeclared fields on the record itself. The two readings
disagree about whether a caller can set a declared field and an extras key of the same name at once, which is
exactly what proposal 0108's clause (b) governs. Retrieval §10, every §8.x mapping and 24 fixtures assume the
container; one implementation read §6 the other way and concluded that shipped fixtures pin an unreachable
case. This settles the shape, reconciles an enumeration §8.4 never updated for clause (b), and tightens a
malformed-element test that reads as a vocabulary check.

## Motivation

### Two readings of the same sentence

§6 says: "`RuntimeConfig` is extensible. Implementations MUST accept fields beyond the declared set above
without erroring at the API boundary; undeclared fields MUST be preserved on the config record and forwarded
to the wire request body untouched."

**Reading A, a named container.** The config record carries its declared fields plus a container holding
undeclared keys. A caller can set the declared `stop_sequences` and put a key also named `stop_sequences` in
the container; they occupy different places.

**Reading B, undeclared fields on the record.** Extras *are* fields on the record, beyond the declared ones. A
record cannot carry two fields of one name, so a caller cannot set a declared field and supply an extras key
of the same name. The same-name collision is inexpressible.

Nothing in §6 chooses. "Preserved on the config record" is satisfied by either.

### Everything except that sentence assumes Reading A

- **Retrieval §10** states it outright: a declared field's value "is set through its declared slot, never
  through the extras bag (the bag carries only *undeclared* keys) — though a key whose **name** matches a
  declared field's wire realization (`dimensions`, or Jina's `task`) **may still appear in the bag as an
  undeclared colliding key**, governed by the realization rule below." Under Reading B that sentence
  describes something a caller cannot do.
- **The mappings** speak of "the bag" as a place: an unmanaged extras key "rides the bag untouched"
  (llm §8.1.5, retrieval §8.2).
- **The fixtures**, 24 of them, write `config: {<declared>: ..., extras: {...}}`. Fixture 079 sets
  `stop_sequences: ["STOP"]` and `extras: {stop_sequences: ["END"]}` in one call and asserts they merge, and
  its header says so: "the same wire NAME as the declared field, no rename, unlike OpenAI's `stop`".

So Reading A is the operative model everywhere the spec is concrete. Reading B survives only in §6's
abstraction, which is the section an implementer reads first.

### The divergence is real, not hypothetical

An implementation read §6 as Reading B, built its extras surface accordingly, and concluded that llm fixture
075 and retrieval fixture 052 pin a collision no caller can reach. Both fixtures are held unrun on that basis.
That is a correct deduction from Reading B and a wrong one about the corpus, and it happened because §6 let
them make it.

Under Reading A both fixtures are reachable and correct, as are 079's merge cases and everything else clause
(b) governs. Nothing needs retiring or repointing; the surface needs stating.

### An enumeration that clause (b) left behind

§6 requires each mapping to "enumerate the keys it manages (and, under **(b)**, the declared field each one
realizes)". Proposal 0105 introduced that requirement and explicitly **deferred** the declared-field
realizations to a follow-on; 0108 was that follow-on, and it extended llm-provider's mappings but not
retrieval's.

A sweep of every mapping confirms the split. llm-provider is complete: §8.1, §8.2 and §8.3 each carry a
*Declared-field realizations (§6 clause (b))* block. Retrieval is not:

| Mapping | Clause-(b) realization per §10 | Enumerated in the mapping |
|---|---|---|
| §8.1 TEI | `dimensions` to `dimensions` | no, only the clause-(a) `truncate` |
| §8.2 Jina | `input_type` to `task` | yes |
| §8.3 OpenAI | `dimensions` to `dimensions` | no, only `encoding_format` as unmanaged |
| §8.4 Cohere | `dimensions` to `output_dimension` | no, and it states it manages exactly two keys |

§8.4 is the sharpest case because its enumeration is explicit: "§8.4 **manages** two wire keys ...
`embedding_types` ... and `truncate` ... Every other undeclared extras key keeps §6's untouched
pass-through." §10 says `output_dimension` is a clause-(b) realization and therefore managed while
`dimensions` is set. Two implementers reading §8.4 and §10 reach opposite answers about whether an extras
`output_dimension` is rejected or passed through, and the same question is simply unanswered for TEI and
OpenAI embeddings.

### A structural test that reads as a vocabulary check

§6's merge arm is explicit: "Malformation is judged **structurally**; the mapping does **not** semantically
validate element *values* against a provider vocabulary (none is enumerated), so a well-typed but
provider-unrecognized member is not malformed — it merges, and the provider rejects it if unsupported."

§8.4 restates that for `embedding_types` as "an element that is not a precision string", readable either as
*a string of the kind this field holds* or *a string naming a precision*. The second contradicts the rule
§8.4 says it inherits.

What settles it is internal to §8.4: that mapping knows how to enumerate a closed vocabulary normatively and
does so for `input_type`, whose recognized set is "still fixed — a value outside it is still a pre-send
`provider_invalid_request`". It does no such thing for `embedding_types`. So the structural reading governs,
and a well-typed element such as an empty string merges. An implementation has already read it the other way
and gates the empty string locally. No shipped fixture exercises the case, so it is latent rather than a live
break.

## Detailed design

### §6: name the surface

Amend *Extras pass-through* to state the shape:

> Undeclared fields supplied for a call are carried in a **named extras container** on the config record,
> distinct from its declared fields. A key in that container is undeclared **by virtue of being there**, so a
> key whose name matches a declared field, or matches the wire name a mapping realizes a declared field
> under, is a legitimate extras key and is governed by *Managed-field collision* below. The container is
> addressable separately from the declared fields, so a caller can set a declared field and supply a
> same-named extras key in one call.
>
> The container's **ergonomics** are implementation-defined (a constructor argument, a builder method, a
> mapping-valued field), but its **name is `extras`** and is normative for cross-implementation consistency,
> so a caller moving between implementations writes the same key.

That is the whole resolution. Clause (b) is unchanged, every arm of it stays reachable on every mapping, and
the fixture corpus is correct as it stands.

The name is fixed for the same reason observability §5.5.4 fixes its flag names, which reads "specific
ergonomics (constructor argument, builder method, etc.) are implementation-defined; flag names below are
normative for cross-implementation consistency". A name the caller types is not the mechanism-level API shape
the language-agnostic rule holds back from; it is the vocabulary the caller writes, and leaving it free would
repeat this proposal's own defect one level down. All 24 fixtures already spell it `extras`, so fixing it
also closes the gap between the fixture convention and the caller surface, which the adapter currently
absorbs.

**This has a cost, and it belongs on the record.** An implementation whose extras surface is undeclared fields
on the config record satisfies §6's first sentence but not this one, and will need an addressable container
named `extras`. That is a real change for at least one implementation, and it is the price of the corpus and
§10 being right about a surface §6 declined to pin down. The name adds no work beyond the container itself,
since an implementation adding one chooses a name either way.

### Retrieval §8.1, §8.3 and §8.4: complete the managed enumerations

Each of the three gains the clause-(b) block llm-provider's mappings already carry, naming the realization and
the declared field it realizes. For §8.4, whose enumeration is explicit and currently excludes it:

> §8.4 **manages** three wire keys: `embedding_types` (list-shaped, merge), `truncate` (scalar fail-loud flag,
> reject), and `output_dimension` (the realization of the declared `dimensions` under §6 clause (b),
> non-additive scalar, managed while `dimensions` is set and unmanaged when it is absent). Every other
> undeclared extras key keeps §6's untouched pass-through.

§8.1 and §8.3 gain the equivalent for their same-name `dimensions` realization, non-additive, managed while
the declared field is set and unmanaged when absent.

Each mapping **restates** the contract rather than cross-referencing another, following llm-provider's
pattern: §8.2 and §8.3 there each carry a full block rather than pointing at §8.1's, because the specifics
differ per mapping (Anthropic's `stop_sequences` is array-only with no scalar-string coercion, Gemini's
realizations are camelCase under `generationConfig`). A cross-reference cannot carry those.

### §8.4: structural, not vocabulary

Change the malformed-element test to read "not a list, or a list carrying an element that is not a **string**",
and add:

> The element test is **structural**, per the general rule this inherits (llm-provider §6): an element of the
> expected type that names no precision this mapping recognizes is **not** malformed. It merges, and the
> provider rejects it if unsupported. `embedding_types` is not a closed vocabulary in this mapping; contrast
> `input_type` above, whose recognized set is fixed and whose unrecognized values are rejected pre-send.

### Fixtures

**No fixture is retired or repointed.** Under the settled surface, llm 075 (same-name scalar reject), llm 079
(same-name merge on Anthropic), retrieval 051 (Jina `task` rename) and retrieval 052 (same-name `dimensions`
on OpenAI) are all reachable and all correct. The implementation holding 075 and 052 unrun can run them.

**053 gains a case** supplying `embedding_types: ["float", ""]` alongside a well-typed unrecognized precision,
asserting the wire carries the merged list rather than the mapping's mandatory value alone. That pins the
structural reading against the vocabulary one.

**The three enumeration corrections need fixtures**, because each is a behavior change rather than a
restatement. Today §8.4's "every other undeclared extras key keeps §6's untouched pass-through" sentence makes
an extras `output_dimension` ride through; afterwards, while declared `dimensions` is set, a conflicting one
is rejected pre-send and a matching one is absorbed. §8.1 and §8.3 move from unanswered to managed on the
same rule. A new fixture pins the Cohere rename arm (`dimensions` declared, `output_dimension` in the bag),
and retrieval 052 already pins the same-name arm that §8.1 and §8.3 share, so it covers those two once their
enumerations name it.

## Conformance test impact

**No fixture changes except 053's new case.** The corpus is correct under the settled reading; that is the
point of settling it in this direction rather than the other.

**One implementation has work.** An extras surface built as undeclared fields on the config record needs an
addressable container named `extras`, and the two fixtures currently held unrun become runnable. The name
constrains the caller-facing surface but nothing observable in wire output or conformance results, so it
cannot make a passing implementation fail; it is a consistency requirement rather than a behavioral one. 053's new case may fail an
implementation that gates the empty string locally, which is the second divergence being closed.

**§8.4's enumeration change is a behavior change for Cohere embeddings**: an extras `output_dimension` that
today rides untouched per §8.4's "every other undeclared extras key" sentence must, while declared
`dimensions` is set, be rejected pre-send when conflicting and absorbed when matching. That follows from §10
and clause (b) already; §8.4 was the section out of step.

## Alternatives considered

1. **Do nothing.** Rejected: §6 admits two readings that disagree about whether shipped fixtures are
   reachable, and an implementation has already acted on the reading the rest of the spec contradicts.
2. **Settle toward Reading B** (undeclared fields on the record) and fix everything else to match. Rejected,
   and this was an earlier draft of this proposal. It requires rewriting §10's colliding-key clause, retiring
   or repointing llm 075, llm 079 and retrieval 052, and forbidding a shape 24 fixtures use. It would also
   forbid fixture 077, since `stream` is realized under its own name with no rename, which is the fixture that
   would have to justify retiring 075. Reading B is the minority reading and settling toward it costs far more
   than it saves.
3. **Leave the surface unstated and change only the fixtures.** Rejected: the fixtures are not wrong under the
   operative reading, and changing them would encode Reading B without saying so, leaving the next implementer
   to make the same deduction.
4. **Leave §8.4's enumeration alone** and treat §10 as authoritative. Rejected: §6 requires the mapping to
   enumerate its own managed keys, so a mapping whose enumeration omits one is non-conforming to §6
   regardless of what §10 says. The enumeration is the mapping's obligation.
5. **Resolve `embedding_types` toward the vocabulary reading.** Rejected: it contradicts the general rule §8.4
   says it inherits, and it would require §8.4 to enumerate a closed precision vocabulary with a reject rule,
   which it deliberately does not do. Every unrecognized precision would then need spec maintenance each time
   a vendor adds one.

## Open questions

None. The three questions this proposal opened while drafting are settled in the text above: each retrieval
mapping restates its clause-(b) contract rather than cross-referencing, following llm-provider's pattern; the
§8.4 enumeration correction is a behavior change and therefore carries a fixture; and the extras container's
name is fixed as `extras` for cross-implementation consistency, on the §5.5.4 precedent.
