# 0126: Complete Structured-Output Failure Reports and a Bounded Exception Record

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-10-11
- **Targets:**
  - spec/llm-provider/spec.md: modifies §7 (`structured_output_invalid`: `error_message` describes every
    violation, each resolved to its location and constraint); modifies §8.1.5.1 and §8.2.5.1 (each
    mapping's structured-output path is reported on the typed event, and the silent-ignore case is
    detectable)
  - spec/graph-engine/spec.md: modifies §6 (`LlmCompletionEvent` and `LlmFailedEvent` gain
    `structured_output_path`; the `error_message` paragraph after the failure-event table is reconciled
    with §7)
  - spec/observability/spec.md: modifies §4.2 (the recorded exception message is bounded by §5.5.5's
    cap without becoming payload; a failure with no error category takes its error type as the status
    description); modifies §5.5.1 (new `openarmature.llm.structured_output.path` attribute); modifies
    §5.5.7 (the `schema_not_honored` diagnostic); modifies §7 (one new row in *Diagnostic event names*)
  - spec/conformance-adapter/spec.md: modifies §5.13 (`_mentions` accepts a list); modifies §5.1, §5.5
    and §5.11 (directives to force the structured-output path, to assert a log record's absence, and to
    assert truncation of a span's exception message; documents the existing `status_description` and
    `exception_recorded`, which six fixtures use and neither definition home defines)
  - spec/llm-provider/conformance/082-structured-output-error-message-completeness.{yaml,md} (new)
  - spec/observability/conformance/161-otel-exception-record-bounded.{yaml,md} (new)
  - spec/observability/conformance/162-structured-output-schema-not-honored.{yaml,md} (new)
- **Related:** 0016 (structured output), 0082 (named the §7 error fields and put the response-side surface
  on the failure event), 0095 (the `reask` builder that consumes `error_message`), 0118 (the exhaustive-
  mapping rule that names the OTel exception record as an owner surface), 0119 (the cap on a failed
  observation's `error_message`), 0121 (diagnostic event names)

## Summary

A `structured_output_invalid` failure's `error_message` is required to describe the failure but not to
describe all of it, so an implementation may report only the first violation, and the field's one
documented consumer, a caller-authored correction, then needs a round trip per violated field. This
proposal requires every violation, each resolved to the location and constraint that failed. It also
lets an implementation report when a native schema constraint the call sent was not honoured, by
recording the structured-output path on the typed event, and it bounds the one place a harvested
exception message still reaches an OTel span unbounded.

## Motivation

### A correction can only fix what it is told

llm-provider §7 requires the error to expose "a description of the validation or parse failure as
**`error_message`** (the wrapped exception's message, the failing JSON Pointer, or the language's
idiomatic equivalent)". The parenthetical describes one failure. Many JSON Schema validators stop at the
first violation by default, so an implementation following the text faithfully reports one violation
per failure.

§7.1's `reask` builder exists to turn that description into a correction the model can act on. When the
description names one of several violations, the correction can address only that one, and the next
attempt fails on the next violation. A record with several independently wrong fields needs a round trip
per field, against an attempt budget that is usually small. Reporting every violation at once lets one
correction address all of them.

### "Every violation" is not enough on its own

A rule requiring every violation but not saying what a violation is can be satisfied unhelpfully. For a
union or composite schema node, `anyOf` and `oneOf` in JSON Schema, a validator may report the failure
at the composite node:

```
$.site: {"name": "Mare", "lat": "x"} is not valid under any of the given schemas
```

That names no field and no constraint, and it is the shape of the most common case, since schema
generators commonly render a nullable or optional field as an `anyOf` with `null`. A correction quoting
it is worse off than one quoting the single leaf violation it replaced, `$.site.lat: "x" is not of type
"number"`. So the rule must resolve each violation to the specific location and constraint that failed.

### A fixture assertion cannot mean one thing today

conformance-adapter §5.12's `error_message_mentions` asserts that the field contains a substring, since
the wording is implementation-defined. Under the current text it can only ever match whichever
violation an implementation surfaces first, and which violation is first is not stable across
validators or languages. A fixture asserting a substring of anything but the sole violation cannot have
one answer across conforming implementations. Requiring every violation is what makes the assertion
well defined.

### A native constraint that was not honoured looks like a model failure

Every mapping that supports structured output sends the schema to the provider as a native constraint
where it can. llm-provider §8.1.5.1 already recognizes that some servers "raise an error or silently
ignore the field", and says implementations SHOULD detect this, but the detection it describes is "a
first-call attempt that returns an error". The silent case has no detection.

When an intermediary drops the constraint, the model never sees the schema, its output does not conform,
and the call fails with `structured_output_invalid`. That failure is indistinguishable from a model that
saw the schema and got it wrong. The only remedy the spec offers is choosing the prompt-augmentation
fallback up front, a decision a caller has to make before the first call about a property that only
shows up at runtime.

The evidence is already on the failure event. What is missing is which path the call took: a failure on
the prompt-augmentation fallback is a model that was told the schema and failed, while a failure on the
native path, where the model finished on its own (`finish_reason` of `"stop"`), is a constraint that was
not honoured. Recording the path lets an implementation report the second case once, as a diagnostic a
caller can act on at the serving layer.

The diagnostic reports; it does not act. Nothing here retries, switches path, or adds schema text to a
request on the caller's behalf. llm-provider §7.1 is explicit that the implementation authors no prompt
text of its own, and §8.1.5.1's fallback is the sanctioned exception because the caller opts into it.
Making that switch automatic would reverse it.

### The exception record is unbounded, and two outlets carry it

observability §4.2 requires an OTel exception event on every `ERROR` span, "carrying the exception's
class name and message". For a `structured_output_invalid` failure that message quotes the model's
output, and once it describes every violation it can be long. Nothing bounds it: §5.5.5's cap reaches
`openarmature.*` payload attributes and, for values with no span-attribute source, "a failed
observation's `error_message`", which is a Langfuse field. The OTel exception record is neither.

§5.5.5's own rationale applies to it unchanged: "Emission without bounds would produce spans larger than
typical OTLP exporters accept and inflate observability storage unbounded."

It should be **bounded** and should **not** be payload-gated. observability §8.4's exhaustive-mapping
rule forbids rendering harvested exception detail on Langfuse where no table maps it, and it can do so
because it names where that detail goes instead: "openarmature's OTel span via `record_exception` where
the error propagates". The exception record is the designated owner surface. Gating it under the payload
flag would leave that detail reaching no surface at all. The cap removes the size hazard without closing
the outlet.

A second outlet has the same content. The status description is a category identifier on every failure
§4.2 enumerates, but a tool-execution failure carries no error category (observability §8.4.6), and the
spec does not say what its description should be. Using the exception message there puts an unbounded
copy of it in a second place. The error type is the classification every other failure path uses in that
position.

## Detailed design

### llm-provider §7: what `error_message` describes

In the `structured_output_invalid` entry, replace the description of `error_message`, "a description of
the validation or parse failure as **`error_message`** (the wrapped exception's message, the failing
JSON Pointer, or the language's idiomatic equivalent)", with:

> a description of the failure as **`error_message`**, which **MUST** describe **every violation** the
> content commits against `response_schema`, **each resolved to the specific location and constraint
> that failed**, rather than to a composite schema node (such as `anyOf` or `oneOf`) that contains it.
> A violation inside a union or composite resolves to the member constraint that caused it. Where the
> content is not well-formed in the requested encoding, that is the single violation reported, since no
> schema constraint could be evaluated. Violations **SHOULD** appear in a stable order for a given
> content and schema. `error_message` is a human-readable string; its wording is
> implementation-defined.

The requirement is stated against the content and the schema, not against a validator: an
implementation whose validator stops at the first violation enumerates the rest, and "the first
violation" never appears in the rule. The `response_schema` is unchanged as a separately exposed field
and is not folded into `error_message`. Composing a correction from the two is the caller's work under
§7.1.

### llm-provider §8.1.5.1 and §8.2.5.1: the path is reported

Append to each, after the existing requirement that implementations document which path a call uses:

> The path a call took is reported on the typed LLM event as `structured_output_path` (graph-engine §6),
> so a caller or observer can inspect it per call.

§8.1.5.1 additionally gains:

> A server that silently ignores the native constraint is not detectable from the request. Where such a
> call fails `structured_output_invalid`, observability §5.5.7's `schema_not_honored` diagnostic reports
> it.

§8.3 needs no change: the Gemini mapping has a native path only.

### graph-engine §6: `structured_output_path`

Add one row to both the `LlmCompletionEvent` and the `LlmFailedEvent` tables, after `request_extras`:

| Field | Type | Description |
|---|---|---|
| `structured_output_path` | string \| null | Which path the call used to obtain structured output, when `complete()` was called with a `response_schema` (llm-provider §5): `"native"` when the request carried the schema as the provider's native structured-output constraint, `"tool_coercion"` when it carried the schema as a synthetic tool's input schema (llm-provider §8.2.5.1), or `"prompt_augmentation"` when it carried the schema only in the prompt (llm-provider §8.1.5.1). Null when no `response_schema` was supplied. A classification, not payload: never gated by `disable_provider_payload`. |

The failure table already states that it mirrors the completion event's request-side fields one for one;
the explicit row keeps the table complete.

Replace the paragraph after the failure-event table, which currently describes `error_message` as "the
wrapped exception's message or failing locator", with:

> For a `structured_output_invalid` failure, `error_message` carries the llm-provider §7 failure
> description: every violation, each resolved to its location and constraint. Implementations populate
> the exception message with that description, so observers read it from `error_message` without a
> dedicated field.

### observability §5.5.1: the path attribute

Add:

> - **`openarmature.llm.structured_output.path`** (string): the call's `structured_output_path`
>   (graph-engine §6). Set on the LLM provider span when a `response_schema` was supplied; absent
>   otherwise. A classification, not payload: not gated by `disable_provider_payload`.

This keeps the span surface in step with the typed event, which §5.5.7 says carries the same data.

### observability §5.5.7: the `schema_not_honored` diagnostic

Add after the *Typed LLM failure event* paragraph:

> **A native constraint that was not honoured.** When an `LlmFailedEvent` has `error_category` of
> `structured_output_invalid`, `structured_output_path` of `"native"`, and `finish_reason` of `"stop"`,
> the implementation **SHOULD** emit a `WARNING`-level log record (§7) carrying the event name
> `openarmature.structured_output.schema_not_honored` (§7 *Diagnostic event names*). The model finished
> on its own and its output did not satisfy a schema the request carried as a native constraint, which
> is evidence that the constraint did not reach or did not bind the model. The diagnostic reports that
> the constraint was not honoured; it does not establish why.
>
> It is not emitted for `finish_reason` of `"length"` or `"content_filter"`, where the output was cut
> off rather than unconstrained, nor for the `"tool_coercion"` or `"prompt_augmentation"` paths. It is
> **advisory only**: it never retries, changes the path, or alters any request, and the implementation
> authors no prompt text in response to it (llm-provider §7.1).

### observability §7: one row

Add to the *Diagnostic event names* table:

| Event name | Emitted when | Obligation |
|---|---|---|
| `openarmature.structured_output.schema_not_honored` | §5.5.7, a structured-output call on the native path finished on its own and failed schema validation | SHOULD |

### observability §4.2: the exception record and the status description

Replace the paragraph following the status table, "When a span is set to `ERROR`, an OTel exception
event MUST be recorded on the span carrying the exception's class name and message; the exception's
stack trace SHOULD be attached when the language's OTel SDK supports it.", with:

> When a span is set to `ERROR`, an OTel exception event **MUST** be recorded on the span carrying the
> exception's class name and message; the exception's stack trace **SHOULD** be attached when the
> language's OTel SDK supports it. The recorded message is subject to §5.5.5's per-value byte cap,
> truncation algorithm and marker, applied at the configured cap of the observer that records it. It is
> **not** a payload-classified value and is **not** gated by `disable_provider_payload`: this record is
> the surface §8.4 names as the owner of harvested exception detail, so gating it would leave that detail
> reaching no surface.
>
> Where the failure carries **no error category**, as a tool-execution failure does (§8.4.6), the status
> description **MUST** be the failure's error type. The exception message never appears in the status
> description.

§5.5.5's *Values with no span-attribute source* gains a sentence pointing here, so the cap's reach is
stated in the section that defines it:

> The OTel exception record's message (§4.2) is also bounded by this contract, applied by the observer
> that records it, without being payload-classified.

### conformance-adapter §5.13: `_mentions` takes a list

Extend the `_mentions` flavor:

> - the **`_mentions`** suffix: the field's value **contains** the given substring (used where the exact
>   wording is implementation-defined). The value **MAY** be a list of substrings, asserting the field
>   contains **every** one.

This widens one flavor's value domain. It adds no flavor, so the flavor set stays closed.

### conformance-adapter: three directives

- **`structured_output_path: native | tool_coercion | prompt_augmentation`** on a `calls_llm` block
  (§5.1): the adapter forces the call onto that path through the implementation's path override
  (llm-provider §8.1.5.1 requires one to exist as a SHOULD). An adapter that cannot force the named path
  **MUST** fail the case rather than run it on another path.
- **`log_records_absent: [{event_name: <string>}, ...]`** under `expected` (§5.5): asserts no log record
  matching any listed entry was emitted. The log-record analogue of `attributes_absent` and
  `metadata_absent`, which exist because a subset match can pin a value but never an absence.
- **`exception_truncation: {max_bytes: <int>, marker_pattern: <str>, utf8_valid: <bool>,
  prefix_of_full_serialization: <bool>}`** on an OTel span entry (§5.11): asserts the span's recorded
  exception message was truncated per observability §5.5.5. It is the exception-record analogue of
  `attribute_truncation` (§5.11) and `metadata_truncation` (§5.5), with the same four independent
  sub-keys and the same honor rule: an adapter **MUST** honor it when present, an entry asserts an
  exception event is **present** as well as truncated, and an entry **MUST** carry at least one sub-key.
  It exists for the same reason `metadata_truncation` does: the value has no span attribute for
  `attribute_truncation` to assert against.
- **`status_description: <str>`** and **`exception_recorded: <bool>`** on an OTel span entry (§5.11).
  `status_description` asserts the span's status description equals the value. `exception_recorded: true`
  asserts the span carries an OTel exception event (§4.2); `false` asserts it carries none.
  Both are **documented rather than introduced**. Six observability fixtures (003, 004, 008, 119, 124,
  131) already use the pair, always together and always with `exception_recorded: true` on a span with
  `status: ERROR`, and neither is defined in either definition home. Under §8.2 a conforming adapter must
  raise on a directive outside the recognized vocabulary, so as the corpus stands a strict adapter would
  reject all six. Defining them makes the corpus consistent with its own adapter spec without changing
  what any of the six assert.

  `exception_truncation` asserts an exception event is present, so an entry carrying it together with
  `exception_recorded: false` is contradictory and **MUST** raise `fixture_schema_invalid` (§9's
  co-occurrence clause), rather than the adapter choosing which assertion to honour.

## Conformance test impact

**llm-provider 082, `structured-output-error-message-completeness`** (new). Each case returns content
that fails a schema in a known set of ways and asserts `error_message_mentions` as a list.

The cases cover the shapes where an enumeration can go wrong, not only the flat one: a flat object with
several violations, a nested object, a nullable field rendered as `anyOf` with a violation inside it, a
union of two object schemas, an array of objects with a violation in one element, and content that is
not valid JSON (`error_message_present: true`, nothing more).

**Each case asserts the names of missing required fields, never of present ones.** A composite-node
message echoes the instance, so `$.site: {"name": "Mare", "lat": "x"} is not valid under any of the given
schemas` contains `lat` and would satisfy a mention of it while being exactly the defect the case exists
to catch. A required field that is absent from the instance cannot be echoed, so mentioning it can only
pass if the violation was resolved to that field. The sidecar states the remaining limit: a mention is
necessary evidence of resolution, not proof of it.

Existing fixtures 022, 023, 063 and 064 are unaffected: each has a single violation, or asserts a
substring of one that remains named.

**observability 161, `otel-exception-record-bounded`** (new). Two cases.

- An LLM call whose mock raises with a long message, synthesized with `message_repeat` from a
  **multi-byte** character as fixture 160 does, against a small `otel_observer.payload_byte_cap`. Asserts
  `exception_truncation` with all four sub-keys, under the default `disable_provider_payload: true`, which
  confirms the flag does not remove the record. The multi-byte filler is what lets `utf8_valid` fail, and
  using a raised provider error rather than a validation failure keeps this case independent of the
  completeness rule above.
- A tool-execution failure with a long message, asserting `status_description` equals the error type, so
  the message reaches the status description by neither route.

**observability 162, `structured-output-schema-not-honored`** (new). Four cases, the span asserting
`openarmature.llm.structured_output.path` in each:

| Path | `finish_reason` | Diagnostic |
|---|---|---|
| `native` | `stop` | emitted |
| `native` | `length` | absent |
| `prompt_augmentation` | `stop` | absent |
| `tool_coercion` | `stop` | absent |

The three absence cases are what make the emitted case mean anything. Without them an implementation
emitting the diagnostic on every `structured_output_invalid` would pass.

No existing fixture changes.

## Alternatives considered

**Do nothing.** The convergence cost stays, `error_message_mentions` stays unable to mean one thing
across implementations, and the exception record stays unbounded.

**Require only that the first violation be reported, deterministically.** It would fix the fixture
determinism by defining "first" and leave the round trip per violation in place. It also cannot be
specified without naming a traversal order across validators that do not share one.

**State the rule as "every violation the validator can enumerate".** Rejected: conformance would depend
on the validator an implementation chose, and an implementation whose validator stops early would be
conformant by construction.

**A structured per-violation field alongside `error_message`.** More useful to a programmatic consumer
and out of scope here. It would be a new field rather than a change to this one, and nothing in this
proposal prevents it.

**Have the implementation detect non-enforcement and switch to the prompt-augmentation fallback, or add
the schema to the next attempt.** Rejected on principle: it authors prompt text on the caller's behalf,
which §7.1 forbids, and it makes the opt-in fallback automatic.

**Emit the diagnostic from the provider rather than from the typed event.** It would need no event field,
but it breaks the pattern that observability diagnostics are evaluated from the terminal typed event, as
`token_budget.exceeded` is, and it would leave the path invisible to every observer and to callers
inspecting events, which §8.1.5.1 already says they SHOULD be able to do.

**Gate the OTel exception record under `disable_provider_payload`.** Rejected: §8.4's exhaustive-mapping
rule relies on that record as the surface for harvested exception detail that Langfuse must not render.

**Bound the exception itself rather than the record.** Rejected: the caller composing a correction needs
every violation. Only the copy an observer emits is bounded, so a wide schema lengthens what a caller
reads and not what a trace carries.

## Open questions

1. **`tool_coercion` and the diagnostic.** The synthetic tool's input schema is a constraint, so a
   failure on that path with `finish_reason` of `"stop"` may also mean it was not honoured. It is
   excluded here because the silent-ignore case §8.1.5.1 describes is about the native field, and
   including it without evidence risks a diagnostic that fires on ordinary model error. Revisit if
   coerced calls are seen to fail this way.
2. **Repetition.** The diagnostic is emitted per qualifying failure, so a misconfigured endpoint produces
   one record per call. That is the right signal for alerting, which counts them. Whether an
   implementation MAY rate-limit it, for example once per provider instance, is left open.
3. **The stack trace.** §4.2 attaches it as a SHOULD and this proposal bounds only the message. Frames
   can carry long strings too. Bounding the trace is a separate decision with its own cost to debugging.
4. **Langfuse rendering of the path.** The path attribute has no §8.4 mapping. It is a classification
   rather than harvested content, so the exhaustive-mapping rule does not require one, and a Langfuse
   user loses only the inspection surface. Mapping it to `generation.metadata` is cheap if wanted.
5. **Verify before accept.** No normative text here rests on how a particular provider or server treats
   an unsupported or non-strict native constraint, and it should stay that way. Any such claim the accept
   adds to motivation or sidecars needs checking against current vendor documentation first.
