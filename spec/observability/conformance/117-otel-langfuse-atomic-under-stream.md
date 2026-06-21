# 117 — Bundled OTel / Langfuse stay atomic under streaming

Verifies observability §5.5 and §8: the bundled OTel and Langfuse observers do NOT render `LlmTokenEvent`. A streamed call collapses back to one atomic recording at the terminal `LlmCompletionEvent` — exactly one `openarmature.llm.complete` span (no per-token child spans) and one Langfuse Generation observation (no per-token child observations), each carrying the full assembled input/output, identical to a non-streamed call. A 500-token response is one span / one Generation, not 500.

This fixture's purpose is the atomic-collapse contract (span / observation count and the full assembled output), not full Generation field population — fixture 023 owns the complete Langfuse Generation field set. The asserted `metadata` is the subset load-bearing for atomic collapse (`finish_reason`, `system`).

**Spec sections exercised:**

- observability §5.5 — the OTel observer renders the terminal `LlmCompletionEvent` as one `openarmature.llm.complete` span; token events are not rendered (no per-token spans).
- observability §8 — the Langfuse observer renders the terminal event as one Generation; token events are not rendered (no per-token observations).

**Cases:**

1. `otel_one_llm_span_no_per_token_children_under_stream` — A `stream=True` call (OTel observer, payload enabled) streaming `"Hel"`/`"lo "`/`"world"`. Asserts exactly one `openarmature.llm.complete` span with `children: []` and `openarmature.llm.output.content` = `"Hello world"` (the full assembled content).
2. `langfuse_one_generation_no_per_token_observations_under_stream` — The same streamed call with the Langfuse observer (`disable_provider_payload=False`). Asserts exactly one Generation observation with `children: []`, assembled `output` = `"Hello world"`, and the assembled usage.

**What passes:**

- Exactly one `openarmature.llm.complete` span / one Generation observation for the streamed call.
- No per-token child spans / observations.
- The span / Generation output is the full assembled content, not a per-chunk fragment.

**What fails:**

- Per-token child spans or observations rendered (the stream fanned out into the trace).
- More than one `openarmature.llm.complete` span / Generation for one call.
- The recorded output carrying a single chunk rather than the assembled content.
