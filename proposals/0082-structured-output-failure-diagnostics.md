# 0082: Structured-Output Failure Diagnostics on the LLM Failure Event

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-24
- **Accepted:** 2026-06-25
- **Targets:** spec/graph-engine/spec.md (§6 — the `LlmFailedEvent` typed variant from proposal 0058 gains the **response-side field surface** — `output_content`, `finish_reason`, `usage`, `response_id`, `response_model` (five of `LlmCompletionEvent`'s response-side fields, all but `output_tool_calls`) — populated only for the one llm-provider §7 category that received a response, `structured_output_invalid`, and null for every other category); spec/llm-provider/spec.md (§7 — the `structured_output_invalid` error additionally exposes the response's normalized `finish_reason` and token `usage`, reconciling §8.2.5's existing "surfaces the mapped `finish_reason`" statement with §7's error contract); spec/observability/spec.md (§5.5.7 — reconciles the "response-side fields are absent — no response was received" framing; §8.4.2 / §8.4.3 — the bundled Langfuse failed Generation populates `output` / `usage` / `metadata.finish_reason` / `response_id` / `response_model`; §5.5.1 / §5.5.3 — the OTel error span carries the same surface on its existing `openarmature.llm.*` attributes (`output.content` per §5.5.1; `finish_reason` / `usage.*` per §5.5.3); §11.2 — reconciles the token-usage histogram's "failed attempts ... contribute nothing" rule, since a `structured_output_invalid` failure now carries a usage record); plus new conformance fixtures under `spec/observability/conformance/` and updates to llm-provider fixtures 022 / 023.
- **Related:** 0058 (typed LLM failure event — this extends its field set, and its *Motivation* named this follow-on: *"structured-output validation failure events if demand emerges"*), 0049 (typed LLM completion event — its *Out of scope* anticipated the same follow-on; the response-side field semantics this mirrors), 0057 (LlmCompletionEvent field-set extension — the `output_content` privacy posture this mirrors), 0016 (llm-provider structured output — defines the `structured_output_invalid` §7 category and the error's mandated surface; this proposal extends that surface)
- **Supersedes:**

## Summary

A `structured_output_invalid` failure is the one llm-provider §7 error category where the model **did**
return a response — the provider call succeeded at the wire level, and the failure is a downstream
parse-or-validate step rejecting the returned content. Yet `LlmFailedEvent` (proposal 0058) carries
**no** response-side fields, on the premise that a failure means "no response was received," and the
`structured_output_invalid` error itself (§7) exposes only the schema, the raw content, and a failure
description. The single most useful triage signal — **why** the generation stopped — is therefore lost
to observers and to retry logic: a truncated completion (the model hit `max_tokens`, `finish_reason ==
"length"`) is indistinguishable from a model that finished cleanly but emitted malformed or
schema-violating JSON (`finish_reason == "stop"`).

This proposal carries the full response-side surface for `structured_output_invalid` failures across
both surfaces. `LlmFailedEvent` gains five of `LlmCompletionEvent`'s response-side fields (all but `output_tool_calls`) —
`output_content`, `finish_reason`, `usage`, `response_id`, `response_model` — populated for
`structured_output_invalid` (null for every other category), so the failed generation renders with its
actual output, token usage, and stop reason instead of a null, zero-token record. The §7 error gains
`finish_reason` and `usage` so a node's exception handler can make a truncation-aware retry decision.
All purely additive.

## Motivation

Proposal 0058 carved LLM failures into the `LlmFailedEvent` typed variant and scoped its field set
deliberately: it mirrors the request side plus `error_category` / `error_type` / `error_message`, and
*"Response-side fields (`response_id`, `response_model`, `usage`, `output_content`, `finish_reason`) are
absent from the failure variant — no response was received."*

**That premise has exactly one exception, and it is the category that needs response-side data most.**
Of the nine §7 categories, eight describe a call that produced no usable response —
`provider_authentication`, `provider_unavailable`, `provider_invalid_model`, `provider_model_not_loaded`,
`provider_rate_limit`, `provider_invalid_request`, `provider_unsupported_content_block`, and (wire-shape
malformation) `provider_invalid_response`. For those, "no response was received" is correct. But `structured_output_invalid` is structurally a **completion whose final
validation gate failed** (§7): the provider returned content, the model produced output, and the parse
or schema-validation step rejected it. The wire response is intact; everything the success variant
carries — `output_content`, `finish_reason`, `usage`, `response_id`, `response_model` — genuinely exists
and is in the implementation's hand at the moment the error is raised.

**The lost signal is `finish_reason`, and it is the key to triage.** A structured-output failure has
three distinguishable causes, separated by the response's normalized §6 `finish_reason`:

| `finish_reason` | What happened | Typical remediation |
|---|---|---|
| `"length"` | **Truncated** — the model hit `max_tokens` (or the provider's budget) and the JSON was cut off mid-output | raise the token budget / shrink the requested output; **may succeed on retry** with a larger budget |
| `"stop"` | The model finished normally but emitted invalid JSON, or valid JSON that violated the schema | prompt / model / schema fix; usually **fails the same way on retry** |
| `"content_filter"` | The provider's safety filter blocked or truncated the response | prompt fix; a distinct path |

Today an observer or a node's retry classifier cannot tell these apart without heuristically inspecting
the raw bytes ("does this JSON look truncated?") — fragile, and impossible for a pure event-stream
observer that never sees the exception. `finish_reason` makes the distinction authoritative and
cross-provider: OpenAI `length`, Anthropic `max_tokens`, and Gemini `MAX_TOKENS` all normalize to
`"length"` (llm-provider §8.1.2 / §8.2.2 / §8.3.2), and §6 defines `"length"` as "the model hit
`max_tokens` or the equivalent provider budget."

**The spec already computes this — it just doesn't expose it on the event.** llm-provider §8.2.5
already states that on a `stop_reason: "max_tokens"` truncation "the mapping surfaces the non-conforming
content **and the mapped `finish_reason`** (`content_filter` / `length`) per §6 / §7." So the value is
computed at the failure site. But §7's error MUST-list does not name `finish_reason` (a soft gap vs.
§8.2.5), and `LlmFailedEvent` does not carry it at all. This proposal closes both.

**`usage` is the corroborating signal — and fixes a real observability defect.** On a `length`
failure, `usage.completion_tokens` sits at (or just under) the configured `max_tokens`, corroborating
the truncation. Independently, carrying `usage` fixes the failed generation rendering as
**zero tokens** in the bundled Langfuse observer (no usage attribute exists to source from today) — so
failed structured-output calls currently drop out of token / cost accounting entirely, even though they
consumed tokens.

**This is the follow-on 0049 and 0058 named.** Both anticipated a "structured-output validation
failure" follow-on "if demand emerges." Demand has emerged from observability consumers triaging
exactly the truncation-vs-malformed case. The clean shape is not a new event type but enriching the
variant that already fires for `structured_output_invalid` with the response-side surface it structurally
has.

## Proposed change

### graph-engine §6 — `LlmFailedEvent` gains the response-side surface

First, reconcile the field table's lead-in sentence — it predates this change and now contradicts the
rows below. It currently reads *"The event mirrors `LlmCompletionEvent`'s identity / scoping /
request-side field set 1:1, carries failure-specific fields **in place of** the success-only
response-side fields:"*. Reword to:

> The event mirrors `LlmCompletionEvent`'s identity / scoping / request-side field set 1:1, carries the
> failure-specific fields, and — for `structured_output_invalid` alone — the success-only response-side
> surface (null for every other §7 category):

Then add five rows to the `LlmFailedEvent` field table (after `error_message`) — five of
`LlmCompletionEvent`'s response-side fields by the same names (all but `output_tool_calls`):

> | `output_content` | string \| null | The assistant's response content verbatim per llm-provider §6 `Response.message.content` — the same field the success variant carries. For a `structured_output_invalid` failure this is the content that failed downstream parse/validation; the §7 error exposes the same bytes as its mandated *raw response content* attribute, and the event mirrors them under the completion-event field name (a deliberate cross-surface naming choice — see Alternatives). Payload-bearing: populated unconditionally on the event, gated observer-side by `disable_provider_payload` per observability §5.5.4, identical to the success variant's `output_content`. Null for every other §7 category (no response received). |
> | `finish_reason` | string \| null | The normalized §6 finish reason of the response that failed validation — for a `structured_output_invalid` failure, one of `"stop"`, `"length"`, or `"content_filter"` (never `"tool_calls"`, which skips schema validation per §6). `"length"` is the canonical cross-provider truncation signal (the model hit `max_tokens`). Same value space as the success variant's `finish_reason`. Not payload-gated. |
> | `usage` | mapping \| null | Token usage of the response that failed validation (`prompt_tokens` / `completion_tokens` / `total_tokens` per §6), enabling cost attribution on failed calls and truncation corroboration (`completion_tokens` at the configured `max_tokens` ceiling). Same shape as the success variant's `usage`. Not payload-gated. |
> | `response_id` | string \| null | The provider's response identifier on the failed-validation response, when present. Same semantics as the success variant. Not payload-gated. |
> | `response_model` | string \| null | The model identifier the provider reported on the failed-validation response, when present. Same semantics as the success variant. Not payload-gated. |

Add a framing paragraph after the table:

> These five fields are the **response-side surface** of the failure variant — `LlmCompletionEvent`'s
> response-side fields by the same names, **less `output_tool_calls`** (a structured-output failure never
> carries tool calls; its `finish_reason` is never `"tool_calls"`, and the structured-content and
> tool-call paths are mutually exclusive). They are populated **only** for
> `structured_output_invalid` — the one §7 category where the provider returned a response (the model
> produced content that failed downstream parse or validation). For that category, `LlmFailedEvent` is, in
> effect, a completion whose final validation gate failed: it carries `output_content` (the verbatim
> content that failed), `finish_reason`, `usage`, `response_id`, and `response_model` exactly as the
> success variant would. The validated value (`Response.parsed`) is not carried, as on the completion
> event. For **every other** §7 category the five fields are null — no response was received.

Add a clarifying sentence (resolving where the failure description lives — no dedicated field):

> For a `structured_output_invalid` failure, `error_message` carries the §7 failure description (the
> validation/parse failure description the error exposes — the wrapped exception's message or failing
> locator). Implementations populate the exception message with that description, so observers read it
> from `error_message` without a dedicated field.

Extend the existing privacy paragraph to name `output_content` (the only payload-bearing addition):

> The privacy posture for `input_messages` / `request_extras` / `output_content` is identical to
> `LlmCompletionEvent`'s — observer-side gating at the rendering boundary per observability §5.5.4. The
> other four response-side fields (`finish_reason`, `usage`, `response_id`, `response_model`) are not
> payload-bearing and are not gated, matching their treatment on the success variant.

The sibling failure variants `EmbeddingFailedEvent` / `RerankFailedEvent` (graph-engine §6, proposals
0059 / 0060) keep their identical *"in place of the success-only response-side fields"* framing unchanged —
they have no structured-output path, so no §7 category gives them a response body. `LlmFailedEvent` becomes
the sole failure variant carrying a response-side surface: an intended asymmetry among the three mirror
paragraphs, not an oversight.

The dispatch, mutual-exclusion, exception-flow, and phase-filter contracts from 0058 are unchanged.

### llm-provider §7 — the `structured_output_invalid` error exposes `finish_reason` and `usage`

Extend the `structured_output_invalid` MUST-list:

> The error MUST expose the requested `response_schema`, the raw response content (the bytes the model
> produced), a description of the validation or parse failure …, **and the response's normalized
> `finish_reason` (§6) and token `usage`** — both available from the received response, since the
> failure is a downstream parse/validation step on an intact wire response, not a transport failure.
> The `finish_reason` lets callers distinguish a truncation (`"length"` — the model hit `max_tokens`)
> from a model that finished (`"stop"`) but emitted invalid or schema-violating content, and choose
> retry policy accordingly: a truncation MAY succeed with a larger token budget, whereas a `"stop"`
> schema failure usually fails the same way on retry. (This makes the §7-level note above — that users
> MAY add `structured_output_invalid` to a `RetryMiddleware` transient set — actionable on a per-failure
> basis, and reconciles §8.2.5's statement that the mapping surfaces the mapped `finish_reason`.)

The **Non-transient by default** classification is **unchanged** — this proposal exposes the signal that
lets a caller refine retry policy; it does not alter the default.

**Why the error exposes only `finish_reason` + `usage`, not the full event surface.** The event gains all
five response-side fields; the §7 error gains only these two. The asymmetry is deliberate:
`response_id` / `response_model` are cross-backend correlation aids an *observer* attaches to a rendered
generation — a caller's exception handler already holds the call context and acts on the *outcome*, for
which `finish_reason` (retry-vs-fail) and `usage` (budget) are the actionable signals. The error surfaces
what a caller's retry logic needs; the event surfaces what an observer's rendering needs.

### observability §5.5.7 — reconcile the "no response was received" framing

The current §5.5.7 paragraph states response-side fields "are absent from the failure variant — no
response was received." Reconcile the final clause:

> … Response-side fields (`response_id`, `response_model`, `usage`, `output_content`, `finish_reason`)
> are absent from the failure variant for the §7 categories where no response was received — **with one
> exception: a `structured_output_invalid` failure carries the response-side surface (`output_content` —
> the verbatim content that failed validation — plus `finish_reason`, `usage`, `response_id`,
> `response_model`), because the provider did return a response (content that failed downstream parse or
> validation). Observers surface what the model actually returned, why it stopped (`finish_reason ==
> "length"` signals truncation), and what it cost — instead of a null, zero-token record.** (`error_message`
> carries the §7 failure description for this category, per graph-engine §6.)

### observability §8.4 + §5.5.1 — render the surface on the failed generation / error span

**Langfuse (§8.4.2 / §8.4.3).** The §8.4.3 Generation-specific rows that map `output_content` →
`generation.output`, `usage.*` → `generation.usage.*`, `finish_reason` → `generation.metadata.finish_reason`,
and `response_id` / `response_model` → `generation.metadata.*` already exist for the success Generation.
Specify that on a `structured_output_invalid` terminal failure the **failed** Generation populates the
same fields from `LlmFailedEvent`'s response-side surface (`generation.output` from `output_content`,
payload-gated per §5.5.4) — in addition to its `level = "ERROR"` + category mapping (§8.4.2), not in
place of it. The failed generation thus shows the raw output, real token usage, and the stop reason,
rather than null / zero. This includes the call-level-retry path: §8.4.3's *"one terminal Generation per
call"* paragraph currently describes the terminal failed Generation (on retry exhaustion) as
`level = "ERROR"` + category only — reconcile it so that when the terminal failure is
`structured_output_invalid`, that Generation also carries `output` / `usage` / `metadata.finish_reason`
from the terminal `LlmFailedEvent`.

**OTel (§5.5.1 / §5.5.3).** The LLM error span carries the same surface on the attributes the success span
already uses — `openarmature.llm.output.content` (from `output_content`, payload-gated, §5.5.1),
`openarmature.llm.finish_reason` and the `openarmature.llm.usage.*` token attributes (§5.5.3), and the
response id / model attributes — for a `structured_output_invalid` failure. Span status remains `ERROR`
with the §4.2 exception event; the attributes are additive. No new attribute names are introduced (the
success-path attributes simply populate on the error span).

### observability §11.2 — a `structured_output_invalid` failure records token usage

§11.2 says the token-usage histogram (`openarmature.gen_ai.client.token.usage`) "records only for an
attempt that returned a usage record; failed attempts have no response and contribute nothing." That held
when no failure carried usage. A `structured_output_invalid` failure now carries a usage record
(graph-engine §6 `LlmFailedEvent.usage`), so it records a token-usage observation like a completion — the
response *was* received and tokens *were* consumed; excluding it is the cost-accounting gap this proposal
closes. Reconcile the sentence:

> … failed attempts that received **no** response contribute nothing; a `structured_output_invalid`
> failure — which carries a usage record — records a token-usage observation like a completion, with the
> same dimensions (§11.3).

The duration histogram and `error.type` dimensioning (§11.3) are unchanged — the failed attempt already
records duration + `error.type`; this adds only the token-usage observation, for the one failure category
that has a usage record. (Token usage is cost, recorded whenever a usage record exists; the failure itself
is captured on the duration histogram's `error.type` dimension.)

## Conformance test impact

### New fixtures

New fixtures **120–125** under `spec/observability/conformance/` (in the order listed below; the 0058
LlmFailedEvent dispatch fixtures 069–073 live here). The structured-output cases drive the **real** failure
path via `mock_llm` (like 069) plus a **`calls_llm.response_schema`** field — new to the observability
suite, documented in each fixture's §3.2 header note — so the implementation runs structured-output
validation and raises `structured_output_invalid` carrying the response-side surface:

1. **`NNN-llm-failure-event-structured-output-truncation`** — **the truncation use case.** Mocked
   provider returns truncated JSON with `finish_reason: "length"` against a `response_schema`. Asserts the
   `LlmFailedEvent` carries `error_category = "structured_output_invalid"`, `finish_reason = "length"`,
   `output_content` = the verbatim truncated bytes, `usage` populated (the mock body's literal token
   counts — §5.10 has no `<non-zero>` matcher, so assert the concrete values), and `response_id` /
   `response_model`. Asserts the exception still raises and no `LlmCompletionEvent` is emitted (0058
   mutual exclusion).

2. **`NNN-llm-failure-event-structured-output-schema-mismatch`** — the contrast case. Valid JSON missing a
   required field, `finish_reason: "stop"`. Asserts `finish_reason = "stop"` alongside the full surface —
   pinning the triage distinction (`length` vs. `stop`) that motivates the proposal.

3. **`NNN-llm-failure-event-response-side-null-on-non-body-failure`** — companion: provider raises
   `provider_unavailable`. Asserts all five response-side fields are null. Locks "populated only for
   `structured_output_invalid`."

4. **`NNN-langfuse-failed-generation-renders-output-usage-finish-reason`** — the truncation failure through
   the bundled Langfuse observer. Asserts the failed Generation is `level = "ERROR"` + category **and**
   `generation.output` = the raw bytes (from `output_content`), `generation.usage` = the token counts,
   `generation.metadata.finish_reason = "length"`. A payload-disabled variant asserts `output` is redacted
   while `usage` / `finish_reason` / error status are unchanged.

5. **`NNN-otel-error-span-renders-output-usage-finish-reason`** — same failure through the bundled OTel
   observer; asserts the error span carries the surface (payload-gated output), `ERROR` status + exception
   event unchanged.

6. **`NNN-metrics-token-usage-recorded-on-structured-output-failure`** — the truncation failure with
   `enable_metrics` set. Asserts a `openarmature.gen_ai.client.token.usage` observation **is** recorded for
   the failed call (it carries a usage record), dimensioned per §11.3, alongside the `operation.duration`
   observation with `error.type`. Pins the reconciled §11.2 rule (a `structured_output_invalid` failure
   records token usage; other failure categories still record none).

### Updated fixtures

llm-provider **022** (parse failure) and **023** (schema validation failure) assert the
`structured_output_invalid` error's exposed surface (the error keeps its `raw_response_content` attribute);
update both to also assert the now-required `finish_reason` (`"stop"` for both as currently bodied) and
`usage` — otherwise they would assert an incomplete required set (per the conformance principle that
fixtures assert every required dimension).

### Unaffected fixtures

Existing LlmFailedEvent fixtures (069–073, and 114 — the mid-stream streaming failure) exercise
non-`structured_output_invalid` categories, for which the five fields are null; they assert the
failure-specific fields they already cover and are unaffected.

## Versioning

**MINOR bump** (pre-1.0). Additive across three capability specs (one whole-spec SemVer increment):

- graph-engine §6 — five response-side fields (the same names the success variant carries) added to the
  `LlmFailedEvent` variant; new to the failure variant, null for all but one category, dispatch /
  mutual-exclusion contracts unchanged.
- llm-provider §7 — the `structured_output_invalid` error exposes two additional attributes
  (`finish_reason`, `usage`); the non-transient-by-default classification is unchanged.
- observability §5.5.7 reconciled; §8.4 / §5.5.1 rendering extended (no new attributes); §11.2 token-usage
  rule reconciled (a `structured_output_invalid` failure — alone among failures — records token usage);
  new + updated fixtures.

No behavior change for any observer or caller that does not read the new fields.

## Alternatives considered

1. **Do nothing.** Observers keep heuristically inspecting raw bytes (or never seeing them, on the event
   stream); retry classifiers cannot tell truncation from a genuine schema failure. Rejected — the
   reported use case (triaging max-tokens truncation) is unserved, and `usage`-less failed generations
   silently drop token/cost accounting.

2. **Carry only the verbatim content** (`output_content`), no `finish_reason` / `usage` (the proposal's
   first draft). Rejected once the truncation case surfaced: the bytes alone force a heuristic "is this
   truncated?" guess, when `finish_reason == "length"` answers it authoritatively, and a `usage`-less
   failed generation still drops out of cost accounting.

3. **Carry a diagnostic trio** (`output_content` + `finish_reason` + `usage`), omitting `response_id` /
   `response_model`. A reasonable lean-scope option, but it draws an arbitrary line through a surface that
   exists in full: a `structured_output_invalid` failure *is* a completion whose validation gate failed,
   so carrying everything the completion event carries is the cleaner, less-arbitrary rule, and the id /
   model fields are already mapped on both backends. Rejected in favor of the full surface.

4. **A category-keyed `failure_detail` sub-record** instead of flat fields. Rejected as premature
   generality — `structured_output_invalid` is the only §7 category with a response body, and the flat
   conditionally-null shape matches how `LlmFailedEvent` already handles context-conditional fields
   (`error_type`, `fan_out_index`, `branch_name` are null outside their context). A sub-record can be
   introduced if a future category arrives with its own structured detail.

5. **A dedicated `StructuredOutputFailedEvent` variant.** Rejected — `LlmFailedEvent` already fires for
   `structured_output_invalid`; a dedicated event would duplicate that dispatch or punch a hole in 0058's
   mutual-exclusion contract, and re-derive the entire identity / scoping / request-side surface for one
   category's extra fields.

6. **Mint a distinct `raw_response_content` field** (and a distinct `openarmature.llm.raw_output.content`
   OTel attribute) to mark the bytes as unvalidated, rather than reusing `output_content`. Rejected:
   `output_content` is the **verbatim** `Response.message.content` (graph-engine §6) — *not* the validated
   value (`Response.parsed`, which the event never carries) — so the failure bytes fit it exactly. The
   failed outcome (event type + `error_category`, OTel `ERROR` status) already marks the content as having
   failed validation, making a distinct name redundant; reusing `output_content` keeps field-name symmetry
   with the completion event, lets the existing Langfuse / OTel output mappings fire unchanged (no new
   rows or attributes), and lets generic observers read one field across both outcomes. The §7 error
   retains its "raw response content" wording — an accepted, deliberate cross-surface naming difference
   (the error is the caller-facing view of the failed bytes; the event is the completion-shaped
   observability surface).

## Open questions

None remaining. The three drafting questions are resolved in the text above:

- **A dedicated `failure_description` field** — not added. `error_message` carries the §7 failure
  description for `structured_output_invalid` (clarified normatively in graph-engine §6 and observability
  §5.5.7); a separate field would only invite two subtly-different strings.
- **Event / span field name** — reuse `output_content` (and the existing `openarmature.llm.output.content`
  attribute + Langfuse output mapping), not a distinct `raw_response_content`. `output_content` is the
  verbatim `Response.message.content`, so the failed bytes fit it; the failed outcome marks them failed.
  See Alternatives §6.
- **`provider_invalid_response` surface** — out of scope (see Out of scope below); §7 mandates no response
  surface for wire-shape malformation.

## Out of scope

- **A response-side surface for `provider_invalid_response`.** Wire-shape malformation has no §7-mandated
  raw/response surface to source from, and its malformed transport is a different artifact from model
  output (`finish_reason` / `usage` may be unextractable from an unparseable response). A future proposal
  could revisit if demand emerges. This proposal stays scoped to the one category the §7 contract backs.
- **The retry classification of `structured_output_invalid`.** Unchanged — non-transient by default. This
  proposal exposes `finish_reason` so a caller / classifier can refine the decision; it does not move the
  category into the transient set or add automatic truncation-retry.
- **Per-prompt token budgets.** A `Prompt`-level output token budget (so truncation becomes a managed,
  configured concern rather than an incidental one) is a prompt-management feature tracked separately; it
  composes with this proposal but is not part of it.
- **Streaming-failure events.** Mid-stream failures (proposal 0062's `LlmTokenEvent` surface) are out of
  scope; this proposal scopes to atomic `provider.complete()` structured-output failures.
- **Embedding / rerank failure variants.** `EmbeddingFailedEvent` / `RerankFailedEvent` have no
  structured-output path and are unaffected.
- **Surfacing `response_schema` on the event.** The schema is request-side and reconstructible from the
  call configuration; the reported gap is the response surface, not the schema. A future proposal could
  add it if demand emerges.
