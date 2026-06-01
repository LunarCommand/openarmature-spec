# 051 — Type-discrimination filtering on `LlmCompletionEvent`

Verifies that an observer subscribing via type discrimination receives the typed event
regardless of whether the implementation also emits the impl-current sentinel-namespaced
`NodeEvent` for LLM completions. The spec-normative contract is the typed event; the sentinel
emission is implementation-current convention preserved for backwards compatibility.

**Spec sections exercised:**

- graph-engine §6 — Type-discrimination filter (`isinstance(event, LlmCompletionEvent)` or
  per-language equivalent) as the spec-normative consumer surface.
- observability §5.5.7 — SHOULD-emit-both transition for the impl-current sentinel-namespace
  convention; backends SHOULD subscribe to one variant per LLM completion.

**Cases:**

1. `type_discriminating_observer_receives_typed_event_only` — A graph with one LLM-calling
   node and two observers:
   - Observer A subscribes via type discrimination: it captures events where
     `isinstance(event, LlmCompletionEvent)` is true. Asserts observer A captures exactly
     one event.
   - Observer B subscribes to ALL events (no filter) for assertion purposes. Asserts
     observer B's captured list contains the `LlmCompletionEvent` AND — depending on the
     implementation under test — MAY contain a sentinel-namespaced `NodeEvent`
     (`node_name = "openarmature.llm.complete"`) emitted per the SHOULD-emit-both transition.

   The fixture asserts the type-discriminating observer's behavior is INDEPENDENT of whether
   the implementation also emits the sentinel NodeEvent. Both impls (emit-both vs.
   typed-only) MUST satisfy the type-discrimination filter case.

**Harness extensions:** the harness MUST support two observers with different filter modes
(type discrimination vs all-events), each retaining captured events in observer-internal
storage (observers MUST NOT mutate state per graph-engine §6), and observer-introspection
expectations that count occurrences of events by type.

**What passes:**

- Observer A captures exactly one `LlmCompletionEvent`, regardless of whether the impl emits
  the sentinel NodeEvent.
- Observer B captures the same `LlmCompletionEvent` PLUS (impl-defined) any
  sentinel-namespaced NodeEvent.
- Type-discrimination filter is independent of the sentinel-namespace convention.

**What fails:**

- Observer A captures zero events — the typed event is not dispatched or the
  type-discrimination filter does not see it.
- Observer A captures more than one `LlmCompletionEvent` — the framework emitted the typed
  event more than once for a single LLM call.
- Observer A captures the sentinel NodeEvent instead of `LlmCompletionEvent` — the typed
  event was not constructed as a distinct event variant.
