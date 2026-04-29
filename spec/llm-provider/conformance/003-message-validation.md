# 003 — Message Validation

Table-style fixture: each case is a malformed `complete()` input that MUST raise
`provider_invalid_request` BEFORE the implementation reaches the wire (i.e., before any HTTP call
to the provider).

The fixture format is documented in fixture 001's `.md`; the table-style extension uses a `cases:`
list, each with a `name`, `description`, `call`, and `expected.raises` block.

**Spec sections exercised:**

- §3 per-role constraints (system position, content emptiness, assistant content/tool_calls
  invariant, last-message rule).
- §3 `tool_call_id` matching against earlier `assistant` `ToolCall.id`.
- §4 Tool definition uniqueness within a single call's `tools`.
- §5 `complete()` validation timing — implementations MUST validate before sending.
- §7 `provider_invalid_request` category.

**Cases:**

1. `system_message_in_middle` — a `system` message appears after the first message position.
2. `tool_message_without_matching_assistant` — a `tool` message bears a `tool_call_id` that
   doesn't match any earlier `assistant` `ToolCall.id`.
3. `duplicate_tool_names` — two `Tool` entries share a `name`.
4. `empty_user_content` — `user` message with empty `content`.
5. `assistant_with_neither_content_nor_tool_calls` — `assistant` message with empty content and
   no tool calls.
6. `last_message_assistant` — the message list ends with an `assistant` message instead of
   `user` or `tool`.

**What passes:**

- Each case raises an error with category `provider_invalid_request`.
- No HTTP call is made to the mock provider (the mock has no responses configured; if the
  implementation reached the wire, the harness would observe a missing-canned-response failure).

**What fails:**

- The implementation defers the validation to the provider (sends the malformed request and
  surfaces a `provider_invalid_request` from the wire response). The category is correct but the
  timing is wrong: pre-send validation is required.
- A different category is raised (e.g., `provider_invalid_response`).
