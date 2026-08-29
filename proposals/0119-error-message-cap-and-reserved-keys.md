# 0119: Cap the Harvested Error Message and Close the Reserved-Key Gaps

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-08-14
- **Accepted:** 2026-08-28
- **Targets:**
  - spec/observability/spec.md **§5.5.5 Truncation contract**: generalize the contract from an enumerated
    list of `openarmature.*` span attributes to **every payload-classified value**, and state that where a
    value has no span-attribute source the cap is applied by the backend mapping that writes it. Add the two
    values that already fall in that category: the §8.4.1 Trace-level state payload (`trace.input` /
    `trace.output`), which §8.4.1 already subjects to this cap without §5.5.5 listing it, and a failed
    observation's `error_message`, which nothing currently caps. State that the marker is appended to a
    plain string for a value that is not JSON-encoded, so the unparseable-JSON truncation signal defined for
    the encoded attributes does not apply to it.
  - spec/observability/spec.md **§8.7 Generation rendering**: extend the *Truncation contract* paragraph,
    which currently describes only inheritance from an already-truncated attribute source, with the
    direct-application arm for `metadata.error_message` on a failed Generation and its Embedding / Tool /
    Retriever counterparts (§8.4.5 to §8.4.7). State that the **Langfuse observer's own** configured cap
    governs, since §5.5.5 makes the cap per-observer and §8.9 makes the two observers independent.
  - spec/observability/spec.md **§5.5.4 Opt-out flags**: in the *Failed-call error message* paragraph, state
    that a message the flag permits to emit is subject to §5.5.5. 0118 classified the message as payload for
    gating without saying whether the cap followed it, and this closes that.
  - spec/observability/spec.md **§3.4 Caller-supplied invocation metadata**: two reservation gaps. Add
    `error_type`, `error_message`, `token_budget` and `token_budget_exceeded` to the exact-match reserved
    set. And extend the **reserved-namespace** rule to cover `openarmature_` alongside the existing dotted
    `openarmature.` and `gen_ai.`, closing the nine underscore-prefixed keys §8.4.5 to §8.4.7 write, which
    clear both current rules.
  - spec/conformance-adapter/spec.md **§5.15 Retrieval-provider directives**: add `message_repeat: {char:
    <str>, bytes: <int>}` as an alternative to the literal `message` on the `raises` sub-directive this
    section defines for `mock_embedding` / `mock_rerank`, synthesizing an oversized exception message.
  - spec/conformance-adapter/spec.md **§5.5 Observer / observability directives**: add `metadata_truncation:
    {<key>: {max_bytes, marker_pattern, utf8_valid, prefix_of_full_serialization}}` on a Langfuse
    observation entry, the metadata-field analogue of the span-level `attribute_truncation`, carrying all
    **four** of that directive's sub-keys. And add a `raises: {error_type, message | message_repeat}` form to
    the case-level `mock_llm` directive, which today accepts only `{status, body}` and therefore cannot
    induce a Generation failure with a caller-controlled message.
  - spec/conformance-adapter/spec.md **§5.11**: document the existing **`attribute_truncation`** directive
    and all four of its sub-keys, beside `attributes_absent`, its span-side sibling.
  - spec/conformance-adapter/spec.md **§5.1 Node behavior directives**: document the existing
    **`content_repeat`** primitive beside the `calls_llm` directive whose message entries carry it, so it
    sits at the same level as the `message_repeat` sibling this proposal promotes to the general surface.
  - spec/observability/conformance/160-langfuse-error-message-truncation.{yaml,md}: new fixture, three cases,
    gating the cap on a failed Embedding **and** a failed Generation.
  - spec/observability/conformance/028-caller-metadata-namespace-rejection.yaml: extend with a rejection case
    per newly reserved name and one for the `openarmature_` namespace, following the 0042 precedent.
- **Related:** 0041 (reserved-key mechanism and its maintenance rule), 0042 (prior catch-up under that rule,
  and the fixture-028 precedent this one follows), 0043 (the §8.4.1 state-payload channel whose cap hookup is
  the precedent for the error-message hookup), 0083 and 0109 (introduced `token_budget` /
  `token_budget_exceeded`), 0095 (`attributes_absent`), 0107 (the `raises` mock-failure directive), 0118
  (classified `error_message` as payload)

## Summary

Proposal 0118 classified a failed observation's `error_message` as harvested payload for gating purposes but
did not bound it, and the mechanism that carries the byte cap to most Langfuse fields does not reach it. The
spec already solved this shape once, for the Trace-level state payload, so this generalizes §5.5.5 rather
than inventing a mechanism. It also closes two reservation gaps in §3.4: four missing exact names, and a
whole family of underscore-prefixed keys that the namespace rule does not cover.

## Motivation

### The cap does not reach the error message

§5.5.5 defines the truncation contract against an enumerated list of `openarmature.*` payload attributes.
§8.7 describes how Langfuse fields normally acquire truncation: the cap applies to the OA-attribute source
values, and the observer receives a string that was already truncated upstream. Most payload-classified
Langfuse fields are bounded by that **inheritance**.

`error_message` has no attribute source to inherit from. §5.5.4 states it directly: the gate on the message
is Langfuse-side only "because the OTel surface carries no `error_message` span attribute", the exception
reaching the OTel backend through `record_exception` instead. So inheritance cannot deliver a cap to it, and
0118 classified the field as payload without noticing that the classification bought it gating but not
bounding.

The field is therefore written verbatim at all four failure handlers. A provider returning a large exception
string, an echoed HTML error page being the ordinary case, renders in full on the observation. Two concrete
failures follow:

1. **The §5.5.5 rationale applies unchanged.** That section exists because unbounded emission produces
   payloads "larger than typical OTLP exporters accept" and inflates storage without bound. An oversized
   observation risks rejection at ingest, which loses the whole observation. Observability then goes dark on
   precisely the failure path it was installed to record, which is worse than a truncated message.
2. **It reopens a bound the flag-off posture otherwise holds.** With `disable_provider_payload=False`, a model
   output that exceeds the cap is truncated in `generation.output`. A `structured_output_invalid` message
   commonly quotes that same output, so the content re-enters uncapped through the message. The gating
   argument 0118 made for classifying the message as payload is the same argument for bounding it: if the
   message can carry the payload, it can carry the payload's size.

### The spec already solved this shape, which makes the fix smaller

`error_message` is **not** the first payload-classified value with no span-attribute source. The §8.4.1
Trace-level state payload is the same shape and was hooked up years earlier: §8.4.1 states that when
`disable_state_payload` is off the observer serializes `initial_state` to `trace.input` and final state to
`trace.output`, "subject to the existing payload-byte-cap truncation (§5.5.5)". No `openarmature.state.*`
span attribute exists, and §6 classifies the state payload as one of the harvested-payload channels
alongside the provider payload and the error message.

So the house pattern for a source-less payload value is already established: the mapping that writes the
field applies the cap directly, and one clause in the owning section says so. This proposal is that clause
for the error message.

It also surfaces a smaller defect in §5.5.5 itself. That section's enumeration lists only span attributes, so
the state payload is subject to the cap by §8.4.1's say-so while §5.5.5 does not mention it. Rather than add
a second special case, §5.5.5 is generalized to cover every payload-classified value and to state where the
cap is enforced when there is no attribute to inherit from. Both source-less values then sit under one rule.

### The reserved set has two gaps, not one

§3.4 keeps caller-supplied metadata from colliding with OA-emitted metadata. Both land at the same top level
because Langfuse filters reliably only there, so a reservation is what keeps them apart. Two mechanisms
exist: a **namespace** rule reserving `openarmature.*` and `gen_ai.*`, and an **exact-match** list of
individual names, whose match §3.4 states is "exact (whole keys, not prefixes)". §3.4 also carries a
maintenance rule: any future proposal introducing a new top-level OA-emitted metadata key MUST add it.

**Gap one, four missing names.** These are written by the §8.4 mapping and absent from the exact list:

| Key | Written at | Introduced by |
|---|---|---|
| `error_type` | `observation.metadata.error_type` (§8.4.2) | pre-0118 error mapping |
| `error_message` | `observation.metadata.error_message` (§8.4.2) | pre-0118 error mapping |
| `token_budget` | `generation.metadata.token_budget.*` (§8.4.3) | 0083 |
| `token_budget_exceeded` | `generation.metadata.token_budget_exceeded` (§8.4.3) | 0109 |

**Gap two, an entire family.** §8.4.5 to §8.4.7 write nine further top-level metadata keys under an
`openarmature_` **underscore** prefix: `openarmature_input_count`, `_dimensions`, `_response_id`,
`_tool_name`, `_tool_call_id`, `_query_length`, `_document_count`, `_top_k` and `_result_count`. The
underscore form is not the dotted `openarmature.` namespace, so the namespace rule does not reach it, and
none of the nine is on the exact list, so that rule does not either. §8.4.2 merges caller metadata into every
observation's metadata at the same top level, so a caller passing `openarmature_tool_name` shadows the
OA-emitted tool name unopposed.

Enumerating nine more names would close today's instance and leave the next §8.4.x addition exposed, so this
extends the namespace rule to `openarmature_` instead. That reserves the family, matches how the dotted
namespace already works, and means a future proposal adding an `openarmature_*` key inherits the reservation
without needing to remember the maintenance rule.

For `error_message` the shadowing is sharper than a naming collision. Under the default posture 0118 requires
that key to be **absent**. An unreserved caller key of the same name lands in it unopposed, so a consumer
cannot tell an OA-emitted message from a caller-authored one, and an absence assertion over it is not
decidable. That is exactly what 0041 built the reservation to prevent.

This is caller-**attached** rather than harvested content, so it is not §6's payload leak reopening through a
side door; the harvest-versus-attach exemption governs it and the caller owns what they attach. The defect is
shadowing, and that carries the change on its own.

`userId` is written at that same top level and is deliberately **not** reserved, which §8.4.1 explains: it is
a caller key openarmature reads and promotes, not an OA-emitted one. That exclusion is correct and is left
alone.

## Detailed design

### §5.5.5: one rule for every payload-classified value

Replace the section's opening scope sentence, which enumerates span attributes, with a rule stated over
payload-classified values, and add after the *Minimum cap* paragraph:

> **Values with no span-attribute source.** Most payload-classified values originate as an `openarmature.*`
> span attribute and reach a backend mapping already truncated (§8.7). Two do not, and for those the cap is
> enforced by the backend mapping that writes the field rather than inherited from an attribute:
>
> - the Trace-level **state payload** (`trace.input` / `trace.output`, §8.4.1), whether sourced from the
>   serialized state or from a caller-supplied `trace_*_from_state` hook's return value; and
> - a failed observation's **`error_message`** (§5.5.4, §8.4.2), because the OTel surface defines no
>   `error_message` span attribute (§5.5.4).
>
> Both are subject to this contract on the same terms as the attributes above: the same configured cap, the
> same default and minimum, the same truncation algorithm, and the same marker. Implementations MUST apply
> the cap at the point the backend mapping writes such a field.
>
> Where the value is a plain string rather than a JSON-encoded structure, the marker is appended to the
> truncated text and the field remains a readable string. The unparseable-JSON truncation signal described
> above is a property of truncating an encoded value; for a plain-string field the marker itself is the
> signal.
>
> Truncation applies only to a value the implementation is emitting. Where `disable_provider_payload` or
> `disable_state_payload` withholds the value (§5.5.4, §8.4.1), or where §6's suppress-all arm withholds it,
> no value is written and the cap is not reached. Implementations MUST NOT emit a truncated value in place of
> a value one of those rules requires to be absent.

The last sentence is deliberately phrased as an observable emission rather than as a prohibition on treating
one thing as a substitute for another, so that a fixture can assert it.

### §8.7: the direct-application arm, and whose cap

Add alongside the existing inheritance bullet:

> - Applies the §5.5.5 cap **directly** to a failed observation's `metadata.error_message`, on a Generation
>   and on the Embedding / Tool / Retriever observations (§8.4.5 to §8.4.7), whenever
>   `disable_provider_payload` permits the field to emit. This field has no OA-attribute source to inherit a
>   truncated value from, so the observer is the point of enforcement rather than a passive recipient of one.
>   The cap that governs is the **Langfuse observer's own** configured cap: §5.5.5 makes the cap per-observer
>   and §8.9 makes the two observers independent, so where a composed OTel observer is configured with a
>   different cap, that value does not govern this field. An implementation that shares one truncation
>   implementation between the observers (permitted, above) MUST still apply the Langfuse observer's
>   configured cap here.

### §5.5.4: say that the cap follows the classification

Append to the *Failed-call error message* paragraph:

> When the flag permits the message to emit, it is subject to the §5.5.5 truncation contract like every other
> payload-classified value. §5.5.5 states how the cap reaches a field that has no span-attribute source.

### §3.4: close both reservation gaps

Extend the reserved-namespace sentence to read that keys MUST NOT collide with the reserved namespaces
`openarmature.`, `openarmature_` and `gen_ai.`, and add `error_type`, `error_message`, `token_budget` and
`token_budget_exceeded` to the exact-match list. The exact-match rule, the backend-independence rule and the
maintenance rule are otherwise unchanged.

Note the consequence plainly in the section: extending a reservation converts a previously-accepted caller
key into a hard raise at the `invoke()` boundary. That is the intended behavior, and it is the reason this is
called out as caller-visible in *Conformance test impact* below.

### Conformance-adapter directives

**`message_repeat: {char, bytes}` (§5.15).** The `raises: {error_type, message}` sub-directive (0107) takes a
literal string, which cannot express a message large enough to exceed even the 256-byte minimum cap without
putting the literal in the fixture. `message_repeat` synthesizes it. It is defined for the
`mock_embedding` / `mock_rerank` forms §5.15 actually defines. It is deliberately **not** extended to
`mock_tool`, which §5.15 mentions once as a cross-reference and which no section of this capability spec
defines; extending a directive that has no normative home would leave adapter authors guessing at the
grammar. See *Open questions*.

**`raises` on `mock_llm` (§5.5).** The case-level `mock_llm` directive accepts only `[{status, body}]`, so an
LLM failure can be induced by status code but its message is implementation-sourced (which is why fixture 159
asserts that message by format rather than by value). A cap fixture needs a message of controlled **size**,
so `mock_llm` gains the same `raises: {error_type, message | message_repeat}` form the retrieval and tool
paths already have. Without it the Generation arm of this rule cannot be gated at all, and the Generation is
the arm the motivation is built on.

**`metadata_truncation` (§5.5).** A Langfuse observation entry gains the metadata-field analogue of the
span-level `attribute_truncation`, with **all four** of that directive's sub-keys:

- `max_bytes`: the value's UTF-8 byte length MUST be at most this.
- `marker_pattern`: the value MUST end with a string matching this regex.
- `utf8_valid`: the value MUST decode as valid UTF-8 in full, with no split multi-byte sequence.
- `prefix_of_full_serialization`: the bytes preceding the marker MUST be a prefix of the untruncated value
  the implementation would have produced for the same input.

The last two are not optional garnish. §5.5.5's algorithm step 4 is a MUST to backtrack to a code-point
boundary, and the reason given is that splitting a sequence emits invalid UTF-8 that exporters may reject.
`max_bytes` and `marker_pattern` alone cannot detect a violation of it, so a byte-slicing implementation
would pass a cap fixture built from those two while failing the rule the fixture exists to gate.

**Documenting `attribute_truncation` (§5.11).** That span-side directive is itself undefined in this
capability spec; its only description is fixture 014's markdown sidecar. Defining `metadata_truncation` as
its analogue while the original stays undefined would leave "the same semantics" pointing at nothing
normative. It is documented beside `attributes_absent`, its span-side sibling.

**Documenting `content_repeat` (§5.1).** `message_repeat` mirrors `content_repeat`, which is used by
observability fixtures 014 and 023 and is described only in fixture 014's sidecar.

The justification here is narrower than it may appear, and it is worth being precise because §3.2 is easy to
misread as prohibiting the current arrangement. §3.2 explicitly **permits** per-directory harness notes,
states that such a comment block "is normative for the observability fixture suite even though it isn't part
of this capability spec", and calls per-directory specialization "a permitted extension". So `content_repeat`
living in the observability suite's fixture notes is legitimate today and is not, on its own, a defect. What
this proposal changes is that its sibling `message_repeat` is being promoted to the general §5.x surface.
Leaving one of a matched pair general and the other per-directory is the inconsistency, and documenting
`content_repeat` resolves it in the direction the pair is moving.

Both `content_repeat` and `message_repeat` MUST define their byte semantics for a multi-byte `char`, since
these directives feed the truncation contract and an off-by-one at a sequence boundary is exactly what
`utf8_valid` exists to catch. The rule: the synthesized body repeats `char` until adding another repetition
would exceed `bytes`, so the result is the largest whole number of repetitions whose UTF-8 encoding is at
most `bytes`. The body is therefore never longer than `bytes`, may be shorter when `char` is multi-byte, and
is always valid UTF-8. A fixture needing an exact byte count uses a single-byte `char`.

An entry MUST NOT carry both `message` and `message_repeat`, or both `content` and `content_repeat`. An
adapter encountering both MUST reject the fixture with `fixture_schema_invalid` (§9), whose scope is widened
in the same change to cover a violated co-occurrence constraint on known directives.

### Fixture 160

Three cases, all with `disable_provider_payload: false`, the configuration whose point is that the message
emits:

1. **`oversized_embedding_error_message_truncated`**: a failed Embedding whose mock raises with a
   `message_repeat` body exceeding the default cap, using a **multi-byte** `char` so the code-point
   backtracking is exercised. Asserts all four `metadata_truncation` sub-keys. `error_type` and the error
   category are asserted present and untouched, since neither is payload and neither is capped.
2. **`oversized_generation_error_message_truncated`**: the same against a failed **Generation**, via the new
   `mock_llm` `raises` form. This is the arm the motivation is built on, and §8.4.3's Generation path is
   separate from §8.4.5's, so an implementation can cap one and not the other.
3. **`error_message_below_cap_untouched`**: an ordinary short message, asserted literally, with no marker.
   The control that keeps the other two honest: without it, an implementation truncating every message
   unconditionally would pass.

### Fixture 028

Following 0042, which extended this fixture with one rejection case per newly reserved name, 028 gains a case
per name added here plus one asserting a caller key in the `openarmature_` namespace is rejected. The
namespace case is the load-bearing one, since it is what the family reservation buys.

## Conformance test impact

**Breaking for callers, not for the corpus.** These are different claims and the proposal states both:

- **The fixture corpus is unaffected.** The longest `error_message` any fixture asserts is 35 bytes, against
  a 256-byte minimum cap and a 64 KiB default, so no existing assertion can be reached by truncation.
  Fixtures 150 and 151, whose literal assertions look most exposed, sit far below the default cap and are
  untouched. No fixture supplies any newly reserved name, or any `openarmature_` key, as caller metadata.
- **Callers can break.** Extending a reservation is a caller-visible runtime change: an application calling
  `invoke()` today with a metadata key named `error_type`, or any `openarmature_`-prefixed key, works on the
  current spec version and raises at the boundary on the next, with no deprecation path. `error_type` in
  particular is a plausible domain key name. Implementations SHOULD call this out in release notes. This is
  the intended effect of a reservation, and it is why the namespace extension is worth preferring over
  enumerating nine names: it is one rule a caller can check, rather than a list that grows silently.

This lands as a MINOR bump under the pre-1.0 allowance for breaking changes in a MINOR.

New directives, each required rather than convenient: `message_repeat` because a literal oversized message
cannot live in fixture YAML; `mock_llm.raises` because the Generation arm is otherwise untestable;
`metadata_truncation` because a truncated value cannot be asserted literally. Two existing directives
(`attribute_truncation`, `content_repeat`) are documented rather than added.

Fixture inventory:

- **New:** 160 (three cases, gating the cap on two observation types plus a below-cap control).
- **Extended:** 028 (a rejection case per newly reserved name, plus the `openarmature_` namespace case).
- **Changed:** none.

A repository check that fails when a top-level metadata key written by the §8 mapping is neither in the §3.4
exact set nor covered by a reserved namespace lands alongside this proposal. It changes no spec text and is
therefore not a target, but the rationale belongs on the record: the maintenance rule has been in force since
0041 and has now been missed by three separate proposals, and the family gap went unnoticed longer than that.
The check must encode the `userId` exclusion, and it must scan every `<observation-type>.metadata.` prefix
rather than a subset. A sweep that looked only at `observation.` / `trace.` / `generation.` / `span.metadata`
is what missed the nine underscore keys in the first place.

## Alternatives considered

1. **Do nothing; leave the message verbatim.** Rejected: it leaves the payload classification half-applied,
   with the message gated but unbounded, and leaves the one field that can quote a capped payload as the one
   field with no cap. The ingest-rejection failure is real and lands on the failure path.
2. **Add `error_message` to §5.5.5's attribute list and rely on §8.7's inheritance.** Rejected: this is the
   change that looks right and does nothing. Inheritance needs a source attribute, and the OTel surface
   defines no `error_message` attribute, so listing the field among the attributes would leave the delivery
   mechanism unable to reach it. §8.4.1 shows the correct shape instead: name the field in the owning section
   and have the mapping apply the cap directly.
3. **Special-case the error message and leave §5.5.5's enumeration alone.** Rejected: it would make two
   source-less values (the state payload and the error message) governed by two differently-worded rules in
   two sections, with §5.5.5 mentioning neither. Generalizing once is smaller than special-casing twice.
4. **Define an `openarmature.error.message` span attribute** so the message acquires a source and inherits
   truncation. Rejected: it adds an OTel-side emission duplicating what `record_exception` carries, widening
   the OTel surface to solve a Langfuse-side bounding problem, and it would need its own gating rule to avoid
   becoming a further harvested channel.
5. **Give the error message its own smaller cap.** Rejected: a second knob with a second default and minimum,
   for no benefit. A message large enough to matter is pathological at any of these bounds, and the marker
   records the pre-truncation length either way.
6. **Enumerate the nine `openarmature_` names in the exact-match list** rather than reserving the namespace.
   Rejected: it closes today's instance and leaves the next §8.4.x addition exposed, which is the failure
   mode this proposal exists to stop repeating. The namespace rule already exists for the dotted form; the
   underscore family clearing it is an oversight in the rule's spelling, not a reason to fall back on
   enumeration.
7. **Reserve only `error_type` and `error_message`**, leaving the token-budget keys and the underscore family
   for whenever they next surface. Rejected: they were found by sweeping the mapping rather than by waiting
   for a report, and leaving known misses in place while fixing others reproduces the exact failure this
   closes.
8. **Nest OA-emitted metadata under a sub-object** so no reservation is needed at all. Rejected on the
   grounds 0041 already settled: Langfuse filters reliably only on top-level metadata keys, so nesting puts
   OA fields where filtering does not reach.
9. **Ship `metadata_truncation` with two sub-keys** (`max_bytes`, `marker_pattern`) as originally drafted.
   Rejected: those two cannot detect a split multi-byte sequence, so a fixture built from them would pass an
   implementation violating §5.5.5's step-4 MUST, on exactly the oversized-provider-error input this proposal
   exists to bound.

## Open questions

1. **The directive vocabulary has a systemic documentation gap, and this proposal only patches its edge.**
   `mock_tool` has no normative definition: fixtures 092 to 098, 150 and 158 depend on it, and this
   capability spec mentions it once as a cross-reference. `message_repeat` is deliberately scoped away from
   it here rather than extending a directive with no grammar.

   That is not an isolated case. Four undefined directives surfaced while drafting this proposal
   (`content_repeat` and `attribute_truncation`, both documented here; `mock_tool` and the case-level
   `disable_provider_payload`, both left at the time. Proposal 0121 has since retired the latter, migrating
   twelve cases across eleven fixtures onto the documented `otel_observer` directive). A subsequent sweep of every directive-shaped key used three or
   more times across the fixture corpus, checked against this capability spec, found **at least fifteen**
   more with no definition in it, among them `capture_as`, `expected_failure_isolation_event`,
   `no_spans_emitted`, `no_langfuse_observations_emitted`, `run_tool`, `noop`, `recoverable_state`,
   `seeded_record` / `from_seeded_record`, `render_variables`, `prompt_backend` and `span_tree`. Several are
   expected-outcome assertions, which is the category where an adapter silently not implementing one turns a
   fixture green for the wrong reason.

   §3.2 permits per-directory harness notes, so some of these are legitimately per-directory rather than
   defects. Sorting which is which turned out to be proposal-sized rather than open-question-sized, and it
   became **proposal 0120**.

   0120 as accepted is narrower than earlier drafts of this paragraph described. It reconciles **where** a
   directive's definition may live, naming exactly two homes and re-anchoring §8.2's parsing rule to them.
   It deliberately does **not** add a rule that every directive must have a definition, and it explicitly
   leaves the population defined in neither home unresolved, since identifying which keys are genuinely
   directives requires settling the open-versus-closed vocabulary question it puts out of scope. `span_tree`
   appears there as its worked example rather than as an open gap. So the systemic gap this open question
   names is still open after 0120; what 0120 settled is where a definition belongs once someone writes one.

   This proposal still documents `content_repeat`, `attribute_truncation` and `base64_data_synthetic`
   itself, since it is the one that mirrors them and 0120 does not depend on it.
2. **Whether the cap should be configurable separately from the attribute cap.** This reuses the single
   per-observer cap on the grounds that one bound is easier to reason about than two. If a caller wants
   generous payload attributes and a tight bound on error text, that is a second knob, introduced by the
   proposal that has a caller asking for it.
3. **Where truncation assertions belong in the directive vocabulary.** `metadata_truncation` is placed in
   §5.5 beside `metadata_absent`, its stated analogue, while `attribute_truncation` is documented in §5.11
   beside `attributes_absent`. That mirrors the existing organization rather than reorganizing it, but it
   does leave two closely-related assertion families in different sections. Left as is, flagged because a
   future vocabulary audit (open question 1) would be the place to reconcile it.
