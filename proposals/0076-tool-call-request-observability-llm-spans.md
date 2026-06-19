# 0076: Tool-Call Request Observability on LLM Spans

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-18
- **Accepted:** 2026-06-19
- **Targets:** spec/observability/spec.md (§5.5 — a new first-class, queryable attribute family on the existing `openarmature.llm.complete` span surfacing the tool calls the model *requested* in its completion: `openarmature.llm.tool_calls.count`, `openarmature.llm.tool_calls.names`, `openarmature.llm.tool_calls.ids`; §5.5.5 — retire the "first-class tool-call observability is a separate forthcoming proposal" forecast in *Tool-call serialization*, which this proposal fulfills); plus new conformance fixtures under `spec/observability/conformance/`.
- **Related:** 0049 (typed `LlmCompletionEvent` — the model *requesting* tools via `tool_calls`; this proposal renders that request as first-class span attributes), 0057 (`LlmCompletionEvent` field-set extension), 0006 / 0025 (llm-provider — the `ToolCall` record shape and `tool_choice` request-side control), 0050 (the `openarmature.llm.attempt_index` precedent — an OA-namespace LLM-span attribute with no upstream GenAI semconv equivalent), 0063 (tool-**execution** observability — the *execution*-side complement this splits cleanly against; linked by the `ToolCall.id`)
- **Supersedes:**

## Summary

Promotes the tool calls a model **requests** in its completion from buried free-form payload to
**first-class, queryable span attributes** on the existing `openarmature.llm.complete` span.

Today (observability §5.5.5, *Tool-call serialization*) an assistant message's `tool_calls` are
serialized *into* the output payload attribute (`openarmature.llm.output.content`, JSON-encoded,
gated by `disable_provider_payload`). They are not independently queryable, and when payload is
disabled (the default) they vanish from the span entirely. §5.5.5 already flags that "first-class
tool-call observability is a separate forthcoming proposal" — this is it.

The proposal adds three attributes on the LLM completion span:

- `openarmature.llm.tool_calls.count` — how many tool calls the model requested,
- `openarmature.llm.tool_calls.names` — the requested tool names, in order,
- `openarmature.llm.tool_calls.ids` — the requested `ToolCall.id`s, in order (the linkage to a
  later tool execution).

These are **identity, not payload** — ungated by `disable_provider_payload`, so "which tools did
this completion ask for, and how many" survives with payloads off. The tool **arguments** stay in
`openarmature.llm.output.content` (payload, gated) — not duplicated here.

This is the **request** side. It composes with — and is deliberately distinct from — proposal
0063's tool-**execution** observability (a separate `openarmature.tool.call` span for the caller
*running* a tool). The split is clean and maps onto the attribute namespace; see *Relationship to
0063* below.

## Motivation

**The model's tool requests aren't queryable.** An agent or RAG pipeline that uses tools needs to
answer operational questions over its LLM spans: *which completions requested tools, which tools,
how many calls per completion, did this tool-request ever get executed?* Today none of that is
answerable from the span without parsing the JSON-encoded output payload — and the payload is
off by default (`disable_provider_payload = True`, §5.5.4). So in the default posture the span
signals *that* the model requested tools (its `finish_reason`, §5.5.3) but not *which* ones, *how
many*, or their *ids* — that identity is absent, buried in the suppressed payload. The request lives in the typed `LlmCompletionEvent` (0049/0057), but only
as part of the serialized message content, not as a first-class dimension.

**Names and ids are identity, not payload.** A tool *name* is a function identifier from the
application's own tool schema (llm-provider §4 `Tool.name`), and a `ToolCall.id` is a correlation
token — neither is user content or external data the way tool *arguments* are. Treating
count/names/ids as ungated identity attributes (the same class as `openarmature.llm.model` or
`openarmature.llm.attempt_index`) lets tool-request visibility coexist with a payload-off privacy
posture, which is exactly the common production configuration. The arguments remain payload and
remain gated.

**It completes the request half of the agent observability picture.** With these attributes the
LLM completion span answers "what tools did the model ask for," and proposal 0063's
`openarmature.tool.call` span answers "what happened when the caller ran one" — linked by the
`ToolCall.id`. A user-authored `call_llm → execute_tools → call_llm` graph is then observable on
both halves without payload exposure, on OA's vendor-neutral terms.

## Proposed change

### observability §5.5 — tool-call request attributes on the LLM completion span

A new attribute family on the `openarmature.llm.complete` span (per §5.5), populated from the
completion's assistant-message `tool_calls` (llm-provider §3 — the ordered list of `ToolCall`
records the model is requesting):

| Attribute | Type | Description |
|---|---|---|
| `openarmature.llm.tool_calls.count` | int | The number of tool calls the model requested in this completion. A convenience scalar for aggregation (equal to the length of `.names`). Emitted only on a tool-calling completion (count ≥ 1); **absent** when the completion requested no tools. |
| `openarmature.llm.tool_calls.names` | string array | The requested tool names, in request order — each the `Tool.name` (llm-provider §4) of a `ToolCall`. Absent when no tools were requested. |
| `openarmature.llm.tool_calls.ids` | string array | The requested `ToolCall.id`s (llm-provider §3), in the same order as `.names` (`names[i]` and `ids[i]` describe the same requested call). The linkage to a downstream tool execution: a 0063 `ToolCallEvent` / `openarmature.tool.call` span carrying `tool_call_id = X` satisfies the request whose id is `X` here. Absent when no tools were requested. |

**Identity, not payload — ungated.** These three attributes are NOT gated by
`disable_provider_payload` (§5.5.4): tool names and call ids are identifiers, not provider
payload. The tool **arguments** are payload and are NOT added here — they remain in
`openarmature.llm.output.content` (§5.5.1), gated and truncated by the existing rules. Rendering
the names/ids/count alongside a disabled payload is the intended, default-posture behavior.

**Parallel arrays, request order.** `.names` and `.ids` are equal-length and index-aligned, in the
order the model emitted the calls. `.count` equals their length. This mirrors the ordered
`tool_calls` list of llm-provider §3 and the determinism guarantees of §5.5.6 (same completion ⇒
same attribute values).

**OA-namespace, no GenAI mirror.** Unlike the §5.5.3 GenAI response attributes, these are
OA-namespace (`openarmature.llm.*`) with no `gen_ai.*` counterpart, for the same reason
`openarmature.llm.attempt_index` (proposal 0050) is: the upstream OTel GenAI semantic conventions
carry the model's output tool calls inside the structured `gen_ai.output.messages` attribute, not
as a flat per-request count/names/ids surface, so there is no upstream attribute to adopt or
mirror. (The `gen_ai.tool.*` family is upstream-defined for the **`execute_tool`** span — the
execution side, proposal 0063's domain — not the chat-completion span; reusing it here would
conflate request with execution. See *Relationship to 0063*.) The upstream output representation
MUST be re-verified at Accept (see *Open questions*).

### observability §5.5.5 — retire the forecast

The *Tool-call serialization* paragraph notes "(First-class tool-call observability is a separate
forthcoming proposal.)" This proposal fulfills that forecast for the request side. At Accept the
parenthetical is updated to point at the new attribute family (names/ids/count are now first-class;
the serialized arguments remain in the output payload as described there).

### Relationship to 0063 (request vs execution)

0076 and 0063 are complementary halves, split cleanly by **moment**, **span**, and **namespace** —
there is no overlap:

| | **0076 — request side (this proposal)** | **0063 — execution side** |
|---|---|---|
| What | the model *requesting* tools in its completion | the caller *executing* a tool |
| Where | attributes on the existing `openarmature.llm.complete` span | a separate `openarmature.tool.call` span |
| Namespace | `openarmature.llm.tool_calls.*` (request) | `openarmature.tool.*` (execution; mirrors `gen_ai.tool.*`) |
| Payload | names/ids/count ungated; arguments stay in `output.content` | `arguments` / `result` payload-gated on the tool span |
| Linkage | the requested `ToolCall.id`s (`.ids`) → | ← `tool_call_id` on the `ToolCallEvent` / tool span |

A request may be executed later (or never, or several times). The two surfaces are joined only by
the `ToolCall.id`. This proposal does not touch the execution side; 0063 does not touch the LLM
completion span.

### No typed-event or Langfuse change

The typed `LlmCompletionEvent` already carries the requested tool calls within its output messages
(0049/0057); this proposal is **span-rendering only** and adds no field to the observer-event union
(graph-engine §6 is untouched). A Langfuse mapping for the request-side tool calls is **out of
scope** and tracked as future work — the OTel queryable-attribute gap is the concern here; the
Langfuse Generation `output` already carries the calls, and a dedicated Langfuse surface can follow
if a need is demonstrated.

## Conformance test impact

New fixtures under `spec/observability/conformance/` (numbered at Accept):

- **llm-tool-call-request-attributes** — a completion whose assistant message requests two tools
  emits `openarmature.llm.tool_calls.count = 2`, `.names = [t1, t2]`, `.ids = [id1, id2]` on the
  `openarmature.llm.complete` span, index-aligned and in request order.
- **llm-tool-call-request-absent** — a completion with no tool calls emits **none** of the three
  attributes (not `count = 0`).
- **llm-tool-call-request-survives-payload-gating** — with `disable_provider_payload = True`
  (default), the count/names/ids attributes are still emitted while `openarmature.llm.output.content`
  (carrying the arguments) is suppressed; with the flag `False`, both are present.

## Versioning

**MINOR bump** (pre-1.0). Additive and observability-only: three new OA-namespace span attributes
on an existing span plus a fulfilled-forecast edit to §5.5.5; no change to the observer-event union,
the LLM completion contract, or any existing attribute. Spec version target deferred to Accept.

## Alternatives considered

1. **Leave tool calls in the output payload (`output.content`) only.** Reject — not independently
   queryable (requires parsing JSON), and absent entirely under the default payload-off posture.
   The whole gap is that the most basic tool-request fact disappears exactly when privacy is on.

2. **Use `gen_ai.tool.*` names on the LLM span.** Reject — those are upstream-defined for the
   `execute_tool` span (the execution side, 0063). Putting them on the chat-completion span would
   conflate request with execution and collide with 0063's mirror. The request side has no flat
   upstream `gen_ai.*` equivalent (upstream uses structured `gen_ai.output.messages`), so
   OA-namespace is correct — the `openarmature.llm.attempt_index` (0050) precedent.

3. **Also render the arguments as a flat attribute here.** Reject — arguments are payload and
   already live in `openarmature.llm.output.content` (gated, truncated). A second copy would
   shadow that surface, double the truncation problem, and blur the identity-vs-payload line that
   makes names/ids/count safe to leave ungated.

4. **Add a Langfuse mapping in this proposal.** Defer (tracked as future work). The Langfuse
   Generation `output` already carries the requested calls; the queryable-OTel-attribute gap is the
   real one. A dedicated Langfuse request-side surface can follow if demonstrated.

5. **Promote a first-class `tool_calls` field on `LlmCompletionEvent` (graph-engine §6).** Reject
   for this proposal — the event already carries the calls in its output messages, and the gap is
   span queryability, not the event. A future proposal may promote a typed field if the
   queryable-observer pattern (0048) shows the need; out of scope here.

6. **Emit `count = 0` (and empty arrays) on non-tool completions.** Reject — most completions
   request no tools, so emitting the family on every span is pure noise. Absence cleanly means "no
   tools requested"; `count` is emitted only when ≥ 1, matching the §5.5 omit-when-empty convention.

## Open questions

- **Upstream output representation (verify at Accept).** The OA-namespace rationale rests on the
  current OTel GenAI semconv having no flat chat-span attribute for the model's requested tool
  calls (carrying them in the structured `gen_ai.output.messages` instead). This MUST be
  re-verified against the live GenAI semantic conventions at Accept, per the external-fact
  verification discipline, and recorded in `docs/compatibility.md`. (Consistent with proposal
  0063's finding that the `gen_ai.tool.*` family is scoped to the `execute_tool` span.)

## Out of scope

- **Tool execution observability** — proposal 0063 (the `openarmature.tool.call` span +
  `ToolCallEvent` / `ToolCallFailedEvent`). This proposal is request-side only.
- **The agent tool-loop / orchestration** — OA does not select, run, loop, or feed back tools
  (llm-provider §1). This is an observability surface, not an orchestration one.
- **A Langfuse request-side mapping** — tracked as future work; the Generation `output` already
  carries the calls.
- **A first-class typed `tool_calls` field on the observer event** — the event carries the calls
  in its output messages; a typed field is a possible future proposal.
- **`gen_ai.tool.*` adoption** — that family is the execution-side (`execute_tool`) surface and is
  proposal 0063's concern, to be reconciled against the GenAI de-facto-standard carve-out
  (`GOVERNANCE.md`, proposal 0073) at 0063's Accept.
