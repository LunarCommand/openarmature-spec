# 0122: Pin the Reachability of the Declared-Field Collision Rule

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-19
- **Accepted:**
- **Targets:**
  - spec/llm-provider/spec.md **§6 Managed-field collision**: state the reachability condition on clause (b).
    A collision between an undeclared extras key and the wire realization of a declared field is reachable
    only where the mapping **renames** the field on the wire. Where the wire name equals the declared name,
    the collision cannot occur through the sanctioned caller surface, because extras are undeclared fields on
    the config record and a record cannot carry two fields of one name. The rule is unchanged; what it can be
    exercised on is stated.
  - spec/llm-provider/spec.md **§6 Extras pass-through**: clarify that `config.extras` as it appears in
    conformance fixtures is a fixture-schema device denoting the undeclared fields, not a second API surface.
    The caller-facing shape is undeclared fields on the config record, which is what makes the same-name
    collision unreachable.
  - spec/retrieval-provider/spec.md **§8.4**: change the malformed-`embedding_types` element test from "not a
    precision string" to "not a string". The current wording reads as a vocabulary check, which the general
    §6 rule it inherits from explicitly is not, and an implementation has already read it that way.
  - spec/llm-provider/conformance/075-managed-declared-scalar-collision.{yaml,md}: **retire**. Both of its
    cases rest on a same-name collision that cannot be reached, and fixture 077 already covers both arms of
    the non-additive rule through a reachable path.
  - spec/retrieval-provider/conformance/052-embed-openai-dimensions-collision.{yaml,md}: **repoint** from the
    OpenAI mapping, where `dimensions` keeps its declared name on the wire and the collision is unreachable,
    onto the Cohere mapping, where §8.4 renames `dimensions` to `output_dimension` and the collision is real.
  - spec/retrieval-provider/conformance/053-embed-cohere-embedding-types-malformed.{yaml,md}: add a case
    pinning a well-typed but provider-unrecognized element, including the empty string, as **merging** rather
    than being treated as malformed.
- **Related:** 0099 (made this same reachability argument for `input_type`), 0105 and 0108 (introduced the
  managed-field collision rule and clause (b)), 0113 (the malformed-merge rule whose wording this tightens)

## Summary

Proposal 0108's clause (b) governs a collision between an undeclared extras key and the wire realization of a
declared field. Two of its fixtures pin instances of that collision which cannot occur, because the extras
surface is undeclared fields on the config record and both fixtures chose a field whose wire name equals its
declared name. Separately, the malformed-element test §8.4 states for `embedding_types` reads as a vocabulary
check while the rule it inherits is explicitly structural, and an implementation has diverged on that reading.
The rules are sound; this pins what they can be exercised on and removes the ambiguity.

## Motivation

### The same-name collision cannot be reached

§6 defines the extras surface: "Implementations MUST accept fields beyond the declared set above without
erroring at the API boundary; undeclared fields MUST be preserved on the config record and forwarded to the
wire request body untouched."

Extras are therefore **undeclared fields on the config record**, not entries in a separate container. A record
cannot carry two fields of the same name. So for a declared field whose mapping emits it under its own name,
a caller cannot simultaneously set the declared field and supply an undeclared field of that name: the second
is not undeclared, it is the first.

Clause (b) is consequently reachable only where the wire name **differs** from the declared name:

| Instance | Declared | Wire | Reachable |
|---|---|---|---|
| `stop_sequences` on OpenAI | `stop_sequences` | `stop` | yes |
| `stop_sequences` on Gemini | `stop_sequences` | `stopSequences` | yes |
| `stream` | a `complete()` argument, not a config field | `stream` | yes |
| `dimensions` on Cohere | `dimensions` | `output_dimension` | yes |
| `temperature` on OpenAI | `temperature` | `temperature` | **no** |
| `dimensions` on OpenAI | `dimensions` | `dimensions` | **no** |

**The spec has already made this argument once.** Proposal 0099 struck a §8.4 sentence claiming Cohere's other
`input_type` values "are reached via the extras-pass-through bag", on the grounds that it was "unachievable,
since OA's `input_type` is a **declared** field and the bag carries only *undeclared* keys (llm-provider §6)".
That is the same reasoning, accepted one proposal before 0108 shipped two fixtures resting on the shape it
rules out.

Fixture 075 states the condition in its own header: it pins the scalar arm on `temperature`, noting "wire name
== the declared name on OpenAI". Retrieval fixture 052 does the same for `dimensions` on the OpenAI embeddings
mapping.

### Why fixture syntax made this easy to miss

Conformance fixtures express the collision as `config: {temperature: 0.7, extras: {temperature: 0.2}}`, which
reads as though `extras` were a container a caller populates directly. It is not: it is a fixture-schema
device for saying "these are the undeclared fields", and the conformance-adapter spec never defines it as an
API shape. Read as a container, the same-name collision looks perfectly reachable. Read as §6 defines the
surface, it is not. Stating that distinction is what stops the next fixture making the same choice.

### The malformed-element test reads as a vocabulary check

§6's merge arm is explicit that malformation is structural: "Malformation is judged **structurally**; the
mapping does **not** semantically validate element *values* against a provider vocabulary (none is
enumerated), so a well-typed but provider-unrecognized member is not malformed — it merges, and the provider
rejects it if unsupported."

§8.4 restates that for `embedding_types` as "not a list, or a list carrying an element that is not a precision
string". "Precision string" is readable two ways: a string of the kind this field holds (structural), or a
string naming a precision (vocabulary). The second reading contradicts the rule §8.4 says it is inheriting.

What settles it is internal to §8.4. That mapping knows how to enumerate a closed vocabulary normatively and
does so for `input_type`, where the recognized set is "still fixed — a value outside it is still a pre-send
`provider_invalid_request`". For `embedding_types` it does no such thing: the precisions appear only in prose
describing what rides the extras bag, with no reject rule attached. So `embedding_types` is not a closed
vocabulary, the structural reading governs, and a well-typed element such as an empty string merges and is the
provider's to reject.

An implementation has already read it the other way and gates the empty string locally, which is the
divergence the wording invites. No shipped fixture exercises the case, so it is latent rather than a live
conformance break, which is why it is worth pinning now rather than after two implementations disagree in
the field.

## Detailed design

### §6: the reachability condition

Append to clause (b):

> **Reachability.** This clause is exercisable only where the mapping emits the declared field under a wire
> name that **differs** from the declared name. Extras are undeclared fields on the config record (see
> *Extras pass-through* above), and a record cannot carry two fields of one name, so where the wire name
> equals the declared name a caller cannot both set the declared field and supply an undeclared field of that
> name. Such a pairing is not a collision the caller can express, and a conformance fixture MUST NOT pin one.
> The rule itself is unchanged and applies wherever the wire name is renamed.

### §6: what `config.extras` means in a fixture

Append to *Extras pass-through*:

> Conformance fixtures denote the undeclared fields with a `config.extras` mapping. That is a fixture-schema
> device for identifying which fields are undeclared, not a second caller-facing surface: the API shape this
> section defines is undeclared fields on the config record itself.

### §8.4: structural, not vocabulary

Change the malformed-element test to read "not a list, or a list carrying an element that is not a **string**",
and add:

> The element test is **structural**, per the general rule this inherits (llm-provider §6): an element of the
> expected type that names no precision this mapping recognizes is **not** malformed. It merges, and the
> provider rejects it if unsupported. `embedding_types` is not a closed vocabulary in this mapping; contrast
> `input_type` above, whose recognized set is fixed and whose unrecognized values are rejected pre-send.

### Fixtures

**075 is retired.** Both cases pin an unreachable collision. Fixture 077 already covers the non-additive rule
through `stream`, which is reachable because `stream` is a `complete()` argument rather than a config field,
and covers all three outcomes: conflicting reject in both directions, and the matching no-op. Retiring 075
loses no coverage.

**052 is repointed** from OpenAI to Cohere. On the OpenAI embeddings mapping `dimensions` keeps its declared
name, so the fixture pins the unreachable case. On Cohere, §8.4 renames it to `output_dimension`, so a caller
can set the declared `dimensions` and an undeclared `output_dimension` at once and the collision is real. That
keeps retrieval's clause-(b) coverage and moves it onto a path a caller can take. No fixture currently
exercises an `output_dimension` collision, so this adds coverage rather than relocating it.

**053 gains a case** supplying `embedding_types: ["float", ""]` alongside a well-typed unrecognized precision,
asserting the wire carries the merged list rather than the mapping's mandatory value alone. That is what pins
the structural reading against the vocabulary one.

## Conformance test impact

**One fixture retired, one repointed, one extended.** Retiring 075 is the only coverage question, and 077's
three cases cover the same rule through a reachable path, so the answer is that nothing is lost.

**052's repoint changes which mapping it targets**, so an implementation that passed it against OpenAI must
now satisfy it against Cohere. That is the point: the OpenAI form asserted behavior no caller can trigger.

**053's new case may fail an implementation that gates the empty string locally.** That is the divergence
being closed, and the failing implementation is the non-conforming one under the structural reading.

No new directive. The `config.extras` clarification changes no fixture syntax; it states what the existing
syntax means.

## Alternatives considered

1. **Do nothing.** Rejected: two fixtures assert behavior no caller can reach, so an implementation either
   holds them deferred, as one already does, or writes unreachable code to satisfy them. The
   `embedding_types` ambiguity separately leaves two implementations free to diverge.
2. **Make the same-name collision reachable** by defining extras as an explicit container alongside the
   declared fields. Rejected: it would add a second caller-facing surface for the same thing, contradict §6's
   existing definition, and change the API shape of every implementation to make an unreachable rule
   reachable. The rule is not valuable enough to reshape the surface for.
3. **Retire clause (b) entirely.** Rejected: it governs real, reachable collisions on every renamed field,
   including `stop` and `stopSequences`, which fixtures 077 and 081 exercise.
4. **Retire 052 rather than repoint it.** Rejected: it is retrieval's only clause-(b) fixture, and Cohere's
   rename gives it a reachable home, so repointing preserves coverage that retiring would drop.
5. **Resolve `embedding_types` toward the vocabulary reading**, making the empty string malformed and the
   local gate correct. Rejected: it contradicts the general rule §8.4 says it inherits, and it would require
   §8.4 to enumerate a closed precision vocabulary with a reject rule, which it deliberately does not do.
   Every unrecognized precision would then need spec maintenance each time a vendor adds one.

## Open questions

1. **Whether other mappings carry unreachable clause-(b) instances** that no fixture pins. The reachability
   condition makes them identifiable by inspection: any mapping section enumerating a managed declared-field
   realization whose wire name equals the declared name. A sweep is cheap once the condition is stated, and
   could fold into the accept.
2. **Whether `stream` should be described as clause (b) at all.** It is a `complete()` argument rather than a
   `RuntimeConfig` field, so it is reachable for a different reason than a rename: no declared config field
   shares its name. The rule covers it correctly today; whether the reachability note should name that as a
   second condition or leave it as an instance is an editorial call.
