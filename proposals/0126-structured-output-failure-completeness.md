# 0126: Complete Structured-Output Failure Reports and a Schema-Not-Honored Diagnostic

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-10-11
- **Accepted:** 2026-10-28
- **Targets:**
  - spec/llm-provider/spec.md: modifies §5 (a `response_schema` call requests and validates conforming
    output, whether decoding is constrained depends on the path, and a `response_schema` that declares no
    `$schema` is read as JSON Schema draft 2020-12); modifies §7 (the
    `structured_output_invalid` entry's exposure sentence is rewritten, and a definition of what
    `error_message` describes is added); modifies §7.1 (the
    *Per-attempt span emission* paragraph states that each attempt's span, and the call's typed event,
    describe the request actually sent); modifies §8.1.2 and §8.1.6 (an OpenAI refusal, atomic or
    streamed, maps to a `finish_reason` of `"content_filter"`, and a streamed refusal's pieces are content
    deltas); modifies §8.1.5.2 (`message.content` is the refusal text for a refusal); modifies §8.1.5
    (`strict` decides the path a call reports, and the sentence on what `strict`
    leaves unchanged is narrowed to validation); modifies §8.2.5 and §8.3.5 (each states what its
    provider's constrained decoding guarantees, and names its native path); modifies §8.1.5.1, §8.2.5.1
    and §8.3.5.1 (each states that the path a call took is reported on the typed event)
  - spec/graph-engine/spec.md: modifies §6 (`LlmCompletionEvent` and `LlmFailedEvent` gain
    `structured_output_path`; under call-level retry, the call's event describes the request of the
    attempt whose outcome it reports and keeps the node-level `attempt_index`; `input_messages` is the
    list as sent, including a prompt-augmentation directive, or the caller's list for a call rejected
    before sending; the failure event's `output_content` row and the `error_message` paragraph after its
    table point to llm-provider §7)
  - spec/observability/spec.md: modifies §5.5 (a baseline attribute,
    `openarmature.llm.structured_output.path`); modifies §5.5.2 (an absent request attribute means the
    field was not supplied for the request the span describes); modifies §5.5.7 (the `schema_not_honored`
    diagnostic and its record's attributes); modifies §7 (one row in *Diagnostic event names*); modifies
    §11 (a caught attempt's duration, `error.type` and token-usage samples come from the implementation's
    record of that attempt, and `error.type` applies per attempt)
  - spec/conformance-adapter/spec.md: modifies §5.10 (the observability suite's binding tokens gain
    `<call_id_X>`); modifies §5.1 (defines `calls_llm`'s `model`, `response_schema`, `config` and `retry`
    keys, all already in use); modifies §5.5 (`mock_llm` gains a mapping form carrying `capabilities`;
    `log_records` entries gain `count`; new `log_records_absent`; `otel_observer` gains `attached`; when a
    case composes a Langfuse observer); modifies §5.11 (documents `mock_provider.capabilities` and its
    three flags, and the per-attempt `expected.llm_spans` assertion, all already in use); modifies §5.12
    and §5.13 (`error_message_mentions`, and the `_mentions` flavor generally, accept a non-empty list, and
    §5.12's `output_content` entry follows llm-provider §7's definition)
  - docs/compatibility.md: rows for RFC 6901 and RFC 8259; the JSON Schema row notes that llm-provider §5
    now names draft 2020-12; the OpenAI, Anthropic, Gemini and OpenAI streaming rows re-verified, with drift
    in Gemini's structured-output guide logged
  - spec/llm-provider/conformance/021-structured-output-success.md and
    022-structured-output-parse-failure.md (sidecar wording only, where they paraphrase §5 and §7)
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
a response that is not even well-formed JSON, or whose top level is not an object, and that was not cut
short or refused, is then reported as a schema the provider did not apply, rather than passing as an
ordinary model error, and it is diagnosed for every attempt, including one a retry recovers from. Under
call-level retry, the call's typed event and each attempt's span describe the request actually sent.

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
document is `#`, rather than an empty string that prints as nothing. And a location in the content does
not occur inside a location in the schema, which validators write as `/properties/site/properties/lat`,
unless a property is named like a JSON Schema keyword.

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
schema is in no other part of the request. Its output is commonly prose, JSON wrapped in a code block, or
JSON of the wrong shape, such as a bare list when the prompt asked for a list. Today that is
indistinguishable from a model that saw the schema and got it wrong. But a constrained response is
malformed only when it was cut short or refused, and each of those already surfaces: a refusal or a
`max_tokens` truncation as a `finish_reason` of `"content_filter"` or `"length"`, and a matched stop
sequence on a request that carried one. A constrained response also always has an object at its top level,
since llm-provider §5 requires every schema to. So content that is not well-formed JSON, or whose top
level is not an object, on an enforced native path, with a `finish_reason` of `"stop"` and no stop
sequence on the request, is evidence that the constraint did not reach or did not bind the model.

Content that parses to an object but fails the schema is not such evidence, because a provider that
applied the schema can return it, as the capitalization and subset cases show. The diagnostic therefore
keys on those two failures alone. A dropped constraint whose output happens to be a well-formed object
stays indistinguishable from a model error, as it is today.

One gap in the mappings stands in the way. Anthropic's refusal already maps to `"content_filter"`
(§8.2.2). OpenAI returns a refusal in a separate `refusal` field rather than as the message's content, or
in a streamed response as `delta.refusal` pieces, and neither §8.1.2 nor §8.1.6 maps it, so an OpenAI
refusal reads as unparseable content on a normal finish. This proposal maps it to `"content_filter"` as
well, and carries the refusal text as the message's content, the way an Anthropic refusal's text already
arrives.

The evidence is already at hand for each attempt except for one fact: which path the request took, and
whether that path is enforced. Recording it lets an implementation report the condition, as a diagnostic a
caller can act on at the serving layer. It is reported for every attempt, because under reask a later
attempt can recover, and diagnosing only the call's final failure would then hide the problem every time.

The diagnostic reports; it does not act. Its condition is evidence, not proof (see the residual cases in
*Open questions*), and acting on it automatically would mean switching to a fallback that writes schema
text into the request on the implementation's own initiative. So the condition is defined as distinct from
§8.1.5.1's detection, and it never changes what is sent.

### A retried call's event and spans can describe another request

Under call-level retry (llm-provider §7.1), each wire attempt has its own span, and the call has one typed
event, which reports its last attempt's outcome (graph-engine §6; a caught attempt emits no typed event).
The spec never says which request either describes. Two features change the request between attempts: a
per-attempt override changes the attempt's configuration, and reask adds the model's failed output and the
caller's correction to its messages. An implementation may describe the caller's original request
everywhere. An attempt's span then reports a temperature that attempt was not sent with, which defeats the
point of a span per attempt, and the call's event can describe a request its reported outcome did not come
from. This proposal requires each to describe the request actually sent.

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
An SDK sets it per tracer provider, and the standard environment variable
`OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT` sets it across the process. Whether the span-specific
`OTEL_SPAN_ATTRIBUTE_VALUE_LENGTH_LIMIT` reaches span events differs by SDK: at least one bounds event
attributes with the general limit only, and at least one bounds them with the span limit, read from the
span-specific variable and then the general one. The general variable bounds the exception record in
both when the span-specific variable is unset. Because observability §6 requires openarmature's spans to go through a private tracer provider, the
environment variable is the route that reaches them unless an implementation exposes its provider's limits.
That trade is the operator's to make on their own backend, so this proposal adds no spec-level cap.

## Detailed design

### llm-provider §5: what supplying a schema does

In the `complete()` description, replace "When `response_schema` is supplied, the call additionally
constrains the model's output to conform to the schema." with:

> When `response_schema` is supplied, the call additionally requests output that conforms to the schema
> and validates the response against it (§6 `parsed`, §7 `structured_output_invalid`); whether the provider
> constrains decoding to the schema depends on the path the mapping takes and on the vendor's own limits
> (§8).

The old sentence promised conformance on every path, which the paths below do not give.

In the `response_schema` parameter's description, add after "When present, MUST be a valid JSON Schema.":

> A `response_schema` that declares no `$schema` **MUST** be interpreted as JSON Schema draft 2020-12, so
> that validation, and the violations §7 reports, do not depend on which validator an implementation uses.

A violation is defined by the schema's keywords, and drafts disagree about some of them: `items` means
something different in 2020-12 than in earlier drafts, `dependentRequired` first appears in 2019-09, and
`prefixItems` in 2020-12. So "every violation" has one answer only once the draft is fixed.
`docs/compatibility.md` already records 2020-12 as the version the spec is written against. A tool's
`parameters` (§4) is left for a later change, since no fixture here covers it.

### llm-provider §7: what the error exposes, and what `error_message` describes

In the `structured_output_invalid` entry, replace the sentence beginning "The error MUST expose the requested
`response_schema`" and ending "not a transport failure." with:

> The error **MUST** expose the requested `response_schema`; the response's message content as
> **`output_content`**, verbatim as the mapping produced it (§6 `message.content`, which for an OpenAI
> refusal is the refusal text, §8.1.2); a description of the failure as **`error_message`**, defined below; and the response's normalized **`finish_reason`** (§6) and token
> **`usage`**. The last two are available from the received response, since the failure is a downstream
> parse or validation step on an intact wire response, not a transport failure. `output_content` and
> `error_message` match the graph-engine §6 failure-event field names (0082), and the call-level `reask`
> builder (§7.1) consumes them.

Then add, as the last paragraph of the entry, after its closing sentence beginning "Distinct from
`provider_invalid_response`", so it does not separate the exposure sentence from the `finish_reason`
explanation that follows it:

> **What `error_message` describes.** `error_message` **MUST** describe **every violation** the content
> commits against `response_schema`. A violation is a failing assertion, such as `type`, `required`, `enum`
> or `pattern`, not the applicator that contains it. Every failing assertion is a violation unless an
> enclosing keyword discards its result: an `anyOf` or `oneOf` discards its other members' results once
> one member is satisfied, and `if`, `not` and `contains` discard their subschemas' results.
>
> Each violation **MUST** state its **location** and the **constraint** that failed, and a `type`
> violation **MUST** also state the expected type. The location is a JSON Pointer into the content,
> written in its URI fragment form (RFC 6901 §6), with the percent-encoding that form requires: `#` for
> the whole content, `#/site/lat` for a property, `#/rows/2` for an array element, and `#/first%20name`
> for a property named `first name`.
>
> - **Where a violation is located.** At the part of the content its failing assertion applies to, with one
>   exception: a property the schema requires but the content lacks (`required`, `dependentRequired`) is
>   located at the pointer it would occupy, so a missing `lat` inside `site` is at `#/site/lat`, and each
>   missing property is its own violation. A property the schema does not allow, such as one excluded by
>   `additionalProperties: false`, is one violation at that property's own location. An array element the
>   schema does not allow is one violation at that element. A count or uniqueness constraint on an object
>   or array, such as `minItems` or `uniqueItems`, is one violation at the object or array.
> - **An `anyOf` or `oneOf` that no member satisfies.** The violations are every failing assertion of every
>   member whose own `type` admits the content's type at that location, after resolving references. A
>   member without a `type` of its own, including one that is itself a composite, counts as matching.
>   Where no member's type matches, the composite's location and the members' types are reported as one
>   violation.
> - **An `allOf`.** Every member applies, so the violations are every failing assertion of every member,
>   including a member's `type` when the content's type does not match it.
> - **A composite whose own constraint fails.** A `oneOf` that more than one member satisfies, whatever its
>   other members do, a `not` whose subschema is satisfied, and a `contains` that too few or too many array
>   elements satisfy are each one violation, located where the keyword applies.
> - **Content that is not well-formed JSON** (RFC 8259). That is the single violation reported. It has no
>   location, since no schema constraint could be evaluated, and in place of a constraint it states what
>   made the content malformed.
>
> Violations **SHOULD** appear in a stable order for a given content and schema. The wording around each
> location and constraint is implementation-defined.

The requirement is stated against the content and the schema, not against a validator. An implementation
whose validator stops at the first violation enumerates the rest, and "the first violation" never appears
in the rule. Likewise, a validator that reports locations in another notation, or reports an unexpected
property at its parent object, has its report converted to the form above. `response_schema` stays a
separately exposed field and is not folded into `error_message`.

### llm-provider §7.1: spans and the event describe the request actually sent

In the *Per-attempt span emission* paragraph, add after its first sentence:

> Each attempt's span describes the request that attempt sent, and the call's typed event describes the
> request of the attempt whose outcome it reports (graph-engine §6).

### llm-provider §8.1.2 and §8.1.6: an OpenAI refusal

In §8.1.2's `finish_reason` bullet, add after "Map any unknown `finish_reason` to `error`.":

> When `choices[0].message.refusal` is a non-empty string and the message carries no `tool_calls`, the
> message's content is the refusal text and the `finish_reason` is `"content_filter"`, whatever value
> OpenAI reports. This matches the Anthropic mapping, where a refusal's text arrives as content and its
> `stop_reason: "refusal"` maps to `"content_filter"` (§8.2.2), and it keeps the message within §3. `raw`
> keeps the response as received.

In §8.1.6, add a `refusal` delta to the **Wire** bullet's list of what a chunk's `choices[].delta`
carries, and add to the **Content deltas** bullet:

> A `refusal` delta is a content delta: OpenAI streams a refusal's text there in place of `content`, so
> each piece is emitted as a content token event as it arrives.

Add to the bullet beginning "**finish_reason / usage**":

> When the chunks' `choices[].delta.refusal` pieces, concatenated, form a non-empty string and the stream
> carried no tool-call deltas, the `finish_reason` is `"content_filter"`, whatever value the last chunk
> reports, as for an atomic response (§8.1.2). The refusal pieces are content deltas, so the refusal's
> text becomes the message's content, as it does for an atomic response that carries no tool calls. The
> pieces are content whether or not tool-call deltas arrive, since each is emitted as it streams.

Treating the pieces as content deltas keeps §6 *Streaming assembly* and §5's conformance proxy true as
written: the content is still the ordered concatenation of the content deltas, each emitted as a token
event. The section's verified-shapes sentence gains the `refusal` delta field. A refusal beside content or
beside tool calls would assemble differently on the two paths; OpenAI documents neither, and
`docs/open-questions.md` records the case.

In §8.1.5.2, the `message.content` bullet becomes:

> `message.content` is the response body's content string, verbatim, or the refusal text when the
> response is a refusal (§8.1.2).

### llm-provider §8.1.5, §8.2.5 and §8.3.5: what each native path guarantees

In §8.1.5, replace "The behavioral contract at the spec layer is identical regardless of `strict`:
validation happens post-receive against `response_schema`; failures raise `structured_output_invalid`
(§7)." with:

> Validation is identical regardless of `strict`: it happens post-receive against `response_schema`, and
> failures raise `structured_output_invalid` (§7). The path a call reports is not. OpenAI documents
> schema-constrained decoding only for `strict: true`, so the mapping reports a call sent with
> `strict: true` as the `"native"` path (graph-engine §6 `structured_output_path`), and one sent with
> `strict: false`, or without `strict`, as `"native_unenforced"`, whatever a particular
> OpenAI-compatible server does with the field.

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

In the closing note on Anthropic's strict tool use, replace "guarantees tool-call *argument* conformance"
with "constrains tool-call *arguments* to the tool's input schema, with the same inherent exceptions as
above". Anthropic's guide says the capitalization caveat applies to strict tool use too.

In §8.3.5, replace "The response's text content is the JSON string conforming to the schema;" through
"The behavioral contract matches §8.1.5's native path." with:

> The response's text content is a JSON string; the §8.3 mapping parses it into `Response.parsed` and
> validates against `response_schema` per §6. On validation failure, raise `structured_output_invalid` per
> §7. Gemini's constrained decoding produces well-formed JSON, but Gemini documents support for a subset of
> JSON Schema, so content can fail validation on a call that finished normally. The behavioral contract
> otherwise matches §8.1.5's native path with `strict: true`, and a call on it reports the `"native"` path
> (graph-engine §6 `structured_output_path`).

### llm-provider §8.1.5.1, §8.2.5.1 and §8.3.5.1: the path is reported

Append to each, after its existing requirement that implementations document which path a call uses:

> The path a call took is reported on the typed LLM event as `structured_output_path` (graph-engine §6),
> so a caller or observer can inspect it per call.

§8.1.5.1 additionally gains:

> A server that silently ignores the native constraint is not detectable from the request. When an attempt
> on the `strict: true` path returns content that is not well-formed JSON, or whose top level is not an
> object, and was not cut short or refused, observability §5.5.7's `schema_not_honored` diagnostic reports
> it. That diagnostic is not one of the detection arms above, and its condition **MUST NOT** by
> itself trigger the fallback.

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

### graph-engine §6: the event describes the request its outcome came from

Add to the *Typed LLM completion event* paragraph, after its field table:

> **Under call-level retry, the event describes the request its outcome came from.** Where llm-provider
> §7.1 issues more than one attempt for a call, the call's single typed event reports its last attempt's
> outcome, and its `input_messages`, `request_params` and `request_extras` describe that attempt's
> request: the messages it sent, as reask extended them, and the configuration after any per-attempt
> override is merged. For `request_params`, "supplied on this call" means supplied for that attempt. The
> event's `attempt_index` stays the node-level index; the wire attempt's index is on that attempt's span
> (observability §5.5).
>
> `input_messages` is the message list as sent, so on the prompt-augmentation path it includes the schema
> directive the mapping added (llm-provider §8.1.5.1, §8.2.5.1, §8.3.5.1), as the span's
> `openarmature.llm.input.messages` does (observability §5.5.1). For a call rejected before any request was
> sent, it is the caller's message list.

The `attempt_index` sentence keeps "reports its last attempt's outcome" from being read as moving the
event onto the wire attempt's index, which `LlmTokenEvent` already rules out for its own field. The
`input_messages` paragraph settles a reading the old row left open ("the message list the call was made
with"): the span renders from the event and reports what was sent, so the event has to carry the same
list.

`LlmFailedEvent` inherits the rule through its table's statement that it mirrors the completion event's
request-side fields. Its `output_content` row, which referred to §7's "raw response content" attribute, now
refers to §7's `output_content`, the response's message content as the mapping produced it.

### observability §5.5: the path attribute

Add a bullet to the *Baseline attributes* list, in that list's existing format, for
**`openarmature.llm.structured_output.path`**, a string, saying:

> The call's `structured_output_path` (graph-engine §6). When a `response_schema` was supplied and a
> request was sent, it **MUST** be set on the LLM provider span; otherwise it **MUST NOT** be set. A
> classification, not payload: not gated by `disable_provider_payload`.

That list is emitted on every LLM provider span unless the span itself is suppressed, independent of the
payload flag, which is why the attribute belongs there rather than in §5.5.1.

### observability §5.5.2: request attributes describe the span's own request

Replace "(or `RuntimeConfig` is absent on the call)" with "(or no `RuntimeConfig` applies to the request
this span describes)", replace "The absence of an attribute means "the field was not supplied for this
call,"" with "The absence of an attribute means "the field was not supplied for the request this span
describes,"", and add:

> Under call-level retry each attempt's span describes its own request, after any per-attempt override
> (llm-provider §7.1).

### observability §5.5.7: the `schema_not_honored` diagnostic

Add after the paragraph beginning "With both `LlmCompletionEvent` and `LlmFailedEvent` defined", so the
paragraphs about the typed failure event stay together:

> **A schema the provider did not honor.** For each wire attempt of a `complete()` call, including an
> attempt whose failure call-level retry (llm-provider §7.1) catches, the implementation **MUST** emit
> exactly one `WARNING`-level log record (§7), however many observers are attached, when all of the
> following hold:
>
> - the attempt failed with `structured_output_invalid`, and either the failure is llm-provider §7's
>   parse failure, content that is not well-formed JSON, or the content is well-formed JSON whose top level
>   is not an object;
> - the attempt's request took the `"native"` path (graph-engine §6 `structured_output_path`);
> - the attempt's `finish_reason` is `"stop"`; and
> - the attempt's request carried no stop sequence: no declared `stop_sequences`, and none under the stop
>   key of the mapping that issued it in its extras (`stop` for llm-provider §8.1, `stop_sequences` for
>   §8.2, `stopSequences` for §8.3). An empty list carries none.
>
> The record carries the event name `openarmature.structured_output.schema_not_honored` (§7 *Diagnostic
> event names*), the §7 correlation fields, and four attributes:
>
> - `openarmature.llm.provider` (string): the call's provider identifier, graph-engine §6's `provider`.
> - `openarmature.llm.model` (string): the call's model, as the §5.5 baseline attribute of that name.
> - `openarmature.llm.call_id` (string): the call's graph-engine §6 `call_id`, which joins the record to
>   the call's typed event, including when no span records the attempt.
> - `openarmature.llm.attempt_index` (int): the attempt's index, the value on the attempt's own span (§5.5).
>
> It reports that an attempt on a native path the provider constrains during decoding, which was not cut
> short or refused, returned content that is not well-formed JSON, or not a JSON object, which a
> constraint that bound cannot produce, since llm-provider §5 requires an object at the schema's top level.
> That is evidence the constraint did not reach or did not bind the model. It does not establish why.
>
> The implementation **MUST NOT** emit the record in any other case. In particular: not for content that
> parses to a JSON object, whether or not it validates, since a provider that applied the schema can still
> return content that fails validation (llm-provider §8.2.5, §8.3.5); not for a `finish_reason` of
> `"length"` or `"content_filter"`, where the output was cut short or refused; not when the request carried
> a stop sequence, since a matched sequence also reports `"stop"` while cutting the output short; and not
> for a `structured_output_path` of `"native_unenforced"`, `"tool_coercion"` or `"prompt_augmentation"`.
>
> The record is advisory. Its condition **MUST NOT** by itself cause the implementation to retry the
> call, change its structured-output path, or alter any request. It is not one of llm-provider §8.1.5.1's
> detection arms.

The attributes are keyed so that two implementations write the same record. `openarmature.llm.provider`
mirrors graph-engine §6's `provider` in the `openarmature.llm.*` namespace rather than reusing
`gen_ai.system`, which upstream has removed and which observability keeps on spans only for the installed
base. `openarmature.llm.call_id` is the record's join key to the call: the record is emitted whether or not
an OTel observer is attached, so its trace context cannot be relied on to reach the attempt's span.

### observability §11: a caught attempt's metric samples

In §11's opening paragraph, replace "for errored attempts (the source of an errored attempt's duration
sample and its `error.type` dimension, §11.3) — and introduce no new data source." with:

> for failed calls (the source of a failed call's duration sample and its `error.type` dimension, §11.3).
> An LLM attempt that call-level retry catches has no typed event of its own (graph-engine §6), so its
> duration sample, its `error.type` and any token-usage samples come from the implementation's record of
> that attempt, the same data its §5.5 span carries. Metrics introduce no other data source.

The rest of §11 follows. §11.1's "(Both draw from the §6 event stream, which exists regardless of span
emission.)" names the attempt's record as the second source. §11.2's *Call-level retry* paragraph takes a
`structured_output_invalid` attempt's usage from the call's `LlmFailedEvent.usage` when it is the call's
last attempt and from the attempt's record when retry catches it. §11.3's `error.type` row applies "when
the attempt errored", names the caught attempt's category as a source beside the typed failure events,
and is "Absent on an attempt that succeeded".

### observability §7: one row

Add to the *Diagnostic event names* table:

| Event name | Emitted when | Obligation |
|---|---|---|
| `openarmature.structured_output.schema_not_honored` | §5.5.7, an attempt of a structured-output call on a native path that constrains decoding, not cut short or refused, returned content that is not well-formed JSON or not a JSON object | MUST |

### conformance-adapter §5.12 and §5.13: `_mentions` takes a list

Extend the `_mentions` flavor in §5.13:

> - the **`_mentions`** suffix: the field's value **contains** the given substring (used where the exact
>   wording is implementation-defined). The value **MAY** be a non-empty list of substrings, asserting the
>   field contains **every** one. An empty list is `fixture_schema_invalid` (§9).

This widens one flavor's value domain. It adds no flavor, so the flavor set stays closed.

In §5.12, the `error_message_mentions` entry is retyped to `<str | [str, ...]>` with the same non-empty
rule, and fixtures 082 and 083 join the list of fixtures that use the block. Its `output_content` entry,
which described the value as "the verbatim content the model produced", now follows §7: the response's
message content as the mapping produced it.

### conformance-adapter: keys already in use, path forcing, and log assertions

- **`calls_llm.model`**, **`calls_llm.response_schema`**, **`calls_llm.config`** and **`calls_llm.retry`**
  (§5.1). The model the call's provider is bound to, which the typed events report as `model` and the
  span as `openarmature.llm.model`, and the schema, the `RuntimeConfig` and the retry configuration the
  call passes to `complete()`. None is new. `model`, used by 23 observability fixtures, is defined nowhere.
  `response_schema` is defined today only by harness notes in the observability fixtures that use it (120,
  121, 123, 124, 125, 131 and 155). `config`, used by fixtures 016, 017, 018, 021, 023, 025, 062, 063, 120,
  123, 124, 125, 131 and 155, is defined nowhere. `retry`, used by fixture 116, has only that fixture's
  harness note on the streamed mock it pairs with. `retry` takes the same mapping as §5.11's `call.retry`,
  including its `per_attempt_override` and `reask` fields. §5.1 becomes the general definition of all
  four, and where a harness note differs, §5 governs (§5 *Definition homes*). The definitions carry no list
  of the fixtures that use them, which would go stale. This closes a small part of the vocabulary gap that
  0119's first open question records. Fixture 161 uses all four.
- **`mock_provider.capabilities`** (§5.11, beside `mock_provider.responses`; §5.11's opening sentence, which
  describes the section as call-retry directives, gains the mock's capability flags). A mapping of boolean
  capability flags for the llm-provider mock, each meaning the capability is present when absent:
  - `supports_native_response_format`, for the OpenAI mapping, and `supports_native_structured_output`,
    for the Anthropic and Gemini mappings. When `false`, the mock presents as lacking native structured
    output, so an implementation takes the mapping's fallback through the static detection arm (§8.1.5.1,
    §8.2.5.1, §8.3.5.1).
  - `supports_image_input`. When `false`, the mock presents as a model without image input, so a request
    carrying an image block fails with `provider_unsupported_content_block` (llm-provider §7), raised
    before sending or mapped from the provider's rejection.

  None is new: llm-provider fixtures 026, 027 and 072 use the first flag, 040, 041, 050 and 051 the
  second, and 016, 035 and 039 the third.
- **A mapping form for `mock_llm`** (§5.5). `mock_llm` also accepts
  `{capabilities: {...}, responses: [{status, body}, ...]}`, mirroring `mock_provider`. The list form
  stays, as shorthand for a mapping with only `responses`. Since the observability mock presents an
  OpenAI-compatible provider, `capabilities` takes `supports_native_response_format`, with the meaning
  above, so an observability fixture can force the fallback the way the llm-provider fixtures already do.
  An absent flag means the capability is present. Each wire request takes the next entry, so under
  call-level retry each attempt does, as with `mock_provider.responses`; §5.5's existing "successive
  `complete()` calls" becomes "successive wire requests" to match.
- **`count: <int>`** on an `expected.log_records` entry (§5.5). The number of captured records the entry
  matches **MUST** equal it. Without `count`, an entry asserts at least one match, as today.
- **`log_records_absent: [<entry>, ...]`** under `expected` (§5.5). Asserts that no captured log record
  matches any listed entry, where an entry matches by the same subset rule as `log_records` (an entry
  naming only `event_name` matches any record with that event name). The log-record analogue of
  `attributes_absent` and `metadata_absent`, which exist because a subset match can pin a value but never
  an absence.
- **`otel_observer: {attached: false}`** (§5.5). Composes no OTel observer for the case; log records and
  typed events are still captured. Without it every observability case runs with one, so no case could show
  that the diagnostic does not depend on an observer being attached.
- **When a case composes a Langfuse observer** (§5.5). Today nothing says. A case composes one when it
  carries a `langfuse_observer` or `langfuse_client` block, an empty `langfuse_observer: {}` included, or an
  expected-outcome assertion on Langfuse output; otherwise it composes none. That matches every existing
  observability case: the only case in a Langfuse-named fixture without such a key is fixture 117's
  OTel-only case. Without the rule, one adapter could compose Langfuse only for cases that assert its
  output and another for every case, and fixture 161's absence and count assertions would mean different
  things under each.
- **`expected.llm_spans`** (§5.11). The per-attempt span assertion llm-provider fixtures 056, 057, 058 and
  061 to 066 already use, with `attempt_index`, `attributes`, `attributes_absent` and `error_category`,
  which §5.11 refers to as existing but nowhere defines. The list is exhaustive and positional, one entry
  per span in attempt order, as every existing use already is, and an entry asserts only the keys it
  carries, so an entry without `error_category` asserts neither failure nor success. Fixture 161 uses it
  for every span it asserts.
- **`<call_id_X>`** (§5.10). A first-occurrence-binding token for a call's graph-engine §6 `call_id`, added to
  the observability suite's set and defined in fixture 161's header, so a case can assert that the
  diagnostic record and the call's typed event name the same call.

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
| Nullable field, `anyOf` with `null` | the object member has one property of the wrong type | that property's location only, and the expected type's name |
| Union of two object schemas | each member has a different property of the wrong type | both members' locations, and the expected type's name |
| `allOf` of a referenced object schema and a `required` list | `site` is a string | `#/site`, and `object` |
| `oneOf` of two object schemas | `pet` satisfies both members | `#/pet` |
| Object with `additionalProperties: false` | `site` carries an extra property, `zulu` | `#/site/zulu` |
| A property name with a space | `first name` has the wrong type | `#/first%20name`, and the expected type's name |
| Array of objects | the first and third elements each have a property of the wrong type, the second is valid | `#/rows/0/...` and `#/rows/2/...`, and the expected type's name |
| Not valid JSON | | `error_message_present: true` only |
| Nullable field, `anyOf` with `null` | `site` is a string, which no member's type admits | `#/site`, and both members' types |
| `dependentRequired` | a property it makes required is missing | the missing property's location |
| Array with `prefixItems` and `items: false` | one element more than allowed | that element's location |
| Array with `minItems` | too few items | the array's location |
| Array with `uniqueItems` | a repeated item | the array's location |

**The assertions name fragment pointers, not property names**, which closes three ways a mention could pass
wrongly. A composite-node message names only the composite's location, such as `#/site`, so it cannot
contain `#/site/lat`. A message that quotes the schema, or echoes the content, contains property names but
not instance locations. And a schema location, which validators write as `/properties/site/properties/lat`
or `#/properties/site/properties/lat`, does not contain an instance location such as `#/site/lat`, provided
no property is named like a JSON Schema keyword, so the fixture's property names avoid `properties`,
`required`, `items` and the like. Choosing property names that cannot occur as substrings of one another
keeps one location from matching another.

The `allOf` row is answered by an empty set under a rule that filters `allOf` members by type, the
`oneOf` row by an empty set under a rule that reports only failing members' assertions, and the string
`site` row by an empty set under a rule that filters union members by type and reports only the survivors'
failures, so a mention there separates the rule from those readings. The `additionalProperties`,
`dependentRequired` and `items: false` rows separate it from validators that report the property or
element at its parent, and the space row from an implementation that skips the fragment form's
percent-encoding. The rows that assert a wrong type also assert the expected type's name, which the rule
requires a `type` violation to state. The `dependentRequired` and `prefixItems` rows rely on §5's draft
2020-12 default, since earlier drafts do not define those keywords.

The sidecar records the limits. A mention proves a violation was reported, not that nothing extra was,
because the closed flavor set has no negative form. So four rules are not pinned: that a nullable field's
`null` member is omitted; that a `oneOf` over-match is reported whatever its other members do, since every
member's locations share the composite's prefix; the wording of a missing property's constraint; and that
a type-name mention comes from the stated constraint, since a message that quotes the schema contains
type names anyway. A root-level location, `#`, cannot be asserted by substring either, since every
location contains it, and a location asserted by substring also matches a deeper one under it, so the
union, `minItems` and `uniqueItems` rows do not pin that the violation sits at the composite or array
rather than inside it. `not` and `contains` are covered by the rule but not by a case.

Existing fixtures 022, 023, 063 and 064 are unaffected: 022 asserts only that a description is present,
and 023, 063 and 064 assert the property name `age`, which a fragment-form location still contains.

**llm-provider 083, `openai-refusal-finish-reason`** (new). Mock OpenAI responses whose message carries a
non-empty `refusal` and no content:

- OpenAI's own `finish_reason` is `"stop"`, with no `response_schema`. The `Response`'s `finish_reason` is
  `"content_filter"`, its message's content is the refusal text, and `raw` carries the response as
  received.
- The same with OpenAI's `finish_reason` `"length"`, so the rule is seen to ignore OpenAI's value.
- With a `response_schema`, the call raises `structured_output_invalid` whose `carries` show
  `finish_reason` `"content_filter"`, `output_content` equal to the refusal text,
  `error_message_present: true` and `response_schema_present: true`.
- Streamed, in the SSE wire shape fixture 059 uses: `delta.refusal` pieces and a last chunk reporting
  `"stop"` give a `finish_reason` of `"content_filter"` and the concatenated pieces as the content.
- Three cases on the other side of the rule, since OpenAI sends `refusal: null` on ordinary messages: an
  atomic message with content and `refusal: null`, the same with `refusal: ""`, and a stream whose first
  chunk carries `refusal: null`. Each keeps its content and `"stop"`, so a mapping that fires on the key's
  presence fails.

**observability 161, `structured-output-schema-not-honored`** (new). Every case asserts the typed event's
`structured_output_path` through a typed-event collector (`typed_observers`, `contains_event`) and the
diagnostic with `log_records` or `log_records_absent`. Every case except 14 attaches the OTel observer and
a Langfuse observer; case 14 attaches neither. Every case that expects the record sets a literal
`caller_correlation_id` and asserts, on a `WARNING` record, its four attributes and that correlation id,
with its `openarmature.llm.call_id` bound to the call's typed event; a separate entry counts the records
with the event name at any level. Case 1's response reports a dated model name, so the record must name the
bound model.
Every case but 11 and 14 asserts each attempt's span through `llm_spans`, with its
`openarmature.llm.structured_output.path`, or its absence, and its error category. Case 11 asserts no span,
since whether a call rejected before sending gets one is not specified, and case 14 attaches no OTel
observer:

| Case | Path | Outcome | Diagnostic |
|---|---|---|---|
| 1 | `native` | content not valid JSON, `finish_reason` `stop` | emitted once (`count: 1`) |
| 2 | `native` | a valid JSON object that fails the schema, `stop` | absent |
| 3 | `native` | a valid JSON array, `stop` | emitted once |
| 4 | `native` | content not valid JSON, `length` | absent |
| 5 | `native` | content not valid JSON, `content_filter` | absent |
| 6 | `native` | content not valid JSON, `stop`, `stop_sequences` set on the call | absent |
| 7 | `native` | content not valid JSON, `stop`, a stop list only in the call's extras | absent |
| 8 | `prompt_augmentation`, forced with `supports_native_response_format: false` in `mock_llm`'s `capabilities` | content not valid JSON, `stop` | absent |
| 9 | `native` | valid content, on `LlmCompletionEvent` | absent |
| 10 | no `response_schema` | completion | absent; path null on the event and no path attribute (`attributes_absent`) |
| 11 | a schema is supplied but the call is rejected before sending, by a conflicting extras `response_format` (llm-provider §8.1.5) | `provider_invalid_request` | absent; path null on the event |
| 12 | `native`, with reask | attempt 0 not valid JSON on `stop`, attempt 1 valid | emitted once, carrying `openarmature.llm.attempt_index` 0; the call's single `LlmCompletionEvent` reports attempt 1, and its `input_messages` end with attempt 0's output and the rendered correction |
| 13 | `native`, with reask and a `per_attempt_override` that adds `stop_sequences` for attempt 1 | both attempts not valid JSON on `stop` | emitted once, carrying `openarmature.llm.attempt_index` 0; the call's single `LlmFailedEvent` reports attempt 1, and its `request_params` carry the stop sequence |
| 14 | `native`, with no backend observer attached (`otel_observer: {attached: false}`) | content not valid JSON, `stop` | emitted once |
| 15 | `native`, `stop_sequences: []` | content not valid JSON, `stop` | emitted once |
| 16 | `native` | an OpenAI refusal, which OpenAI reports as `stop` | absent; `content_filter` and the refusal text on the event |
| 17 | `native`, streamed | an OpenAI refusal in `delta.refusal` pieces, last chunk `stop` | absent; the pieces as content token events, and `content_filter` on the event |
| 18 | `native`, `stop: []` in extras | content not valid JSON, `stop` | emitted once |
| 19 | `native`, with reask | both attempts not valid JSON on `stop`, no stop sequence | emitted twice, carrying `attempt_index` 0 and 1 and the same call id; the call's single `LlmFailedEvent` keeps `attempt_index` 0 |

The absence cases are what make the emitted cases mean anything. Without them an implementation that
emitted on every `structured_output_invalid`, or on every native call, would pass. Case 2 pins the
narrowing to malformed and non-object content, case 3 the non-object arm, case 7 the stop sequence carried
in extras, cases 12 and 13 the per-attempt diagnosis and the rule that the call's event describes the
request its outcome came from, cases 15 and 18 that an empty stop list, declared or in extras, suppresses
nothing, cases 16 and 17 that the check reads the mapped `finish_reason` rather than the one OpenAI
reports, and case 19 one record per qualifying attempt. Cases 12, 13 and 19 also count the call's typed
events and assert the event's node-level `attempt_index`, and case 13 asserts the stop sequence on attempt
1's span and its absence on attempt 0's. As in fixture 116, none of them sees a typed event for its caught
attempt, so that attempt's record is the only trace of its failure outside its span. Case 8 asserts the
event's `input_messages` as the list sent: the schema directive as a leading system message, its wording
left to the implementation, then the caller's message. With both
observers attached in every case but 14, an absence case also covers a check placed in either observer, and the
emitted cases' record counts catch an implementation that emits once per observer; case 14, with no
observer attached, catches one that emits only from inside an observer. The schema in cases 1 to 7, 9 and
12 to 19 satisfies OpenAI's strict-mode rules, so the request carries `strict: true` and the path is
`native`. That leans on §8.1.5's SHOULD to send `strict: true` for such a schema, which llm-provider
fixture 026 already requires on the wire, so the case asks nothing the corpus does not.

No existing fixture's cases change. The sidecars of llm-provider fixtures 021 and 022 are reworded where
they paraphrase the §5 and §7 text this proposal changes.

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
avoids both, at the cost of a `#` prefix and of percent-encoding for property names with spaces, non-ASCII
characters, or other characters a URI fragment cannot carry.

**A structured per-violation field alongside `error_message`.** More useful to a programmatic consumer, and
out of scope here. It would be a new field rather than a change to this one, and nothing here prevents it.

**Keep the diagnostic a SHOULD, as the token-budget warning is.** Rejected: a fixture could not require it,
so its exclusions could not be tested either, and its condition is determined by facts the implementation
already holds for each attempt, its outcome, path, `finish_reason` and request, so requiring it costs an
implementation nothing it does not already have.

**Key the diagnostic on any validation failure.** Rejected: a provider that applied the schema can still
return a well-formed object that fails validation, as Anthropic's capitalization caveat and Gemini's subset
show, and a MUST that fired on those would report a healthy provider as one that ignored the schema. The
cost is that a dropped constraint whose output happens to be a well-formed object goes unreported, as it
does today.

**Count a call as native only when its schema stays inside the provider's enforced keyword subset.**
Rejected: it would put each vendor's supported keyword list into the spec, a list that changes as vendors
extend support, to recover a case the malformed-or-not-an-object rule already covers in its most common
form.

**Describe the caller's original request on the event and every span.** Rejected: an attempt's span would
report settings and messages that attempt was not sent with, which defeats having a span per attempt, and
the call's event would describe a request its outcome did not come from.

**Emit a typed event per wire attempt, and diagnose from those.** Rejected: graph-engine §6 makes the
typed event terminal, one per `complete()` call, and fixture 116 asserts that a caught attempt emits none.
Changing that is an event-model change for every consumer, the Langfuse mapping included. The
implementation already knows each attempt's outcome, so it can diagnose per attempt without one.

**Diagnose only the call's final failure.** Rejected: under reask, a later attempt that recovers would hide
a dropped constraint every time, and that is the case the diagnostic exists to surface.

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
2. **Residual false positives.** Anthropic's `pause_turn` also maps to a `finish_reason` of `"stop"`
   (llm-provider §8.2.2), and the event does not carry the raw stop reason, so a paused turn whose content
   is incomplete JSON meets the condition without the constraint having been dropped. Whether the
   Anthropic mapping should surface a paused turn differently is left open. Forwarded stop settings the
   exclusion does not name, such as a token-id stop list some OpenAI-compatible servers accept, are residual
   cases of the same kind.
3. **`native_unenforced` has no fixture.** Forcing it depends on §8.1.5's SHOULD to send `strict: false`
   for a schema outside strict mode, so a case could fail an implementation that conforms.
4. **Langfuse rendering of the path.** The path attribute has no §8.4 mapping. It is a classification
   rather than harvested content, so the exhaustive-mapping rule does not require one, and a Langfuse user
   loses only the inspection surface. Mapping it to `generation.metadata` is cheap if wanted.
5. **Verify before accept.** The diagnostic rests on vendor statements: that each native path constrains
   decoding to well-formed JSON with an object at the top level, that OpenAI's does so only with
   `strict: true`, Anthropic's capitalization caveat, and Gemini's support for a subset of JSON Schema.
   §8.1.2's and §8.1.6's refusal rule rests on the shape of an OpenAI Chat Completions refusal: the
   `refusal` field and the `delta.refusal` pieces, whether content accompanies a refusal, and the
   `finish_reason` OpenAI reports with it. And the OpenTelemetry specification applies the attribute value
   length limit to span events, which at least one SDK implements; coverage across the SDKs implementations
   use should be checked. Each should be confirmed against current documentation before accept.
6. **Forcing the fallback rests on a SHOULD.** Case 8 reaches prompt augmentation through §8.1.5.1's
   static detection, which the spec states as a SHOULD, and llm-provider fixture 027 already treats it as
   required ("the implementation MUST fall back per §8.1.5.1"). Whether static detection becomes a MUST
   waits on a prior question. The fallback appends a schema directive the implementation writes, which sits
   uneasily with the charter's principle 7, "No built-in prompts": every prompt the LLM sees is authored by
   the developer. Making the fallback mandatory would harden that tension before it is settled.
