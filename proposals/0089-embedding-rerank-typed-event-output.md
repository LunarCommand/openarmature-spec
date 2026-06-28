# 0089: Embedding / Rerank Typed-Event Output

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-28
- **Targets:** graph-engine §6 — `EmbeddingEvent` gains `output_vectors`, `RerankEvent` gains `output_results`, and each event's *Privacy and observer-side gating* enumeration lists the new payload field. observability §8.4.5 / §8.4.7 — re-source `embedding.output` / `retriever.output` from the event fields and specify the failure-observation rendering. observability §5.5.13 / §5.5.14 — re-source the OTel rerank `openarmature.rerank.results` attribute from `RerankEvent.output_results`; the §5.5.9 / §5.5.14 typed-event privacy-posture notes list the new fields. New + existing conformance fixtures.
- **Related:** 0049 (typed `LlmCompletionEvent`), 0059 (embedding protocol), 0060 (rerank protocol), 0063 (tool-execution observability — the failure-rendering precedent in §8.4.6), 0076 (`output_tool_calls` on `LlmCompletionEvent`), 0082 (`LlmFailedEvent` response-side surface).
- **Supersedes:**

## Summary

The typed `EmbeddingEvent` and `RerankEvent` (graph-engine §6) carry only the **count** of their output — `dimensions` (the inner-vector length) and `result_count` — not the output **payload** (the embedding vectors, the scored results). Yet the observability mappings render the actual output: Langfuse §8.4.5 maps `embedding.output` ← `EmbeddingResponse.vectors`, Langfuse §8.4.7 maps `retriever.output` ← the scored results list, the **OTel rerank span** carries `openarmature.rerank.results` (§5.5.13), and the conformance fixtures assert all of it. Because an observer's only input is the typed event (per 0049), the output it is told to render is **not present on the event** — these mappings and their fixtures are unsatisfiable.

This adds an output-payload field to each event, paralleling `LlmCompletionEvent.output_content` (0049 / 0082): `EmbeddingEvent.output_vectors` and `RerankEvent.output_results`, populated on the success event and privacy-gated at the rendering boundary. The Langfuse output mappings (§8.4.5 / §8.4.7) and the OTel rerank attribute (§5.5.13) re-source from these fields. Folding in two adjacent observability gaps in the same area: it **specifies the embedding/rerank failure-observation rendering** (today unstated, unlike §8.4.6's tool failure), and it **confirms** the embedding/rerank span is not gated by `disable_llm_spans` (already stated — §5.5.8 for embedding, §5.5.13 for rerank — a confirmation, no change).

## Motivation

The success events carry an output *count* but no output *payload*, while the mappings render the payload — a contradiction the observer cannot resolve from the event alone:

| typed event (graph-engine §6) | output count carried | renders the output payload at | result |
|---|---|---|---|
| `EmbeddingEvent` | `dimensions` (int) | Langfuse §8.4.5 `embedding.output` (no OTel output attribute) | unsatisfiable (Langfuse) |
| `RerankEvent` | `result_count` (int) | Langfuse §8.4.7 `retriever.output` **and** OTel §5.5.13 `openarmature.rerank.results` | unsatisfiable (both backends) |

`LlmCompletionEvent` does not have this problem: it carries `output_content` (+ `output_tool_calls`), so its observations render the output from the event. Embedding/rerank carry `input_strings` / `query` + `documents` on the input side but have no output-side counterpart. The conformance fixtures for the embedding observation (`083`) and the rerank observation (`108`) each assert the populated `output` under the payload-flag-off case — assertions no conforming observer can satisfy at present, because the field they would read does not exist.

Note the pre-existing **embedding/rerank OTel asymmetry**: the rerank OTel span renders its output (`openarmature.rerank.results`, per 0060), while the embedding OTel span renders no output attribute (only the `dimensions` count + gated input, per 0059) — vectors being larger and noisier than score echoes. This proposal preserves that asymmetry; it only makes the existing rerank attribute satisfiable.

Two adjacent gaps live in the same mapping sections and are cheapest to close in the same pass:

- **Failure-observation rendering is unspecified.** §8.4.6 (tool) spells out the failure observation (`ERROR` level on `ToolCallFailedEvent`, with `error_type` / `error_message` in metadata + the status message). §8.4.5 (embedding) and §8.4.7 (rerank) say nothing about how `EmbeddingFailedEvent` / `RerankFailedEvent` render, leaving a cross-implementation gap.
- **`disable_llm_spans` scope.** §5.5.8 (embedding) and §5.5.13 (rerank) already state the span is *not* gated by `disable_llm_spans` (that flag is scoped to LLM completion spans only). This is correct as written; the proposal records the confirmation and makes no change.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive typed-event fields + observability-mapping reconciliations + a failure-rendering specification. No field is removed; observers that could not render output (because the event lacked it) gain the ability.

### graph-engine §6 — output fields on the success events

- **`EmbeddingEvent.output_vectors`** — `list of list of float`. The embedding vectors the call returned (`EmbeddingResponse.vectors`, retrieval-provider §4). Populated unconditionally on the success event (the provider has the vectors at dispatch); observer-side privacy gating applies at the rendering boundary, the same posture as `input_strings`. The inner-vector length continues to surface separately as the `dimensions` count.
- **`RerankEvent.output_results`** — `list of scored-document records`, each `{index, relevance_score, document?}` (`ScoredDocument`, retrieval-provider §6). The scored results the call returned (`RerankResponse.results`). Populated unconditionally on the success event; observer-side privacy gating at the rendering boundary, same posture as `query` / `documents`. The `result_count` count is retained.
- **Gating enumerations.** The events' *Privacy and observer-side gating* paragraphs, and the §5.5.9 / §5.5.14 typed-event privacy-posture notes, currently enumerate only the input-side payload fields; they are extended to list `output_vectors` / `output_results` as gated payload — matching how `LlmCompletionEvent`'s paragraph enumerates `output_content` / `output_tool_calls` alongside `input_messages`.
- **Failure events unchanged.** `EmbeddingFailedEvent` / `RerankFailedEvent` carry no output — no response was received. This is consistent with 0082's framing that the embedding/rerank failure events have no response-side surface (they have no structured-output path, unlike `LlmFailedEvent`).

### observability §8.4.5 / §8.4.7 — re-source the Langfuse output mapping + specify failure rendering

- **§8.4.5** `embedding.output` is re-sourced from `EmbeddingEvent.output_vectors` (the observer's input is the event, not the `EmbeddingResponse` object; the event field is itself populated from `EmbeddingResponse.vectors` at dispatch). The privacy posture (`disable_provider_payload`, default suppressed) is unchanged. For consistency, the section's input row is reworded to source from the event's `input_strings` rather than "the list passed to `embed()`" — a wording reconcile, not a behavior change (the value was always event-derivable).
- **§8.4.7** `retriever.output` is re-sourced from `RerankEvent.output_results`, identically; its input rows (`query` / `documents`) are reworded to source from the event the same way.
- **Failure-observation rendering (both sections).** An `EmbeddingFailedEvent` / `RerankFailedEvent` renders its Langfuse observation at `ERROR` level with the §7 error category as the status message and `error_type` / `error_message` in metadata, via the generic §4.2 / §8.4.2 error mapping — mirroring §8.4.6's tool failure. A confirming fixture pins it cross-implementation.

### observability §5.5.13 / §5.5.14 — re-source the OTel rerank output attribute

The OTel rerank span's `openarmature.rerank.results` attribute (§5.5.13) renders the scored results, and §5.5.14 already routes the OTel rerank span through an observer consuming the typed event — so it has the **same unsatisfiability** as the Langfuse side. It is re-sourced from `RerankEvent.output_results`. The embedding OTel span is genuinely unchanged: it carries no output attribute (only `dimensions` + gated input per §5.5.8), so no embedding OTel reconcile is needed.

### `disable_llm_spans` scope — confirmation, no change

§5.5.8 (embedding) and §5.5.13 (rerank) already scope `disable_llm_spans` to LLM completion spans only; neither span is gated by it. The proposal adds no suppression flag and makes no edit here — it records the confirmation so the contract is explicit.

## Conformance test impact

- The existing embedding (`083`) and rerank (`108`) Langfuse observation fixtures each assert the populated `output` under the payload-flag-off case; both are **unsatisfiable today** and become satisfiable once `output_vectors` / `output_results` land. Neither is net-new — they already exist and encode the intended behavior.
- The OTel rerank fixture asserting `openarmature.rerank.results` is likewise satisfiable once `output_results` lands.
- New embedding-failure and rerank-failure observation fixtures pin the `ERROR`-level failure rendering (the embedding/rerank analog of the tool-failure observation).
- No new directive vocabulary is introduced.

## Versioning

**MINOR bump** (pre-1.0): additive typed-event fields, observability-mapping reconciliations (Langfuse §8.4.5 / §8.4.7 + OTel rerank §5.5.13), and a failure-rendering specification. The concrete version is the maintainer's call at acceptance.

## Out of scope

- **An OTel *embedding* output attribute.** Embedding vectors stay off the OTel embedding span (identity + gated input only, per the existing §5.5.8 design). The rerank OTel span keeps its existing `openarmature.rerank.results` attribute — re-sourced, not added.
- **Embedding / rerank metrics.** The token/usage-metrics surface is the GenAI-metrics domain (0067), unchanged here.
- **Any `disable_llm_spans` change.** §5.5.8 / §5.5.13 scoping stands; this proposal only records the confirmation.

## Alternatives considered

- **Do nothing.** Rejected: the §8.4.5 / §8.4.7 and OTel §5.5.13 output mappings and their fixtures are unsatisfiable as written — exactly the cross-implementation ambiguity the conformance suite exists to remove.
- **Add an embedding OTel output attribute (symmetry with rerank).** Rejected: embedding vectors are larger and noisier than rerank score echoes; the embedding OTel span's existing design carries identity + gated input only, and the Langfuse Embedding observation is the appropriate home for the vectors. The proposal preserves the pre-existing asymmetry rather than expanding the OTel surface.
- **Source the output mapping from the response object directly.** Rejected: the observer's only input is the typed event (0049); it has no handle to the `EmbeddingResponse` / `RerankResponse` object. The event must carry the payload.
- **Embedding-only; defer rerank.** Rejected: the gap is exactly symmetric — `RerankEvent` has the same count-not-payload shape against both §8.4.7 and the OTel `openarmature.rerank.results` attribute — so deferring would leave two rerank mappings unsatisfiable and force a near-duplicate follow-on.

## Open questions

None. Field names (`output_vectors` / `output_results`) follow `LlmCompletionEvent.output_content`'s `output_` convention; the failure events carry no output (consistent with 0082); `disable_llm_spans` needs no change (already settled by §5.5.8 / §5.5.13).
