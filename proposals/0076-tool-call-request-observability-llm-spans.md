# 0076: Tool-Call Request Observability on LLM Spans

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-18
- **Accepted:** 2026-06-19
- **Targets:** spec/observability/spec.md (§5.5.1 — a new **gated** output-payload attribute `openarmature.llm.output.tool_calls` serializing the model's output tool calls as `[{id, name, arguments}]`, the output-side counterpart to the existing input tool-call serialization — fixing the asymmetry where the output payload (`output.content`) is text-only and omitted for tool-call-only completions; §5.5.10 — **ungated** identity projections `openarmature.llm.output.tool_calls.count` / `.names` / `.ids` for payload-off visibility + queryable filtering; §5.5.5 — note that `output.tool_calls` reuses the input tool-call encoding, and retire the "first-class tool-call observability is a separate forthcoming proposal" forecast which this proposal fulfills); spec/graph-engine/spec.md (§6 — `LlmCompletionEvent` gains an `output_tool_calls` field carrying the assistant message's output tool calls, the source the observability span attributes render from); plus new conformance fixtures under `spec/observability/conformance/`.
- **Related:** 0049 (typed `LlmCompletionEvent` — the model *requesting* tools via `tool_calls`), 0057 (`LlmCompletionEvent` field-set extension), 0006 / 0025 (llm-provider — the `ToolCall` record shape and `tool_choice` request-side control), 0050 (the `openarmature.llm.attempt_index` precedent — an OA-namespace LLM-span attribute with no upstream GenAI semconv equivalent), 0063 (tool-**execution** observability — the *execution*-side complement this splits cleanly against; linked by the `ToolCall.id`)
- **Supersedes:**

## Summary

A model's **tool-call request is part of its output** — yet the observability layer has no
output-side home for it. The output payload attribute `openarmature.llm.output.content` (§5.5.1) is
the assistant's **text** content only, and is omitted entirely for a tool-call-only completion
(§5.5.1) — so the tool calls the model produces are not captured on the output side at all. They
surface only incidentally, on a *later* turn, when the assistant message is replayed as input
history (`openarmature.llm.input.messages`, §5.5.5). §5.5.5 already flags that "first-class
tool-call observability is a separate forthcoming proposal" — this is it.

This proposal gives the model's output tool calls their proper output-side home, in two layers on
the existing `openarmature.llm.complete` span:

- **`openarmature.llm.output.tool_calls`** (§5.5.1) — a **gated** payload attribute serializing the
  full output tool calls (`[{id, name, arguments}]`), the output-side counterpart to the input
  tool-call serialization. This is where the request (including arguments) lives.
- **`openarmature.llm.output.tool_calls.count` / `.names` / `.ids`** (§5.5.10) — **ungated**
  identity projections, so *which* tools the model requested (how many, and their ids) stays visible
  with payloads off (the default posture) and is queryable without parsing JSON.

This is the **request** side, complementary to proposal 0063's tool-**execution** observability (a
separate `openarmature.tool.call` span for the caller *running* a tool); the two are linked by
`ToolCall.id`.

## Motivation

**The model's output tool calls have no output-side home.** The §5.5.1 output payload is
`output.content` — the assistant's response *text*, "emitted only when `message.content` is
non-empty (assistant messages with only `tool_calls` and empty content MUST NOT emit this
attribute)." A tool-call-only completion writes no text, so `output.content` is absent, and it never
held the tool calls anyway (it is text). The input side serializes full messages — including
`tool_calls` — into `openarmature.llm.input.messages` (§5.5.5), but that captures the model's tool
calls only *incidentally*, on the next turn, once the assistant message is replayed as history. On
the turn that actually produces the request, the tool calls appear in **no** payload attribute. The
span shows `finish_reason` indicating tool calls were requested (§5.5.3) and nothing about *which*.

**Identity must survive the payload-off default.** A tool *name* is a function identifier from the
caller's own tool schema (llm-provider §4 `Tool.name`) and a `ToolCall.id` is a correlation token —
neither is user content the way *arguments* are. Surfacing count / names / ids as ungated identity
(the class of `openarmature.llm.model` or `openarmature.llm.attempt_index`) lets "which tools, how
many" be answered with `disable_provider_payload` on — the common production posture — and queried
without parsing JSON.

**The arguments belong on the output side too — gated.** Beyond identity, the full request
(arguments included) deserves the same treatment the input side already gives tool calls: a
serialized, payload-gated attribute. `openarmature.llm.output.tool_calls` is that — the output-side
counterpart to the input tool-call serialization, closing the asymmetry where `output.content`
carried only text.

**It completes the request half of the agent observability picture.** With these attributes the LLM
completion span answers "what tools did the model ask for" (gated full + ungated identity), and
proposal 0063's `openarmature.tool.call` span answers "what happened when the caller ran one" —
linked by the `ToolCall.id`.

## Proposed change

### observability §5.5.1 — output tool-call payload attribute

Add `openarmature.llm.output.tool_calls` to the §5.5.1 input/output payload attributes:

- `openarmature.llm.output.tool_calls` — string. The assistant message's output `tool_calls`
  (llm-provider §3), JSON-encoded as `[{id, name, arguments}, ...]` — the same encoding the §5.5.5
  *Tool-call serialization* rule defines for `tool_calls` inside `openarmature.llm.input.messages`,
  applied to the output side. Emitted only when the response carries tool calls (analogous to
  `output.content`'s emit-only-when-non-empty rule). Gated by `disable_provider_payload` (§5.5.4)
  and subject to the §5.5.5 truncation contract, like the other payload attributes — it carries the
  argument values, which are payload.

This is the output-side counterpart to the input tool-call serialization: `output.content` (text) +
`output.tool_calls` (tool calls) together make the output payload symmetric with the full-message
input payload.

### observability §5.5.10 — ungated tool-call identity

A new sub-subsection: the **identity** projections of the output tool calls, on the
`openarmature.llm.complete` span, **not** gated by `disable_provider_payload`:

| Attribute | Type | Description |
|---|---|---|
| `openarmature.llm.output.tool_calls.count` | int | The number of tool calls the model requested. A convenience scalar (equal to the length of `.names`). Emitted only on a tool-calling completion (count ≥ 1); absent otherwise. |
| `openarmature.llm.output.tool_calls.names` | string array | The requested tool names, in request order (each the `Tool.name`, llm-provider §4, of a `ToolCall`). Absent when no tools were requested. |
| `openarmature.llm.output.tool_calls.ids` | string array | The requested `ToolCall.id`s (llm-provider §3), in the same order as `.names` (`names[i]` / `ids[i]` describe the same call). The linkage to a downstream tool execution. Absent when no tools were requested. |

`.names` and `.ids` are equal-length and index-aligned, in the order the model emitted the calls;
`.count` equals their length — mirroring the ordered `tool_calls` list (llm-provider §3), subject to
the §5.5.6 determinism guarantee.

**Identity vs. payload.** These three are identity (tool names, call ids, a count) — **ungated**, so
they render with `disable_provider_payload` on. The full **arguments** are payload and live in the
gated `openarmature.llm.output.tool_calls` (§5.5.1), not here. So with payload off you see *which*
tools were requested; with payload on you additionally get the arguments. Neither lives in
`output.content` (text only).

**OA-namespace, no GenAI mirror.** `openarmature.llm.output.tool_calls*` is OA-namespace with no
`gen_ai.*` counterpart — the same situation as `openarmature.llm.attempt_index` (proposal 0050).
Upstream carries the model's output tool calls as `tool_call` *parts* inside the structured
`gen_ai.output.messages` attribute, not as a flat per-call serialization or a flat count / names /
ids surface, so there is no upstream attribute to adopt or mirror. (The `gen_ai.tool.*` family is
upstream-defined for the **`execute_tool`** span — the execution side, proposal 0063's domain — not
the chat-completion span.) Verified against the GenAI semantic-conventions registry at Accept
(recorded in `docs/compatibility.md`).

### observability §5.5.5 — serialization note + retire the forecast

The *Tool-call serialization* paragraph (which defines the `[{id, name, arguments}]` encoding for
`tool_calls` in `input.messages`) notes that `openarmature.llm.output.tool_calls` (§5.5.1) reuses
the same encoding for the output side. Its "(First-class tool-call observability is a separate
forthcoming proposal.)" forecast is retired — fulfilled for the request side by `output.tool_calls`
(gated full) + the §5.5.10 identity projections.

### Relationship to 0063 (request vs execution)

0076 and 0063 are complementary halves, split cleanly by **moment**, **span**, and **namespace**:

| | **0076 — request side (this proposal)** | **0063 — execution side** |
|---|---|---|
| What | the model *requesting* tools in its completion (output) | the caller *executing* a tool |
| Where | attributes on the existing `openarmature.llm.complete` span | a separate `openarmature.tool.call` span |
| Namespace | `openarmature.llm.output.tool_calls*` | `openarmature.tool.*` (mirrors `gen_ai.tool.*`) |
| Payload | full args gated in `output.tool_calls`; identity (`.count`/`.names`/`.ids`) ungated | `arguments` / `result` payload-gated on the tool span |
| Linkage | the requested `ToolCall.id`s (`.ids`) → | ← `tool_call_id` on the `ToolCallEvent` / tool span |

A request may be executed later (or never, or several times). The two surfaces are joined only by
the `ToolCall.id`. This proposal does not touch the execution side; 0063 does not touch the LLM
completion span.

### Typed-event field (graph-engine §6); no Langfuse change

The OTel span attributes render from the typed `LlmCompletionEvent` (observability §5.5.7), and that
event did **not** carry the model's output tool calls — it has `output_content` (the response *text*,
null for a tool-call-only response) but no output tool-call field. So this proposal adds an
`output_tool_calls` field to `LlmCompletionEvent` (graph-engine §6): the assistant message's output
tool calls in typed-event-native form, populated unconditionally, the source the §5.5.1 gated
serialization and the §5.5.10 identity projections render from. (The event already carried *input*
tool calls within `input_messages` as history, and output *text* in `output_content` — never the
output tool calls themselves; that was the gap.) No other observer-event-union change. A Langfuse
mapping for the request-side tool calls (e.g. on the Generation observation's output) is **out of
scope** and tracked as future work.

## Conformance test impact

New fixtures under `spec/observability/conformance/` (numbered at Accept):

- **llm-tool-call-request-attributes** — a completion whose assistant message requests two tools
  emits `openarmature.llm.output.tool_calls.count = 2`, `.names = [t1, t2]`, `.ids = [id1, id2]` on
  the `openarmature.llm.complete` span, index-aligned and in request order.
- **llm-tool-call-request-absent** — a completion with no tool calls emits **none** of the
  attributes (not `count = 0`, no `output.tool_calls`).
- **llm-tool-call-request-survives-payload-gating** — with `disable_provider_payload = True`
  (default), the ungated identity (`count` / `names` / `ids`) is still emitted while the gated
  `openarmature.llm.output.tool_calls` (carrying the arguments) is suppressed; with the flag
  `False`, the gated `output.tool_calls` is also present.

## Versioning

**MINOR bump** (pre-1.0). Additive: a new `output_tool_calls` field on the existing
`LlmCompletionEvent` (graph-engine §6); one new gated payload attribute (§5.5.1) plus three ungated
identity attributes (§5.5.10) on the existing LLM span; a fulfilled-forecast edit to §5.5.5. The new
event field is additive (existing fields unchanged); no change to the LLM completion contract or any
existing attribute. Spec version target deferred to Accept.

## Alternatives considered

1. **Identity only — leave the arguments unserialized (the original draft of this proposal).**
   Reject — that leaves the model's output tool-call *arguments* with no output-side home at all
   (`output.content` is text, omitted for tool-call-only). The gated `output.tool_calls` gives them
   the same serialized, payload-gated home the input side already provides, closing the asymmetry;
   identity-only would have shipped a half-surface.

2. **Put the arguments in `output.content` (or claim they already are).** Reject — factually wrong:
   `output.content` is the assistant's text and is omitted for tool-call-only completions, so it
   never carries tool calls. A dedicated `output.tool_calls` is the correct home.

3. **Use `gen_ai.tool.*` names on the LLM span.** Reject — those are upstream-defined for the
   `execute_tool` span (the execution side, 0063). Putting them on the chat-completion span would
   conflate request with execution. The request side has no flat upstream `gen_ai.*` equivalent
   (upstream uses structured `gen_ai.output.messages`), so OA-namespace is correct — the
   `openarmature.llm.attempt_index` (0050) precedent.

4. **One attribute, not two (only the gated full, or only the ungated identity).** Reject — both
   are needed: the gated `output.tool_calls` carries the arguments (suppressed when payload is off),
   and the ungated identity keeps "which tools / how many / ids" visible *under* the default
   payload-off posture and queryable without parsing JSON. Collapsing to one loses either the
   arguments or the payload-off visibility.

5. **Add a Langfuse mapping in this proposal.** Defer (tracked as future work). The OTel
   attribute gap is the immediate one; a dedicated Langfuse request-side surface can follow.

6. **A separate typed event variant (e.g. `ToolCallRequestedEvent`) instead of a field on
   `LlmCompletionEvent`.** Reject — the tool-call request is part of the completion, so the natural
   home is a field on the existing `LlmCompletionEvent` (`output_tool_calls`, added by this proposal
   — see *Typed-event field*), not a new event variant. (Contrast 0063's `ToolCallEvent`, which is
   the separate tool *execution*, a distinct event with its own lifecycle.)

7. **Emit `count = 0` (and empty arrays / empty `output.tool_calls`) on non-tool completions.**
   Reject — most completions request no tools, so emitting the family on every span is pure noise.
   Absence cleanly means "no tools requested"; the attributes are emitted only when ≥ 1, matching
   the §5.5 omit-when-empty convention.

## Open questions

- **Upstream output representation (verified at Accept).** The OA-namespace rationale rests on the
  GenAI semconv carrying the model's output tool calls as `tool_call` parts inside
  `gen_ai.output.messages` (no flat per-call or count/names/ids surface). Verified against the live
  GenAI semantic-conventions registry at Accept and recorded in `docs/compatibility.md`. (Consistent
  with proposal 0063's finding that the `gen_ai.tool.*` family is scoped to the `execute_tool` span.)

## Out of scope

- **Tool execution observability** — proposal 0063 (the `openarmature.tool.call` span +
  `ToolCallEvent` / `ToolCallFailedEvent`). This proposal is request-side only.
- **The agent tool-loop / orchestration** — OA does not select, run, loop, or feed back tools
  (llm-provider §1). This is an observability surface, not an orchestration one.
- **A Langfuse request-side mapping** — tracked as future work (the Generation observation's output
  is the natural home).
- **A first-class typed `tool_calls` field on the observer event** — the event carries the calls in
  its output messages; a typed field is a possible future proposal.
- **`gen_ai.tool.*` adoption** — that family is the execution-side (`execute_tool`) surface and is
  proposal 0063's concern, to be reconciled against the GenAI de-facto-standard carve-out
  (`GOVERNANCE.md`, proposal 0073) at 0063's Accept.
