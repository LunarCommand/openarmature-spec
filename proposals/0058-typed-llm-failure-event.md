# 0058: Typed LLM Failure Event

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-08
- **Accepted:**
- **Targets:** spec/graph-engine/spec.md (§6 — adds `LlmFailedEvent` as a second spec-normatively-typed event variant on the observer event union, alongside `LlmCompletionEvent` from proposal 0049 and `NodeEvent`); spec/observability/spec.md (§5.5.7 — extends the typed-event framing paragraph to acknowledge the failure-path event variant; existing success-only framing for `LlmCompletionEvent` preserved); plus new conformance fixtures under `spec/observability/conformance/` covering the failure event's dispatch contract + field-set population from llm-provider §7 errors.
- **Related:** 0049 (typed LLM completion event — anticipated this follow-on by name in *Out of scope*: *"`LlmCallFailedEvent` typed variant... warrants a follow-on proposal if demand emerges"*; this proposal lands that follow-on), 0057 (LlmCompletionEvent field-set extension — the request-side / prompt-identity / per-call disambiguator fields this proposal mirrors onto the failure variant)
- **Supersedes:**

## Summary

Carves LLM provider failures into a second spec-normatively-typed event variant on the
observer event union: `LlmFailedEvent`. Mirrors `LlmCompletionEvent`'s identity / scoping /
request-side field set 1:1, plus three failure-specific fields (`error_category`,
`error_type`, `error_message`) sourced from the llm-provider §7 error categories the
provider raises through the exception path.

The proposal does not change the provider's exception-flow contract — failures STILL raise
the original §7 category exception out of `provider.complete()` per proposal 0049's
alternative-3 framing. The typed event is dispatched on the observer delivery queue
alongside the exception, giving observers a type-discriminated surface for both outcome
sides of an LLM call. With both `LlmCompletionEvent` and `LlmFailedEvent` defined,
observers consuming the typed events have full type-discriminated coverage of LLM call
observability; impl-level sentinel-namespace `NodeEvent` emission for LLM completions can
retire fully (success and failure paths both have typed equivalents).

## Motivation

Proposal 0049 carved LLM completions into the first typed event variant on the observer
event union — `LlmCompletionEvent` — but scoped it to successful completions per the
alternative-3 framing:

> The event is dispatched ONLY for LLM call completions that produce a structured response
> per llm-provider §6. Failure cases (provider exceptions, malformed responses) do NOT emit
> this event variant; a future `LlmCallFailedEvent` typed variant MAY be added if demand
> emerges.

**Failure-event demand has surfaced.** With `LlmCompletionEvent` defined for the success
path (and the field set extended at v0.51.0 per proposal 0057 to mirror the full §5.5
attribute surface), the failure path is the remaining surface that an observer consuming
typed events has no type-discriminated access to. Observers wanting to render an
error-status span / ERROR-level Langfuse Generation / etc. on LLM failures today still
need to filter via the sentinel-namespace `NodeEvent` shape — defeating the
type-discrimination contract for the failure half of LLM observability.

Three forces converge:

**Type-discrimination contract completeness.** Observers consuming `LlmCompletionEvent`
via `isinstance(event, LlmCompletionEvent)` (or per-language idiomatic equivalent) get the
success path. The failure path requires a separate sentinel-namespace string match against
`NodeEvent.node_name` — defeating the very brittleness 0049 set out to remove. A typed
failure variant lets observers use the same discrimination pattern on both outcome sides.

**Sentinel-pattern retirement on the impl side.** Implementations that historically emitted
a sentinel-namespaced `NodeEvent` for LLM completions are running a transition window per
observability §5.5.7's SHOULD-emit-both rule. The §5.5.7 SHOULD-emit-both transition
window's purpose is met on the success side via `LlmCompletionEvent`; the failure side
keeps the sentinel emission load-bearing for observability. A typed failure variant lets
the sentinel emission retire fully on both outcome sides.

**Setting precedent.** Future typed event variants — a planned LLM token streaming
proposal's chunk events, structured-output validation failure events if demand emerges,
etc. — all face the same "discriminated-union variant vs extend an existing variant"
question. Establishing the discriminated-union precedent for the LLM success/failure
split keeps the event taxonomy clean across the typed-event surface.

## Proposed change

### graph-engine §6 — add `LlmFailedEvent` typed event variant

§6 today carries the `LlmCompletionEvent` typed variant from proposal 0049 (field-set
extended at v0.51.0 per proposal 0057). Add a second spec-normatively-typed variant on
the observer event union: `LlmFailedEvent`, dispatched on the observer delivery queue when
a `provider.complete()` call raises one of the llm-provider §7 error categories.

The class name `LlmFailedEvent` is spec-normative as an identifier; implementations MAY
use a per-language idiomatic name (e.g., adjusted casing or symbol conventions per the
language's naming idioms) provided the field set + dispatch contract are preserved.
Discriminator-on-type is the load-bearing piece — observers filter via
`isinstance(event, LlmFailedEvent)` (or per-language equivalent) rather than via the
sentinel-namespace string match.

> **LLM failure event.** A typed event variant on the observer event union signaling that
> an LLM provider call raised one of the llm-provider §7 error categories. Mirrors
> `LlmCompletionEvent`'s identity / scoping / request-side field set 1:1; carries
> failure-specific fields in place of the success-only response-side fields:
>
> | Field | Type | Description |
> |---|---|---|
> | `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
> | `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
> | `node_name` | string | The user-defined node that issued the call. |
> | `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
> | `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
> | `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. Part of the event-source identity tuple; required for disambiguating sibling fan-out instances. |
> | `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11, with the resolved `branch_names` per proposal 0044 governing the value space). Null otherwise. Part of the event-source identity tuple; required for disambiguating sibling parallel branches. |
> | `provider` | string | The LLM provider identifier (matches `gen_ai.system` per observability §5.5.3). |
> | `model` | string | The model identifier the request was made against (matches `gen_ai.request.model` / `openarmature.llm.model` per observability §5.5 / §5.5.3). |
> | `latency_ms` | float \| null | Wall-clock latency from `provider.complete()` entry to the point the failure was raised, in milliseconds. May be null when latency is not measured. Implementations measure at the adapter boundary; per-attempt under call-level retry. |
> | `caller_invocation_metadata` | mapping \| null | OPTIONAL field — a snapshot of the caller-supplied invocation metadata (per observability §3.4) at the time of the LLM call, populated only when the observer is configured to include it (per-language opt-in mechanism). Default absent / null; off by default to avoid bloating every event with potentially-large metadata. Same opt-in mechanism as on `LlmCompletionEvent`. |
> | `input_messages` | list of message records | The §3 message list of llm-provider that the call was made with, in the typed-event-native form. Populated unconditionally on every typed event; the empty-history case is represented as an empty list, not null. Inline image bytes follow the observability §5.5.5 redaction rule before population. Observer-side privacy gating applies at the rendering boundary per `LlmCompletionEvent`'s *Privacy and observer-side gating* paragraph (the same posture applies to this variant). |
> | `request_params` | mapping | The observability §5.5.2 GenAI request-parameter family. Keys are the GenAI semconv attribute names without the `gen_ai.request.` prefix. Absence-is-meaningful semantics per the equivalent field on `LlmCompletionEvent`. Empty mapping when no observability §5.5.2 parameters were supplied. |
> | `request_extras` | mapping | The `RuntimeConfig` extras pass-through bag per llm-provider §6. Same shape and privacy posture as on `LlmCompletionEvent`. Empty mapping when no extras were supplied. |
> | `active_prompt` | record \| null | A snapshot of the active `Prompt` identity at LLM-call time, sourced from the implementation's prompt-context binding mechanism. Same fields and nullability as on `LlmCompletionEvent`. |
> | `active_prompt_group` | record \| null | A snapshot of the active `PromptGroup` identity at LLM-call time. Same fields and nullability as on `LlmCompletionEvent`. |
> | `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); freshly minted per `provider.complete()` call. Same contract as on `LlmCompletionEvent` — a failed call gets its own `call_id`, distinct from any retry-attempt sibling. |
> | `error_category` | string | The llm-provider §7 normative error category the provider call raised. One of `provider_authentication`, `provider_unavailable`, `provider_invalid_model`, `provider_model_not_loaded`, `provider_rate_limit`, `provider_invalid_response`, `provider_invalid_request`, `provider_unsupported_content_block`, `structured_output_invalid` (per the §7 enumeration; new categories added by future llm-provider proposals extend the enum naturally). Always present. |
> | `error_type` | string \| null | OPTIONAL impl-level / vendor-specific error type or code (e.g., the upstream exception class name, or a vendor error code like OpenAI's `rate_limit_exceeded` before normalization to `provider_rate_limit`). Provides per-error-source detail beyond the normative category; useful for vendor-specific filtering on observability backends. Null when no impl-side type is available. |
> | `error_message` | string | The human-readable error message from the raised exception. Always present (the empty string when the exception carried no message). |
>
> The event MUST be dispatched on the observer delivery queue at the point of LLM call
> failure (after the adapter catches the provider exception and before the call re-raises
> to the caller). Delivery semantics follow the *Event delivery* rules above —
> strict-serial across the invocation, async-delivered concurrently with graph execution,
> not blocking the engine's execution loop.
>
> The event is dispatched ONLY for LLM call failures that raise one of the llm-provider §7
> error categories above. Successful completions emit `LlmCompletionEvent` per proposal
> 0049's contract; the two variants are mutually exclusive on a given `provider.complete()`
> call. Both variants share the same `call_id` slot — implementations MUST NOT emit both
> `LlmCompletionEvent` and `LlmFailedEvent` for the same call.
>
> **Provider exception-flow contract preserved.** The §7 error category exception still
> raises out of `provider.complete()` per llm-provider §7; the typed event is dispatched
> alongside the exception, not in place of it. Callers handling exceptions see the
> exception path unchanged; observers consuming typed events see the failure event on the
> observer delivery queue. The two surfaces compose without conflict.
>
> Like the other typed event variants, `LlmFailedEvent` carries no `phase` discriminator
> and is NOT subject to the §6 `phases` subscription filter. Observers filter via type
> discrimination (`isinstance` or per-language idiomatic equivalent).

### observability §5.5.7 — extend the typed-event framing paragraph

§5.5.7 today (post proposal 0057) frames `LlmCompletionEvent` as the structured form of
the §5.5 attribute surface for successful LLM completions. Extend the framing to
acknowledge the failure-side variant:

> **Typed LLM failure event.** Implementations MUST emit the `LlmFailedEvent` typed variant
> (per graph-engine §6) on every LLM call failure that raises one of the llm-provider §7
> error categories. The typed event carries the same identity / scoping / request-side
> field surface `LlmCompletionEvent` carries, plus the failure-specific
> `error_category` / `error_type` / `error_message` fields sourced from the raised
> exception. Response-side fields (`response_id`, `response_model`, `usage`,
> `output_content`, `finish_reason`) are absent from the failure variant — no response was
> received.
>
> Observers consuming the typed event for backend-specific rendering (Langfuse generation
> error per §8.7, OTel span error status per §5.5, custom queryable observer accumulators
> per §9) MAY filter via type discrimination (`isinstance(event, LlmFailedEvent)` or
> per-language idiomatic equivalent). The success and failure variants are mutually
> exclusive on a given LLM call; observers needing both outcome sides handle them as two
> separate type-discrimination branches.
>
> With both `LlmCompletionEvent` and `LlmFailedEvent` defined, the impl-current
> sentinel-namespace `NodeEvent` convention for LLM observability can retire fully —
> success and failure paths both have spec-normative typed equivalents. The §5.5.7
> SHOULD-emit-both transition window's purpose is met across both outcome sides;
> implementations MAY conclude the transition once their backends filter both typed
> variants via type discrimination.

The existing §5.5.7 paragraphs covering `LlmCompletionEvent`'s framing and the
backwards-compatibility / SHOULD-emit-both rule are unchanged.

## Conformance test impact

### New fixtures

Five new fixtures under `spec/observability/conformance/`:

1. **`06X-llm-failure-event-dispatch-on-provider-unavailable`** — Graph with one
   LLM-calling node; mocked provider raises `provider_unavailable`. Asserts the observer
   receives an `LlmFailedEvent` (not an `LlmCompletionEvent`) with the field set populated
   (identity / scoping / request-side per the mirrored shape, `error_category =
   "provider_unavailable"`, `error_message` matching the raised exception). Asserts the
   exception ALSO raises out of `provider.complete()` (the exception-flow contract is
   preserved). Asserts that NO `LlmCompletionEvent` is emitted for the failed call
   (mutual-exclusion rule).

2. **`06X-llm-failure-event-dispatch-on-provider-invalid-request`** — Variant covering a
   different llm-provider §7 category (pre-send validation failure). Asserts
   `error_category = "provider_invalid_request"`; same field-set populated as case 1.

3. **`06X-llm-failure-event-call-id-distinct-from-completion-event`** — Sequence of two
   LLM calls in a graph: first succeeds, second fails. Asserts one `LlmCompletionEvent`
   (for the first call) and one `LlmFailedEvent` (for the second), both with non-null and
   distinct `call_id` values.

4. **`06X-llm-failure-event-mutual-exclusion-with-completion-event`** — Graph with one
   LLM-calling node; mocked provider raises `provider_unavailable`. Asserts exactly one
   `LlmFailedEvent` and exactly zero `LlmCompletionEvent` are observed. Locks down the
   mutual-exclusion rule explicitly (an impl that emits both for the same call fails this
   fixture).

5. **`06X-llm-failure-event-error-type-vendor-specific`** — Mocked provider raises
   `provider_rate_limit` with a vendor-specific `error_type`. Two positive cases cover
   the two `error_type` styles the spec text describes: a vendor error code
   (`"rate_limit_exceeded"`) and an upstream exception class name (`"RateLimitError"`).
   Both assert the typed event carries `error_category = "provider_rate_limit"`
   (normative) AND `error_type` populated with the appropriate vendor-specific value.
   Companion case: provider raises an exception with no vendor-specific type; assert
   `error_type == null` while `error_category` is populated.

Final fixture numbers assigned at acceptance.

### Unaffected fixtures

All existing observability fixtures (001-068) continue to pass unchanged. The new event
variant is purely additive on the observer event union; existing fixtures testing
`LlmCompletionEvent` exercise only the success path (which is unaffected). Fixtures
testing the impl-current sentinel-namespace `NodeEvent` pattern (where present) continue
to pass — this proposal does not retire the sentinel; that's an impl-side concern per the
§5.5.7 SHOULD-emit-both rule.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer increments:

- New `LlmFailedEvent` typed event variant on the graph-engine §6 observer event union
  (purely additive — `LlmCompletionEvent`'s field set and dispatch contract from proposal
  0049 / 0057 are unchanged; the new variant adds a second discriminator-on-type slot).
- New observability §5.5.7 paragraph framing the failure-side typed event (informative-
  clarifying alongside the additive emission rule).
- Five new conformance fixtures.

The change is purely additive at the spec level — observers consuming only
`LlmCompletionEvent` continue to work unchanged; observers wanting to consume the failure
event opt in via type discrimination on the new variant.

## Alternatives considered

1. **Extend `LlmCompletionEvent` with optional error fields (single-variant approach).**
   Lift the success-only constraint on `LlmCompletionEvent`; add optional `error_category`,
   `error_type`, `error_message` fields. Success path leaves them null; failure path
   populates them and leaves the success-only fields (`response_id`, `response_model`,
   `usage`, `output_content`, `finish_reason`) null. Rejected on four grounds:
   - Proposal 0049's *Out of scope* section explicitly anticipated the typed failure
     variant approach: *"`LlmCallFailedEvent` typed variant... warrants a follow-on
     proposal if demand emerges."* Adopting the single-variant approach would actively
     contradict 0049's documented direction.
   - Nullability-bag fragility. Success-only fields would become null on failure;
     null on a completion event would be ambiguous between "doesn't apply on this outcome"
     and "provider didn't report on this successful call" (a real distinction for
     `usage.completion_tokens` etc.). Observers would need to disambiguate via the
     `error_category` check, leaking outcome-discrimination into field-presence logic.
   - Naming. `LlmCompletionEvent` connotes successful completion; rebadging it to also
     carry failures fights the existing semantics. Renaming to `LlmCallEvent` would
     propagate a breaking rename across the field set just stabilized at v0.51.0
     (proposal 0057's `response_id` rename) — a second breaking rename to the same field
     table.
   - Precedent setting. Future typed event variants face the same A/B question.
     Establishing the discriminated-union pattern for the LLM success / failure split
     keeps the typed-event taxonomy clean across the broader event surface.

2. **Status quo — keep failure-path observability on the sentinel-namespace `NodeEvent`
   pattern.** Document that LLM failures permanently surface via the sentinel-namespaced
   `NodeEvent(completed, error_category=..., error_type=...)` shape. Successes use the
   typed event; failures stay on sentinel. Rejected: leaves the type-discrimination
   contract incomplete for the failure half of LLM observability. The §5.5.7
   SHOULD-emit-both transition window's purpose (let backends migrate to type
   discrimination across the LLM-call surface) is defeated if failures permanently
   require sentinel-namespace filtering. The "successes are fully typed; failures are
   sentinel-only" framing is harder to document than full coverage.

3. **Combined success / failure event with a `kind` discriminator field on a single
   class.** A single `LlmCallEvent` type with a `kind: "completed" | "failed"` field;
   field set unions success and failure (success path leaves failure fields null and vice
   versa). Rejected: equivalent to alternative 1 in practice (single class, field-set
   union, outcome-discrimination via a field check rather than a type check). Type
   discrimination per the established proposal 0049 pattern is the load-bearing
   abstraction; switching to field discrimination on the LLM-call surface specifically
   would split the discriminator pattern across event variants.

4. **Per-error-category sub-variants** (`LlmFailedEvent.RateLimit`,
   `LlmFailedEvent.InvalidRequest`, etc.). One typed variant per llm-provider §7
   category. Rejected: the §7 category enumeration is the value space; encoding it as
   classes proliferates types where a field captures the distinction more cleanly.
   Observers needing category-specific handling already filter on `event.error_category`;
   no additional discrimination value from per-category classes.

## Open questions

None at draft time. All design choices are settled in the proposal text above:

- **Variant approach** (alternative 1 vs 3) — new typed variant `LlmFailedEvent`, not
  field-set extension on `LlmCompletionEvent`. Matches proposal 0049's *Out of scope*
  framing.
- **Field-set scope** — 17 fields mirrored from `LlmCompletionEvent` (identity /
  scoping / request-side / per-call disambiguator) + 3 failure-specific fields
  (`error_category`, `error_type`, `error_message`). Response-side fields absent (no
  response received).
- **Mutual exclusion with `LlmCompletionEvent`** — implementations MUST NOT emit both
  variants for the same `provider.complete()` call. Codified in the *LLM failure event*
  paragraph and locked down by the dedicated conformance fixture.
- **Exception-flow contract** — preserved per proposal 0049's alternative-3 framing.
  Failures still raise the §7 category exception out of `provider.complete()`; the typed
  event is dispatched alongside the exception, not in place of it.
- **`error_type` field** — OPTIONAL impl-level / vendor-specific detail. Always
  populated when the implementation has an impl-side type to surface (e.g., upstream
  exception class name); null when no impl-side type is available.
- **`call_id` slot sharing** — both `LlmCompletionEvent` and `LlmFailedEvent` carry
  `call_id` from the same per-call slot. A failed call has its own `call_id`; impls do
  NOT mint a single `call_id` for the combined success-and-failure history of a
  retry-attempted call (each attempt has its own `call_id` per the existing per-attempt
  contract).
- **Privacy / inline-image redaction** — same posture as `LlmCompletionEvent`. The
  `input_messages` / `request_extras` fields follow the same observer-side rendering-
  boundary gating per observability §5.5.4; inline image bytes redacted per §5.5.5
  before population.

If reviewers surface a substantive question during PR review, it gets resolved into the
proposal text rather than left here as a defer.

## Out of scope

- **Streaming-failure events.** Provider streaming-call failures (mid-stream exceptions
  during a streaming generation) are scoped to a planned LLM token streaming proposal,
  which would need its own event-taxonomy decisions. This proposal scopes to atomic
  `provider.complete()` failures only.
- **Changes to the provider exception-flow contract.** Failures still raise the §7
  category exception out of `provider.complete()` per llm-provider §7. The typed event is
  added on the observer surface; the caller-facing exception path is preserved.
- **Failure-event aggregation / suppression.** Implementations emit one `LlmFailedEvent`
  per failed `provider.complete()` call, including per-attempt under call-level retry
  (each attempt that fails emits its own event). Aggregation across attempts is an
  observer-side concern, not a spec contract.
- **Pinning the sentinel-namespaced `NodeEvent(completed, error=...)` shape as a spec
  contract.** The legacy sentinel convention is implementation-current; this proposal
  does not retroactively define its shape in the spec. The §5.5.7 SHOULD-emit-both
  transition window addresses backwards compatibility at the impl layer.
- **Cross-impl byte-identical event serialization.** Same caveat as proposal 0049 — event
  objects are language-native; cross-language byte equality is out of scope.
