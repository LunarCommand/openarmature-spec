# 098 — Langfuse Tool observation

Verifies observability §8.4.6 (proposal 0063): tool executions render as Langfuse's
dedicated `Tool` observation type, not a `Generation`.

## Spec coverage

- §8.4.6 — the observation type is `Tool` (`asType: "tool"`), nested under the
  calling node's `Span`.
- `tool.input` / `tool.output` payload-gated per `disable_provider_payload`;
  `tool_name` / `tool_call_id` in metadata.
- Level — `DEFAULT` on `ToolCallEvent`; `ERROR` (with `error_type`, and `error_message` when the
  payload flag permits it
  in metadata) on `ToolCallFailedEvent`.

## Cases

1. `tool_execution_renders_dedicated_tool_observation` — success (payload on) →
   `Tool` observation, `DEFAULT`, input / output populated, identity in metadata.
2. `failed_tool_execution_renders_error_level` — failure → `Tool` observation at
   `ERROR` with `error_type` / `error_message`. Both of these cases set
   `langfuse_observer: {disable_provider_payload: false}`, the per-observer convention
   (conformance-adapter §5.5): the Langfuse observer keeps its own copy of the flag, so a top-level
   setting configures only the OTel side and would leave Langfuse at its default `true`.
   `error_message` is harvested exception text gated by that flag (observability §5.5.4, proposal
   0118), so the failure case sets it explicitly rather than relying on the default. `error_type` is
   not gated.
3. `failed_tool_default_posture_withholds_message_without_smuggling` — the same failure under the
   **default** posture (no flag set): `error_type` present, `error_message` withheld, and
   `statusMessage: null`. Detailed under *Default-posture failure and anti-smuggling* below.

## Anti-cases

- Rendering the tool call as a `Generation` with `metadata.operation = "tool"`.
- Populating `input` / `output` under the default payload-off posture.

**Default-posture failure and anti-smuggling (proposal 0118).** A third case,
`failed_tool_default_posture_withholds_message_without_smuggling`, runs the failure under the default
posture (`disable_provider_payload` unset, so `true`). It asserts `error_type` present, `error_message`
withheld via `metadata_absent`, and `statusMessage: null`. The last of those gates observability §6's Tool
anti-smuggling clause for **every** adapter: fixture 158's shared-provider tool case is restricted to
non-detection-capable adapters, since a detection-capable one raises before emitting anything, so this case
carries the clause's only coverage on detection-capable adapters. It also shows why `error_type` is not
gated: a Tool failure has no error category, so without the type a failed Tool observation under the default
posture would carry no failure discriminator at all.
