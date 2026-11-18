# 090: Gemini Text Streaming, With Usage From the Last `usageMetadata`

Verifies llm-provider §8.3.6 (proposal 0128) for a plain text stream. The mapping sends the atomic request
body to `:streamGenerateContent?alt=sse`, joins adjacent unsigned text parts, emits a content token event for
each non-empty text part, and maps the merged response by §8.3.2.

Gemini reports `usageMetadata` already accumulated, on each chunk. The mapping takes the last one any chunk
carried, whole. It does not sum the counts and does not merge counters from different chunks.

**Spec sections exercised:**

- llm-provider §8.3.6 *Assembly*: the endpoint, text-part joining, `finishReason`, `usageMetadata` and the
  other fields taking the last value, and `raw` as the merged response.
- llm-provider §8.3.6 *Token events* and §6 *Empty deltas*: no event for an empty text part.
- graph-engine §6: `chunk_index` counts emitted events with no gaps.
- llm-provider §8.3.2: the response mapping, including `cached_tokens` from `cachedContentTokenCount`.
- conformance-adapter §5.16: `expected_wire_url` under `mapping: gemini`.

**The stream:** four chunks. The first carries `"Hello"` and a `usageMetadata` with
`cachedContentTokenCount: 4`. The second carries an empty text part. The third carries `", world."`,
`finishReason: STOP` and a `usageMetadata` whose `promptTokenCount` is lower than the first chunk's and which
has no `cachedContentTokenCount`. The fourth carries only `finishReason` and no `usageMetadata`.

**What passes:**

- One request, to `/v1beta/models/gemini-test:streamGenerateContent?alt=sse`, with the atomic body.
- Two content token events, `chunk_index` 0 and 1.
- One `TextBlock` with `"Hello, world."`, `finish_reason` `"stop"`, and usage 11, 4 and 15 with no
  `cached_tokens`.
- `raw` holds the merged response: the third chunk's `usageMetadata`, one joined text part, and the last
  `finishReason`, `modelVersion` and `responseId`.

**What fails:**

- The `:generateContent` endpoint, a missing `alt=sse`, or a body `stream` field.
- A token event for the empty part, or `chunk_index` 0 and 2.
- Summed usage, or the first chunk's counts.
- A per-counter merge that keeps `cached_tokens: 4` from the first chunk.
- The fourth chunk's missing `usageMetadata` read as "no usage", nulling the counters.
- Two text blocks, or an empty `TextBlock` for the empty part.
