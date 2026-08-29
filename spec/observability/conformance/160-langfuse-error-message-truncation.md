# 160 — Langfuse Error-Message Truncation

Verifies that a failed observation's `metadata.error_message` is subject to observability §5.5.5's
per-observer byte cap, and that the Langfuse observer applies that cap **directly** rather than inheriting
an already-truncated value (§8.7).

Proposal 0118 classified the harvested exception message as payload so `disable_provider_payload` could gate
it, but did not say whether the size bound followed it. Proposal 0119 closes that: §5.5.5 now governs every
payload-classified value, and where a value has no span-attribute source the mapping that writes it applies
the cap. `error_message` is the case in point. Nothing writes it to a span attribute, so §8.7's inheritance
arm cannot reach it, and before this it was the one payload channel with no size limit.

## How the cases discriminate

Each case fails a call whose mock supplies a 100 KiB harvested message, well over the 64 KiB default cap,
synthesized with `message_repeat` (conformance-adapter §5.15 for the retrieval mock, §5.5 for `mock_llm`)
rather than carried inline.

1. **`embedding_failure_error_message_truncated_to_cap`** — the Embedding mapping. Asserts all four
   `metadata_truncation` sub-keys: at most 64 KiB, ends with the §5.5.5 marker, valid UTF-8, and a
   byte-exact prefix of the untruncated message. Each fails a different wrong implementation: one that
   shortened without the marker, one that split a multi-byte sequence, one that re-serialized rather than
   cut.
2. **`generation_failure_error_message_truncated_to_cap`** — the same on the LLM mapping. §8.7 states the
   rule for a failed Generation *and* its Embedding, Tool and Retriever counterparts, so an implementation
   that hooked the cap into one mapping in isolation passes case 1 and fails here.
3. **`default_posture_withholds_message_so_nothing_to_truncate`** — the same failure under
   `disable_provider_payload: true`. The message is gated off entirely (§5.5.4, proposal 0118), so
   `error_message` is **absent** rather than truncated, asserted via `metadata_absent`. Without this case an
   implementation could satisfy the cap by always suppressing the message.

`error_type` is asserted present in all three. It is a classification token, ungated and short, so it is
unaffected by the cap; asserting it keeps the truncation assertions from passing against an observation that
emitted nothing at all.

## Why no `otel_observer` block

§5.5.5 makes the cap **per-observer** and §8.9 makes the two observers independent, so the cap that governs
`error_message` is the **Langfuse** observer's own. An implementation taking the OTel observer's cap for this
value is non-conforming. Setting both observers here would make the two agree and hide exactly that defect,
so only the Langfuse observer is configured.

## Not JSON-encoded

§5.5.5's unparseable-JSON truncation signal is a property of truncating a JSON-encoded attribute.
`error_message` is a plain string, so the marker is appended directly and its presence is itself the signal.
`marker_pattern` asserts that rather than any parse failure.

## Spec coverage

- **observability §5.5.5** — the truncation contract's direct-application arm for a payload-classified value
  with no span-attribute source.
- **observability §8.7** — the Langfuse observer applying the cap when it writes `metadata.error_message`,
  under its own configured cap.
- **observability §5.5.4** — a message the payload flag permits is subject to the cap; one it withholds is
  absent rather than truncated.
- **conformance-adapter §5.5 / §5.15** — `metadata_truncation`, `mock_llm`'s `raises` form, and
  `message_repeat`.
