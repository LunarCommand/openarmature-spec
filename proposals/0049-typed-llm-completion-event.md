# 0049: Typed LLM Completion Event

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-01
- **Accepted:**
- **Targets:** spec/graph-engine/spec.md (§6 — introduces the first normatively-typed event variant on the observer event union, `LlmCompletionEvent`, alongside the existing `NodeEvent`); spec/observability/spec.md (§5.5 — frames the typed event as the structured form of the existing LLM provider span attribute surface, with a dual-emit transition window during which both the typed event and the existing sentinel-namespaced `NodeEvent` for LLM completions fire); plus new conformance fixtures covering the typed event's field-set + dual-emit composition.
- **Related:** 0024 (LLM span payload + GenAI semconv — established the §5.5 attribute surface this proposal mirrors in typed-event form), 0040 (mid-invocation augmentation — RECOMMENDED a framework-emitted metadata-augmentation event as the dispatch mechanism for open-span updates; this proposal extends the event surface with the first spec-mandated typed variant for a related concern)
- **Supersedes:**

## Summary

OpenArmature's observer events today flow through a single normative
shape — `NodeEvent` per graph-engine §6 — covering node-execution
lifecycle. Proposal 0040 introduced a RECOMMENDED framework-emitted
metadata-augmentation event mechanism on the same delivery queue, but
the spec frames that as a dispatch mechanism rather than a normatively-
typed event variant; the typed shape is per-language idiom.

LLM completion events flow through the same observer queue but ride on
the `NodeEvent` shape via a **sentinel-namespaced** convention:
backends interested in LLM calls filter by
`event.namespace == ("openarmature.llm.complete",)` (or
`event.node_name == "openarmature.llm.complete"`, per spec phrasing) and
unpack typed fields by hand from the event payload.

The sentinel-namespace pattern is brittle. Every backend's LLM-aware
hook (OTel observer's span emission per §5.5, Langfuse observer's
generation rendering per §8.7, custom user accumulators consuming
LLM events) does the same string-match-and-unpack dance. Backends
that miss the namespace string get silent failures; backends that
hard-code the namespace string couple themselves to the convention
in a way that's fragile across spec edits.

This proposal carves LLM completions out of the sentinel-namespace
shape and into the first normatively-typed event variant —
`LlmCompletionEvent` — on the observer event union:

1. **Typed event variant on the observer event union.** A new
   structured event type carrying the LLM call's identity / scoping
   / outcome data as typed fields. Observer code filters via
   `isinstance(event, LlmCompletionEvent)` (or per-language
   discriminator) and accesses typed fields directly. Field set
   mirrors the existing observability §5.5 attribute surface — no
   new data, just a structured carrier for data the spec already
   surfaces.

2. **Dual-emit transition.** During the transition window, the
   existing sentinel-namespaced `NodeEvent` for LLM completions
   continues to fire alongside the new typed event. Backends MAY
   consume either; backends already filtering by the sentinel
   namespace continue to work unchanged. A follow-on proposal MAY
   deprecate the sentinel emission in a future spec cycle.

3. **Scope: completion only.** The typed event fires on LLM call
   completion (successful or returning a structured response). Start
   events, streaming chunk events, and failure events are explicitly
   out of scope for v1 — each has different field shapes and
   different downstream use cases; bundling them would entangle
   concerns. Failure events MAY warrant a follow-on `LlmCallFailedEvent`
   typed variant if demand emerges.

The change is backwards-compatible during the dual-emit window:
applications relying on the sentinel-namespaced `NodeEvent` see no
behavioral change; applications opting into the typed event get
cleaner filtering and typed access without payload unpacking.

## Motivation

Three forces converge:

**Brittleness of sentinel-namespace filtering.** Backend hooks for
LLM calls — the OTel observer's §5.5 span emission, the Langfuse
observer's §8.7 generation rendering, custom accumulators per the
queryable observer pattern from proposal 0048 — all do the same
namespace-string-match-and-unpack dance to identify LLM events.
Misspelled namespace strings produce silent failures; spec edits
that rename the namespace string require every backend hook to
update in lockstep. The typed event variant eliminates the
brittleness by making the discriminator type-level rather than
string-level.

**Cross-impl consistency.** The sentinel-namespace shape relies on
backends knowing the exact string `"openarmature.llm.complete"`
(and any spec changes to it). A typed event variant gives
implementations a single point of definition — the event's typed
shape and field set — that cross-language implementations mirror
without worrying about namespace-string drift.

**Setting the precedent.** Proposal 0040 RECOMMENDED a framework-
emitted augmentation event mechanism but left the typed shape per-
language idiom. This proposal establishes the first spec-normative
typed event variant on the observer event union; subsequent
proposals (failure events, streaming events, additional cross-
cutting events) MAY follow the same pattern. The pattern's value
shows clearly in the LLM-completion case where the field set is
stable and broadly consumed.

The dual-emit transition keeps existing backends working through
the window; the typed-event surface is added without breaking any
sentinel-matching consumer.

## Proposed change

### graph-engine §6 — extend the observer event union with `LlmCompletionEvent`

§6 today describes observers receiving `NodeEvent` records as the
primary signal (with proposal 0040's RECOMMENDED metadata-
augmentation event mechanism dispatched on the same delivery queue).
Add a new typed event variant for LLM call completions, the first
spec-normatively-typed variant on the event union.

The class name `LlmCompletionEvent` is spec-normative as an
identifier; implementations MAY use a per-language idiomatic name
(e.g., adjusted casing or symbol conventions per the language's
naming idioms) provided the field set + dispatch contract are
preserved. The discriminator-on-type contract is the load-bearing
piece; the exact symbol matters less than the
distinct-from-`NodeEvent` typed shape.

> **LLM completion event.** A typed event variant on the observer
> event union signaling completion of an LLM provider call. Carries
> the call's identity / scoping / outcome data as typed fields:
>
> | Field | Type | Description |
> |---|---|---|
> | `invocation_id` | string | The outer invocation's identifier, per §5.1 of observability. |
> | `correlation_id` | string \| null | Cross-backend correlation ID, per §3.1 of observability. |
> | `node_name` | string | The user-defined node that issued the call. |
> | `namespace` | tuple of strings | The calling node's namespace (NOT the sentinel namespace). |
> | `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
> | `provider` | string | The LLM provider identifier (matches `gen_ai.system` per observability §5.5.3). |
> | `model` | string | The model identifier (matches `gen_ai.request.model` / `openarmature.llm.model` per observability §5.5 / §5.5.3). |
> | `request_id` | string \| null | The provider-returned response identifier, when present (matches `gen_ai.response.id` per observability §5.5.3). |
> | `usage` | record \| null | Token usage record per llm-provider §6 `Response.usage` shape. May be null when the provider does not report usage. |
> | `latency_ms` | float \| null | Wall-clock latency of the LLM call measured at the adapter boundary, in milliseconds. May be null when latency is not measured. Implementations MAY use a provider-reported latency value when the provider surfaces one, documenting which source is in use. |
> | `finish_reason` | string \| null | The LLM call's finish reason per llm-provider §6 `Response.finish_reason`. May be null when the call did not complete normally. |
> | `caller_invocation_metadata` | mapping \| null | OPTIONAL field — a snapshot of the caller-supplied invocation metadata (per §3.4 of observability) at the time of the LLM call, populated only when the observer is configured to include it (per-language opt-in mechanism). Default absent / null; off by default to avoid bloating every event with potentially-large metadata. Consumers wanting a fresh metadata view rather than a snapshot use the `get_invocation_metadata()` read API per proposal 0048. |
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

### observability §5.5 — frame the typed event + dual-emit

§5.5 today specifies the LLM provider span surface (attributes
per §5.5.1 through §5.5.4 from proposal 0024). Add a paragraph
framing the typed event as the structured form of the same data
surface, and specify the dual-emit transition.

> **Typed LLM completion event.** Implementations MUST emit the
> `LlmCompletionEvent` typed variant (per graph-engine §6) on every
> LLM call completion that produces a structured response. The
> typed event carries the same identity / scoping / outcome data
> the §5.5 span attribute surface exposes — `gen_ai.system`,
> `gen_ai.request.model`, `gen_ai.response.id`, `gen_ai.usage.*`,
> `gen_ai.response.finish_reasons`, plus the OA-namespaced
> attributes (`openarmature.invocation_id`, `openarmature.node.name`,
> etc.) — in a structured form rather than as separate span
> attributes.
>
> Observers consuming the typed event for backend-specific rendering
> (Langfuse generation per §8.7, OTel span enrichment per §5.5,
> custom queryable observer accumulators per proposal 0048) MAY
> filter the observer event stream via type discrimination
> (`isinstance(event, LlmCompletionEvent)` or per-language idiomatic
> equivalent) rather than via the sentinel-namespace string match
> the existing pattern uses.
>
> **Dual-emit transition.** During the dual-emit window (defined as
> the spec versions between this proposal's acceptance and a
> potential follow-on proposal that deprecates the sentinel-
> namespaced `NodeEvent` for LLM completions), implementations MUST
> emit BOTH the typed `LlmCompletionEvent` AND the existing
> sentinel-namespaced `NodeEvent` carrying the LLM-call payload.
> Both fire on the same observer queue; both carry the same
> logical data.
>
> **Backends MUST subscribe to one event variant, not both, per LLM
> completion.** A backend that filters for both the typed event AND
> the sentinel-namespaced `NodeEvent` will receive two distinct
> events for the same logical LLM completion — accumulators counting
> events will double-count, span emitters will double-emit. Backends
> opting into the typed event MUST filter out (or stop subscribing
> to) the sentinel-namespaced `NodeEvent` for LLM completions; the
> two-variant emission is for transition consumption, not parallel
> consumption.
>
> Backends filtering only by the sentinel namespace continue to
> work unchanged through the dual-emit window. Backends filtering
> only by the typed event get the cleaner surface. A follow-on
> proposal MAY deprecate the sentinel emission in a future cycle;
> no specific timeline is set by this proposal.

### graph-engine §6 *Driving span lifecycle* — implications

§6's existing observer event delivery semantics (strict-serial
across the invocation, async-delivered, etc.) apply to the new
typed event variant unchanged. The typed event fits the same
delivery queue as `NodeEvent` and the metadata-augmentation event
mechanism from proposal 0040; no new delivery mechanism is
introduced.

The §6 driving-span-lifecycle text (in observability) explains how
observers consume `started` / `completed` events to drive span
lifecycle. The `LlmCompletionEvent` complements this — it fires
when an LLM call completes, alongside the underlying `NodeEvent`
that drives the LLM span lifecycle. Observers MAY consume one or
both depending on what they need. Span lifecycle continues to
flow through the existing `started` / `completed` `NodeEvent` pair
during the dual-emit window.

## Conformance test impact

### New fixtures

Four new fixtures under `observability/conformance/` (numbers
assigned at acceptance):

1. **Typed event dispatches on LLM completion.** A graph with one
   LLM-calling node, a mocked provider returning a structured
   response, and a custom observer that collects events. Asserts
   the observer receives an `LlmCompletionEvent` with the field set
   populated from the mocked response (provider, model, usage,
   finish_reason all present and matching).

2. **Dual-emit during transition window.** Same shape as fixture 1,
   plus assertion that the observer ALSO receives the existing
   sentinel-namespaced `NodeEvent` for the LLM completion. Both
   fire on the same observer queue; the typed event carries
   structured data; the `NodeEvent` carries the same data via the
   sentinel-namespace pattern. The fixture asserts both arrive
   without ordering coupling between them (either may fire first
   on the queue).

3. **`caller_invocation_metadata` opt-in.** A graph that uses
   `set_invocation_metadata({"user_id": "u123"})` before an LLM
   call. With opt-in disabled (default), the typed event's
   `caller_invocation_metadata` field is null. With opt-in enabled
   (per-language flag on the observer), the field is populated
   with a snapshot containing `user_id: "u123"`.

4. **No event on failure.** A graph that issues an LLM call against
   a mocked provider raising `provider_unavailable`. Asserts the
   observer does NOT receive an `LlmCompletionEvent` for the failed
   call (the failure surfaces via the exception path; the typed
   event is completion-only per the v1 scope).

### Unaffected fixtures

All existing fixtures continue to pass unchanged. The dual-emit
transition means the sentinel-namespaced `NodeEvent` continues to
fire as before; backends and fixtures depending on the existing
shape are not broken. The typed event is purely additive during
the dual-emit window.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- New `LlmCompletionEvent` typed event variant on the graph-engine
  §6 observer event union (additive — existing `NodeEvent` shape
  unchanged; proposal 0040's metadata-augmentation event mechanism
  remains RECOMMENDED rather than typed).
- New observability §5.5 paragraph framing the typed event +
  dual-emit transition (informative-clarifying alongside additive
  emission rule).
- New conformance fixtures (four required). Existing fixtures
  unchanged.

The change is backwards-compatible during the dual-emit window.
Existing applications subscribed to the sentinel-namespaced
`NodeEvent` continue to receive it; applications opting into the
typed event get cleaner filtering. A potential follow-on cycle
that deprecates the sentinel emission would be backwards-
incompatible only against backends that haven't migrated; that
deprecation lands per its own proposal cycle.

## Alternatives considered

1. **Always-on `caller_invocation_metadata` field.** Populate the
   field on every typed event with the metadata view at emission
   time. Rejected: every LLM call's event would carry a snapshot
   of the (potentially-large) metadata mapping, even when consumers
   don't care; the snapshot is also frozen at emission time, which
   may not match what the consumer wants (the consumer can fetch a
   fresh view via `get_invocation_metadata()` per proposal 0048 if they
   need it). Opt-in via observer configuration is the right scope —
   default absent, populated only when the consumer explicitly asks.

2. **Replace the sentinel emission immediately (no dual-emit).**
   Stop emitting the sentinel-namespaced `NodeEvent` for LLM
   completions at this proposal's acceptance; only the typed event
   fires. Rejected: breaking for any backend currently reading the
   sentinel-namespaced event (the OTel observer's §5.5 hook, the
   Langfuse observer's §8.7 hook, custom user backends). The
   dual-emit window keeps the existing surface available while the
   typed surface lands additively; a separate follow-on proposal
   handles deprecation when the time is right.

3. **Bundle failure event + streaming event into v1.** Add
   `LlmCallFailedEvent` and `LlmStreamChunkEvent` typed variants
   alongside the completion event. Rejected: each has different
   field shapes (failure event needs no `usage`, different
   `finish_reason` values; streaming events need partial-content
   accumulators, sequence ordering). Bundling would triple the
   proposal's review burden and entangle three distinct concerns.
   Each warrants a follow-on if downstream demand surfaces.

4. **Make the event live in observability §-something, not
   graph-engine §6.** The typed event is observability-specific
   (it carries LLM-call data, mirroring §5.5 attributes). Place it
   under observability §5 or §6 rather than the graph-engine event
   union. Rejected: the observer event union shape is in
   graph-engine §6; observability §5.5 doesn't define new event
   types, it consumes the existing union. Adding a new event variant
   means extending the union at graph-engine §6 — and observability
   §5.5 then frames the typed variant as the structured form of
   its existing attribute surface. The split keeps the event
   shape's normative home in graph-engine §6 (where Observer's
   contract lives) while the rendering / mapping concern stays in
   observability.

5. **Mirror more `gen_ai.*` attributes verbatim as typed fields.**
   The §5.5 attribute surface includes additional GenAI semconv
   attributes (`gen_ai.request.temperature`, `gen_ai.request.max_tokens`,
   etc. from §5.5.2). Mirror those as typed fields on the event too.
   Rejected for v1: per-call `RuntimeConfig` fields are caller-
   controlled (the caller knows what they passed), so observers
   typically don't need them on the event — they can reach the
   request shape via the `Response.raw` or via the existing
   `NodeEvent`'s payload if needed. The v1 typed event scopes to
   the outcome-side data (provider response, usage, finish_reason)
   plus identity / scoping. Request-side fields can be added in a
   follow-on if observer demand surfaces.

## Open questions

None at draft time. The design choices are settled in the proposal
text above:

- **Failure event** (alternative 3) — out of scope; follow-on if
  demand emerges.
- **Streaming events** (alternative 3) — out of scope;
  completion-only on stream close per v1.
- **`latency_ms` source** — wall-clock measured by adapter;
  provider-reported value MAY override when surfaced. Per the
  §6 event field definition above.
- **`caller_invocation_metadata` always-on vs opt-in** (alternative
  1) — opt-in via observer configuration; default absent.
- **Replace vs dual-emit** (alternative 2) — dual-emit additively
  lands the typed surface; a follow-on proposal MAY deprecate the
  sentinel emission in a future cycle (no timeline pinned).
- **Event variant home (graph-engine vs observability)**
  (alternative 4) — graph-engine §6 hosts the event union shape;
  observability §5.5 frames the typed variant as the structured
  form of its attribute surface.
- **Field set scope** (alternative 5) — outcome-side data plus
  identity / scoping; request-side fields out of scope for v1.

**Sequencing note.** The `caller_invocation_metadata` opt-in field
references the `get_invocation_metadata()` read API from proposal
0048 (Draft). The cross-reference assumes 0048 lands ahead of or
alongside 0049's Accept; both proposals are in the same Cat-B
batch and the sequence is straightforward to manage. If 0048
substantively shifts during its own review, this proposal's
`caller_invocation_metadata` framing may need a small follow-up
edit to align.

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **`LlmCallFailedEvent` typed variant** (alternative 3). Failure
  events have different field shapes and use cases; warrant a
  follow-on proposal if demand emerges. Today's failure surface
  flows through the exception path per llm-provider §7.
- **`LlmStreamChunkEvent` typed variant** (alternative 3). Streaming
  per-chunk events warrant their own typed variant; bundling would
  entangle ordering and accumulator concerns with the completion
  shape.
- **Request-side typed fields** (alternative 5). `RuntimeConfig`
  parameters (`temperature`, `max_tokens`, etc.) are caller-known;
  observers needing them reach via `Response.raw` or the existing
  `NodeEvent`'s payload.
- **Deprecating the sentinel-namespaced emission.** A separate
  follow-on proposal handles deprecation; this proposal lands the
  typed-event surface additively, leaving the sentinel emission in
  place for the dual-emit window.
- **Cross-impl byte-identical event serialization.** Event objects
  are language-native; cross-language byte equality is out of scope
  (matches the observability §5.5.1 cross-impl byte-stability
  caveat).
- **Event payload truncation contract.** Unlike §5.5.1 attribute
  values (subject to §5.5.5 truncation), the typed event's field
  values flow through observer code unchanged. Observers SHOULD
  apply backend-specific truncation if rendering the event to a
  byte-bounded backend.
