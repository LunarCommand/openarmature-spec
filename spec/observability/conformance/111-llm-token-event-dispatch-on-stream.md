# 111 — `LlmTokenEvent` dispatch on a streamed call

Verifies graph-engine §6's *Typed LLM token event* together with llm-provider §5 *Streaming* and §6 *Streaming assembly*. When `complete()` is called with `stream` set, the provider emits one `LlmTokenEvent` per streamed content chunk, in `chunk_index` order, all before the terminal `LlmCompletionEvent` for the same call. The ordered concatenation of the content deltas equals the terminal event's assembled content, and every token event shares the terminal event's `call_id`. This fixture also introduces the streaming harness directives (`calls_llm.stream`, `mock_llm_stream`, `contains_events_in_order`) documented in its YAML header per conformance-adapter §3.2.

**Spec sections exercised:**

- graph-engine §6 — `LlmTokenEvent` typed event variant; field set; `chunk_index`-ordered dispatch before the terminal `LlmCompletionEvent`; `call_id` linkage.
- llm-provider §5 — `complete()`'s `stream` flag; per-chunk `LlmTokenEvent` emission; unchanged `Response` return type.
- llm-provider §6 — *Streaming assembly*: `message.content` is the ordered concatenation of streamed content deltas.

**Cases:**

1. `token_events_dispatched_in_chunk_order_concatenate_to_content` — A node calls `complete(stream=True)`; the mock yields content chunks `"Hel"` / `"lo "` / `"world"` then a terminal usage chunk. Asserts three `LlmTokenEvent`s with `delta_kind="content"` and `chunk_index` `0,1,2` in order, the terminal `LlmCompletionEvent` whose assembled content is `"Hello world"`, every token event's `call_id` equal to the terminal event's, and the full `LlmTokenEvent` identity / scoping field set (`node_name`, `namespace`, `attempt_index=0`, `fan_out_index=null`, `branch_name=null`, `provider`, `model`, `caller_invocation_metadata=null`) on the first token event.

**What passes:**

- Exactly N `LlmTokenEvent`s for N streamed content chunks, `delta_kind="content"`, `chunk_index` monotonic from 0.
- The ordered concatenation of the token-event `delta`s equals the terminal `LlmCompletionEvent`'s assembled content.
- Every token event's `call_id` matches the single terminal `LlmCompletionEvent`'s `call_id`.
- Exactly one terminal `LlmCompletionEvent` is observed.

**What fails:**

- Zero token events emitted on a `stream`-set call (the provider did not surface the stream).
- `chunk_index` not monotonic / not starting at 0, or token events delivered after the terminal event.
- Assembled content does not equal the concatenated deltas, or a token event carries a `call_id` distinct from the terminal event's.
- More than one terminal `LlmCompletionEvent`, or a token event emitted with a `delta_kind` other than `content`.
