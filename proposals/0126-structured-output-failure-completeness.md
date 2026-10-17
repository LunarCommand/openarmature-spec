# 0126: Complete Structured-Output Failure Reports and a Schema-Not-Honored Diagnostic

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-10-11
- **Targets:**
  - spec/llm-provider/spec.md: modifies §7 (the `structured_output_invalid` entry's exposure sentence is
    rewritten, and a definition of what `error_message` describes is added); modifies §8.1.5.1, §8.2.5.1
    and §8.3.5.1 (each states that the path a call took is reported on the typed event)
  - spec/graph-engine/spec.md: modifies §6 (`LlmCompletionEvent` and `LlmFailedEvent` gain
    `structured_output_path`; the `error_message` paragraph after the failure-event table is reconciled
    with llm-provider §7)
  - spec/observability/spec.md: modifies §5.5 (a baseline attribute,
    `openarmature.llm.structured_output.path`); modifies §5.5.7 (the `schema_not_honored` diagnostic);
    modifies §7 (one row in *Diagnostic event names*)
  - spec/conformance-adapter/spec.md: modifies §5.1 (documents `calls_llm`'s existing `response_schema`
    and `config` keys); modifies §5.5 (`mock_llm` gains `capabilities`; new `log_records_absent`);
    modifies §5.12 and §5.13 (`error_message_mentions`, and the `_mentions` flavor generally, accept a
    non-empty list); documents `mock_provider.capabilities.supports_native_response_format`, which three
    llm-provider fixtures already use
  - spec/llm-provider/conformance/082-structured-output-error-message-completeness.{yaml,md} (new)
  - spec/observability/conformance/161-structured-output-schema-not-honored.{yaml,md} (new)
- **Related:** 0016 (structured output), 0082 (named the §7 error fields and put the response-side surface
  on the failure event), 0095 (the `reask` builder `error_message` was named for), 0118 and 0119 (keep the
  OTel exception record full and ungated, which this proposal leaves in place), 0121 (diagnostic event
  names)

## Summary

A `structured_output_invalid` failure's `error_message` is required to describe the failure but not all of
it, so an implementation may report only the first violation, and a correction built from it fixes one
field per round trip. This proposal requires every violation, each with its location as a JSON Pointer and
the constraint that failed, and defines what a violation is inside a union. It also records on the typed
LLM event which structured-output path a call took, so that a failure on a path whose schema the provider
enforces is reported as a schema the provider did not honor, rather than passing as an ordinary model
error.

## Motivation

### A correction can only fix what it is told

llm-provider §7 requires the error to expose "a description of the validation or parse failure as
**`error_message`** (the wrapped exception's message, the failing JSON Pointer, or the language's
idiomatic equivalent)". The parenthetical describes one failure. Many JSON Schema validators stop at the
first violation by default, so an implementation following the text faithfully reports one violation per
failure.

§7.1's `reask` builder, which the field was named for, turns that description into a correction the model
can act on. When the description names one of several violations, the correction addresses only that one,
and the next attempt fails on the next. A record with several independently wrong fields needs a round
trip per field, against an attempt budget that is usually small. Reporting every violation at once lets
one correction address all of them.

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
another only the non-null member, and all three fit the words. A `oneOf` that matches more than one member,
or a `not` whose subschema matches, has no failing member at all. So the rule has to say which members
count, and what to report when the composite's own constraint is the one that failed.

The location needs a defined form for the same reason. A description that says "site" or "the third item"
in free prose cannot be told apart from one that reports the composite, or one that reports only the first
array element, so no fixture could check that a violation was resolved at all. JSON Pointer (RFC 6901) is
the standard notation for a location in a JSON document, and the current §7 text already names it as an
example.

### A fixture assertion cannot mean one thing today

conformance-adapter §5.12's `error_message_mentions` asserts that the field contains a substring, since the
wording is implementation-defined. Under the current text it can only ever match whichever violation an
implementation surfaces first, and which violation is first is not stable across validators or languages.
A fixture asserting a substring of anything but the sole violation cannot have one answer across
conforming implementations. Requiring every violation, each at a defined location, is what makes the
assertion well defined.

### A schema the provider did not honor looks like a model error

Each mapping sends the schema to the provider as a native constraint where it can, and the spec already
states which native forms the provider enforces during decoding. §8.1.5 sends `strict: true` when the
schema satisfies OpenAI's strict-mode rules, enabling "schema-constrained decoding", and falls back to
`strict: false` when it does not. §8.2.5 states that "Anthropic's constrained decoding guarantees the
generated output conforms to the schema". §8.3.5 states that "Gemini natively supports schema-constrained
decoding".

§8.1.5.1 recognizes that some servers "raise an error or silently ignore the field". It says
implementations SHOULD detect this, either statically from provider capability metadata or dynamically
from a first call that returns an error, and then fall back to prompt augmentation automatically. The
silent case is neither: the call succeeds at the transport level, and its content fails validation.

When an intermediary drops an enforced constraint, the model never sees the schema, its output does not
conform, and the call fails with `structured_output_invalid`. Today that is indistinguishable from a model
that saw the schema and got it wrong. But on a path the provider enforces, a model that finished on its
own should not be able to produce non-conforming content. The two cases §8.2.5 calls inherent, a refusal
and a `max_tokens` truncation, already surface with a `finish_reason` of `"content_filter"` or `"length"`.
So a failure on an enforced native path with a `finish_reason` of `"stop"` is evidence that the constraint
did not reach or did not bind the model.

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

An operator who wants that record bounded already has OpenTelemetry's standard attribute value length
limit, which SDKs apply to attribute collections. In at least one SDK it covers span-event attributes,
including both the exception message and the stack trace, which a cap on the message alone would not. It
is off by default, counts characters rather than bytes, adds no marker, and applies process-wide. That
trade is the operator's to make on their own backend, so this proposal adds no spec-level cap.

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
> commits against `response_schema`, and each violation **MUST** state its **location**, as a JSON Pointer
> (RFC 6901) into the content, and the **constraint** that failed. A violation is a failing assertion, such
> as `type`, `required`, `enum` or `pattern`, not the applicator that contains it:
>
> - A missing required property is located at the pointer it would occupy, so a missing `lat` inside
>   `site` is located at `/site/lat`. A `required` keyword with several missing properties is one
>   violation per missing property.
> - Within a composite (`anyOf`, `oneOf`, `allOf`), the violations are every failing assertion of every
>   member whose declared top-level type matches the content at that location, after resolving
>   references. A member that declares no type counts as matching. Where no member's type matches, the
>   composite's location and its type alternatives are reported as one violation.
> - Where the composite's own constraint fails with no failing member, as when a `oneOf` matches more than
>   one member or a `not` subschema matches, that is one violation, located at the composite.
> - Where the content is not well-formed in the requested encoding, that is the single violation reported,
>   with no location, since no schema constraint could be evaluated.
>
> Violations **SHOULD** appear in a stable order for a given content and schema. The wording around each
> location and constraint is implementation-defined.

The requirement is stated against the content and the schema, not against a validator. An implementation
whose validator stops at the first violation enumerates the rest, and "the first violation" never appears
in the rule. `response_schema` stays a separately exposed field and is not folded into `error_message`.

### llm-provider §8.1.5.1, §8.2.5.1 and §8.3.5.1: the path is reported

Append to each, after its existing requirement that implementations document which path a call uses:

> The path a call took is reported on the typed LLM event as `structured_output_path` (graph-engine §6),
> so a caller or observer can inspect it per call.

§8.1.5.1 additionally gains:

> A server that silently ignores the native constraint is not detectable from the request. When such a
> call fails `structured_output_invalid`, observability §5.5.7's `schema_not_honored` diagnostic reports
> it. That diagnostic is not one of the detection arms above, and its condition **MUST NOT** by itself
> trigger the fallback.

### graph-engine §6: `structured_output_path`

Add one row to both the `LlmCompletionEvent` and the `LlmFailedEvent` tables, after `request_extras`:

| Field | Type | Description |
|---|---|---|
| `structured_output_path` | string \| null | Which path the call used to obtain structured output, when `complete()` was called with a `response_schema` (llm-provider §5). `"native"` when the request carried the schema as the provider's native structured-output constraint in a form the mapping states is enforced during decoding (llm-provider §8.1.5 with `strict: true`, §8.2.5, §8.3.5). `"native_unenforced"` when it carried the schema natively in a form the mapping states is not enforced (§8.1.5 with `strict: false`). `"tool_coercion"` when it carried the schema as a synthetic tool's input schema (§8.2.5.1). `"prompt_augmentation"` when it carried the schema only in the prompt (§8.1.5.1, §8.2.5.1, §8.3.5.1). Where a call issues more than one request, the path of the request whose outcome this event reports. Null when no `response_schema` was supplied, and null when no request was sent. A classification, not payload: never gated by `disable_provider_payload`. |

The failure table already states that it mirrors the completion event's request-side fields one for one;
the explicit row keeps the table complete.

Replace the paragraph after the failure-event table, which currently describes `error_message` as "the
wrapped exception's message or failing locator", with:

> For a `structured_output_invalid` failure, `error_message` carries the llm-provider §7 failure
> description: every violation, each with its location and the constraint that failed. Implementations
> populate the exception message with that description, so observers read it from `error_message` without
> a dedicated field.

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

> **A schema the provider did not honor.** When an `LlmFailedEvent` has an `error_category` of
> `structured_output_invalid`, a `structured_output_path` of `"native"` and a `finish_reason` of `"stop"`,
> and its `request_params` carry no `stop_sequences`, the implementation **MUST** emit exactly one
> `WARNING`-level log record (§7) for that event, however many observers are attached. The record carries
> the event name `openarmature.structured_output.schema_not_honored` (§7 *Diagnostic event names*) and the
> §7 correlation fields, and names the call's provider, model and `call_id`. It reports that the content
> failed to parse or validate against a schema the provider enforces, on a call the model finished on its
> own, which is evidence that the constraint did not reach or did not bind the model. It does not
> establish why.
>
> The implementation **MUST NOT** emit the record in any other case. In particular: not for a
> `finish_reason` of `"length"` or `"content_filter"`, where the output was cut short or refused, which
> includes the two cases llm-provider §8.2.5 calls inherent; not when the caller supplied stop sequences,
> since a matched sequence also reports `"stop"` while cutting the output short; and not for a
> `structured_output_path` of `"native_unenforced"`, `"tool_coercion"` or `"prompt_augmentation"`.
>
> The record is advisory. Its condition **MUST NOT** by itself cause the implementation to retry the
> call, change its structured-output path, or alter any request. It is not one of llm-provider §8.1.5.1's
> detection arms.

### observability §7: one row

Add to the *Diagnostic event names* table:

| Event name | Emitted when | Obligation |
|---|---|---|
| `openarmature.structured_output.schema_not_honored` | §5.5.7, a structured-output call on an enforced native path finished on its own and its content failed to parse or validate | MUST |

### conformance-adapter §5.12 and §5.13: `_mentions` takes a list

Extend the `_mentions` flavor in §5.13:

> - the **`_mentions`** suffix: the field's value **contains** the given substring (used where the exact
>   wording is implementation-defined). The value **MAY** be a non-empty list of substrings, asserting the
>   field contains **every** one. An empty list is `fixture_schema_invalid` (§9).

This widens one flavor's value domain. It adds no flavor, so the flavor set stays closed.

In §5.12, the `error_message_mentions` entry is retyped to `<str | [str, ...]>` with the same non-empty
rule, and fixture 082 joins the list of fixtures that use the block.

### conformance-adapter: path forcing, log absence, and keys already in use

- **`calls_llm.response_schema`** and **`calls_llm.config`** (§5.1). The schema the call passes to
  `complete()`, and the `RuntimeConfig` it passes. **Documented rather than introduced**: observability
  fixtures 120, 121, 123, 124 and 125 already use `response_schema`, and 018, 025 and 062 use `config`,
  with neither defined in either definition home. Fixture 161 uses both.
- **`mock_provider.capabilities.supports_native_response_format: <bool>`**. When `false`, the mock
  provider presents as lacking native structured output, so an implementation takes the prompt-augmentation
  fallback through llm-provider §8.1.5.1's static detection arm. **Documented rather than introduced**:
  llm-provider fixtures 026, 027 and 072 already use it, and conformance-adapter has no section for the
  llm-provider mock's keys, so placement is settled at accept.
- **`mock_llm.capabilities.supports_native_response_format: <bool>`** (§5.5). The same key with the same
  meaning on the observability mock, so an observability fixture can force the fallback the way the
  llm-provider fixtures already do.
- **`log_records_absent: [<entry>, ...]`** under `expected` (§5.5). Asserts that no captured log record
  matches any listed entry, where an entry matches by the same subset rule as `log_records` (an entry
  naming only `event_name` matches any record with that event name). The log-record analogue of
  `attributes_absent` and `metadata_absent`, which exist because a subset match can pin a value but never
  an absence. For any case carrying it, the adapter **MUST** capture log records for the whole case and
  **MUST** wait until observer delivery has completed before asserting; an adapter that cannot capture log
  records **MUST** fail the case rather than pass it.

## Conformance test impact

**llm-provider 082, `structured-output-error-message-completeness`** (new). Each case returns content that
fails a schema in a known set of ways and asserts `error_message_mentions` as a list naming **every**
expected violation's JSON Pointer:

| Shape | Content | Asserted pointers |
|---|---|---|
| Flat object | two required properties missing, one of the wrong type | the three properties' pointers |
| Nested object | inside `site`: one property of the wrong type, one missing | both, under `/site/` |
| Nullable field, `anyOf` with `null` | the object member fails on one property | that property's pointer only |
| Union of two object schemas | both members fail, each on a different property | both members' pointers |
| Array of objects | the first and third elements fail, the second is valid | `/items/0/...` and `/items/2/...` |
| Not valid JSON | | `error_message_present: true` only |

**The assertions name pointers, not property names**, which closes the two ways a mention could pass
wrongly. A composite-node message names only the composite's location, such as `/site`, so it cannot
contain `/site/lat`. A message that quotes the schema, or echoes the content, contains property names but
not instance pointers. Choosing property names that cannot occur as substrings of one another keeps one
pointer from matching another.

The sidecar records two limits. A mention proves a violation was reported, not that nothing extra was: the
rule that a nullable field's `null` member is omitted is not pinned, because the closed flavor set has no
negative form. And `oneOf` over-match and `not` are covered by the rule but not by a case.

Existing fixtures 022, 023, 063 and 064 are unaffected: each has a single violation, or asserts a substring
of one that remains named.

**observability 161, `structured-output-schema-not-honored`** (new). Every case asserts the span's
`openarmature.llm.structured_output.path`, and asserts the diagnostic with `log_records` or
`log_records_absent`:

| Case | Path | Outcome | Diagnostic |
|---|---|---|---|
| 1 | `native` | invalid content, `finish_reason` `stop` | emitted |
| 2 | `native` | content not valid JSON, `stop` | emitted |
| 3 | `native` | invalid content, `length` | absent |
| 4 | `native` | invalid content, `content_filter` | absent |
| 5 | `native` | invalid content, `stop`, caller stop sequences set | absent |
| 6 | `prompt_augmentation`, forced with `supports_native_response_format: false` | invalid content, `stop` | absent |
| 7 | `native` | valid content | absent |
| 8 | no `response_schema` | completion | absent, and no path attribute (`attributes_absent`) |

The absence cases are what make the emitted cases mean anything. Without them an implementation that
emitted on every `structured_output_invalid`, or on every native call, would pass. The schema in cases 1
to 5 and 7 satisfies OpenAI's strict-mode rules, so the request carries `strict: true` and the path is
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

**A structured per-violation field alongside `error_message`.** More useful to a programmatic consumer, and
out of scope here. It would be a new field rather than a change to this one, and nothing here prevents it.

**Keep the diagnostic a SHOULD, as the token-budget warning is.** Rejected: a fixture could not require it,
so its exclusions could not be tested either, and its condition is fully determined by fields already on
the event, so requiring it costs an implementation nothing it does not already have.

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
repeat the message. OpenTelemetry's native limit bounds both, at the operator's choice.

## Open questions

1. **`tool_coercion` and the diagnostic.** A synthetic tool's input schema is also a constraint, so a
   coerced call that fails may also mean it was not honored. It is excluded because the failure event's
   `finish_reason` for a coerced call is not defined today: a coerced response stops with `tool_calls`,
   which graph-engine §6 says a `structured_output_invalid` failure never carries. Including the path waits
   on that being settled.
2. **A residual false positive.** Anthropic's `pause_turn` also maps to a `finish_reason` of `"stop"`
   (llm-provider §8.2.2), and the event does not carry the raw stop reason, so a paused turn whose content
   fails validation meets the condition without the constraint having been dropped. Whether the Anthropic
   mapping should surface a paused turn differently is left open.
3. **`native_unenforced` has no fixture.** Forcing it depends on §8.1.5's SHOULD to send `strict: false`
   for a schema outside strict mode, so a case could fail an implementation that conforms.
4. **Langfuse rendering of the path.** The path attribute has no §8.4 mapping. It is a classification
   rather than harvested content, so the exhaustive-mapping rule does not require one, and a Langfuse user
   loses only the inspection surface. Mapping it to `generation.metadata` is cheap if wanted.
5. **Verify before accept.** The diagnostic's meaning rests on the spec's own statements that the
   Anthropic and Gemini native paths are enforced during decoding, and that OpenAI's is enforced only with
   `strict: true`. Those statements should be checked against current vendor documentation before accept,
   as should the claim that OpenTelemetry SDKs apply the attribute value length limit to span-event
   attributes.
