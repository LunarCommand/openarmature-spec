# OpenArmature Specification

[![CI](https://github.com/LunarCommand/openarmature-spec/actions/workflows/validate-markdown.yaml/badge.svg)](https://github.com/LunarCommand/openarmature-spec/actions/workflows/validate-markdown.yaml)
[![spec](https://img.shields.io/github/v/release/LunarCommand/openarmature-spec?label=spec&color=9D4EDD)](https://github.com/LunarCommand/openarmature-spec/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](https://github.com/LunarCommand/openarmature-spec/blob/main/LICENSE)

Language-agnostic behavioral specification for **OpenArmature**, a workflow
framework for LLM pipelines and tool-calling agents. This repository holds the
specification text, conformance fixtures, governance rules, and numbered
RFC-style proposals. **No implementation code lives here.** Implementations
are in sibling repositories.

---

## Overview

OpenArmature specifies a graph-engine-based workflow framework: typed state,
async nodes, conditional routing, per-field reducers, subgraph composition,
fan-out, middleware, checkpointing, and observer hooks. Behavior is defined
here in prose and verified by canonical conformance fixtures; idiomatic
implementations live in sibling repositories.

OpenArmature is **not**:

- A Python (or any other language) framework. The reference Python
  implementation is at [openarmature-python](https://github.com/LunarCommand/openarmature-python).
- A workflow orchestrator. For long-running, multi-process, multi-day
  workflows, look at Temporal, Prefect, Dagster, or Airflow.
- A model gateway. OpenArmature defines a thin LLM-provider abstraction for
  use within graphs; it doesn't manage credentials, routing, or fallback
  across providers.
- A hosted product.

---

## Why OpenArmature

Production LLM work splits awkwardly between two camps. Agent frameworks built
around the tool-calling loop impose a conversation abstraction on
non-conversation work, forcing deterministic multi-stage pipelines through
message-list state and LLM-driven control flow. Pipeline orchestrators built
for deterministic ETL have no LLM primitives, no prompt management, no LLM
observability, no evaluation. The work in the middle (content analysis,
multi-source research, structured extraction, large-scale enrichment) mostly
ends up shoehorned into one camp or glued together from parts of both.

The design insight is that pipelines and agents share primitives. Typed state
evolving across async nodes, conditional and static edges, reducers,
subgraphs, observability: both shapes need the same substrate and differ only
in node content. A graph engine that's agnostic about whether control flow is
LLM-driven or deterministic serves both equally.

Both pipelines and tool-calling agents are first-class. An agent is a graph
whose LLM-driven conditional edge loops back to the LLM node until a stop
condition fires. Because agents are graphs and graphs compose as subgraphs, a
"pipeline" in OpenArmature can be a sequence of deterministic stages, a
single agent, or several agents running in sequence or in parallel through the
same fan-out and middleware primitives.

The specification is informed by seven production projects across content
analysis, creator sourcing, multi-stage extraction, GPU ML pipelines,
tool-calling agents, and MCP integration. The full thesis, distilled patterns,
and architecture are in [`docs/openarmature.md`](docs/openarmature.md).

---

## Status

### Accepted capabilities

Scope cells summarize each capability's headline shape (≤500 chars target). Detail
lives in each capability spec's §1 *Purpose* and in [`CHANGELOG.md`](CHANGELOG.md).

| Capability | Introduced | Latest | Fixtures | Scope |
|---|---|---|---|---|
| [graph-engine](spec/graph-engine/spec.md) | 0.1.0 | 0.70.0 | 38 | Typed state, async nodes, conditional/static edges, 8 canonical reducers, subgraph composition, observer hooks (bounded `drain` + per-invocation `drain_events_for`), three `invoke()` outcomes (completed / errored / suspended), typed `LlmCompletionEvent` + `LlmFailedEvent` + `EmbeddingEvent` + `EmbeddingFailedEvent` + `RerankEvent` + `RerankFailedEvent` + `ToolCallEvent` + `ToolCallFailedEvent` event variants alongside `NodeEvent` on the observer event union (success / failure variants mutually exclusive per call), opt-in tool-call instrumentation scope. |
| [pipeline-utilities](spec/pipeline-utilities/spec.md) | 0.5.0 | 0.66.0 | 74 | Middleware (canonical retry + timing + failure isolation), parallel fan-out (per-instance resume with success/error discrimination + state migration), checkpointing (shares persistence with suspension), parallel branches. |
| [llm-provider](spec/llm-provider/spec.md) | 0.4.0 | 0.42.0 | 58 | Stateless LLM-provider abstraction with canonical error categories, image + reasoning content blocks, structured output via `response_schema`, `tool_choice` request-side control, wire-format mapping catalog (OpenAI-compatible / Anthropic / Gemini), `RuntimeConfig` with seven declared sampling params + extras pass-through, optional call-level retry. |
| [observability](spec/observability/spec.md) | 0.7.0 | 0.70.0 | 109 | OpenTelemetry + Langfuse backend mappings (LLM completion spans + Langfuse Generation observations; embedding spans + Langfuse dedicated `Embedding` observations; rerank spans + Langfuse dedicated `Retriever` observations; tool-execution spans + Langfuse dedicated `Tool` observations), GenAI metrics, cross-backend correlation IDs, caller-supplied invocation metadata (`openarmature.user.*` span attributes + symmetric `get_invocation_metadata()` read), provider-payload + GenAI semconv attributes (default-off payload via `disable_provider_payload`), prompt-identity / prompt-group linkage, queryable observer pattern, suspension status mapping. |
| [prompt-management](spec/prompt-management/spec.md) | 0.15.0 | 0.63.0 | 34 | Named/versioned template fetch + render; composite backends with infrastructure-only fallback; `PromptGroup` tracing primitive; strict-undefined-by-default variable injection; typed `Prompt.sampling` + `Prompt.observability_entities`; Chat-prompt variant (`chat_template: list[ChatSegment]` with content-blocks + placeholders for multimodal authoring); `LabelResolver` for deployment-time A/B label override. |
| [sessions](spec/sessions/spec.md) | 0.33.0 | 0.33.0 | 13 | Typed cross-invocation state under caller-supplied `session_id`; `SessionStore` protocol (`load` / `save` / `delete` / `list`); full-state + projected `SessionState` modes; auto-save-on-completion; schema migration; last-write-wins concurrency with optimistic / pessimistic extension points; observability propagation via `openarmature.session_id`. |
| [suspension](spec/suspension/spec.md) | 0.47.0 | 0.47.0 | 15 | Node-side `suspend(descriptor)` operation that pauses an invocation, persists state under a typed signal descriptor, and returns a structured suspended outcome distinct from completion / error; resume via `invoke(resume_invocation, signal_payload)` with shallow-overlay merge; load-bearing architectural consequence is stateless workers (pause on machine A, resume on machine B). |
| [harness](spec/harness/spec.md) | 0.49.0 | 0.49.0 | 11 | Abstract behavioral contract for any harness wrapping the engine for a deployment runtime (HTTP, event bus, queue worker, CLI repl). Specifies inbound dispatch path classification, turn lifecycle, three-bucket error categorization, signal coordinator for suspend-resume, sessioned-vs-stateless mode as first-class. Per-harness-type sub-specs land per-case (chat is the first; FastAPI / Inngest / CLI as needed). |
| ↳ [harness-chat](spec/harness-chat/spec.md) | 0.50.0 | 0.50.0 | 10 | Chat-loop sub-spec on top of the abstract harness contract; first per-harness-type sub-spec. Canonical `ChatMessage` shape (mirrors llm-provider §3 unchanged), per-session conversation history via `messages: list[ChatMessage]` + `append` reducer, `send(session_id, message) -> ChatTurnOutcome` callable (three-way discriminator: completed / errored / suspended), suspension composition via reducer + subscribed-listener resume. Sessioned-mode only. |
| [conformance-adapter](spec/conformance-adapter/spec.md) | 0.48.0 | 0.68.0 | N/A (meta) | Meta-capability ratifying the language-agnostic conformance fixture system. Specifies the YAML schema, the full directive vocabulary, the harness primitives implementations MUST provide (real not simulated), nondeterminism handling, and adapter responsibility (discovery / parsing / execution / assertion via the host's idiomatic test framework). v1 is descriptive of what exists. |
| [retrieval-provider](spec/retrieval-provider/spec.md) | 0.54.0 | 0.70.0 | 12 | First non-LLM-completion provider capability; sibling to `llm-provider` covering retrieval-primitive provider operations. Two protocol surfaces: the `EmbeddingProvider` protocol (`ready()` + `embed(input: list[str]) -> EmbeddingResponse`) and the `RerankProvider` protocol (`ready()` + `rerank(query, documents, *, top_k=None) -> RerankResponse` of `ScoredDocument` entries sorted by relevance, each carrying its input-documents `index`); paired typed events `EmbeddingEvent` / `EmbeddingFailedEvent` and `RerankEvent` / `RerankFailedEvent` on the graph-engine §6 observer event union; OTel mapping via core GenAI semconv subset + span-name discrimination; Langfuse mapping via dedicated `Embedding` and `Retriever` observation types. First member of the planned `<domain>-provider` capability family. |

### In the pipeline

Proposals currently in flight. Status is Draft; contracts may change before
they are Accepted.

| Proposal | Status | Targets | Summary |
|---|---|---|---|
| [0062](proposals/0062-llm-completion-streaming.md) | Draft | spec/llm-provider/spec.md (§5 `complete()` gains an opt-in `stream` flag — return type unchanged; §6 streaming-assembly contract; §8.1 OpenAI-compatible SSE handling; §10 streaming deferral lifted); spec/graph-engine/spec.md (§6 typed `LlmTokenEvent`); spec/observability/spec.md (§5.5 + §8 note — bundled observers ignore token events, trace recording stays atomic) | Lifts LLM response streaming from llm-provider §10 *Out of scope* into a normative capability. `complete(stream=...)` makes the provider consume the streaming wire response and emit `LlmTokenEvent` per chunk, while still returning the atomic `Response` (the flag controls event emission, not the return type). Provider reassembles content + tool-call argument deltas into the atomic `Response` so node bodies are streaming-agnostic. Token events are a within-call sub-event correlated to the terminal `LlmCompletionEvent` by `call_id`; bundled OTel/Langfuse observers ignore them (atomic trace recording preserved). |
See [`proposals/`](proposals/) for the full history (Accepted and Draft both).

---

## Conformance

Behavior is specified by both the prose spec text *and* a set of canonical
test fixtures under `spec/<capability>/conformance/`. Each fixture is a pair:

- `NNN-name.yaml`: declarative graph definition, initial state, and expected
  outcome.
- `NNN-name.md`: prose description of what the fixture verifies and which
  spec sections it exercises.

Implementations don't just read the spec; they run the fixtures. The Python
reference implementation passes every fixture in its CI; new implementations
validate the same way. Fixture additions land via the same proposal that
introduces the behavior they verify, so the prose spec, the formal contract,
and the conformance suite stay in lockstep.

---

## Implementations

| Language | Status | Repository |
|---|---|---|
| Python | Shipping | [openarmature-python](https://github.com/LunarCommand/openarmature-python) (docs at [openarmature.ai](https://openarmature.ai)) |
| TypeScript | Planned | not yet started |

OpenArmature follows the pattern LangChain, LlamaIndex, and Vercel's AI SDK
use: maintain a language-agnostic specification and conformance test suite
that each implementation targets. Idiomatic implementations in each language;
behavioral parity guaranteed by the fixtures. Each language gets to look like
itself (Python decorators where idiomatic, TypeScript middleware where
idiomatic) while the behavioral contract holds.

The TypeScript implementation is gated on the conformance suite being complete
enough to validate a parallel implementation against. That's meaningful work
and not yet started; no committed date.

---

## Governance

Spec changes go through a numbered RFC-style proposal lifecycle:

1. **Draft.** Author opens a proposal at `proposals/NNNN-<slug>.md`. The
   prose iterates via PR review (the Review stage). The spec, conformance
   fixtures, and CHANGELOG are not touched yet.
2. **Accepted.** Maintainer flips status when the proposal is ready to
   merge. The proposal text is frozen. Spec text, conformance fixtures,
   and CHANGELOG updates land in the same PR or in a follow-up PR, per
   the author's preference.
3. **Withdrawn** or **Superseded.** A Draft may be Withdrawn by its
   author at any point. A later proposal that revises the same surface
   declares `Supersedes: NNNN` in its header; the original stays in the
   repository as historical record.

Accepted proposals are immutable. Any change to behavior, public types, or
conformance expectations requires a new proposal, even when the maintainer
would otherwise just edit the spec text directly. Typos, formatting, and
charter/governance edits do not need a proposal.

See [`GOVERNANCE.md`](GOVERNANCE.md) for the full proposal template, required
header fields, and review process.

---

## Where to start

- **Curious about the design.** Read the [charter](docs/openarmature.md) for
  the thesis, distilled patterns, architecture, and canonical examples.
- **Implementing in a new language.** Start with `spec/<capability>/spec.md`
  for the behavioral contract, then run the conformance fixtures in
  `spec/<capability>/conformance/`. The Python implementation is a reference
  for non-spec-mandated choices (idiomatic API shape, packaging, etc.).
- **Contributing a proposal.** Read [`GOVERNANCE.md`](GOVERNANCE.md), then
  browse recent `proposals/NNNN-*.md` for shape and style.
- **Evaluating for adoption.** Read the Status table above, then visit
  [openarmature.ai](https://openarmature.ai) for runnable code, the
  Quickstart, and per-feature documentation.

---

## License

Apache-2.0. See [LICENSE](LICENSE).
