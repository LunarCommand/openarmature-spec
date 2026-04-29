# 001 — Basic Completion

Minimal happy-path test of `complete()`: a system + user message exchange where the mock provider
returns a plain text assistant response with `finish_reason: "stop"`.

Also documents the **conformance fixture format** for the `llm-provider` capability. Subsequent
fixtures (002–008) reuse the same shape.

**Spec sections exercised:**

- §3 Message shape — `system` and `user` per-role constraints; `assistant` response carries
  `content` and no `tool_calls`.
- §5 `complete()` — single completion call, returns a `Response`.
- §6 Response shape — `message`, `finish_reason`, `usage`, and `raw` populated.
- §6 `finish_reason: "stop"` — the model produced a complete response naturally.
- §8 OpenAI-compatible wire format — request mapping for `system`/`user` roles; response mapping
  from `choices[0]`.

**What passes:**

- The implementation receives the canned mock response.
- `Response.message.role == "assistant"`, `Response.message.content == "Hello! How can I help you today?"`,
  `Response.message.tool_calls` is null/empty.
- `Response.finish_reason == "stop"`.
- `Response.usage.prompt_tokens == 12`, `completion_tokens == 9`, `total_tokens == 21`.
- `Response.raw` contains all the top-level keys from the mock response (`id`, `object`, `created`,
  `model`, `choices`, `usage`) with values matching the mock body.

**What fails:**

- The implementation strips, rewrites, or omits any field from `raw`.
- The implementation reports `usage` as `null` despite the mock supplying it.
- `finish_reason` is mapped to anything other than `"stop"`.
- The normalized `Response.message.content` does not match the mock's content verbatim.

## Fixture format

This and all subsequent llm-provider fixtures use the format documented at the top of this
fixture's YAML. The high points:

- `mock_provider.responses` — ordered list of canned responses; each `complete()` consumes one.
- `calls` — ordered list of operations to invoke. Each entry has `operation` (`complete` or
  `ready`), the operation's inputs, and an `expected` block.
- `expected.response` — assertions over the returned `Response`. Mutually exclusive with
  `expected.raises`.
- `expected.response.raw_check.required_keys` — subset assertion: these top-level keys MUST appear
  in `raw` with the same values as the mock body. Other keys MAY be present.
- `expected.raises` — assertion that the operation raised an error of the stated category.
- The conformance harness in each implementation supplies a mock OpenAI-compatible provider that
  consumes the YAML and exercises the implementation's normalized API. Live LLM calls are out of
  scope for this suite (per spec §9).
