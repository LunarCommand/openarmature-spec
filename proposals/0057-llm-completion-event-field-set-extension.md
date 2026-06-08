# 0057: LlmCompletionEvent Field-Set Extension

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-07
- **Accepted:** 2026-06-07
- **Targets:** spec/graph-engine/spec.md (§6 — extends the `LlmCompletionEvent` field table from proposal 0049 with eight additive request-side / response-side fields, and renames `request_id` → `response_id` so the field name matches the response-side data it carries); spec/observability/spec.md (§5.5.7 — updates the typed-event framing paragraph to acknowledge that the typed event now mirrors the request-parameter (§5.5.2), payload (§5.5.1), and prompt-identity (§5.5.4 / prompt-management §12) attribute surfaces in addition to the §5.5.3 response-side attributes it covered at v0.41.0); plus new conformance fixtures under `spec/observability/conformance/` covering each of the new fields' population semantics, plus an update to fixture 050 for the `response_id` rename (the only existing 0049 fixture asserting on this field).
- **Related:** 0049 (typed LLM completion event — this proposal extends the field set the original Accepted via the alternative-5 follow-on hook), 0024 (LLM span payload + GenAI semconv — established the §5.5 attribute surface this proposal mirrors in typed-event form on the request side), 0033 (prompt-management active-prompt context binding — the source for the `active_prompt` / `active_prompt_group` fields), 0047 (implicit prefix cache wire stability — `usage.cached_tokens` and `usage.cache_creation_tokens` flow through the existing `usage` field on the typed event unchanged; this proposal does not touch the `usage` field shape)
- **Supersedes:**

## Summary

Extends the `LlmCompletionEvent` typed variant from proposal 0049 with the
request-side and prompt-identity fields observers consuming the §5.5 LLM
provider span attribute surface need from the typed event.
Eight new fields (`input_messages`, `output_content`, `request_params`,
`request_extras`, `active_prompt`, `active_prompt_group`, `call_id`,
`response_model`) land additively; one existing field (`request_id`) is
renamed to `response_id` so the field name matches the response-side data
it carries.

The extension completes the typed event's coverage of the observability
§5.5 LLM provider span attribute surface — at v0.41.0 the typed event
mirrored only the §5.5.3 response-side attributes plus identity / scoping;
this proposal adds the §5.5.1 payload attributes, the §5.5.2 GenAI request
parameters, the prompt-identity attribute family (per prompt-management
§12 / observability §8.4.4), and the missing `gen_ai.response.model`
attribute. With the extension landed, observers consuming the typed event
have the same data surface as observers reading the OTel span — the
remaining sentinel-namespaced `NodeEvent` emission becomes redundant for
LLM-call observability, and impl-level sentinel deprecation can proceed
on schedule without observer-side regressions.

## Motivation

Proposal 0049 carved LLM completions into the first spec-normatively-typed
event variant on the observer event union. Its alternative 5 deliberately
scoped the v1 field set to outcome-side data (provider response, usage,
finish_reason) plus identity / scoping, with the framing:

> Request-side fields can be added in a follow-on if observer demand
> surfaces.

**Observer demand has surfaced.** OTel and Langfuse observers
(observability §5.5 and §8 respectively) source attributes from the
sentinel-namespaced NodeEvent payload across the §5.5 LLM provider span
attribute surface and the prompt-identity attribute family (per
prompt-management §12 / observability §8.4.4) that have no equivalent
on the typed event today:

- Three §5.5.1 payload attributes (`input.messages`, `output.content`,
  `request.extras`)
- Seven §5.5.2 GenAI request parameters (`temperature`, `max_tokens`,
  `top_p`, `seed`, `frequency_penalty`, `presence_penalty`,
  `stop_sequences`)
- Five prompt-identity attributes (`prompt.name`, `prompt.version`,
  `prompt.label`, `prompt.template_hash`, `prompt.rendered_hash`) + the
  prompt-group attribute (`prompt.group_name`)
- The response-side `gen_ai.response.model` attribute (distinct from
  `gen_ai.request.model`; surfaces when the provider returns a more
  specific identifier than requested)

Without these fields on the typed event, observers migrating off the
sentinel-namespace filtering pattern at the v0.15.0 deprecation cutoff
lose the span attribute surface they emit today. The §5.5.7 transition
window's purpose — letting backends move to type-discrimination filtering
without behavior regressions — is defeated if the typed event doesn't
carry the data the backends render.

**Why the v1 fallback paths don't solve this.** Proposal 0049 alternative
5 named two fallback paths for observers needing request-side data:

- **`Response.raw`** is the parsed provider *response* body per
  llm-provider §6 (verbatim wire response for original-bytes inspection:
  tool-call argument repair, vendor error codes). It does not carry
  request shape. The prompt-identity surface is sourced from
  prompt-context binding at LLM-call time, not from the wire response at
  all.
- **"The existing `NodeEvent`'s payload"** is the sentinel pattern itself
  — the very pattern observers are migrating off of. Continuing to read
  it through the dual-emit transition window works only until the
  sentinel emission is removed.

The alternative-5 framing was correct to anticipate the follow-on; this
proposal lands it.

**Why the `request_id` rename.** Proposal 0049's field table named one
field `request_id` while sourcing it from `gen_ai.response.id` (the
provider-returned response identifier). The naming mismatch is a
forever-confusing reader hazard. This proposal renames the field to
`response_id` so the typed event's response-side surface coheres
internally: `response_id`, `response_model`, `usage`, `finish_reason`
all named after the data they carry. The rename rides on this proposal
because the field table is already being edited for the additive
fields; deferring it would leave the inconsistency in the spec text
across additional proposal cycles, each of which would add consumers
that would then have to migrate.

## Proposed change

### graph-engine §6 — extend the `LlmCompletionEvent` field table

§6 today carries the `LlmCompletionEvent` field table introduced by
proposal 0049 (the *LLM completion event* paragraph and its embedded
table). Replace that table with the following extended version. The
changes are:

- **One renamed field**: `request_id` → `response_id`. Type, source, and
  nullability unchanged; only the field name changes. The description
  updates to remove the now-anomalous "request_id" naming reference.
- **Eight new fields**. `response_model` is interleaved between `model`
  and `response_id` so the response-side cluster reads coherently
  (`model` / `response_model` / `response_id`); the remaining seven —
  `input_messages`, `output_content`, `request_params`,
  `request_extras`, `active_prompt`, `active_prompt_group`, `call_id`
  — are appended after the v0.41.0 field set.

Below: the full replacement table. Rows from the v0.41.0 field table are
preserved verbatim except for the `request_id` → `response_id` rename;
the description column on the renamed row drops the old field name
mention. Eight new rows follow.

> **LLM completion event.** A typed event variant on the observer event
> union signaling completion of an LLM provider call. Carries the call's
> identity / scoping / outcome data as typed fields:
>
> | Field | Type | Description |
> |---|---|---|
> | `invocation_id` | string | The outer invocation's identifier, per §5.1 of observability. |
> | `correlation_id` | string \| null | Cross-backend correlation ID, per §3.1 of observability. |
> | `node_name` | string | The user-defined node that issued the call. |
> | `namespace` | tuple of strings | The calling node's namespace (NOT the sentinel namespace). |
> | `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
> | `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance, per graph-engine §6 / pipeline-utilities §9. Null otherwise. Part of the §6 event-source identity tuple; required for disambiguating sibling fan-out instances. |
> | `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch, per graph-engine §6 / pipeline-utilities §11 (with the resolved `branch_names` per proposal 0044 governing the value space). Null otherwise. Part of the §6 event-source identity tuple; required for disambiguating sibling parallel branches. |
> | `provider` | string | The LLM provider identifier (matches `gen_ai.system` per observability §5.5.3). |
> | `model` | string | The model identifier the request was made against (matches `gen_ai.request.model` / `openarmature.llm.model` per observability §5.5 / §5.5.3). The provider-returned model identifier — which MAY be more specific — is carried separately on `response_model` below. |
> | `response_model` | string \| null | The model identifier the provider returned in the response (matches `gen_ai.response.model` per observability §5.5.3). Distinct from `model` because providers MAY return a more specific identifier than the one requested (e.g., requested `gpt-4o`, response carries `gpt-4o-2024-08-06`). Null when the provider does not return a response model. |
> | `response_id` | string \| null | The provider-returned response identifier, when present (matches `gen_ai.response.id` per observability §5.5.3). |
> | `usage` | record \| null | Token usage record per llm-provider §6 `Response.usage` shape (including the prefix-cache fields `cached_tokens` and `cache_creation_tokens` from proposal 0047 when populated). May be null when the provider does not report usage. |
> | `latency_ms` | float \| null | Wall-clock latency of the LLM call measured at the adapter boundary, in milliseconds. May be null when latency is not measured. Implementations MAY use a provider-reported latency value when the provider surfaces one, documenting which source is in use. |
> | `finish_reason` | string \| null | The LLM call's finish reason per llm-provider §6 `Response.finish_reason`. May be null when the call did not complete normally. |
> | `caller_invocation_metadata` | mapping \| null | OPTIONAL field — a snapshot of the caller-supplied invocation metadata (per §3.4 of observability) at the time of the LLM call, populated only when the observer is configured to include it (per-language opt-in mechanism). Default absent / null; off by default to avoid bloating every event with potentially-large metadata. Consumers wanting a fresh metadata view rather than a snapshot use the `get_invocation_metadata()` read API per proposal 0048. |
> | `input_messages` | list of message records | The §3 message list the call was made with, in the typed-event-native form of the spec's message shape (NOT the JSON-encoded string form §5.5.1 emits on the OTel span). Each record carries `{role, content, tool_calls?, tool_call_id?}` per llm-provider §3, including content-block sequences for multimodal messages. Inline image bytes follow the §5.5.5 redaction rule (replaced with the redacted placeholder per §5.5.5) before population. Populated by the implementation on every typed event; the empty-history case is represented as an empty list, not null. Observer-side privacy gating applies at the rendering boundary per *Privacy and observer-side gating* below. |
> | `output_content` | string \| null | The assistant's response content verbatim per llm-provider §6 `Response.message.content`. Null when the response was a tool-call-only assistant message with empty content (the structured-response and tool-call paths are mutually exclusive at the response level, matching the §5.5.1 framing for `openarmature.llm.output.content`). Same privacy-gating posture as `input_messages`. |
> | `request_params` | mapping | The §5.5.2 GenAI request-parameter family — `temperature`, `max_tokens`, `top_p`, `seed`, `frequency_penalty`, `presence_penalty`, `stop_sequences`. Keys are the GenAI semconv attribute names without the `gen_ai.request.` prefix (e.g., `temperature`, not `gen_ai.request.temperature`). Values are the per-parameter types §5.5.2 specifies (double for `temperature` / `top_p` / `frequency_penalty` / `presence_penalty`, int for `max_tokens` / `seed`, list-of-string for `stop_sequences`). **Absence is meaningful**: the mapping carries only parameters the caller actually supplied — a parameter not in the mapping means "not supplied on this call," distinct from "supplied with a zero value." Mapping-shape rather than flat fields to keep the typed event compact when most parameters are unset. Empty mapping when no §5.5.2 parameters were supplied. |
> | `request_extras` | mapping | The `RuntimeConfig` extras pass-through bag per llm-provider §6 — vendor-specific sampling parameters callers supplied as un-declared fields (vLLM `guided_decoding`, OpenAI `service_tier`, etc.). Values are opaque to the spec; the bag carries whatever the caller supplied, in the typed-event-native mapping form rather than the JSON-encoded string form §5.5.1 emits on the OTel span. Same privacy-gating posture as `input_messages`. Empty mapping when no extras were supplied. |
> | `active_prompt` | record \| null | A snapshot of the active `Prompt` identity at LLM-call time, sourced from the implementation's prompt-context binding mechanism (per prompt-management §12 / observability §8.4.4 — the mechanism that drives the `openarmature.prompt.*` span attributes; specific mechanism per-language idiomatic). Fields: `{name, version, label, template_hash, rendered_hash}` matching the §8.4.4 prompt-identity attribute family one-for-one. Null when the LLM call ran outside any prompt-context binding (no `openarmature.prompt.*` attributes would have been emitted on the span). |
> | `active_prompt_group` | record \| null | A snapshot of the active `PromptGroup` identity at LLM-call time, sourced from the same prompt-context binding mechanism. Fields: `{group_name}` matching the §8.4.4 / prompt-management §12 prompt-group attribute family. Null when no group was active. |
> | `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); implementations MUST mint a fresh identifier per `provider.complete()` call. The value MUST be stable for the call's lifetime and unique within the implementation's run. Wire shape unconstrained — UUID, ULID, monotonic counter, any stable string format works. Use cases: cross-language trace correlation, observer-side per-call buffering, log-line correlation with the impl-side trace exporter. Distinct from `response_id` (which is the provider-returned identifier and MAY be absent or duplicated across providers); `call_id` is the implementation's own correlation token. |
>
> The event MUST be dispatched on the observer delivery queue at the
> point of LLM call completion (after the adapter receives a
> successful response and before the call returns to the caller).
> Delivery semantics follow §6 — strictly serial across the
> invocation, async-delivered concurrently with graph execution,
> not blocking the engine's execution loop.
>
> The event is dispatched ONLY for LLM call completions that
> produce a structured response per llm-provider §5. Failure cases
> (provider exceptions, malformed responses) do NOT emit this event
> variant; a future `LlmCallFailedEvent` typed variant MAY be added
> if demand emerges (see *Out of scope*). The existing llm-provider
> §7 error categories — `provider_invalid_response` (malformed
> wire shape), `provider_unavailable` (transient unreachability),
> `provider_authentication`, etc. — cover failure surfaces today
> through the exception path, not the observer event surface.
>
> **Phase subscription filter.** Like the metadata-augmentation
> event mechanism from proposal 0040, `LlmCompletionEvent` is a
> typed event variant without a `phase` discriminator and is NOT
> subject to the §6 `phases` subscription filter. Observers with
> a `phases={"started"}` or `phases={"completed"}` subscription
> still receive `LlmCompletionEvent`; the phases filter applies
> only to phase-bearing `NodeEvent` variants. Observers that want
> to selectively consume the typed event filter via type
> discrimination (`isinstance` or per-language equivalent) rather
> than via phase subscription.
>
> **Privacy and observer-side gating.** The `input_messages`,
> `output_content`, and `request_extras` fields carry potentially
> sensitive payload data. Implementations MUST populate these fields
> on the typed event by default; observer-side privacy gating applies
> at the rendering boundary, matching the observability §5.5.4
> `disable_llm_payload` / `disable_state_payload` opt-out flag
> semantics for the equivalent §5.5.1 span attributes. The OTel and
> Langfuse observers honor their existing `disable_llm_payload` flag
> on the typed-event rendering path identically to the §5.5.1 span
> attribute path.
>
> Custom queryable observers (per observability §9) consuming the
> typed event are responsible for their own redaction posture — the
> §5.5.4 `disable_llm_payload` flag gates OTel + Langfuse rendering;
> the typed-event field surface is uniform across observer types.
> Accumulator authors with payload-redaction requirements MUST gate
> at their own rendering / persistence boundary. The structured event
> surface is uniform; gating belongs at the rendering boundary, with
> the consumer's awareness.
>
> Inline image bytes in `input_messages` MUST be redacted per the
> §5.5.5 inline-image redaction rule before the field is populated,
> identically to how §5.5.1's `openarmature.llm.input.messages`
> attribute treats inline images. The hard-rule prohibition on
> emitting inline image bytes (§5.5.5) applies to the typed event
> field identically.

### observability §5.5.7 — update the typed-event framing paragraph

§5.5.7 today says:

> The typed event carries the same identity / scoping / outcome data
> the §5.5 span attribute surface exposes — `gen_ai.system`,
> `gen_ai.request.model`, `gen_ai.response.id`, `gen_ai.usage.*`,
> `gen_ai.response.finish_reasons`, plus the OA-namespaced attributes
> (`openarmature.invocation_id`, `openarmature.node.name`, etc.) — in
> a structured form rather than as separate span attributes.

Replace with:

> The typed event carries the same identity / scoping / outcome data
> the §5.5 span attribute surface exposes — the §5.5.3 GenAI semconv
> response attributes (`gen_ai.system`, `gen_ai.request.model`,
> `gen_ai.response.model`, `gen_ai.response.id`, `gen_ai.usage.*`,
> `gen_ai.response.finish_reasons`), the §5.5.1 payload attributes
> (`openarmature.llm.input.messages`, `openarmature.llm.output.content`,
> `openarmature.llm.request.extras`), the §5.5.2 GenAI request-parameter
> family (`gen_ai.request.temperature`, `gen_ai.request.max_tokens`,
> etc.), the §5.5.4 / prompt-management §12 prompt-identity attribute
> family (`openarmature.prompt.name`, `.version`, `.label`,
> `.template_hash`, `.rendered_hash`, `.group_name`), plus the OA-
> namespaced cross-cutting attributes (`openarmature.invocation_id`,
> `openarmature.node.name`, etc.) — in a structured form rather than
> as separate span attributes.
>
> The §5.5.4 `disable_llm_payload` opt-out flag continues to gate
> rendering of payload-bearing data (`openarmature.llm.input.messages`,
> `openarmature.llm.output.content`, `openarmature.llm.request.extras`)
> at the OTel observer's rendering boundary. The equivalent typed-event
> fields (`input_messages`, `output_content`, `request_extras`) are
> populated by the implementation unconditionally; observers respect
> their own `disable_llm_payload` flag on the typed-event rendering
> path identically to the span attribute path.

The rest of §5.5.7 (the *Backwards compatibility with the sentinel-
namespace convention* paragraph + the *Backends SHOULD subscribe to one
event variant* paragraph) is unchanged.

## Conformance test impact

### Updated fixtures (rename)

Fixtures 050-056 under `spec/observability/conformance/` assert
`LlmCompletionEvent` fields including `request_id`. The rename swaps
every assertion from `request_id: <value>` to `response_id: <value>`;
no semantic change, no fixture restructuring. The `.md` companion docs
for the affected fixtures get a one-line edit noting the field rename
per proposal 0057. Affected fixtures: 050, 051, 052, 053, 054, 055,
056 (the seven fixtures from 0049's conformance impact section that
assert against the field set).

### New fixtures (additive fields)

Nine new fixtures, one per new field plus one combined-population case:

1. **`06X-llm-completion-event-input-messages-populated`** — a graph
   with one LLM-calling node; mocked provider receives a 2-message
   conversation; the typed event's `input_messages` carries the
   spec-canonical message-list shape per llm-provider §3 (per-message
   `{role, content, tool_calls?, tool_call_id?}` records).
2. **`06X-llm-completion-event-output-content-populated`** — assistant
   response with `content="..."`; assert `output_content` populated
   verbatim. Companion case where the assistant returns `tool_calls`
   with empty content; assert `output_content == null`.
3. **`06X-llm-completion-event-request-params-populated`** — call
   passes `RuntimeConfig(temperature=0.7, max_tokens=512)`; assert
   `request_params == {"temperature": 0.7, "max_tokens": 512}` (the
   other §5.5.2 parameters absent from the mapping per the
   absence-is-meaningful rule).
4. **`06X-llm-completion-event-request-extras-populated`** — call
   passes `RuntimeConfig(extras={"vllm.guided_decoding": {...}})`;
   assert `request_extras` carries the extras mapping as a native
   object (not a JSON-encoded string).
5. **`06X-llm-completion-event-active-prompt-populated`** — LLM call
   inside a prompt-context binding; assert `active_prompt` carries the
   5-field identity record matching the prompt's `name`, `version`,
   `label`, `template_hash`, `rendered_hash`.
6. **`06X-llm-completion-event-active-prompt-null`** — LLM call outside
   any prompt-context binding; assert `active_prompt == null` (parallel
   to the §8.4.4 `openarmature.prompt.*` attributes being absent on the
   span in this case).
7. **`06X-llm-completion-event-active-prompt-group-populated`** — LLM
   call inside a `PromptGroup` context; assert `active_prompt_group ==
   {group_name: "..."}`.
8. **`06X-llm-completion-event-call-id-always-present-and-distinct`** —
   sequence of 3 LLM calls in a graph; assert each
   `LlmCompletionEvent.call_id` is non-null AND the three values are
   distinct (locks down the per-call freshness contract).
9. **`06X-llm-completion-event-response-model-distinct-from-request`**
   — mocked provider returns `model: "gpt-4o-2024-08-06"` for a request
   against `model: "gpt-4o"`; assert `response_model ==
   "gpt-4o-2024-08-06"` while `model == "gpt-4o"`. Plus a companion
   case where the provider does not return a response model; assert
   `response_model == null`.

Final fixture numbers assigned at acceptance; the rough block is 060-068.
Each fixture follows the existing 050-056 pattern (YAML directive +
`.md` companion).

### Unaffected fixtures

All other observability fixtures (001-049) continue to pass unchanged.
The typed event's existing field set is preserved (the `request_id` →
`response_id` rename is the only existing-field change); the new fields
are additive on the typed-event shape. Fixtures asserting other event
types or other span attributes are unaffected.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- Eight new fields on the `LlmCompletionEvent` typed event (additive —
  existing field set preserved).
- One field rename: `request_id` → `response_id`. Per the pre-1.0
  SemVer convention documented in `CHANGELOG.md`, MINOR bumps MAY
  include breaking changes. The CHANGELOG entry calls out the rename
  in the **Changed** section so any consumer pinning against
  `request_id` has lead-time awareness.
- §5.5.7 framing-paragraph update (informative-clarifying alongside the
  field-set extension).
- Nine new conformance fixtures plus seven updated fixtures (050-056).

The change is additive at the typed-event field set level; the rename
is a breaking change on the field-name surface that this proposal
deliberately makes pre-1.0 to preserve internal naming coherence for
the response-side surface.

## Alternatives considered

1. **Hoist the seven §5.5.2 request parameters as flat top-level
   fields rather than bundling into a `request_params` mapping.**
   Define seven typed fields (`temperature: float | null`,
   `max_tokens: int | null`, etc.) on the event directly. Rejected:
   bloats the typed event with seven nullable fields the caller MAY
   never supply; the mapping shape matches the §5.5.2 attribute family
   more naturally (each request parameter is independently optional;
   the cross-vendor pattern is "supply a subset," not "supply all").
   The flat-field shape also leaks vendor-specific parameter additions
   into the typed event surface every cycle — `gen_ai.request.tool_choice`
   per future proposals would have to grow a new typed field; the
   mapping accommodates new parameters without spec edits.

2. **Sink at construction rather than at observer rendering.**
   Provider populates `input_messages` / `output_content` /
   `request_extras` only when no observer in the active subscription
   set has `disable_llm_payload` set; other observers see the fields
   as null. Rejected: requires provider-side introspection of the
   active observer set, complicating the provider/observer boundary.
   Doesn't match how §5.5.1 + §5.5.4 work today — the span attributes
   are emitted unconditionally and each OTel observer gates at its own
   rendering boundary. Sink at observer rendering (the design adopted
   in *Proposed change* above) is the analog that preserves the
   symmetric pattern.

3. **Introduce a new event class
   (`LlmCompletionEventWithRequestSide`) rather than extending the
   existing `LlmCompletionEvent`.** Rejected: fragments the type
   discriminator surface for no behavioral gain. Proposal 0049's
   class-name rule explicitly anticipates field-set extension on the
   existing class — "the class name is spec-normative as an identifier
   ... provided the field set + dispatch contract are preserved." The
   field set extends; the dispatch contract is unchanged; the class
   identity is preserved. A new event class would force every typed-
   event consumer to update their discriminator filter for no
   behavioral upside.

4. **Defer the `request_id` → `response_id` rename to a separate
   follow-on proposal.** Land the eight additive fields now; do the
   rename later when no other field-table edits are pending.
   Rejected: this proposal is already editing the same field table
   for the additive fields and for `response_model`; a coordinated
   edit is cheaper than two sequential edits to the same table.
   Leaving the naming inconsistency to be addressed in a later cycle
   would mean every spec consumer reading the v0.51.0 field table
   encounters the inconsistency unaddressed.

5. **Defer `response_model` to a separate follow-on.** Land the seven
   request-side fields now; add `response_model` later when an
   observer demand specifically surfaces for it. Rejected: the demand
   IS the existing observer-migration case — observers reading
   `gen_ai.response.model` from the OTel span surface today need the
   typed-event equivalent during the same migration. Bundling avoids
   a second follow-on cycle for a single one-field addition that
   completes the §5.5.3 response-attribute coverage on the typed event.

6. **SHOULD-emit-both alias during the `request_id` → `response_id`
   rename transition.** Mirror proposal 0049's sentinel-NodeEvent
   transition pattern by having implementations emit both
   `request_id` and `response_id` carrying the same value during a
   transition window, with `request_id` deprecated in a follow-on
   cycle. Rejected: 0049's SHOULD-emit-both transition addressed a
   backwards-compat concern for a broadly-consumed pattern
   (sentinel-namespace string matching across many backends, accreted
   over the pre-0049 spec history). The `request_id` field was
   introduced at v0.41.0 as part of the same typed-event variant the
   rename also touches; the consumer surface a SHOULD-emit-both alias
   would protect did not exist before v0.41.0 and has no
   broadly-accreted consumer code to migrate. The alias pattern's
   cost — every implementation MUST emit both fields; every observer
   MUST understand the transition window — is disproportionate to the
   migration burden a hard swap actually imposes. CHANGELOG-entry
   operator-awareness is the proportional path.

## Open questions

None at draft time. All design choices are settled in the proposal text
above:

- **Field-set scope** — eight new fields covering the §5.5.1 payload
  attributes, the §5.5.2 GenAI request-parameter family, the §5.5.4 /
  prompt-management §12 prompt-identity attribute family, plus
  `response_model` (completing §5.5.3 coverage) and `call_id` (the
  per-call disambiguator). Outcome-side and identity / scoping fields
  from 0049's v1 set preserved unchanged.
- **Privacy framing** — sink at observer rendering (option b from the
  coord-thread direction). Symmetric with §5.5.1 + §5.5.4. Explicit
  callout to queryable-observer consumers that they're responsible for
  their own redaction posture.
- **Class name** — extends existing `LlmCompletionEvent` per the class-
  name rule from proposal 0049.
- **`request_id` → `response_id` rename** — bundled into this proposal
  (hard swap, no SHOULD-emit-both alias) per alternative 6.
- **`response_model` inclusion** — bundled into this proposal per
  alternative 5.
- **`call_id` wire shape** — spec-neutral on format (UUID, ULID,
  monotonic counter all fine); spec mandates "stable, unique within
  impl run, freshly minted per `complete()` call."
- **`request_params` shape** — mapping with absence-is-meaningful
  semantics per alternative 1.

If reviewers surface a substantive question during PR review, it gets
resolved into the proposal text rather than left here as a defer.

## Out of scope

- **`LlmCallFailedEvent` typed variant** (alternative 3 from proposal
  0049). Failure events have different field shapes and use cases;
  remain scoped to a separate follow-on if demand emerges. Today's
  failure surface flows through the exception path per llm-provider §7.
- **`LlmStreamChunkEvent` typed variant** ([[discuss-llm-token-streaming]]
  is the active design thread for the per-chunk streaming variant).
  This proposal's completion-event field-set extension does not
  pre-empt or constrain the streaming event variant's design.
- **`raw_request` / `raw_response` vendor-body fields.** The typed
  event scopes to the abstracted shapes (`Message`, `Tool`,
  `RuntimeConfig`). Vendor-specific wire bodies remain accessible via
  `Response.raw` on the response side; adding wire-body fields to the
  typed event would couple it to per-vendor serialization details.
  Out of scope for v1; if a use case surfaces (e.g., a backend
  rendering the literal HTTP request body for debugging), a follow-on
  proposal can scope it.
- **Cross-impl byte-identical typed-event serialization.** Same caveat
  as 0049 — event objects are language-native; cross-language byte
  equality is out of scope (matches the observability §5.5.1 cross-impl
  byte-stability caveat that applies identically to the typed event's
  field values).
- **Event payload truncation contract for the typed-event field
  values.** Unlike §5.5.1 attribute values (subject to §5.5.5
  truncation), the typed event's field values flow through observer
  code unchanged. Observers SHOULD apply backend-specific truncation
  if rendering the event to a byte-bounded backend. The inline-image
  redaction rule from §5.5.5 applies (a hard rule, not a configurable
  cap), but the per-attribute byte cap does NOT — that's a span-
  attribute concern, not a typed-event-field concern.
- **A typed-event field for `gen_ai.usage.cache_*.input_tokens`
  attributes.** These already flow through the existing `usage` field
  on the typed event (per llm-provider §6 `Response.usage.cached_tokens`
  / `cache_creation_tokens` from proposal 0047). The typed event's
  `usage` record carries the full `Response.usage` shape unchanged; no
  separate fields needed.
