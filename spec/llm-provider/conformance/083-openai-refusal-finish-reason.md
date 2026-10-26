# 083: An OpenAI Refusal Maps to `content_filter`, With Its Text as Content

Verifies llm-provider §8.1.2 and §8.1.6 (proposal 0126). OpenAI returns a refusal in a separate `refusal`
field, with no content, or in a streamed response as `delta.refusal` pieces. When a non-empty refusal arrives
and the message carries no tool calls, the message's content is the refusal text and the `finish_reason` is
`"content_filter"`, whatever value OpenAI reports. A streamed refusal's pieces are content deltas, so they
form the content, and the `finish_reason` override applies when the stream carried no tool-call deltas. A
null or empty refusal, which OpenAI sends on ordinary messages, changes nothing.

This matches the Anthropic mapping, where a refusal's text arrives as content and `stop_reason: "refusal"`
maps to `"content_filter"` (§8.2.2), and it keeps the message within §3, which requires content on an
assistant message without tool calls. On a structured-output call it also keeps observability §5.5.7's
`schema_not_honored` diagnostic from reading a refusal as unparseable content on a normal finish, since that
diagnostic excludes `"content_filter"`.

**Spec sections exercised:**

- llm-provider §8.1.2: the atomic refusal rule.
- llm-provider §8.1.6: the streamed refusal rule.
- llm-provider §7 and conformance-adapter §5.12: the `structured_output_invalid` surface on a refused
  structured-output call.

**Cases:**

1. `refusal_on_stop_maps_to_content_filter`: OpenAI reports `"stop"`; the `Response` has the refusal text as
   content and `"content_filter"`.
2. `refusal_on_length_still_maps_to_content_filter`: OpenAI reports `"length"`; still `"content_filter"`.
3. `refusal_with_schema_raises_with_content_filter`: with a `response_schema`, the call raises
   `structured_output_invalid` whose `finish_reason` is `"content_filter"` and whose `output_content` is the
   refusal text.
4. `streamed_refusal_maps_to_content_filter`: `delta.refusal` pieces and a last chunk reporting `"stop"` give
   the concatenated refusal as content and `"content_filter"`, using the SSE wire shape fixture 059 uses.
5. `null_refusal_leaves_content_and_stop`: content with `refusal: null` keeps its content and `"stop"`.
6. `empty_refusal_leaves_content_and_stop`: the same with `refusal: ""`.
7. `streamed_null_refusal_leaves_content_and_stop`: a stream whose first chunk carries `refusal: null` keeps
   its content deltas as the content and `"stop"`.

**What passes:**

- Each refusal case's `Response` (or raised error) carries the refusal text as content and
  `"content_filter"`.
- Each case with a null or empty refusal returns the content and `"stop"` OpenAI sent.

**What fails:**

- `finish_reason` passed through as OpenAI reported it (`"stop"` or `"length"`).
- A message with neither content nor tool calls, which §3 forbids.
- The streamed path ignoring `delta.refusal`, so the assembled response has empty content.
- Firing on the `refusal` key's presence or on any non-null value, which turns every ordinary OpenAI
  completion into `"content_filter"` (cases 5 to 7).

**Limits.** `raw_check` compares the listed keys' values literally (fixture 001's harness note), so the cases
that carry it pin `raw.choices`, refusal included, as received; the streamed cases assert no `raw`. Whether
OpenAI ever sends a refusal together with tool calls is not known. The `finish_reason` override, and the
atomic content rule, apply only when there are none, while a stream's refusal pieces are content either way.
No case exercises the combination, and `docs/open-questions.md` records the difference.
