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
   (conformance-adapter §5.5): each observer keeps its own copy of the flag, so the Langfuse setting
   leaves the OTel side at its default `true` unless an `otel_observer` block sets it too.
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

## The caller-metadata assertion on case 1

§8.4.2 maps each caller-supplied metadata entry to `observation.metadata.<key>` on **EVERY** Observation,
with the same propagation rationale as `correlation_id`. That row is unscoped where the table scopes its
other rows explicitly, which makes the unscoped wording deliberate rather than loose.

Fixture 027 pins it on Span and Generation observations. Nothing pinned it on a **Tool** observation, and an
implementation shipped with the set present on its OTel tool span and absent from the Langfuse one: two
bundled observers disagreeing about the same event, which no fixture caught.

Case 1 now supplies `caller_metadata` and asserts those keys in the Tool observation's `metadata`. The
`metadata:` block is a subset match (conformance-adapter §5.5), so listing a key asserts its presence and
value without pinning the observation's other cross-cutting keys. An implementation that omits the caller
set on the Tool observation fails on both keys.

It sits on the **success** case rather than a failure case deliberately: the assertion is about §8.4.2's
scope alone, and putting it on a failure case would entangle it with §8.4.6's error fields and §8.7's cap.
The caller set is not payload-gated, so the case's existing `disable_provider_payload: false` is incidental
to it rather than required by it.
