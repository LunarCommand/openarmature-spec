# 0126: Complete Structured-Output Failure Reports and a Schema-Not-Honored Diagnostic

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-10-11
- **Targets:**
  - spec/llm-provider/spec.md: modifies §7 (the `structured_output_invalid` entry's exposure sentence is
    rewritten, and a definition of what `error_message` describes is added); modifies §8.1.2 (an OpenAI
    refusal maps to a `finish_reason` of `"content_filter"`); modifies §8.1.5 (`strict` decides the path a
    call reports, and the sentence on what `strict` leaves unchanged is narrowed to validation); modifies
    §8.2.5 and §8.3.5 (each states what its provider's constrained decoding guarantees, and names its
    native path); modifies §8.1.5.1, §8.2.5.1 and §8.3.5.1 (each states that the path a call took is
    reported on the typed event)
  - spec/graph-engine/spec.md: modifies §6 (`LlmCompletionEvent` and `LlmFailedEvent` gain
    `structured_output_path`; the `error_message` paragraph after the failure-event table points to
    llm-provider §7)
  - spec/observability/spec.md: modifies §5.5 (a baseline attribute,
    `openarmature.llm.structured_output.path`); modifies §5.5.7 (the `schema_not_honored` diagnostic);
    modifies §7 (one row in *Diagnostic event names*)
  - spec/conformance-adapter/spec.md: modifies §5.1 (defines `calls_llm`'s `response_schema` and `config`
    keys, both already in use); modifies §5.5 (`mock_llm` gains a mapping form carrying `capabilities`;
    `log_records` entries gain `count`; new `log_records_absent`); modifies §5.11 (documents
    `mock_provider.capabilities`, already in use); modifies §5.12 and §5.13 (`error_message_mentions`, and
    the `_mentions` flavor generally, accept a non-empty list)
  - spec/llm-provider/conformance/082-structured-output-error-message-completeness.{yaml,md} (new)
  - spec/llm-provider/conformance/083-openai-refusal-finish-reason.{yaml,md} (new)
  - spec/observability/conformance/161-structured-output-schema-not-honored.{yaml,md} (new)
- **Related:** 0016 (structured output), 0058 (introduced `error_message` on the typed LLM failure event),
  0082 (added the response-side fields to the failure event, and made a `structured_output_invalid`
  failure's `error_message` carry the §7 description), 0095 (named the §7 error fields `output_content` and
  `error_message`, which its `reask` builder consumes by name), 0118 and 0119 (keep the OTel exception
  record full and ungated, which this proposal leaves in place), 0121 (diagnostic event names)

## Summary

A `structured_output_invalid` failure's `error_message` is required to describe the failure but not all of
it, so an implementation may report only the first violation, and a correction built from it fixes one
field per round trip. This proposal requires every violation, each with its location as a JSON Pointer and
the constraint that failed, and defines what a violation is inside a composite schema. It also records on
the typed LLM event which structured-output path a call took. On a path whose provider constrains decoding,
a response that is not even well-formed JSON, and was not cut short or refused, is then reported as a
schema the provider did not apply, rather than passing as an ordinary model error.

## Motivation

### A correction can only fix what it is told

llm-provider §7 requires the error to expose "a description of the validation or parse failure as
**`error_message`** (the wrapped exception's message, the failing JSON Pointer, or the language's
idiomatic equivalent)". The parenthetical describes one failure. Many JSON Schema validators stop at the
first violation by default, so an implementation following the text faithfully reports one violation per
failure.

§7.1's `reask` builder consumes that description to build the correction the next attempt receives. When
the description names one of several violations, the correction addresses only that one, and the next
attempt fails on the next. A record with several independently wrong fields needs a round trip per field,
against an attempt budget that is usually small. Reporting every violation at once lets one correction
address all of them.

### "Every violation" needs a definition of a violation

A rule requiring every violation, without saying what one is, can be satisfied unhelpfully. For a union or
composite schema node, `anyOf` and `oneOf` in JSON Schema, a validator may report the failure at the
composite:

```
$.site: {"name": "Mare", "lat": "x"} is not valid under any of the given schemas
```

That names no field and no constraint. It is also the shape of the most common case, since schema
generators commonly render a nullable field as an `anyOf` with `null`. A correction quoting it is worse off
than one quoting the single leaf violation it replaced, that `lat` is not a number.

Resolving to "the member that caused it" is not enough either. When every member of a union fails, no
single member caused it. One implementation reports every member's failures, another a best match,
another only the non-null member, and all three fit the words. Composites also fail in ways no member
explains: a `oneOf` fails when more than one member matches, a `not` when its subschema matches, and an
`allOf` when any member fails, whatever that member's type. So the rule has to say which members count,
and what to report when the composite's own constraint is the one that failed.

The location needs a defined form for the same reason. A description that says "site" or "the third item"
in free prose cannot be told apart from one that reports the composite, or one that reports only the first
array element, so no fixture could check that a violation was resolved at all. JSON Pointer (RFC 6901) is
the standard notation for a location in a JSON document, and the current §7 text already names it as an
example. Its URI fragment form, `#/site/lat`, settles two details the plain form leaves open. The whole
document is `#`, rather than an empty string that prints as nothing. And a location in the content never
occurs inside a location in the schema, which validators write as `/properties/site/properties/lat`.

### A fixture assertion cannot mean one thing today

conformance-adapter §5.12's `error_message_mentions` asserts that the field contains a substring, since the
wording is implementation-defined. Under the current text it can only ever match whichever violation an
implementation surfaces first, and which violation is first is not stable across validators or languages.
A fixture asserting a substring of anything but the sole violation cannot have one answer across
conforming implementations. Requiring every violation, each at a defined location, is what makes the
assertion well defined.

### A schema the provider did not apply looks like a model error

Each mapping sends the schema to the provider as a native constraint where it can. §8.1.5 sends
`strict: true` when the schema satisfies OpenAI's strict-mode rules, enabling "schema-constrained
decoding", and falls back to `strict: false` when it does not. §8.2.5 and §8.3.5 use Anthropic's and
Gemini's constrained decoding.

What a constrained response is promised differs by vendor in its details, but not on syntax: each vendor
documents that a constrained response is well-formed JSON. Full conformance to the schema is promised less
widely. Anthropic documents that the capitalization of string `enum` and `const` values is not guaranteed,
on a response that otherwise completes normally, and Gemini documents support for a subset of JSON Schema.
§8.2.5 currently says Anthropic's constrained decoding "guarantees the generated output conforms to the
schema", which overstates the vendor's documented guarantee, and this proposal corrects it.

§8.1.5.1 recognizes that some servers "raise an error or silently ignore the field". It says
implementations SHOULD detect this, either statically from provider capability metadata or dynamically
from a first call that returns an error, and then fall back to prompt augmentation automatically. The
silent case escapes the dynamic arm, since the call succeeds at the transport level, and the static arm
catches it only when the capability metadata records the gap.

When an intermediary drops the constraint, the model never sees the schema, because on the native path the
schema is in no other part of the request. Its output is commonly prose, or JSON wrapped in a code block,
and the call fails with `structured_output_invalid` as a parse failure. Today that is indistinguishable
from a model that saw the schema and got it wrong. But a constrained response is malformed only when it was
cut short or refused, and each of those already surfaces: a refusal or a `max_tokens` truncation as a
`finish_reason` of `"content_filter"` or `"length"`, and a matched stop sequence on a request that carried
one. So content that is not well-formed JSON, on an enforced native path, with a `finish_reason` of
`"stop"` and no stop sequence on the request, is evidence that the constraint did not reach or did not
bind the model.

Content that parses but fails the schema is not such evidence, because a provider that applied the schema
can return it, as the capitalization and subset cases show. The diagnostic therefore keys on parse
failures alone. A dropped constraint whose output happens to parse stays indistinguishable from a model
error, as it is today.

One gap in the mappings stands in the way. Anthropic's refusal already maps to `"content_filter"`
(§8.2.2). OpenAI returns a refusal in a separate `refusal` field rather than as the message's content, and
§8.1.2 does not map it, so an OpenAI refusal reads as unparseable content on a normal finish. This
proposal maps it to `"content_filter"` as well.

The evidence is already on the failure event except for one fact: which path the call took, and whether
that path is enforced. Recording it lets an implementation report the condition once, as a diagnostic a
caller can act on at the serving layer.

The diagnostic reports; it does not act. Its condition is evidence, not proof (see the residual case in
*Open questions*), and acting on it automatically would mean switching to a fallback that writes schema
text into the request on the implementation's own initiative. So the condition is defined as distinct from
§8.1.5.1's detection, and it never changes what is sent.

### What this does to the exception record

Requiring every violation lengthens `error_message`, and a description commonly quotes offending values
from the content. That text reaches two backends differently.

On Langfuse, a failed observation's `error_message` stays gated by `disable_provider_payload` and, when the
flag permits it, bounded by observability §8.7's cap. Nothing changes there.

On OTel, the exception recorded on the span stays **full and ungated**, by deliberate design: observability
§5.5.5 says the `record_exception` path "is not such a value ... this contract does not reach it", and
§5.5.4 tells callers they see "full exception text in their OTel backend". That record is the surface
observability §8.4's exhaustive-mapping rule relies on for harvested exception detail. This proposal does
not change it. The consequence should be stated plainly: under the default posture, a longer description
means more of the model's content reaches the operator's own OTel backend.

An operator who wants that record bounded already has OpenTelemetry's attribute value length limit. The
OpenTelemetry specification's *Attribute Limits* section applies it to span event attributes as well as
span attributes, so it bounds the exception's message and its stack trace together, which a cap on the
message alone would not. It is off by default, counts characters rather than bytes, and adds no marker.
An SDK sets it per tracer provider, and the standard environment variables
`OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT` and `OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT` set it across the process.
Because observability §6 requires openarmature's spans to go through a private tracer provider, the
environment variables are the route that reaches them unless an implementation exposes its provider's
limits. That trade is the operator's to make on their own backend, so this proposal adds no spec-level cap.

## Detailed design

### llm-provider §7: what the error exposes, and what `error_message` describes

In the `structured_output_invalid` entry, replace the sentence beginning "The error MUST expose the requested
`response_schema`" and ending "not a transport failure." with:

> The error **MUST** expose the requested `response_schema`; the raw response content as
> **`output_content`**, the verbatim content the model produced; a description of the failure as
> **`error_message`**, defined below; and the response's normalized **`finish_reason`** (§6) and token
> **`usage`**. The last two are available from the received response, since the failure is a downstream
> parse or validation step on an intact wire response, not a transport failure. `output_content` and
> `error_message` match the graph-engine §6 failure-event field names (0082), and the call-level `reask`
> builder (§7.1) consumes them.

Then add, as the last paragraph of the entry, after its closing sentence beginning "Distinct from
`provider_invalid_response`", so it does not separate the exposure sentence from the `finish_reason`
explanation that follows it:

> **What `error_message` describes.** `error_message` **MUST** describe **every violation** the content
> commits against `response_schema`. A violation is a failing assertion that makes the content fail
> validation, such as `type`, `required`, `enum` or `pattern`, not the applicator that contains it. An
> assertion that does not decide the outcome, such as one in a member of an `anyOf` that another member
> satisfies, or in the branch of an `if` that does not apply, is not a violation.
>
> Each violation **MUST** state its **location** and the **constraint** that failed. The location is a
> JSON Pointer into the content, written in its URI fragment form (RFC 6901 §6): `#` for the whole
> content, `#/site/lat` for a property, `#/rows/2` for an array element.
>
> - **Where a violation is located.** At the part of the content its failing assertion applies to, with one
>   exception: a property the schema requires but the content lacks (`required`, `dependentRequired`) is
>   located at the pointer it would occupy, so a missing `lat` inside `site` is at `#/site/lat`, and each
>   missing property is its own violation. A property the schema does not allow, such as one excluded by
>   `additionalProperties: false`, is one violation at that property's own location. An array element the
>   schema does not allow is one violation at that element. A count or uniqueness constraint on an object
>   or array, such as `minItems` or `uniqueItems`, is one violation at the object or array.
> - **An `anyOf` or `oneOf` that no member matches.** The violations are every failing assertion of every
>   member whose declared type matches the content at that location, after resolving references. A
>   member's declared type is its `type`, or, for a member that is itself an `anyOf` or `oneOf`, the types
>   its own members declare. A member that declares no type counts as matching. Where no member's type
>   matches, the composite's location and the members' types are reported as one violation.
> - **An `allOf`.** Every member applies, so the violations are every failing assertion of every member,
>   including a member's `type` when the content's type does not match it.
> - **A composite whose own constraint fails.** A `oneOf` that more than one member matches, whatever its
>   other members do, a `not` whose subschema matches, and a `contains` that no array element satisfies
>   are each one violation, located where the keyword applies.
> - **Content that is not well-formed** in the requested encoding. That is the single violation reported.
>   It has no location, since no schema constraint could be evaluated, and in place of a constraint it
>   states what made the content malformed.
>
> Violations **SHOULD** appear in a stable order for a given content and schema. The wording around each
> location and constraint is implementation-defined.

The requirement is stated against the content and the schema, not against a validator. An implementation
whose validator stops at the first violation enumerates the rest, and "the first violation" never appears
in the rule. Likewise, a validator that reports locations in another notation, or reports an unexpected
property at its parent object, has its report converted to the form above. `response_schema` stays a
separately exposed field and is not folded into `error_message`.

### llm-provider §8.1.2: an OpenAI refusal

In the `finish_reason` bullet, add after "Map any unknown `finish_reason` to `error`.":

> When `choices[0].message.refusal` is a non-empty string, the `finish_reason` is `"content_filter"`,
> whatever value OpenAI reports, as §8.2.2 maps Anthropic's `stop_reason: "refusal"`. The refusal text
> stays in `raw`.

### llm-provider §8.1.5, §8.2.5 and §8.3.5: what each native path guarantees

In §8.1.5, replace "The behavioral contract at the spec layer is identical regardless of `strict`:
validation happens post-receive against `response_schema`; failures raise `structured_output_invalid`
(§7)." with:

> Validation is identical regardless of `strict`: it happens post-receive against `response_schema`, and
> failures raise `structured_output_invalid` (§7). Enforcement is not, since only `strict: true`
> constrains decoding. A call sent with `strict: true` reports the `"native"` path (graph-engine §6
> `structured_output_path`), and one sent with `strict: false`, or without `strict`, reports
> `"native_unenforced"`.

In §8.2.5, replace "Anthropic's constrained decoding guarantees the generated output conforms to the
schema." with:

> Anthropic's constrained decoding guarantees well-formed JSON with the schema's field types and required
> properties. It does not guarantee the capitalization of string `enum` and `const` values: a response
> that differs from the schema only in that capitalization completes normally, with
> `stop_reason: "end_turn"`, and fails validation. A call on this path reports the `"native"` path
> (graph-engine §6 `structured_output_path`).

and replace the paragraph beginning "Two non-conformance cases are inherent to the provider" with:

> Three non-conformance cases are inherent to the provider and are NOT validation bugs: a
> `stop_reason: "refusal"` (the refusal takes precedence, so output might not match the schema), a
> `stop_reason: "max_tokens"` (truncation), and the capitalization case above. In each case the mapping
> surfaces the non-conforming content and the mapped `finish_reason` (`content_filter`, `length` or
> `stop`) per §6 / §7; implementations MUST NOT silently coerce these into a schema-conforming shape.

In §8.3.5, replace "The behavioral contract matches §8.1.5's native path." with:

> The behavioral contract matches §8.1.5's native path with `strict: true`, and a call on it reports the
> `"native"` path (graph-engine §6 `structured_output_path`). Gemini's constrained decoding produces
> well-formed JSON, but Gemini documents support for a subset of JSON Schema, so content can fail
> validation on a call that finished normally.

### llm-provider §8.1.5.1, §8.2.5.1 and §8.3.5.1: the path is reported

Append to each, after its existing requirement that implementations document which path a call uses:

> The path a call took is reported on the typed LLM event as `structured_output_path` (graph-engine §6),
> so a caller or observer can inspect it per call.

§8.1.5.1 additionally gains:

> A server that silently ignores the native constraint is not detectable from the request. When such a
> call on the `strict: true` path returns content that is not well-formed JSON, and was not cut short or
> refused, observability §5.5.7's `schema_not_honored` diagnostic reports it. That diagnostic is not one
> of the detection arms above, and its condition **MUST NOT** by itself trigger the fallback.

### graph-engine §6: `structured_output_path`

Add one row to both the `LlmCompletionEvent` and the `LlmFailedEvent` tables, after `request_extras`:

| Field | Type | Description |
|---|---|---|
| `structured_output_path` | string \| null | Which path the mapping chose to obtain structured output, when `complete()` was called with a `response_schema` (llm-provider §5). `"native"` when the request carried the schema as the provider's native structured-output constraint in a form that constrains decoding (llm-provider §8.1.5 with `strict: true`, §8.2.5, §8.3.5). `"native_unenforced"` when it carried the schema natively in a form that does not (§8.1.5 with `strict: false` or without `strict`). `"tool_coercion"` when it carried the schema as a synthetic tool's input schema (§8.2.5.1). `"prompt_augmentation"` when the mapping took the prompt-augmentation fallback (§8.1.5.1, §8.2.5.1, §8.3.5.1), whatever the request's extras carry. Where a call issues more than one request, the path of the request whose outcome this event reports. Null when no `response_schema` was supplied, and null when no request was sent. A classification, not payload: never gated by `disable_provider_payload`. |

The failure table already states that it mirrors the completion event's request-side fields one for one;
the explicit row keeps the table complete.

Replace the paragraph after the failure-event table, which currently describes `error_message` as "the
wrapped exception's message or failing locator", with:

> For a `structured_output_invalid` failure, `error_message` carries the failure description llm-provider
> §7 defines. Implementations populate the exception message with that description, so observers read it
> from `error_message` without a dedicated field.

### observability §5.5: the path attribute

Add a bullet to the *Baseline attributes* list, in that list's existing format, for
**`openarmature.llm.structured_output.path`**, a string, saying:

> The call's `structured_output_path` (graph-engine §6). When a `response_schema` was supplied and a
> request was sent, it **MUST** be set on the LLM provider span; otherwise it **MUST NOT** be set. A
> classification, not payload: not gated by `disable_provider_payload`.

That list is emitted on every LLM provider span unless the span itself is suppressed, independent of the
payload flag, which is why the attribute belongs there rather than in §5.5.1.

### observability §5.5.7: the `schema_not_honored` diagnostic

Add after the *Typed LLM failure event* paragraph:

> **A schema the provider did not honor.** The implementation **MUST** emit exactly one `WARNING`-level log
> record (§7) for an `LlmFailedEvent`, however many observers are attached, when all of the following
> hold:
>
> - its `error_category` is `structured_output_invalid`, and its `output_content` is absent or does not
>   parse as JSON, the parse-failure case of llm-provider §7;
> - its `structured_output_path` is `"native"`;
> - its `finish_reason` is `"stop"`; and
> - the request the event reports carried no stop sequence: no `stop_sequences` in `request_params`, and
>   none under the mapping's stop key in `request_extras` (`stop` for llm-provider §8.1,
>   `stop_sequences` for §8.2, `stopSequences` for §8.3). An empty list carries none. A stop sequence
>   added by a per-attempt override (llm-provider §7.1) counts.
>
> The record carries the event name `openarmature.structured_output.schema_not_honored` (§7 *Diagnostic
> event names*) and the §7 correlation fields, and names the call's provider, model and `call_id`. It
> reports that a call on a native path the provider constrains during decoding, which was not cut short or
> refused, returned content that is not well-formed JSON. That is evidence the constraint did not reach or
> did not bind the model. It does not establish why.
>
> The implementation **MUST NOT** emit the record in any other case. In particular: not for content that
> parses as JSON, whether or not it validates, since a provider that applied the schema can still return
> content that fails validation (llm-provider §8.2.5, §8.3.5); not for a `finish_reason` of `"length"` or
> `"content_filter"`, where the output was cut short or refused; not when the request carried a stop
> sequence, since a matched sequence also reports `"stop"` while cutting the output short; and not for a
> `structured_output_path` of `"native_unenforced"`, `"tool_coercion"` or `"prompt_augmentation"`.
>
> The record is advisory. Its condition **MUST NOT** by itself cause the implementation to retry the
> call, change its structured-output path, or alter any request. It is not one of llm-provider §8.1.5.1's
> detection arms.

### observability §7: one row

Add to the *Diagnostic event names* table:

| Event name | Emitted when | Obligation |
|---|---|---|
| `openarmature.structured_output.schema_not_honored` | §5.5.7, a structured-output call on an enforced native path, not cut short or refused, returned content that is not well-formed JSON | MUST |

### conformance-adapter §5.12 and §5.13: `_mentions` takes a list

Extend the `_mentions` flavor in §5.13:

> - the **`_mentions`** suffix: the field's value **contains** the given substring (used where the exact
>   wording is implementation-defined). The value **MAY** be a non-empty list of substrings, asserting the
>   field contains **every** one. An empty list is `fixture_schema_invalid` (§9).

This widens one flavor's value domain. It adds no flavor, so the flavor set stays closed.

In §5.12, the `error_message_mentions` entry is retyped to `<str | [str, ...]>` with the same non-empty
rule, and fixture 082 joins the list of fixtures that use the block.

### conformance-adapter: keys already in use, path forcing, and log assertions

- **`calls_llm.response_schema`** and **`calls_llm.config`** (§5.1). The schema the call passes to
  `complete()`, and the `RuntimeConfig` it passes. Neither is new. `response_schema` is defined today only
  by harness notes in the observability fixtures that use it (120, 121, 123, 124, 125, 131 and 155), and
  `config`, used by fixtures 016, 017, 018, 021, 023, 025, 062, 063, 120, 123, 124, 125, 131 and 155, is
  defined nowhere. §5.1 becomes their general definition, and where a harness note differs, §5 governs
  (§5 *Definition homes*). This closes a small part of the vocabulary gap that 0119's first open question
  records. Fixture 161 uses both.
- **`mock_provider.capabilities`** (§5.11, beside `mock_provider.responses`). A mapping of boolean
  capability flags for the llm-provider mock: `supports_native_response_format` for the OpenAI mapping,
  and `supports_native_structured_output` for the Anthropic and Gemini mappings. When a flag is `false`,
  the mock presents as lacking that native capability, so an implementation takes the mapping's fallback
  through the static detection arm (§8.1.5.1, §8.2.5.1, §8.3.5.1). An absent flag means the capability is
  present. Neither flag is new: llm-provider fixtures 026, 027 and 072 use the first, and 040, 041, 050
  and 051 the second.
- **A mapping form for `mock_llm`** (§5.5). `mock_llm` also accepts
  `{capabilities: {...}, responses: [{status, body}, ...]}`, mirroring `mock_provider`. The list form
  stays, as shorthand for a mapping with only `responses`. Since the observability mock presents an
  OpenAI-compatible provider, `capabilities` takes `supports_native_response_format`, with the meaning
  above, so an observability fixture can force the fallback the way the llm-provider fixtures already do.
  An absent flag means the capability is present.
- **`count: <int>`** on an `expected.log_records` entry (§5.5). The number of captured records the entry
  matches **MUST** equal it. Without `count`, an entry asserts at least one match, as today.
- **`log_records_absent: [<entry>, ...]`** under `expected` (§5.5). Asserts that no captured log record
  matches any listed entry, where an entry matches by the same subset rule as `log_records` (an entry
  naming only `event_name` matches any record with that event name). The log-record analogue of
  `attributes_absent` and `metadata_absent`, which exist because a subset match can pin a value but never
  an absence.

For any case carrying `log_records_absent`, or a `log_records` entry with `count`, the adapter **MUST**
capture log records for the whole case and **MUST** wait until observer delivery has completed before
asserting; an adapter that cannot capture log records **MUST** fail the case rather than pass it.

## Conformance test impact

**llm-provider 082, `structured-output-error-message-completeness`** (new). Each case returns content that
fails a schema in a known set of ways and asserts `error_message_mentions` as a list naming **every**
expected violation's location, in the URI fragment form:

| Shape | Content | Asserted mentions |
|---|---|---|
| Flat object | two required properties missing, one of the wrong type | the three properties' locations, and the expected type's name |
| Nested object | inside `site`: one property of the wrong type, one missing | both locations, under `#/site/`, and the expected type's name |
| Nullable field, `anyOf` with `null` | the object member fails on one property | that property's location only |
| Union of two object schemas | both members fail, each on a different property | both members' locations |
| `allOf` of a referenced object schema and a `required` list | `site` is a string | `#/site`, and `object` |
| `oneOf` of two object schemas and `null` | `pet` matches both object members | `#/pet` |
| Object with `additionalProperties: false` | `site` carries an extra property, `zulu` | `#/site/zulu` |
| Array of objects | the first and third elements fail, the second is valid | `#/rows/0/...` and `#/rows/2/...` |
| Not valid JSON | | `error_message_present: true` only |

**The assertions name fragment pointers, not property names**, which closes three ways a mention could pass
wrongly. A composite-node message names only the composite's location, such as `#/site`, so it cannot
contain `#/site/lat`. A message that quotes the schema, or echoes the content, contains property names but
not instance locations. And a schema location, which validators write as `/properties/site/properties/lat`
or `#/properties/site/properties/lat`, never contains an instance location such as `#/site/lat`. Choosing
property names that cannot occur as substrings of one another keeps one location from matching another.

The `allOf` and `oneOf` rows are each answered by an empty set under a rule that filters `allOf` members by
type, or reports a `oneOf` over-match only when no member fails, so a mention there separates the rule from
those readings. The `additionalProperties` row separates it from validators that report the property at
its parent object.

The sidecar records the limits. A mention proves a violation was reported, not that nothing extra was,
because the closed flavor set has no negative form. So three rules are not pinned: that a nullable field's
`null` member is omitted; that a `oneOf` over-match is reported alone when another member fails with a
matching type, since that member's locations would share the composite's prefix; and the wording of a
missing property's constraint. A root-level location, `#`, cannot be asserted by substring either, since
every location contains it. `not` and `contains` are covered by the rule but not by a case.

Existing fixtures 022, 023, 063 and 064 are unaffected: 022 asserts only that a description is present,
and 023, 063 and 064 assert the property name `age`, which a fragment-form location still contains.

**llm-provider 083, `openai-refusal-finish-reason`** (new). A mock OpenAI response whose message carries a
non-empty `refusal` and no content, with OpenAI's own `finish_reason` set to `"stop"`. Without a
`response_schema`, the `Response`'s `finish_reason` is `"content_filter"`. With one, the call raises
`structured_output_invalid` whose `finish_reason` (§5.12 `carries`) is `"content_filter"`.

**observability 161, `structured-output-schema-not-honored`** (new). Every case asserts the span's
`openarmature.llm.structured_output.path`, or its absence, and the typed event's `structured_output_path`
through a typed-event collector (`typed_observers`, `contains_event`). Every case asserts the diagnostic
with `log_records` or `log_records_absent`:

| Case | Path | Outcome | Diagnostic |
|---|---|---|---|
| 1 | `native` | content not valid JSON, `finish_reason` `stop` | emitted once (`count: 1`), with an OTel and a Langfuse observer both attached |
| 2 | `native` | valid JSON that fails the schema, `stop` | absent |
| 3 | `native` | content not valid JSON, `length` | absent |
| 4 | `native` | content not valid JSON, `content_filter` | absent |
| 5 | `native` | content not valid JSON, `stop`, `stop_sequences` set on the call | absent |
| 6 | `native` | content not valid JSON, `stop`, a stop list only in the call's extras | absent |
| 7 | `prompt_augmentation`, forced with `supports_native_response_format: false` in `mock_llm`'s `capabilities` | content not valid JSON, `stop` | absent |
| 8 | `native` | valid content, on `LlmCompletionEvent` | absent |
| 9 | no `response_schema` | completion | absent; path null on the event and no path attribute (`attributes_absent`) |
| 10 | a schema is supplied but the call is rejected before sending, by a conflicting extras `response_format` (llm-provider §8.1.5) | `provider_invalid_request` | absent; path null on the event and no path attribute |

The absence cases are what make the emitted case mean anything. Without them an implementation that
emitted on every `structured_output_invalid`, or on every native call, would pass. Case 2 pins the
narrowing to parse failures, and case 6 the stop sequence carried in extras. The schema in cases 1 to 6
and 8 satisfies OpenAI's strict-mode rules, so the request carries `strict: true` and the path is
`native`. That leans on §8.1.5's SHOULD to send `strict: true` for such a schema, which llm-provider
fixture 026 already requires on the wire, so the case asks nothing the corpus does not.

No existing fixture changes.

## Alternatives considered

**Do nothing.** The convergence cost stays, `error_message_mentions` stays unable to mean one thing across
implementations, and an unhonored schema keeps passing as a model error.

**Require only that the first violation be reported, deterministically.** It would fix the fixture
determinism by defining "first" and leave the round trip per violation in place. It also cannot be
specified without naming a traversal order across validators that do not share one.

**State the rule as "every violation the validator can enumerate".** Rejected: conformance would depend on
the validator an implementation chose, and one whose validator stops early would be conformant by
construction.

**Report only the best-matching member of a union.** Rejected: validators disagree on which member is
best, so two conforming implementations would report different sets.

**Leave the location's form free.** Rejected: a fixture could then not tell a leaf from the composite that
contains it, or the first array element from the third, so the resolution rule would be untestable.

**Write locations as plain JSON Pointer strings.** Rejected: the whole content's pointer is the empty
string, which prints as nothing and reads like the no-location form a parse failure uses, and a short
pointer such as `/charlie` occurs inside a schema location such as `/properties/charlie/type`, so a fixture
could not tell where a violation was found from where its rule sits in the schema. The URI fragment form
avoids both, at the cost of a `#` prefix and percent-encoding for unusual property names.

**A structured per-violation field alongside `error_message`.** More useful to a programmatic consumer, and
out of scope here. It would be a new field rather than a change to this one, and nothing here prevents it.

**Keep the diagnostic a SHOULD, as the token-budget warning is.** Rejected: a fixture could not require it,
so its exclusions could not be tested either, and its condition is fully determined by fields the event
carries once the path is added, so requiring it costs an implementation nothing it does not already have.

**Key the diagnostic on any validation failure, not only a parse failure.** Rejected: a provider that
applied the schema can still return well-formed content that fails validation, as Anthropic's
capitalization caveat and Gemini's subset show, and a MUST that fired on those would report a healthy
provider as one that ignored the schema. The cost is that a dropped constraint whose output happens to
parse goes unreported, as it does today.

**Count a call as native only when its schema stays inside the provider's enforced keyword subset.**
Rejected: it would put each vendor's supported keyword list into the spec, a list that changes as vendors
extend support, to recover a case the parse-failure rule already covers in its most common form.

**Carry enforcement in a separate boolean field.** Rejected in favor of one field with four values, which
reads more simply and keeps the path and its enforcement from disagreeing.

**Detect an unhonored schema and fall back, or add the schema to the next attempt.** Rejected: the
condition is evidence rather than proof, and acting on it would have the implementation write schema text
into the request on its own initiative.

**Report the condition from the provider without recording the path on the event.** Rejected: it would
leave the path invisible to observers and to callers, which §8.1.5.1 already says SHOULD be able to inspect
the path chosen.

**Bound the OTel exception record in this proposal.** Rejected: it would reverse a deliberate decision that
keeps that record full, and a cap on the message alone would not bound it, since stack-trace renderings
repeat the message. OpenTelemetry's attribute value length limit bounds both, at the operator's choice.

## Open questions

1. **`tool_coercion` and the diagnostic.** A synthetic tool's input schema is also a constraint, so a
   coerced call that fails may also mean it was not honored. It is excluded because the failure event's
   `finish_reason` for a coerced call is not defined today: a coerced response stops with `tool_calls`,
   which graph-engine §6 says a `structured_output_invalid` failure never carries. Including the path waits
   on that being settled. No fixture asserts the `tool_coercion` value either, since the observability
   mock presents an OpenAI-compatible provider, which has no such path.
2. **A residual false positive.** Anthropic's `pause_turn` also maps to a `finish_reason` of `"stop"`
   (llm-provider §8.2.2), and the event does not carry the raw stop reason, so a paused turn whose content
   is incomplete JSON meets the condition without the constraint having been dropped. Whether the
   Anthropic mapping should surface a paused turn differently is left open.
3. **`native_unenforced` has no fixture.** Forcing it depends on §8.1.5's SHOULD to send `strict: false`
   for a schema outside strict mode, so a case could fail an implementation that conforms.
4. **Langfuse rendering of the path.** The path attribute has no §8.4 mapping. It is a classification
   rather than harvested content, so the exhaustive-mapping rule does not require one, and a Langfuse user
   loses only the inspection surface. Mapping it to `generation.metadata` is cheap if wanted.
5. **Verify before accept.** The diagnostic rests on vendor statements: that each native path constrains
   decoding to well-formed JSON, that OpenAI's does so only with `strict: true`, Anthropic's capitalization
   caveat, and Gemini's support for a subset of JSON Schema. §8.1.2's refusal rule rests on the shape of an
   OpenAI Chat Completions refusal: the `refusal` field, the absent content, and the `finish_reason` OpenAI
   reports with it. Each should be checked against current vendor documentation before accept.
6. **Forcing the fallback rests on a SHOULD.** Case 7 reaches prompt augmentation through §8.1.5.1's static
   detection, which the spec states as a SHOULD, and llm-provider fixture 027 already treats it as
   required ("the implementation MUST fall back per §8.1.5.1"). Whether static detection becomes a MUST is
   left to the separate question of how the fallback should behave, since the fallback writes text into the
   request on the implementation's own initiative.
