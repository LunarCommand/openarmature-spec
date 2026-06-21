# 115 — Token-event `call_id` links to the terminal completion event

Verifies graph-engine §6's `call_id` linkage for `LlmTokenEvent`: across two streamed calls in one invocation, each call's token events carry that call's `call_id` — distinct across the two calls, each matching its own terminal `LlmCompletionEvent`. This is the linkage a forwarding observer uses to associate a token stream with its eventual completion. `chunk_index` is monotonic per call (it restarts at 0 for the second call).

**Spec sections exercised:**

- graph-engine §6 — `LlmTokenEvent.call_id` matches the terminal `LlmCompletionEvent.call_id` for the same call; `chunk_index` is monotonic per call.

**Cases:**

1. `each_streams_token_events_share_their_own_completion_call_id` — Two chained streamed nodes; call 1 streams two content deltas, call 2 streams three. Asserts 5 `LlmTokenEvent`s and 2 `LlmCompletionEvent`s; the call-1 token events share one `call_id` equal to call 1's completion event's, the call-2 token events share another `call_id` equal to call 2's completion event's, the two `call_id`s are distinct and non-null, and `chunk_index` restarts at 0 for the second call.

**What passes:**

- The token events partition into two `call_id` groups, one per call.
- Each group's `call_id` equals exactly one of the two `LlmCompletionEvent`s' `call_id`s.
- The two `call_id`s are distinct and non-null.

**What fails:**

- A single `call_id` shared across both calls' token events (calls not disambiguated).
- A token event whose `call_id` matches neither completion event.
- `chunk_index` continuing across the call boundary instead of restarting at 0.
