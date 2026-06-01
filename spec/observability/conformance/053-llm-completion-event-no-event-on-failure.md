# 053 — `LlmCompletionEvent` NOT emitted on LLM failure

Verifies the completion-only scope of `LlmCompletionEvent` (per graph-engine §6 + observability
§5.5.7). Failure cases (provider exceptions, malformed responses) do NOT emit the typed event;
failures surface through the exception path per llm-provider §7's error categories. A future
`LlmCallFailedEvent` typed variant MAY be added if downstream demand surfaces (out of scope for
v1).

**Spec sections exercised:**

- graph-engine §6 — The typed event is dispatched ONLY for completions producing a structured
  response per llm-provider §6; failure cases do NOT emit this event variant.
- llm-provider §7 — `provider_unavailable` error category surfaces via the exception path, not
  the observer event surface.

**Cases:**

1. `no_llm_completion_event_when_provider_unavailable` — A graph with one LLM-calling node;
   the mocked provider raises `provider_unavailable` (transient unreachability). A custom
   observer collects all events. Asserts: the observer does NOT receive an
   `LlmCompletionEvent` for the failed call. The failure surfaces via the
   `provider_unavailable` exception path; the node's `completed` event carries `error`
   populated per graph-engine §6's node event shape.

**Harness extensions:** the harness MUST support a mocked provider returning a transient
error (HTTP 5xx mapped to `provider_unavailable` per llm-provider §7), plus observer-internal
storage of captured events and an observer-introspection expectation asserting the absence of
events by type (observers MUST NOT mutate state per graph-engine §6).

**What passes:**

- No `LlmCompletionEvent` is in the collected events list.
- The node's `completed` `NodeEvent` carries `error` populated with the `provider_unavailable`
  category (per graph-engine §6 node event shape).
- The graph terminates via the exception path; no typed event is conjured for the failure.

**What fails:**

- An `LlmCompletionEvent` is observed for the failed call — the framework over-eagerly
  emitted the typed event despite the v1 completion-only scope.
- An `LlmCompletionEvent` is observed with null / partial fields representing a
  "failed-but-typed" view — the spec contract is no event for failure, not a degraded event.
