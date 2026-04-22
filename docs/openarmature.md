# OpenArmature

**A workflow framework for LLM pipelines and tool-calling agents.**

OpenArmature ships composable graph primitives — nodes, edges, typed state, conditional routing — plus the supporting
infrastructure production LLM work needs: prompt management, evaluation, observability, and MCP tool integration. One
framework for both deterministic LLM pipelines and tool-calling agents.

---

## Table of Contents

- [1. Thesis](#1-thesis)
  - [1.1 The Gap: LLM Pipelines Have No Home](#11-the-gap-llm-pipelines-have-no-home)
  - [1.2 The Insight: Pipelines and Agents Share Primitives](#12-the-insight-pipelines-and-agents-share-primitives)
  - [1.3 What OpenArmature Proposes](#13-what-openarmature-proposes)
- [2. Evidence](#2-evidence)
  - [2.1 Projects Behind the Design](#21-projects-behind-the-design)
  - [2.2 Distilled Patterns](#22-distilled-patterns)
- [3. Architecture](#3-architecture)
  - [3.1 Design Principles](#31-design-principles)
  - [3.2 Package Structure](#32-package-structure)
  - [3.3 Architecture Diagram](#33-architecture-diagram)
- [4. Module Specifications](#4-module-specifications)
  - [4.1 Graph Engine](#41-graph-engine)
  - [4.2 Pipeline Utilities](#42-pipeline-utilities)
  - [4.3 LLM Provider Abstraction](#43-llm-provider-abstraction)
  - [4.4 Tool System and MCP](#44-tool-system-and-mcp)
  - [4.5 Prompt Management](#45-prompt-management)
  - [4.6 Observability](#46-observability)
  - [4.7 Evaluation](#47-evaluation)
  - [4.8 Logging](#48-logging)
- [5. Canonical Examples](#5-canonical-examples)
  - [5.1 LLM Pipeline (Content Analysis)](#51-llm-pipeline-content-analysis)
  - [5.2 Tool-Calling Agent](#52-tool-calling-agent)
  - [5.3 Hybrid (Pipeline with Agent Step)](#53-hybrid-pipeline-with-agent-step)
- [6. Multi-Language Strategy](#6-multi-language-strategy)
- [7. Implementation Plan](#7-implementation-plan)
  - [7.1 Phasing](#71-phasing)
  - [7.2 Risks](#72-risks)
  - [7.3 What Is Hard](#73-what-is-hard)

---

## 1. Thesis

### 1.1 The Gap: LLM Pipelines Have No Home

The current landscape for building production LLM systems splits cleanly into two camps, neither of which serves LLM
pipelines well:

**Agent frameworks** (LangChain/LangGraph, CrewAI, OpenAI Agents SDK, Claude Agent SDK, Pydantic AI, OpenAI Swarm) are
built around the tool-calling loop. State is typically a message list. Control flow is LLM-driven — the model decides
the next step. These frameworks are excellent for conversational agents and autonomous loops. They are awkward for
deterministic pipelines where the control flow is known up front and LLMs are one of several processing steps.

The friction is specific: a document extraction or content analysis pipeline doesn't need conversation history — it
needs structured data flow between stages. Forcing a deterministic sequence of LLM calls through a `MessagesState` or
`ToolNode` imposes a conversation abstraction on non-conversation work: token overhead for history that nothing reads,
and a loop-shaped control model where a linear sequence of typed Pydantic contracts would be clearer and cheaper.

**Pipeline orchestrators** (Prefect, Dagster, Airflow, Luigi) are built for deterministic ETL and workflow execution.
They have no LLM primitives, no prompt management, no observability for model calls, no eval. A team using one for an
LLM pipeline rebuilds prompt loading, structured-output repair, retry with context, token-aware rate limiting, and
cost/latency tracing from scratch.

The mismatches are specific, not cosmetic:

- **Rate limiting.** Generic orchestrators throttle by concurrent tasks. LLM providers throttle by tokens per minute.
  A concurrency limit of 8 can still hit a TPM ceiling when chunks vary in size.
- **Retry semantics.** Standard retry re-invokes the failed call. LLM failures often need something different — a
  retry with the validation error appended to the prompt, a fallback to a smaller model, a switch from JSON mode to
  text-plus-parse, or a regeneration with a higher temperature.
- **Semantic failure.** A task-level orchestrator reports success when the function returned without exception. LLM
  steps routinely succeed at the process level while producing garbage — a hallucinated JSON schema that breaks the
  next stage, a plausible-looking answer that fails evaluation. Observability that treats these as success is
  observability that hides the actual failure mode.

None of this is an oversight in the orchestrators. It is outside the scope those tools were designed for.

**LCEL is retired.** LangChain's pipeline DSL is being wound down. The chain-of-operations model did not survive —
developers rejected it for the same reason most DSLs fail: they wanted Python control flow (`for`, `if`, explicit
`await`), not pipe operators that hid the underlying `asyncio`. OpenArmature's bet is that Python-native graph
construction beats any DSL, no matter how elegant.

The work in the middle — content analysis pipelines, creator/lead sourcing, forecasting systems, large-scale data
enrichment, multi-stage extraction, document processing — is mostly deterministic with LLM steps for reasoning. It has
no dedicated framework. Teams doing this work either:

- Shoehorn into LangGraph with fake tool-calling loops
- Write raw `asyncio.gather()` with custom retry and checkpointing
- Glue Prefect + LangChain for message types and prompt loading
- Some combination of all three across the same codebase

This is not a new category. It is a major category that has simply been ignored.

### 1.2 The Insight: Pipelines and Agents Share Primitives

The reason the same framework can serve both is that the differences between LLM pipelines and tool-calling agents live
in node _content_, not in graph topology:

- **Pipelines**: nodes are mostly deterministic. A few use LLMs for structured extraction, classification, judgment.
  Control flow is known in advance.
- **Agents**: nodes include an LLM call and tool execution in a loop. Control flow is LLM-driven via conditional edges.

Both need:

- A typed state object that evolves across nodes
- Nodes as async functions with explicit inputs and outputs
- Conditional and static edges
- State reducers (append to list, merge dict, last-write-wins)
- Subgraphs and composition

Both benefit from the same supporting infrastructure:

- Structured output with automatic repair on validation failure
- Prompt management with version tracking and variable injection
- Typed inter-node contracts (Pydantic)
- Observability with ambient correlation IDs
- Evaluation framework with persistent history
- MCP-compatible tool integration

The graph primitives are agnostic. Topology does not care whether the LLM calls the next node or a conditional function
does.

### 1.3 What OpenArmature Proposes

A single workflow framework with:

1. **Graph primitives** — typed state, nodes as async functions, static and conditional edges, reducers, middleware,
   subgraphs. Works for pipelines (deterministic control flow) and agents (LLM-driven control flow).
2. **Pipeline-first utilities** — checkpoint/resume, batch processing with partial failure handling, rate limiting,
   structured-output repair, typed inter-stage contracts, per-item vs per-stage resource lifecycle. These are the
   patterns every LLM pipeline rebuilds.
3. **Production infrastructure** — prompt management with dual backends (Langfuse + local Jinja2), evaluation with
   persistent history, ambient observability, structured logging, MCP with cold-start handling and retry. These are
   non-optional for production LLM work.
4. **MCP-native tools** — discovery, schema conversion, cold-start handling, retry policy, session lifecycle are
   first-class. Remote and local tools use the same interface.
5. **Composable ecosystem** — core package plus sibling packages (`openarmature-eval`, `openarmature-langfuse`,
   `openarmature-otel`). Swap backends by installing a different sibling.

Target audience: teams building LLM pipelines. Non-LLM pipelines work as a byproduct. Tool-calling agents are a
first-class secondary use case.

---

## 2. Evidence

OpenArmature's design is informed by seven production projects. The framework is not a rewrite target for any of them;
the patterns below are distilled observations, not retrofits.

### 2.1 Projects Behind the Design

| Project            | Type                               | Key contribution                                                                                                                                             |
| ------------------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rotas**          | Tool-calling agent                 | Glue-tax quantification: ~40% of 5,284 lines bridging framework gaps (MCP production hardening, observability wiring, prompt DIY, eval-as-parallel-codebase) |
| **Multivac**       | LLM pipeline (content analysis)    | Prompt-pair pattern, multi-stage LLM pipeline with typed inter-stage contracts                                                                               |
| **Bird-Dog**       | LLM pipeline (creator sourcing)    | Checkpoint/resumability, batch processing with incremental persistence, per-stage rerun from checkpoint                                                      |
| **Audio Refinery** | Non-LLM ML pipeline (GPU audio)    | Resource lifecycle management, per-item vs per-stage strategies, Ghost Track recovery                                                                        |
| **MBT Game Agent** | Tool-calling agent (game)          | Tiered decision-making, conversation memory reconstruction from external state                                                                               |
| **Manukora S&OP**  | Minimal LLM pipeline (forecasting) | "Calculate first, reason second" — deterministic computation followed by LLM narrative generation                                                            |
| **Forbin**         | MCP tooling (CLI)                  | MCP server exploration, schema discovery, connection diagnostics                                                                                             |

### 2.2 Distilled Patterns

**Graph topology as a shared primitive.** Pipelines and agents both compose cleanly as directed graphs with typed state
and conditional edges. No project needed anything the graph model could not express.

**Checkpoint/resume is essential for pipelines.** Multi-hour runs fail at item 847 of 1,200. Restart from scratch is not
acceptable. Bird-Dog and Audio Refinery both built this independently. Pattern: checkpoint between stages, optionally
between items within a stage.

**Typed inter-stage contracts catch errors early.** Passing raw dicts between stages lets schema drift propagate
silently. Pydantic models at each stage boundary surface errors at the boundary, not three stages downstream.

**Structured-output repair is expected to fail sometimes.** A framework that does not retry with the validation error in
context is a framework that shifts this burden to every user.

**Per-item vs per-stage resource lifecycle matters.** Loading a 2 GB model per item wastes compute; loading it once per
stage holds GPU memory indefinitely. Both patterns are valid; the framework should make the choice explicit.

**Partial failure is the default.** In a 1,000-item batch, some items will fail. Pipelines should not halt unless
configured to. Per-item exceptions collected and reported without stopping the batch is the expected behavior.

**Rate limiting scope is composable, not fixed.** Provider/model TPM is the base layer (to avoid 429s — limits vary
by model, not just by provider). Pipelines frequently need finer scopes on top: per-node throttling to prevent a
high-fanout step from starving others on the same model, or per-prompt budgets when several prompts share a model but
have different cost/latency targets. The framework should let developers compose limiters at whichever scopes their
pipeline needs, not hard-code one.

**Ambient observability means no plumbing.** Correlation IDs, structured logs, and span creation should happen
automatically inside framework calls. The developer should never wire `contextvars` manually.

**Prompt management needs two backends.** Development uses local Jinja2 templates; production uses Langfuse (or similar)
for version tracking. The framework should handle the dual-source loading once, not in every prompt-using module.

**Evaluation runs against persistent history.** Score trends across runs matter more than single-run scores. Per-test
deltas show what changed between versions. A framework without persistence treats evaluation as a disposable check
rather than a development tool.

**MCP needs production hardening.** Cold starts, retry policies, session refresh on broken pipes, extended timeouts,
sanitized error propagation. The base MCP adapters in the ecosystem solve translation, not production.

**"Calculate first, reason second" is a common architecture.** Deterministic computation produces structured inputs; the
LLM generates narrative or interpretation. The framework should make the boundary explicit, not hide LLM calls inside a
"smart" pipeline step.

---

## 3. Architecture

### 3.1 Design Principles

**1. LLM pipelines and agents share primitives.** The graph engine is agnostic to whether control flow is LLM-driven or
deterministic. Pipeline utilities are first-class in core, not an afterthought. Agents work with the same primitives.

**2. The engine is content-agnostic.** A node is an opaque IO boundary — a black-box async function that returns a
partial update. The engine has no concept of LLMs, tools, or external systems, so validation, retry, and recovery of
external inputs (JSON parsing, schema drift, truncated responses, timeouts) are node-internal concerns.
`NodeException` with `recoverable_state` is the crash-context primitive; patterns built on top (retries, graceful
degradation, circuit breakers) belong at the user level or in pipeline utilities, not the engine.

**3. Focused core, composable ecosystem.** The core handles orchestration, state, LLM abstraction, tool dispatch, and
prompt interfaces. Evaluation, observability backends, and provider integrations live in sibling packages. Swap a
backend by installing a different sibling.

**4. MCP-native.** Tool discovery, calling, retry, cold-start handling, and transport management are first-class in
core. Remote and local tools use the same `ToolSet` interface.

**5. Ambient observability via interfaces.** The core defines observability contracts (trace context, span creation,
correlation IDs) and provides instrumentation automatically. Specific backends (Langfuse, OTEL/HyperDX, Datadog)
implement the contracts. Switching backends is a package swap.

**6. Evaluation as a sibling, not built-in.** Metric base classes and `EvalCase` live in core. The test runner, SQLite
persistence, trend charts, and CLI live in `openarmature-eval`. This keeps core dependency-light while making eval a
first-class ecosystem citizen.

**7. No built-in prompts.** The framework never embeds hidden prompt text that shapes LLM behavior. No ReAct templates,
no default personas. Every prompt the LLM sees is authored by the developer.

**8. Escape hatches everywhere.** Every default can be overridden. The framework handles the common case; developers
handle the exceptional case.

### 3.2 Package Structure

```
openarmature                  Core: graph, state, LLM, tools, prompts (interfaces), pipeline utilities, logging
openarmature-eval             Eval: test runner, metrics, SQLite persistence, trend charts, CLI
openarmature-langfuse         Langfuse: prompt loading backend, trace linking, callback handler
openarmature-otel             OTEL: TracerProvider, LoggerProvider, HyperDX/Jaeger/Grafana exporters
```

Core dependency footprint: `httpx`, `pydantic`, `structlog`, `jinja2`. No database drivers, no plotting libraries, no
provider-specific SDKs.

**Install patterns:**

```bash
# LLM pipeline with OTEL export + evaluation
pip install openarmature openarmature-otel openarmature-eval

# Agent with Langfuse
pip install openarmature openarmature-langfuse

# Minimal
pip install openarmature
```

### 3.3 Architecture Diagram

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                      openarmature (core)                        │
    │                                                                 │
    │   ┌────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐   │
    │   │ Graph  │ │ Pipeline │ │  LLM   │ │  Tools  │ │ Prompts  │   │
    │   │ Engine │ │ Utilities│ │Provider│ │ (MCP +  │ │(interface│   │
    │   │(nodes, │ │(chunks,  │ │ (vLLM, │ │  local) │ │ + local  │   │
    │   │ edges, │ │ batches, │ │OpenAI, │ │         │ │ template)│   │
    │   │ state) │ │ resume)  │ │Bifrost)│ │         │ │          │   │
    │   └────────┘ └──────────┘ └────────┘ └─────────┘ └──────────┘   │
    │                                                                 │
    │   Interfaces: ObservabilityBackend, PromptBackend, EvalMetric   │
    └───────────────────────────────┬─────────────────────────────────┘
                                    │ implements
                ┌───────────────────┼────────────────────┐
                │                   │                    │
          ┌─────▼──────┐   ┌────────▼────────┐  ┌────────▼────────┐
          │openarmature│   │  openarmature   │  │  openarmature   │
          │ -langfuse  │   │     -otel       │  │     -eval       │
          │            │   │                 │  │                 │
          │Prompt fetch│   │ TracerProvider  │  │ Test runner     │
          │Trace link  │   │ LoggerProvider  │  │ SQLite persist  │
          │Callbacks   │   │ OTLP exporters  │  │ Trend charts    │
          │Session mgmt│   │HyperDX/Jaeger   │  │ CLI             │
          └────────────┘   └─────────────────┘  └─────────────────┘
```

---

## 4. Module Specifications

This section summarizes each module's scope, core abstractions, and key design decisions.

### 4.1 Graph Engine

**Scope.** Typed state, nodes as async functions, static and conditional edges, reducers, middleware, subgraph
composition, async compilation.

**Core abstractions.** `Graph`, `State`, `Message`, `Node`, `Edge`, reducers (`append_messages`, `merge_dict`,
`last_write_wins`, custom).

**Key decisions.**

- State is a Pydantic model, not an untyped dict
- Node signature: `async def node(state: StateT) -> dict` (returns partial update)
- Edges are Python callables returning the next node name or `Graph.END`
- Subgraphs compose as single nodes; parent state flows in and out
- Middleware wraps nodes (logging, retry, timing) without changing node signatures

### 4.2 Pipeline Utilities

**Scope.** The patterns that every LLM pipeline rebuilds. First-class in core because LLM pipelines are the target
audience.

**Core abstractions.**

- `@step` decorator for pipeline stages with typed input/output contracts
- `StepRegistry` for discovery and ordering
- `Checkpoint` for persistence between stages (and optionally between items)
- `batch_process()` — async batch executor with partial failure collection, rate limiting, progress reporting
- `chunk_with_overlap()` — text chunking with configurable overlap for context continuity
- `structured_output()` — wrapper that retries on Pydantic validation failure with error context
- `RateLimiter` — token-bucket with composable scopes (per-model, per-node, per-prompt) that stack
- `ResourceLifecycle` — context manager for per-stage resource loading (GPU models, connection pools)

**Key decisions.**

- Checkpoints are opt-in per step; steps declare whether they are checkpointable
- Partial failure is the default; users configure fail-fast when they want it
- Rate limiters compose: a per-model limiter (base layer for provider 429 avoidance) can stack with per-node or
  per-prompt limiters (for fairness and cost control within a pipeline). The framework enforces the strictest active
  scope at each call site
- Resource lifecycle is explicit: per-item (load each call) or per-stage (load once, reuse)

### 4.3 LLM Provider Abstraction

**Scope.** Unified interface over local (vLLM, Ollama, LM Studio) and remote (OpenAI, Anthropic, Google, Bifrost)
providers. Health checks, config composition, structured output, streaming.

**Core abstractions.** `LLM`, `Message` (system, user, assistant, tool), `ToolCall`, provider presets
(`LLM.vllm(...)`, `LLM.openai(...)`, `LLM.bifrost(...)`).

**Key decisions.**

- Pre-flight health check with explicit `ready()` method — agents and pipelines fail fast on missing models
- `structured_output(schema=...)` returns parsed Pydantic instance; retries on validation failure
- No hidden prompts; system messages are always explicit
- Config overrides compose, not mutate (immutable LLM configs)

### 4.4 Tool System and MCP

**Scope.** Unified tool interface for local Python functions and remote MCP tools. Production-grade MCP: discovery,
retry, cold-start handling, session lifecycle, schema conversion.

**Core abstractions.** `ToolSet`, `@tool` decorator, `MCPToolSet`, `LocalToolSet`, `ToolResult`.

**Key decisions.**

- MCP discovery generates tool schemas at runtime (no hand-written schemas)
- Cold-start handling: configurable health-check loop before MCP connection
- Retry policy: classified exceptions (`HTTPStatusError`, `BrokenResourceError`, `ClosedResourceError`) with appropriate
  response (retry with fresh session, fail fast, sanitize error)
- Timeouts: separate init, operation, discovery timeouts
- Error sanitization: framework strips tracebacks from tool errors before returning to LLM

### 4.5 Prompt Management

**Scope.** Dual-source prompt loading (Langfuse for production, local Jinja2 for development), variable injection with
`StrictUndefined`, prompt-pair pattern for dual-observation tracing.

**Core abstractions.** `PromptManager`, `Prompt`, `PromptResult`, `PromptPair`. Backends implement `PromptBackend`
interface.

**Key decisions.**

- `StrictUndefined` by default — unbound variables raise immediately instead of rendering empty strings
- Langfuse backend (sibling package) fetches by name and label; local backend reads from filesystem
- Fallback: if Langfuse fetch fails, fall back to local template with warning
- PromptPair: a classification prompt paired with a follow-up prompt, traced together under one parent span

### 4.6 Observability

**Scope.** Ambient correlation IDs, structured spans around LLM calls, tool calls, and node execution. Provider
isolation to avoid Langfuse v3 + OTEL span duplication.

**Core abstractions.** `ObservabilityBackend` interface. Backends: `openarmature-langfuse`, `openarmature-otel`.

**Key decisions.**

- Correlation IDs via `ContextVar`, set once per invocation and propagated through all async calls automatically
- `TracerProvider` is isolated (not global) to prevent Langfuse v3 from duplicating spans through the global OTEL
  pipeline
- Instrumentation happens inside framework calls; user code never touches `set()`/`reset()` on context tokens
- Session grouping, flush-on-exit, and callback registration are backend responsibilities

### 4.7 Evaluation

**Scope.** Deterministic and LLM-judge metrics, persistent history, per-test deltas, trend charts. Lives in
`openarmature-eval`; base classes live in core.

**Core abstractions.** `DeterministicMetric`, `LLMJudgeMetric`, `EvalCase`, `EvalRun`, `EvalReport`.

**Key decisions.**

- SQLite persistence (WAL mode, foreign keys, idempotent migrations)
- Per-test delta tracking: previous scores queried by `test_id` to show what changed
- Prompt version tracking: current Langfuse versions stored in `runs` table
- Dual-path evaluation: structured output (tool calls as JSON) and natural language responses stored separately, queried
  by different metric types

### 4.8 Logging

**Scope.** Structured logging via structlog, noisy-library suppression, correlation ID enrichment.

**Core abstractions.** `configure_logging()` sets up structlog with JSON output in production, console output in
development. Correlation IDs auto-injected from observability context.

**Key decisions.**

- Known noisy loggers (`httpx`, `openai`, `langfuse`, `urllib3`, ...) are suppressed by default; user can override
- Log records carry correlation ID automatically via `contextvars` integration
- No configuration required for the common case; one call in `main()` configures everything

---

## 5. Canonical Examples

### 5.1 LLM Pipeline (Content Analysis)

```python
from openarmature import Graph, State, step, batch_process, LLM, PromptManager
from pydantic import BaseModel

class TranscriptChunk(BaseModel):
    start: float
    end: float
    text: str

class Analysis(BaseModel):
    themes: list[str]
    sentiment: str
    key_claims: list[str]

class PipelineState(State):
    video_url: str
    transcript: str = ""
    chunks: list[TranscriptChunk] = []
    analyses: list[Analysis] = []

graph = Graph(PipelineState)
llm = LLM.anthropic(model="claude-sonnet-4-6")
prompts = PromptManager.from_env()

@graph.node
async def fetch_transcript(state: PipelineState) -> dict:
    transcript = await fetch_youtube_transcript(state.video_url)
    return {"transcript": transcript}

@graph.node
async def chunk_transcript(state: PipelineState) -> dict:
    chunks = chunk_with_overlap(state.transcript, size=2000, overlap=200)
    return {"chunks": chunks}

@graph.node
@step(checkpointable=True)
async def analyze_chunks(state: PipelineState) -> dict:
    prompt = prompts.get("analyze_chunk")
    async def analyze(chunk: TranscriptChunk) -> Analysis:
        return await llm.structured_output(
            schema=Analysis,
            messages=[prompt.render(chunk=chunk.text)],
        )
    analyses = await batch_process(
        items=state.chunks,
        worker=analyze,
        concurrency=8,
        on_error="collect",
    )
    return {"analyses": analyses.successful}

graph.add_edge("fetch_transcript", "chunk_transcript")
graph.add_edge("chunk_transcript", "analyze_chunks")
graph.add_edge("analyze_chunks", Graph.END)

pipeline = graph.compile()
result = await pipeline.invoke(PipelineState(video_url="https://..."))
```

Control flow is deterministic. LLM calls are scoped to the `analyze_chunks` step. Checkpointing lets a failed run resume
from `chunk_transcript` without refetching. Batch processing handles partial failures without halting.

### 5.2 Tool-Calling Agent

```python
from openarmature import Graph, State, Message, LLM, MCPToolSet

class AgentState(State):
    messages: list[Message]

graph = Graph(AgentState)
llm = LLM.bifrost(model="claude-sonnet-4-6")
tools = await MCPToolSet.connect(url="https://tools.example.com/mcp")
llm.bind_tools(tools)

@graph.node
async def agent(state: AgentState) -> dict:
    response = await llm.chat([prompts.get("system"), *state.messages])
    return {"messages": [response]}

@graph.node
async def execute_tools(state: AgentState) -> dict:
    results = await tools.execute(state.messages[-1].tool_calls)
    return {"messages": results}

@graph.edge(from_="agent")
def route(state: AgentState) -> str:
    return "execute_tools" if state.messages[-1].tool_calls else Graph.END

graph.add_edge("execute_tools", "agent")

compiled = graph.compile()
result = await compiled.invoke(AgentState(messages=[Message.user("Find me flights to Tokyo")]))
```

Same graph primitives. Control flow is LLM-driven via the conditional edge. MCP connection, cold-start handling, schema
discovery, and retry are managed by the framework.

### 5.3 Hybrid (Pipeline with Agent Step)

```python
# Pipeline that dispatches to an agent for one investigative step.
# Example: a lead-enrichment pipeline that uses an agent to research
# ambiguous companies via multiple tool calls.

@graph.node
async def research_ambiguous(state: PipelineState) -> dict:
    agent = load_research_agent()  # a compiled subgraph
    enriched = []
    for lead in state.ambiguous_leads:
        result = await agent.invoke(
            AgentState(messages=[Message.user(f"Research {lead.company}")])
        )
        enriched.append(merge_lead(lead, result))
    return {"enriched_leads": enriched}
```

The agent is a compiled subgraph. It plugs into the pipeline as a single node. The pipeline's checkpoint captures the
agent's results; a failed run resumes without re-invoking the agent for already-researched leads.

---

## 6. Multi-Language Strategy

OpenArmature ships Python first, TypeScript second, via **parallel implementations with a shared specification**.

**Approach.** Maintain a language-agnostic specification (design spec + wire-protocol definitions + conformance test
suite) that both implementations target. Each language gets an idiomatic implementation. This is the pattern LangChain,
LlamaIndex, and Vercel's AI SDK use.

**Why this pattern wins over alternatives.**

- **FFI** (Python core + TS binding): idiomatic mismatch, build complexity, stack traces cross language boundaries
- **Codegen from a single source**: works for protocols (protobuf, OpenAPI) but not for idiomatic frameworks. Generated
  Python feels like TypeScript and vice versa
- **Parallel implementations with spec**: each language is idiomatic; spec keeps them aligned on behavior, not
  implementation

**Release sequencing.**

1. Python v0 → v1: build and ship core + eval + langfuse + otel
2. Extract spec from v1: design spec, wire-protocol definitions, conformance test suite
3. TypeScript v0 → v1: build against the spec, validate with the conformance suite
4. Synchronized releases thereafter

**Repo structure.** Separate repos (`openarmature-python`, `openarmature-typescript`, `openarmature-spec`) rather than a
monorepo. Different language tooling, different contributor pools, different release cadence in practice.

**Risks.**

- TypeScript never ships (Python absorbs all attention) — mitigate by extracting the spec as an explicit artifact
- Spec drift between implementations — mitigate by requiring conformance tests to pass before either language releases
- Idiom mismatch (e.g., Python decorators vs TS middleware) — accept that APIs will differ in syntax while matching in
  behavior

---

## 7. Implementation Plan

### 7.1 Phasing

**v0 — Graph + Pipeline Utilities.** Ship the graph engine and pipeline utilities. Enough to build a working LLM
pipeline end-to-end with basic LLM provider abstraction. No MCP, no eval, no observability yet. Goal: validate the core
primitives against two or three real pipeline builds.

**v1 — LLM Provider + Tools + MCP.** Add production-grade LLM abstraction (local + remote providers, structured output
with repair) and the tool system with MCP support (discovery, retry, cold-start handling). Goal: the framework can build
a tool-calling agent, not just a pipeline.

**v2 — Supporting Infrastructure.** Add prompt management, observability (core interfaces + `openarmature-langfuse` +
`openarmature-otel`), structured logging. This is where the "glue tax" savings materialize. Goal: a real production
deployment can use OpenArmature end-to-end.

**v3 — Evaluation + Ecosystem.** Ship `openarmature-eval` with test runner, SQLite persistence, trend charts, CLI. Build
local dev tooling (mock MCP servers, prompt REPL). Extract the spec and begin TypeScript port.

### 7.2 Risks

**Scope too broad for a small team.** Mitigation: phasing above. Each phase produces a shippable artifact that is useful
on its own.

**Graph engine is overkill for simple pipelines.** Mitigation: pipeline utilities work without explicit graph
construction for straightforward linear flows. The graph is the escape hatch for complex topology, not the only way in.

**MCP ecosystem instability.** Mitigation: core interfaces abstract transport; new MCP transports slot in as ToolSet
backends.

**Observability backend lock-in.** Mitigation: observability is interface-first. Backends are swappable siblings.

**TypeScript port never ships.** Mitigation: extract the spec as an explicit artifact in v3; build the conformance test
suite as part of v3 so TS work has a clear target.

**Eval framework duplicates DeepEval.** Mitigation: `openarmature-eval` focuses on persistence, trends, and
LLM-pipeline-specific metrics. Integration with DeepEval metrics as adapters is an option, not a replacement.

### 7.3 What Is Hard

**Graph engine semantics.** State reducers, subgraph composition, middleware ordering, and conditional edges interact.
Getting the model right before shipping is critical — changes post-v0 will break users.

**Pydantic validation feedback loop.** Structured-output repair needs the validation error in the retry prompt. Making
this automatic, language-model-aware, and low-friction requires care.

**MCP production hardening.** Cold-start handling, session lifecycle, and retry classification are ecosystem-dependent.
Testing against real MCP servers (not mocks) during v1 is essential.

**Observability provider isolation.** The Langfuse v3 / OTEL span duplication trap is subtle. The framework needs to
prevent it by default without blocking users who want a shared TracerProvider.

**Spec extraction without Python leakage.** When the spec is written, Python idioms (decorators, async generators,
context managers) should not leak into the protocol. The spec describes behavior; each language implements idiomatically.
