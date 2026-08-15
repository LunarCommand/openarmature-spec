# 0119: Cap the Harvested Error Message and Close the Reserved-Key Gap

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-08-14
- **Accepted:**
- **Targets:**
  - spec/observability/spec.md **§5.5.5 Truncation contract**: bring a failed observation's `error_message`
    under the per-attribute byte cap. The field is the one payload-classified value with **no
    `openarmature.*` span-attribute source**, because the OTel surface defines no `error_message` attribute
    (§5.5.4), so the §8.7 mechanism that delivers truncation to Langfuse by inheritance cannot reach it. State
    that the cap, the algorithm, the configured value and the marker are the same, and that the point of
    enforcement is the Langfuse mapping rather than an upstream attribute. State that the marker is appended
    to a plain string, so the unparseable-JSON truncation signal defined for the encoded attributes does not
    apply to this field.
  - spec/observability/spec.md **§8.7 Generation rendering**: extend the *Truncation contract* paragraph,
    which currently describes only inheritance from an already-truncated attribute source, with the direct
    application arm for `metadata.error_message` on a failed Generation and its Embedding / Tool / Retriever
    counterparts (§8.4.5 to §8.4.7).
  - spec/observability/spec.md **§5.5.4 Opt-out flags**: in the *Failed-call error message* paragraph, state
    that a message the flag permits to emit is subject to §5.5.5 like every other payload-classified field.
    0118 classified the message as payload for gating without saying whether the cap followed it, and this
    closes that.
  - spec/observability/spec.md **§3.4 Caller-supplied invocation metadata**: add `error_type`,
    `error_message`, `token_budget` and `token_budget_exceeded` to the reserved OA-emitted metadata key set.
    All four are written as top-level keys of a Langfuse metadata object by a §8 mapping, which §3.4's own
    maintenance rule already requires to be reserved. The rule was missed when each was introduced; this is
    the catch-up, not a new policy.
  - spec/conformance-adapter/spec.md **§5.15 Retrieval-provider directives**: add `message_repeat: {char:
    <str>, bytes: <int>}` as an alternative to the literal `message` on the `raises` sub-directive this
    section defines, synthesizing an oversized exception message. It applies to both forms §5.15 names, the
    `mock_embedding` / `mock_rerank` entry and the `mock_tool` analogue.
  - spec/conformance-adapter/spec.md **§5.5 Observer / observability directives**: add `metadata_truncation:
    {<key>: {max_bytes: <int>, marker_pattern: <regex>}}` on a Langfuse observation entry, the metadata-field
    analogue of the existing span-level `attribute_truncation` assertion, and a sibling of the
    `metadata_absent` assertion 0118 added to the same entry.
  - spec/conformance-adapter/spec.md **§5.1 Node behavior directives**: document the existing
    **`content_repeat`** primitive, which appears inside a `calls_llm` message entry and which observability
    fixtures 014 and 023 already depend on, but which this capability spec has never defined. Adding its
    sibling while leaving the original discoverable only from a fixture sidecar would leave two adapters free
    to disagree about whether it exists.
  - spec/observability/conformance/160-langfuse-error-message-truncation.{yaml,md}: new fixture, two cases,
    gating the cap on a failed provider observation with the payload flag off.
- **Related:** 0041 (reserved-key mechanism and its maintenance rule), 0042 (prior catch-up under that rule),
  0083 and 0109 (introduced `token_budget` / `token_budget_exceeded`), 0107 (the `raises` mock-failure
  directive), 0118 (classified `error_message` as payload)

## Summary

Proposal 0118 classified a failed observation's `error_message` as harvested payload for gating purposes but
did not bring it under the §5.5.5 byte cap, and the mechanism that delivers truncation to every other
payload-classified Langfuse field structurally cannot reach it. This proposal applies the cap directly at the
Langfuse mapping. It also adds the four OA-emitted metadata key names that §3.4's maintenance rule already
required to be reserved and that were missed when each was introduced.

## Motivation

### The cap does not reach the error message, and cannot

§5.5.5 defines the truncation contract against the `openarmature.*` payload attributes. §8.7 explains how
Langfuse fields acquire truncation: the cap "applies to the OA-attribute source values; when the source
attribute is truncated, the Langfuse observer receives the already-truncated string." Every
payload-classified Langfuse field is truncated by **inheritance** from an attribute that was capped upstream.

`error_message` has no such source. §5.5.4 states it plainly: the gate on the message is Langfuse-side only
"because the OTel surface carries no `error_message` span attribute," the exception reaching the OTel backend
through `record_exception` instead. So the field is the single payload-classified value that the inheritance
mechanism cannot deliver a cap to, and 0118 classified it as payload without noticing that the classification
bought it gating but not bounding.

The consequence is a field written verbatim at all four failure handlers. A provider that returns a large
exception string, an echoed HTML error page being the ordinary case, renders in full on the observation. Two
concrete failures follow:

1. **The §5.5.5 rationale applies unchanged.** That section exists because unbounded emission produces
   payloads "larger than typical OTLP exporters accept" and inflates storage without bound. An oversized
   observation risks rejection at ingest, which loses the whole observation. Observability then goes dark on
   precisely the failure path it was installed to record, which is worse than a truncated message.
2. **It reopens a bound the flag-off posture otherwise holds.** With `disable_provider_payload=False`, a model
   output that exceeds the cap is truncated in `generation.output`. A `structured_output_invalid` message
   commonly quotes that same output, so the content re-enters uncapped through the message. The gating
   argument 0118 made for classifying the message as payload is the same argument for bounding it: if the
   message can carry the payload, it can carry the payload's size.

### Four keys owe their place in the reserved set

§3.4 reserves the OA-emitted metadata key names so a caller key cannot occupy a metadata key an OA field
already owns. Both sets land at the same top level because Langfuse filters reliably only there, so the
reservation is what keeps them from colliding. The section carries an explicit maintenance rule: any future
proposal introducing a new top-level OA-emitted metadata key in a §8 mapping **MUST** add that name to the
reserved set.

Four names are written by the §8.4 mapping and are absent from the set:

| Key | Written at | Introduced by |
|---|---|---|
| `error_type` | `observation.metadata.error_type` (§8.4.2) | pre-0118 error mapping |
| `error_message` | `observation.metadata.error_message` (§8.4.2) | pre-0118 error mapping |
| `token_budget` | `generation.metadata.token_budget.*` (§8.4.3) | 0083 |
| `token_budget_exceeded` | `generation.metadata.token_budget_exceeded` (§8.4.3) | 0109 |

`userId` is also written at that top level and is deliberately **not** reserved, which §8.4.1 already
explains: it is a caller key openarmature reads and promotes, not an OA-emitted one. That exclusion is
correct and is left alone.

The defect is not hypothetical for `error_message` specifically. Under the default posture 0118 requires that
key to be **absent** from the observation. An unreserved caller key of the same name lands in it unopposed,
so a consumer reading the field cannot tell an OA-emitted message from a caller-authored one, and an absence
assertion over it is not decidable. That is exactly the shadowing 0041 built the reservation to prevent.

This is a caller-**attached** value rather than a harvested one, so it is not §6's payload leak reopening
through a side door; the harvest-versus-attach exemption governs it and the caller owns what they attach. The
defect is shadowing, and that carries the change on its own.

## Detailed design

### §5.5.5: the cap covers the harvested error message

Add, after the *Minimum cap* paragraph:

> **The harvested error message.** A failed observation's `error_message` (§5.5.4, §8.4.2) is subject to this
> contract on the same terms as the payload attributes above: the same configured cap, the same default and
> minimum, the same truncation algorithm, and the same marker. It differs from them in one respect, which
> changes **where** the cap is enforced and not **whether** it applies. Every other covered value originates
> as an `openarmature.*` span attribute and reaches a backend mapping already truncated (§8.7). The error
> message has no span-attribute source, because the OTel surface defines no `error_message` attribute
> (§5.5.4). Implementations MUST therefore apply the cap at the point the backend mapping writes the field.
>
> The message is a plain string rather than a JSON-encoded structure, so the marker is appended to the
> truncated text and the field remains a readable string. The unparseable-JSON truncation signal described
> above is a property of truncating an encoded value and does not apply here; the marker itself is the signal.
>
> Truncation applies only to a message the implementation is emitting. Where `disable_provider_payload`
> withholds the message (§5.5.4), or where §6's suppress-all arm withholds it, no value is written and the
> cap is not reached. An implementation MUST NOT treat truncation as a substitute for either.

### §8.7: the direct-application arm

The *Truncation contract* paragraph currently describes inheritance only. Add a second bullet alongside the
existing `generation.input` / `generation.output` / `generation.metadata.request_extras` bullet:

> - Applies the §5.5.5 cap **directly** to a failed observation's `metadata.error_message`, on a Generation
>   and on the Embedding / Tool / Retriever observations (§8.4.5 to §8.4.7), whenever
>   `disable_provider_payload` permits the field to emit. This field has no OA-attribute source to inherit a
>   truncated value from, so the observer is the point of enforcement rather than a passive recipient of one.

### §5.5.4: say that the cap follows the classification

Append to the *Failed-call error message* paragraph:

> When the flag permits the message to emit, it is subject to the §5.5.5 truncation contract like every other
> payload-classified field. §5.5.5 states how the cap reaches a field that has no span-attribute source.

### §3.4: four names join the reserved set

Extend the reserved set with `error_type`, `error_message`, `token_budget` and `token_budget_exceeded`. The
enumeration is otherwise unchanged, as is the exact-whole-key matching rule, the backend-independence rule,
and the maintenance rule itself.

### Conformance-adapter directives

**`message_repeat: {char, bytes}` (§5.15).** The `raises: {error_type, message}` sub-directive (0107) takes a
literal string, which cannot express a message large enough to exceed even the 256-byte minimum cap without
putting the literal in the fixture. `message_repeat` synthesizes it, mirroring `content_repeat`, the
primitive observability fixtures 014 and 023 already use to synthesize an oversized user message. `message`
and `message_repeat` are mutually exclusive on one entry, and the alternative is available wherever §5.15
defines a `raises` sub-directive rather than only on the embedding form this proposal's fixture exercises.

**Documenting `content_repeat` (§5.1).** That sibling turns out to be an undocumented directive. Two shipped
fixtures depend on it, and the only description of it anywhere is a line in fixture 014's own markdown
sidecar. §3.3 makes the capability spec the authoritative schema reference and per-directory READMEs
navigational aids at most, so an adapter author working from the spec has no way to learn the primitive
exists. It is documented in §5.1 beside the `calls_llm` directive whose message entries carry it, in the
shape it is already used: `content_repeat: {char: <str>, bytes: <int>}` in place of a message entry's
`content`, synthesizing a repeated-character body of the given byte count. No behavior changes and no fixture
changes; this records what two fixtures already require.

**`metadata_truncation: {<key>: {max_bytes, marker_pattern}}` (§5.5).** A Langfuse observation entry gains the
metadata-field analogue of the span-level `attribute_truncation` assertion, with the same two sub-keys and
the same semantics: the named metadata value is at most `max_bytes` bytes and matches `marker_pattern` at its
end. Asserting the value literally is not an option, since the truncated prefix is cap-dependent.

### Fixture 160

Two cases on a failed Embedding observation with `disable_provider_payload: false`, the configuration whose
whole point is that the message emits:

1. **`oversized_error_message_truncated`**: the mock raises with a `message_repeat` body exceeding the
   default cap. The observation's `metadata.error_message` is at most 65,536 bytes and ends with the marker.
   `error_type` and the error category are asserted present and untouched, since neither is payload and
   neither is capped.
2. **`error_message_below_cap_untouched`**: an ordinary short message, asserted literally, with no marker.
   This is the control that keeps case 1 honest: without it, an implementation that truncated every message
   unconditionally would pass.

## Conformance test impact

**Non-breaking.** Both halves were checked against the shipped corpus rather than assumed:

- The longest `error_message` any fixture asserts is 35 bytes, against a 256-byte minimum cap and a 64 KiB
  default, so no existing assertion can be reached by truncation. Fixtures 150 and 151, whose literal
  assertions might look exposed, sit three orders of magnitude below the default cap and are untouched.
- No fixture supplies any of the four newly reserved names as caller metadata, so no case begins failing at
  the `invoke()` boundary.

This lands as a MINOR bump with no reconciliation work, unlike 0118, which had to reconcile five fixtures in
the same change.

Two new directives, both required rather than convenient. `message_repeat` exists because a literal oversized
message cannot reasonably live in fixture YAML, and `content_repeat` already establishes the pattern for
exactly this problem on the input side. `metadata_truncation` exists because a truncated value cannot be
asserted literally, which is the same reason `attribute_truncation` exists on the span side.

The third §5.5 addition is not a directive at all but a gap this change surfaced: `content_repeat` has been
load-bearing in two shipped fixtures without ever appearing in the capability spec that is supposed to be the
authoritative schema reference. It is documented here because writing its sibling into §5.5 while leaving the
original discoverable only from a fixture sidecar would be a worse outcome than either state on its own.

Fixture inventory:

- **New:** 160 (two cases, gating the cap and its lower bound).
- **Changed:** none.

The reserved-key half carries no fixture. Its behavior is a rejection at the `invoke()` boundary that the
existing reservation mechanism already performs for twenty-nine other names; adding four more exercises no
new code path, and a per-name fixture would assert the mechanism rather than the addition. What it needs
instead is a mechanical check, because the failure mode is a name silently missing from a hand-maintained
list, which is what happened four times here. A repository check that fails when a top-level metadata key
written by the §8 mapping is absent from the §3.4 set lands alongside this proposal. It changes no spec text
and is therefore not a target of this proposal, but the rationale belongs on the record here: the maintenance
rule has been in force since 0041 and has now been missed by three separate proposals, which is a sign that
the rule needs enforcement rather than restatement.

## Alternatives considered

1. **Do nothing; leave the message verbatim.** Rejected: it leaves the payload classification half-applied,
   with the message gated but unbounded, and leaves the one field that can quote a capped payload as the one
   field with no cap. The ingest-rejection failure is real and lands on the failure path.
2. **Extend §5.5.5's attribute list and rely on §8.7's inheritance.** Rejected: this is the change that looks
   right and does nothing. Inheritance requires a source attribute to inherit from, and the OTel surface
   defines no `error_message` attribute, so naming the field in an attribute list would leave the delivery
   mechanism unable to reach it. The gap is mechanical, not editorial.
3. **Define an `openarmature.error.message` span attribute** so the message acquires a source and inherits
   truncation like everything else. Rejected: it adds an OTel-side emission that duplicates what
   `record_exception` already carries, widening the OTel surface to solve a Langfuse-side bounding problem,
   and it would need its own gating rule to avoid becoming a fifth harvested channel. Applying the cap at the
   mapping is smaller and touches no OTel behavior.
4. **Give the error message its own smaller cap.** Rejected: a second knob with a second default and a second
   minimum, for no benefit. A message large enough to matter is pathological at any of these bounds, and the
   marker records the pre-truncation length either way.
5. **Truncate only under `structured_output_invalid`**, the category that provably quotes model output.
   Rejected for the reason 0118 rejected the same shape for gating: a provider 4xx can quote the request just
   as readily, and a rule conditional on failure category is fragile.
6. **Reserve only `error_type` and `error_message`**, leaving the token-budget keys for whenever they next
   surface. Rejected: they were found by sweeping the mapping rather than by waiting for a report, and
   leaving two known misses in place while fixing two others would reproduce the exact failure this closes.
7. **Nest OA-emitted metadata under a sub-object** so no reservation is needed at all. Rejected on the
   grounds 0041 already settled: Langfuse filters reliably only on top-level metadata keys, so nesting puts
   OA fields where filtering does not reach.

## Open questions

1. **Whether the cap should be configurable separately from the attribute cap.** This proposal reuses the
   single per-observer cap on the grounds that one bound is easier to reason about than two. If a caller ever
   wants generous payload attributes and a tight bound on error text, that is a second knob, and it would be
   introduced by the proposal that has a caller asking for it rather than pre-emptively here.
2. **Whether the reserved set should carry the `userId` exclusion explicitly.** It is currently explained in
   §8.4.1, one section away from the list a reader consults. Stating it beside the list would prevent a
   future sweep from "correcting" the omission, but it also duplicates a rule that has a home. Left as is,
   flagged because the mechanical check has to encode the same exclusion and will be the second place it
   lives.
