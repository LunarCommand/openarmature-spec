# OpenArmature: A Unified Agent Framework

A design document for a single-library agent framework with native MCP support, ambient observability, built-in
evaluation, and first-class support for local/remote LLM providers.

---

## Table of Contents

- [1. The Problem With Building Agents Today](#1-the-problem-with-building-agents-today)
    - [1.1 The Glue Tax](#11-the-glue-tax)
    - [1.2 Pain Point Inventory](#12-pain-point-inventory)
    - [1.3 This Is Not Unique to Rotas](#13-this-is-not-unique-to-rotas)
- [2. OpenArmature: Core Architecture](#2-openarmature-core-architecture)
    - [2.1 Why "OpenArmature"](#21-why-openarmature)
    - [2.2 Design Principles](#22-design-principles)
    - [2.3 Package Structure](#23-package-structure)
    - [2.4 Architecture Overview](#24-architecture-overview)
- [3. Module Breakdown](#3-module-breakdown)
    - [3.1 Graph Engine](#31-graph-engine)
    - [3.2 Native MCP Support](#32-native-mcp-support)
    - [3.3 LLM Provider Abstraction](#33-llm-provider-abstraction)
    - [3.4 Tool System](#34-tool-system)
    - [3.5 Observability](#35-observability)
    - [3.6 Prompt Management](#36-prompt-management)
    - [3.7 Evaluation](#37-evaluation)
    - [3.8 Logging](#38-logging)
- [4. How Rotas Would Look](#4-how-rotas-would-look)
    - [4.1 Before: Current Architecture](#41-before-current-architecture)
    - [4.2 After: OpenArmature Rewrite](#42-after-openarmature-rewrite)
    - [4.3 Reduction Summary](#43-reduction-summary)
- [5. Broader Use Cases](#5-broader-use-cases)
- [6. Local Developer Experience](#6-local-developer-experience)
    - [Mock MCP Servers](#mock-mcp-servers)
    - [MCP Server Explorer](#mcp-server-explorer)
    - [Prompt Management REPL](#prompt-management-repl)
    - [Local Development Stack](#local-development-stack)
- [7. Implementation Considerations](#7-implementation-considerations)
    - [7.1 What Is Hard](#71-what-is-hard)
    - [7.2 Build vs Extend vs Wrap](#72-build-vs-extend-vs-wrap)
    - [7.3 Incremental Adoption Path](#73-incremental-adoption-path)
    - [7.4 Dependencies and Ecosystem Risk](#74-dependencies-and-ecosystem-risk)
- [Appendix A: Rotas File-by-File Mapping](#appendix-a-rotas-file-by-file-mapping)
- [Appendix B: Configuration Schema](#appendix-b-configuration-schema)
- [Appendix C: Comparison Matrix](#appendix-c-comparison-matrix)

---

## 1. The Problem With Building Agents Today

### 1.1 The Glue Tax

Rotas is a LangGraph-based conversational agent that calls remote MCP tools on a FastAPI server via a local vLLM
inference endpoint. The codebase is 5,284 lines across 13 source files. Of those, roughly **2,100 lines exist solely to
bridge framework gaps** — not to implement domain logic.

| Category                   | Lines      | Files                                                                      | Purpose                                                                        |
|----------------------------|------------|----------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| MCP bridge                 | 302        | `mcp_client.py`                                                            | Cold-start handling, retry, session lifecycle, error classification            |
| Observability wiring       | 291        | `tracing.py` (154), `logging_config.py` (137)                              | OTEL setup, correlation IDs, provider isolation, logger suppression            |
| LLM client wrapper         | 185        | `llm_client.py`                                                            | Health checks, timeout handling, config patching                               |
| Prompt management          | ~210       | `nodes.py` (lines 370-583)                                                 | Dual-source loading, label resolution, Jinja2 rendering, 3x identical patterns |
| Tool schemas               | ~85        | `nodes.py` (lines 589-673)                                                 | Hardcoded OpenAI-format schemas, no generation from discovery                  |
| Eval infrastructure        | 2,612      | `run_eval.py` (897), `metrics.py` (1,191), `db.py` (439), `charts.py` (85) | 10 custom metrics, SQLite persistence, trend charts, output suppression        |
| Langfuse callback plumbing | ~50        | `cli.py` (lines 66-78, 123-139)                                            | Manual init, callback config, flush on exit                                    |
| **Total glue**             | **~2,100** |                                                                            | **~40% of the entire codebase**                                                |

The actual agent logic — graph topology, state shape, business rules like date validation, the Tenet-themed personality,
report formatting — is a minority of the codebase. The majority exists to make frameworks talk to each other.

This is a tax. Every team building a production agent pays it independently, and the glue code is eerily similar across
projects.

### 1.2 Pain Point Inventory

Each pain point is grounded in specific Rotas code with exact file references.

**1. MCP requires production-hardening beyond what adapters provide** — `rotas/mcp_client.py` (302 lines)

LangChain does have an official MCP adapter — `langchain-mcp-adapters` — which is more comprehensive than a thin
wrapper. It provides `MultiServerMCPClient` for connecting to MCP servers, converts discovered tools into LangChain
`StructuredTool` instances, supports streamable-HTTP/SSE/stdio transports, and includes features like tool interceptors,
progress notifications, and structured content handling. For many use cases, this adapter is sufficient.

But for **production deployments with serverless infrastructure**, the adapter doesn't cover what Rotas needs. What the
developer wanted: "Call remote tools via MCP on a Fly.io server." What they had to build on top of (or instead of) what
the adapter provides:

- `wake_up_server()` (lines 72-123): 6-attempt health check loop with 5s intervals — because Fly.io machines scale to
  zero and need waking before MCP can connect. The adapter has no concept of server readiness or cold-start handling.
- `discover_tools()` (lines 125-232): 3-retry exponential backoff (3-10s delay, 1.2x multiplier), fresh `Client()` on
  each attempt to prevent stale connections, `asyncio.wait_for()` with 15s timeout on `list_tools()`. The adapter's
  `MultiServerMCPClient` is stateless by default (fresh session per call) which avoids stale sessions but adds overhead
  for sequential multi-call workflows like Rotas' 15-month date ranges.
- `call_tool()` (lines 234-302): Retry-on-failure with full session refresh (cleanup → rediscover → retry), error
  classification for `HTTPStatusError` / `BrokenResourceError` / `ClosedResourceError`, sanitized error responses. The
  adapter propagates standard exceptions; Rotas needs controlled error messages that don't leak tracebacks to the LLM.
- Extended timeouts: 30s init, 600s operation, 15s discovery — report generation takes minutes. The adapter uses
  standard httpx defaults.

The adapter solves the **MCP-to-LangChain translation** problem well (tool discovery, schema conversion, transport
handling). What it doesn't solve is the **production infrastructure** problem (cold starts, retry policies, extended
timeouts, error sanitization). These concerns are arguably outside any adapter's scope — but they're the bulk of Rotas'
custom MCP code.

**2. LangChain and LangGraph are two libraries pretending to be one**

Building the Rotas graph requires imports from three packages:

```python
from langgraph.graph import StateGraph, START, END          # graph orchestration
from langgraph.graph.message import add_messages             # state reducer
from langchain_core.messages import AIMessage, HumanMessage  # message types
from langchain_openai import ChatOpenAI                      # LLM client
```

These are versioned independently, coupled implicitly, and force developers to hold two mental models (LangChain's "
chain of operations" vs LangGraph's "state machine"). The `add_messages` reducer is in `langgraph.graph.message` but
operates on `langchain_core.messages.BaseMessage` objects. Tool binding uses `langchain_openai.ChatOpenAI.bind_tools()`
but the graph routing checks `langchain_core.messages.AIMessage.tool_calls`. One concept, three packages.

**3. Observability is manual assembly** — `rotas/tracing.py` (154 lines) + `rotas/logging_config.py` (137 lines) +
`rotas/cli.py` (~50 lines)

- Correlation ID via `ContextVar` with manual `set()`/`reset()` token management per `ainvoke()` call (tracing.py:30-43,
  cli.py:208-217)
- OTEL `TracerProvider` deliberately NOT set globally (tracing.py:69-72) because Langfuse v3 exports its LLM spans
  through any global OTEL provider, duplicating data. This is a trap that takes hours to debug and discover — the
  framework should prevent it
- Dual exporter setup: `TracerProvider` + `LoggerProvider` configured separately with identical auth headers (
  tracing.py:62-80)
- Langfuse `CallbackHandler` manually instantiated in cli.py and passed via `config={"callbacks": [...]}` on every
  `ainvoke()` call
- Manual `flush()` on exit for both Langfuse and OTEL (cli.py:268-269)
- 9 noisy library loggers individually suppressed by name (logging_config.py:117-135)

**4. LLM client needs wrapping** — `rotas/llm_client.py` (185 lines)

- Health check via `/models` endpoint (lines 38-95) — `ChatOpenAI` provides no pre-flight validation; you discover the
  model isn't loaded when the first `ainvoke()` fails
- `asyncio.wait_for()` timeout wrapping (lines 98-155) — `ChatOpenAI`'s built-in `max_retries` and `timeout` are
  insufficient; the wrapper disables them (`max_retries=0`) and implements explicit control
- Config patching (lines 157-171) — Langfuse prompt metadata contains `temperature` and `max_tokens` overrides;
  `ChatOpenAI` has no config composition, so the wrapper mutates the instance directly
- `api_key=SecretStr("EMPTY")` — vLLM doesn't need an API key, but `ChatOpenAI` requires one; you pass a dummy value

**5. Eval is a parallel codebase** — `evals/` (2,612 lines across 4 files)

- 10 custom metrics in `metrics.py` (1,191 lines): 6 deterministic (`ToolCorrectness`, `ArgumentCorrectness`,
  `DateParsing`, `MultiMonthHandling`, `StepEfficiency`, `FutureDate`) and 4 LLM-as-judge (`PersonaConsistency`,
  `RejectionQuality`, `ClarificationQuality`, `ResponseRelevancy`)
- OS-level output suppression hack (metrics.py:26-52): DeepEval's `GEval` spawns Rich consoles and Pydantic validation
  output that contaminates stdout — the workaround duplicates file descriptors and redirects fd 1/2 to `/dev/null`
- SQLite persistence in `db.py` (439 lines): 4 tables (`runs`, `aggregate_scores`, `test_results`, `test_case_outputs`),
  WAL mode, foreign keys, idempotent schema migrations via `ALTER TABLE`
- Per-test delta tracking: queries previous scores for each `test_id` from the DB to show what changed between runs
- Terminal trend charts in `charts.py` (85 lines) via plotext
- Prompt version tracking: `run_eval.py` manually queries Langfuse for current prompt versions and stores them in the
  `runs` table
- Dual-path evaluation: structured output (tool calls as JSON) and natural language responses stored separately,
  available to different metric types

**6. Prompt management is DIY** — `rotas/nodes.py` (lines 370-583, ~210 lines)

Three separate `load_*_prompt()` functions (`load_system_prompt`, `load_summarize_error_prompt`,
`load_closing_message_prompt`) with identical structure:

1. Resolve label from `prompt_labels.json` via `_get_prompt_label()`
2. Try `langfuse_client.get_prompt(name, label=label)`
3. Compile with variables
4. On any exception, fall back to local Jinja2 template
5. Return `PromptResult(text, langfuse_prompt, config)`

This pattern is duplicated three times — same try/except, same fallback logic, same logging. A framework should provide
this once.

**7. Tool schemas are hardcoded** — `rotas/nodes.py` (lines 589-634, ~85 lines)

`GENERATE_REPORT_SCHEMA` and `SYNC_TOOL_SCHEMA` are `ClassVar[dict]` in OpenAI function-calling format, maintained
manually. The MCP server already describes `generate_report` via `list_tools()`, and `langchain-mcp-adapters` can
convert discovered tools into `StructuredTool` instances automatically. But Rotas predates the adapter's maturity and
uses `fastmcp` directly, so it hardcodes schemas rather than generating them from discovery. The result is the same
problem either way for local tools like `sync_report_to_sheets` — there's no MCP definition to discover, so those
schemas must still be hand-written. If the MCP server's parameter definition changes, the hardcoded schema silently
drifts.

### 1.3 This Is Not Unique to Rotas

Any agent that uses:

- **Remote tools** (MCP, REST, or otherwise) needs cold-start handling, retry, session management
- **Local LLMs** (vLLM, Ollama, LM Studio) needs health checks and provider-specific workarounds
- **Production observability** (Langfuse, OTEL, structured logging) needs correlation ID plumbing, provider isolation,
  callback wiring
- **Evaluation** needs metric definitions, test runners, persistence, trend tracking
- **Prompt management** needs multi-source loading with fallback, versioning, variable injection

Each team builds approximately the same ~2,000 lines of glue. The code looks different but solves identical problems.
The cost compounds with team size: every new developer must understand the glue before they can touch domain logic.

---

## 2. OpenArmature: Core Architecture

### 2.1 Why "OpenArmature"

An armature is the internal skeleton that holds a sculpture together — the hidden structural framework that lets the
visible thing work. It also has an electromagnetic meaning: the rotating part of a motor that does the actual work. Both
meanings apply. OpenArmature is the invisible structure that makes agents function, and the moving part that powers
them.

But the name carries a third meaning that may be the most important: an armature is built from **articulated joints** —
independent segments connected at flexible points, each posable in any direction. A sculptor doesn't choose between "
standing pose" and "running pose" at the skeleton level; they build a general-purpose armature and bend it into whatever
the piece demands. The same armature supports any form.

The "Open" prefix reflects the project's intent: open-source, open to any LLM provider, open to any tool protocol, and
open in its architecture — no black-box abstractions, every graph is inspectable, every default is overridable.

That's the core design philosophy. OpenArmature doesn't ship "a ReAct agent" or "a plan-and-execute agent." It ships
composable graph primitives — nodes, edges, state, reducers — that articulate into any agent pattern. You mix and match
patterns within the same graph, bending the framework to fit the application rather than fitting the application to a
prescribed pattern.

### 2.2 Design Principles

**Focused core, composable ecosystem.** The core package handles what only it can do: graph orchestration, state
management, LLM abstraction, tool dispatch, and prompt loading interfaces. Everything else — evaluation, observability
backends, provider-specific integrations — lives in sibling packages that compose with the core via well-defined
interfaces. This keeps the core small enough for a small team to maintain while allowing the ecosystem to grow
independently.

**MCP-native.** Tool discovery, calling, retry, and transport management are first-class in the core. Remote tools and
local tools use the same `ToolSet` interface.

**Observability via interfaces.** The core defines observability contracts (trace context, span creation, correlation
IDs) and provides ambient instrumentation. Specific backends (Langfuse, OTEL/HyperDX, Datadog) are sibling packages that
implement these interfaces. Switching from Langfuse to Arize is a package swap, not a code change.

**Evaluation as a sibling, not built-in.** Metric base classes and `EvalCase` data structures live in the core (they
define the contract). The test runner, SQLite persistence, trend charts, and CLI live in `openarmature-eval`. This
avoids bloating the core with plotting libraries and database drivers while keeping eval a first-class citizen in the
ecosystem.

**Pattern-composable.** The graph engine doesn't prescribe an agent pattern. Nodes, edges, conditional routing, and
state reducers are independent primitives that articulate into any pattern — ReAct, plan-and-execute, data pipelines,
multi-agent handoff, human-in-the-loop, or custom hybrids that mix patterns within the same graph. Most real-world
applications aren't pure examples of any single pattern; they're composites shaped by their domain. OpenArmature makes
that natural rather than fighting a prescribed architecture.

**No built-in prompts.** The framework never embeds hidden prompt text that shapes LLM behavior. No ReAct "Thought →
Action → Observation" templates, no hardcoded system messages, no default personas. Every prompt the LLM sees is
authored by the developer and visible in their code or prompt management system. This is a deliberate response to the
security and opacity problems with LangChain's built-in prompts (see
Rotas' [Built-in Prompts: What We Don't Use](./learning_langchain_langgraph.md#built-in-prompts-what-we-dont-use-and-why-thats-good)
analysis).

**Escape hatches everywhere.** Every default can be overridden. The framework handles the common case; the developer
handles the exceptional case.

### 2.3 Package Structure

OpenArmature is a **core package plus sibling packages**, not a monolith. The core stays focused; specialized concerns
live in their own packages with independent versioning.

```
openarmature                  Core: graph, state, LLM, tools, prompts (interfaces), logging
openarmature-eval             Eval: test runner, metrics, SQLite persistence, trend charts, CLI
openarmature-langfuse         Langfuse: prompt loading backend, trace linking, callback handler
openarmature-otel             OTEL: TracerProvider, LoggerProvider, HyperDX/Jaeger/Grafana exporters
```

**Why sibling packages instead of extras?**

Extras (`pip install openarmature[eval]`) install optional dependencies into the same package. Sibling packages are
independently versioned and maintained. The distinction matters:

- **Eval can evolve independently.** Adding new metric types, changing the SQLite schema, or adding a web-based report
  viewer doesn't require a core release. Teams using only the core for agent execution aren't affected.
- **Observability backends are swappable.** `openarmature-langfuse` and `openarmature-otel` implement the same
  observability interface. You install one, both, or neither. A team using Datadog instead of Langfuse writes
  `openarmature-datadog` against the same interface.
- **Core stays small.** The core's dependency footprint is minimal: `httpx`, `pydantic`, `structlog`, `jinja2`. No
  database drivers, no plotting libraries, no provider-specific SDKs.

**What lives where:**

| Concern                                                             | Package                          | Why here                                        |
|---------------------------------------------------------------------|----------------------------------|-------------------------------------------------|
| Graph engine (nodes, edges, state, reducers)                        | `openarmature`                   | Core orchestration — everything depends on it   |
| LLM abstraction (chat, health checks, provider presets)             | `openarmature`                   | Core — agents and pipelines both need it        |
| Tool system (ToolSet, MCP, local tools, schemas)                    | `openarmature`                   | Core — tool dispatch is fundamental             |
| Prompt loading interfaces (PromptManager, PromptResult, PromptPair) | `openarmature`                   | Core interfaces — backends plug in              |
| Prompt Langfuse backend (fetch from Langfuse, trace linking)        | `openarmature-langfuse`          | Provider-specific, optional                     |
| Structured logging (structlog setup, library suppression)           | `openarmature`                   | Core — everyone needs logging                   |
| Observability interfaces (trace context, span creation)             | `openarmature`                   | Core contracts — backends implement             |
| OTEL export (TracerProvider, LoggerProvider, exporters)             | `openarmature-otel`              | Backend-specific, heavy deps (protobuf, grpcio) |
| Langfuse callbacks (CallbackHandler, session grouping)              | `openarmature-langfuse`          | Provider-specific, optional                     |
| Eval metric base classes (DeterministicMetric, LLMJudgeMetric)      | `openarmature`                   | Core contracts — eval package implements        |
| Eval runner, persistence, trends, CLI                               | `openarmature-eval`              | Specialized tooling, independent release cycle  |
| Pipeline utilities (chunking, batch_process, StepRegistry)          | `openarmature`                   | Core — pipelines are a first-class pattern      |
| Companion tools (prompt_mgr REPL)                                   | Separate scripts or CLI packages | Workflow tooling, not library code              |

**Install patterns:**

```bash
# Agent with Langfuse observability
pip install openarmature openarmature-langfuse

# Pipeline with OTEL export + evaluation
pip install openarmature openarmature-otel openarmature-eval

# Minimal — just the graph engine and LLM client
pip install openarmature

# Everything
pip install openarmature openarmature-langfuse openarmature-otel openarmature-eval
```

### 2.4 Architecture Overview

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                     openarmature (core)                         │
    │                                                                 │
    │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
    │  │  Graph   │ │   LLM   │ │  Tools  │ │ Prompts │ │ Logging │ │
    │  │ Engine   │ │Provider │ │  (MCP   │ │(interfaces│ │(structlog│ │
    │  │(nodes,   │ │(vLLM,   │ │+ local) │ │ + local │ │ ambient)│ │
    │  │ edges,   │ │ OpenAI, │ │         │ │template)│ │         │ │
    │  │ state)   │ │Bifrost) │ │         │ │         │ │         │ │
    │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
    │                                                                 │
    │  Interfaces: ObservabilityBackend, PromptBackend, EvalMetric   │
    └──────────────────────────┬──────────────────────────────────────┘
                               │ implements
          ┌────────────────────┼────────────────────┐
          │                    │                    │
    ┌─────▼──────┐  ┌─────────▼────────┐  ┌───────▼────────┐
    │ openarmature│  │  openarmature    │  │  openarmature  │
    │  -langfuse  │  │    -otel         │  │    -eval       │
    │             │  │                  │  │                │
    │ Prompt fetch│  │ TracerProvider   │  │ Test runner    │
    │ Trace link  │  │ LoggerProvider   │  │ SQLite persist │
    │ Callbacks   │  │ OTLP exporters   │  │ Trend charts   │
    │ Session mgmt│  │ HyperDX/Jaeger  │  │ CLI            │
    └─────────────┘  └──────────────────┘  └────────────────┘
```

```

Single entrypoint:

```python
from openarmature import Agent, AgentConfig

agent = Agent(AgentConfig.from_env())
result = await agent.invoke(state)
```

Comparable to Rotas's `RotasAgent(config)` but without 6 manual initialization steps (LLM health check, MCP discovery,
Langfuse client creation, callback handler instantiation, graph compilation, prompt loading).

---

## 3. Module Breakdown

Each module section follows this structure:

- **What it replaces** — specific Rotas files and line counts
- **API surface** — key classes, functions, decorators
- **Code example** — concrete usage
- **How it differs** — comparison with current approach
- **Edge cases handled** — what the framework manages that developers currently build manually

---

### 3.1 Graph Engine

**What it replaces:** `rotas/graph.py` (79 lines), `rotas/state.py` (19 lines), the `langgraph` +
`langgraph-checkpoint` + `langchain-core` dependency chain.

**Design:**

Graph definition via decorator-based builder. State is a typed class with built-in message accumulation — no
`Annotated[list, add_messages]` import dance. Conditional edges via Python callables returning edge names. Compilation
produces an async-callable.

**API surface:**

```python
from openarmature import Graph, State, Message

class MyState(State):
    messages: list[Message]       # auto-accumulating (built-in reducer)
    custom_field: str = ""        # last-write-wins (default)
    items: list[str] = []         # explicit reducer via field config

graph = Graph(MyState)

@graph.node
async def agent(state: MyState) -> dict:
    """LLM call node. Returns state updates."""
    response = await llm.chat([SystemMessage(prompt), *state.messages])
    return {"messages": [response]}

@graph.node
async def execute_tools(state: MyState) -> dict:
    """Tool execution node."""
    results = await tools.execute(state.messages[-1].tool_calls)
    return {"messages": results}

@graph.edge(from_="agent")
def route(state: MyState) -> str:
    """Conditional routing based on state."""
    if state.messages[-1].tool_calls:
        return "execute_tools"
    return Graph.END

graph.add_edge("execute_tools", "agent")  # static edge

compiled = graph.compile()
result = await compiled.invoke(initial_state)
```

**How it differs from LangGraph:**

| LangGraph                                                                | OpenArmature                                                        |
|--------------------------------------------------------------------------|---------------------------------------------------------------------|
| `from langgraph.graph import StateGraph, START, END`                     | `from openarmature import Graph`                                    |
| `from langgraph.graph.message import add_messages`                       | Built into `State` — `messages: list[Message]` auto-accumulates     |
| `from langchain_core.messages import AIMessage, HumanMessage`            | `from openarmature import AIMessage, HumanMessage` (same namespace) |
| `workflow = StateGraph(AgentState)` then `workflow.add_node("name", fn)` | `@graph.node` decorator or `graph.add_node("name", fn)`             |
| `workflow.add_conditional_edges("agent", fn, [...])`                     | `@graph.edge(from_="agent")` decorator                              |
| 3 packages, 4 imports                                                    | 1 package, 1 import                                                 |

**Built-in reducers:**

```python
from openarmature import State, reducers

class MyState(State):
    messages: list[Message]                                    # auto: append + deduplicate
    counters: Annotated[dict[str, int], reducers.merge_dicts]  # merge dicts
    items: Annotated[list[str], reducers.append]               # append without dedup
    score: float = 0.0                                         # last-write-wins
```

**Node middleware:**

Rotas has a `pre_tool_call` node that runs before tool execution — counting tool calls, printing progress. This is a
common pattern. OpenArmature supports node middleware natively:

```python
@graph.before("execute_tools")
async def pre_tool_call(state: MyState) -> None:
    """Runs before execute_tools. Can modify state or produce side effects."""
    tool_count = len(state.messages[-1].tool_calls)
    console.print(f"Processing {tool_count} tool calls...")
```

**Edge cases handled:**

- State field type validation at compile time (not runtime)
- Cycle detection in graph topology
- Deadlock detection when all paths lead to blocked nodes
- Clear error messages when a node returns an unknown field name

**Supported agent patterns:**

The graph engine is pattern-agnostic — it provides nodes, edges, conditional routing, and state management. How you wire
them determines the agent pattern. Rotas uses REPL + single-shot tool-calling, but the same primitives express any
pattern:

**REPL + single-shot tool-calling** (what Rotas uses):

```python
# LLM makes all tool calls in one response, graph executes them, done.
# Outer CLI loop handles multi-turn conversation.
@graph.edge(from_="agent")
def route(state):
    if state.messages[-1].tool_calls:
        return "execute_tools"
    return Graph.END

graph.add_edge("execute_tools", "generate_summary")
```

**ReAct loop** (LLM decides when to stop):

```python
# Agent → tools → agent loop until LLM stops calling tools.
@graph.edge(from_="agent")
def route(state):
    if state.messages[-1].tool_calls:
        return "execute_tools"
    return Graph.END

graph.add_edge("execute_tools", "agent")  # loop back — key difference from Rotas
```

**Plan-and-execute** (plan upfront, execute sequentially):

```python
@graph.node
async def planner(state):
    """LLM creates a multi-step plan."""
    plan = await llm.chat([SystemMessage("Create a plan..."), *state.messages])
    return {"plan": parse_steps(plan), "current_step": 0}

@graph.node
async def executor(state):
    """Execute the current step."""
    step = state.plan[state.current_step]
    result = await tools.call(step.tool, step.args)
    return {"results": [result], "current_step": state.current_step + 1}

@graph.edge(from_="executor")
def next_step(state):
    if state.current_step < len(state.plan):
        return "executor"  # more steps
    return "summarize"
```

**Multi-agent handoff** (supervisor dispatches to specialists):

```python
@graph.node
async def supervisor(state):
    """Decides which specialist to invoke."""
    decision = await llm.chat([SystemMessage("Route to the right agent..."), *state.messages])
    return {"next_agent": decision.content}

@graph.edge(from_="supervisor")
def dispatch(state):
    return state.next_agent  # "research_agent", "coding_agent", "review_agent"

@graph.node
async def research_agent(state):
    """Specialist with its own tools and prompt."""
    ...
    return {"messages": [result]}

graph.add_edge("research_agent", "supervisor")  # hand back to supervisor
graph.add_edge("coding_agent", "supervisor")
```

**Human-in-the-loop** (pause for user confirmation):

```python
@graph.node
async def propose_action(state):
    """LLM proposes an action, graph pauses for user approval."""
    proposal = await llm.chat(...)
    return {"proposal": proposal, "awaiting_approval": True}

@graph.edge(from_="propose_action")
def check_approval(state):
    if state.awaiting_approval:
        return Graph.INTERRUPT  # pause graph, return control to caller
    return "execute_action"
```

**Data pipeline** (fixed order, no LLM routing):

Not all LLM applications are agents. Some are **pipelines** — a fixed sequence of steps where each step uses an LLM to
process data, and the output flows to the next step. The LLM is a tool *within* each step, but it doesn't decide which
steps run or in what order. The topology is defined in code, deterministic, and the same every time.

This is the pattern used by the Multivac project (a content analysis pipeline) where transcript analysis flows through:
product discovery → benefit analysis → ad detection → scoring. Each step's LLM call uses prompt pairs (system = task
instructions, user = context from prior steps).

```python
graph = Graph(PipelineState)

@graph.node
async def discover_products(state, llm, prompts):
    """Step 1: LLM extracts products from transcript."""
    pair = await prompts.get_pair("product_discovery", transcript=state.transcript)
    response = await llm.chat([SystemMessage(pair.system.text), HumanMessage(pair.user.text)])
    return {"discovered_products": parse_products(response)}

@graph.node
async def analyze_benefits(state, llm, prompts):
    """Step 2: LLM analyzes benefits using products from step 1."""
    pair = await prompts.get_pair("benefit_analysis",
        transcript=state.transcript,
        discovered_products=state.discovered_products,  # from step 1
    )
    response = await llm.chat([SystemMessage(pair.system.text), HumanMessage(pair.user.text)])
    return {"benefit_analysis": parse_benefits(response)}

@graph.node
async def score_outcomes(state, llm, prompts):
    """Step 3: LLM scores outcomes using all prior results."""
    pair = await prompts.get_pair("outcome_scoring",
        discovered_products=state.discovered_products,   # from step 1
        benefit_analysis=state.benefit_analysis,          # from step 2
    )
    response = await llm.chat([SystemMessage(pair.system.text), HumanMessage(pair.user.text)])
    return {"scores": parse_scores(response)}

# All edges are static — no conditional routing, no LLM decisions on flow
graph.add_edge(Graph.START, "discover_products")
graph.add_edge("discover_products", "analyze_benefits")
graph.add_edge("analyze_benefits", "score_outcomes")
graph.add_edge("score_outcomes", Graph.END)
```

Key differences from agent patterns:

- **All edges are static** — no conditional routing, no `@graph.edge` functions
- **No tool calls** — the LLM produces structured output, not tool invocations
- **Context flows forward through state** — each node reads prior results from state and injects them into prompt
  templates via `PromptPair`
- **Prompt pairs per step** — each node has its own system + user prompt, independently versioned in Langfuse
- **Deterministic execution** — same input always produces the same step sequence (though LLM output within each step is
  still probabilistic)

Pipelines benefit from the same graph infrastructure as agents: state management with reducers, observability (each node
is a traced span), error handling per step, and checkpointing for resume-after-failure. But pipelines also have their
own concerns that agents don't — the framework should address these natively.

**Pipeline-specific framework capabilities:**

These patterns are drawn from production pipeline implementations (notably the Multivac content analysis project) and
represent problems that every LLM pipeline rebuilds from scratch:

**1. Structured output validation and repair.** Pipeline steps typically expect structured JSON from the LLM, not
free-form text. The framework should provide a `structured_output()` method that handles the common failure modes:

```python
from openarmature import LLM, OutputSchema

# Define expected shape
schema = OutputSchema(model=ProductList)  # Pydantic model

# LLM call with automatic validation + repair
result = await llm.structured_output(
    messages=[SystemMessage(pair.system.text), HumanMessage(pair.user.text)],
    schema=schema,
    repair=True,           # attempt JSON repair on malformed output
    retry_on_truncation=True,  # detect truncation (finish_reason="length"), retry with doubled max_tokens
    max_retries=2,
)
# result.data   — validated Pydantic model instance
# result.raw    — raw LLM response text
# result.repaired — True if JSON repair was needed
# result.retries  — number of retries needed
```

This eliminates the manual JSON repair + truncation detection + retry loop that every pipeline implements. Multivac's
`llm_utils.py` dedicates ~450 lines to this; it should be a single method call.

**2. Input chunking with context overlap.** When inputs exceed token limits (long transcripts, large documents), the
framework should provide chunking utilities that maintain context continuity:

```python
from openarmature.pipeline import chunk_by_tokens

chunks = chunk_by_tokens(
    text=transcript,
    max_tokens=2500,            # per-chunk token budget
    overlap_lines=5,            # last N lines repeated at start of next chunk
    token_estimator="chars/4",  # or a tiktoken-based estimator
)

# Process each chunk, merge results
all_products = []
for chunk in chunks:
    result = await llm.structured_output(
        messages=[SystemMessage(system.text), HumanMessage(chunk)],
        schema=ProductList,
    )
    all_products.extend(result.data.products)

# Deduplicate merged results
products = deduplicate(all_products, key="product_name")
```

The chunking + merge + deduplicate pattern repeats across every pipeline that handles variable-length input. The
framework provides the chunking; the developer provides the merge/dedup logic (which is domain-specific).

**3. Partial failure handling.** Unlike agents (where a tool failure typically means "retry or abort"), pipelines often
want to continue with partial results. The framework should track per-step status without aborting the pipeline:

```python
class PipelineState(State):
    messages: list[Message]
    step_results: dict[str, StepResult] = {}    # per-step status tracking
    pipeline_status: str = "running"             # "running", "success", "partial", "failed"

@graph.node(on_error="continue")  # don't abort pipeline on step failure
async def analyze_benefits(state, llm, prompts):
    """If this step fails, state records the failure and pipeline continues."""
    ...
```

With `on_error="continue"`, a failed node records a `StepResult(status="failed", error=...)` in state and the pipeline
advances to the next step. Subsequent steps can check `state.step_results["analyze_benefits"].status` and adapt their
behavior. The final step reports overall pipeline status: "success" if all steps passed, "partial" if some failed, "
failed" if critical steps failed.

**4. Batch processing with incremental persistence.** Pipelines often process many items (100 transcripts, 500
documents). The framework should support batch execution with per-item callbacks for incremental saving:

```python
from openarmature.pipeline import batch_process

async def on_item_complete(item_id: str, result: dict):
    """Called after each item completes — save immediately, release memory."""
    await db.save(item_id, result)

results = await batch_process(
    graph=pipeline_graph,
    items=content_items,             # list of inputs to process
    on_result=on_item_complete,      # incremental persistence callback
    concurrency=3,                   # parallel item processing
)
# results.metrics — PipelineMetrics with totals
```

This prevents memory exhaustion on large batches (each item's state is released after callback) and ensures completed
work is persisted even if the batch is interrupted partway through.

**5. Step registry with per-step configuration.** Instead of hand-wiring every node, pipelines can declare steps as a
registry with enable/disable flags and per-step config:

```python
from openarmature.pipeline import StepRegistry, Step

steps = StepRegistry([
    Step(name="product_discovery", method="discover_products",
         enabled=config.ENABLE_PRODUCT_DISCOVERY,
         max_tokens=4096),
    Step(name="benefit_analysis", method="analyze_benefits",
         enabled=config.ENABLE_BENEFIT_ANALYSIS,
         max_tokens=8192,
         depends_on=["product_discovery"]),
    Step(name="ad_detection", method="detect_ads",
         enabled=config.ENABLE_AD_DETECTION,
         max_tokens=4096),
])

# Build a pipeline graph from the registry
graph = steps.to_graph(PipelineState)  # only enabled steps are wired
```

This is particularly useful when pipelines have many steps (Multivac has 8+ analysis steps per analyzer) with
per-environment toggles. The registry pattern keeps step definitions declarative and configuration-driven rather than
buried in graph wiring code.

**6. Pipeline metrics.** Agents track cost and latency per trace. Pipelines need aggregate metrics across an entire
batch run:

```python
@dataclass
class PipelineMetrics:
    total_items: int
    items_succeeded: int
    items_failed: int
    items_partial: int
    total_tokens: int                    # across all LLM calls
    total_cost: float                    # estimated cost
    per_step_timing: dict[str, float]    # avg duration per step
    per_step_tokens: dict[str, int]      # total tokens per step
    throughput: float                    # items per minute
    steps_repaired: int                  # JSON repair count
```

The framework collects these automatically from traced nodes and provides them in the batch result. No manual
aggregation needed.

**7. Checkpoint-based resumability.** Long-running pipelines crash. When they do, you don't want to re-run completed
stages. The framework should provide lightweight checkpoint persistence so pipelines resume from where they left off:

```python
from openarmature.pipeline import Checkpoint

checkpoint = Checkpoint(path="output/.checkpoints/")

@graph.node(checkpoint=True)  # auto-save state after this node completes
async def process_platforms(state, tools):
    """Stage 2: Process returns. Checkpointed — if stage 3 crashes,
    this stage's results are loaded from disk on restart."""
    results = await tools.call_batch([...])
    return {"processing_results": results}

# Resume from checkpoint on restart
graph = pipeline_graph.compile()
result = await graph.invoke(
    initial_state,
    checkpoint=checkpoint,     # loads completed stages from disk
    fresh=args.fresh,          # --fresh flag forces re-execution
)
```

How it works:

- After each checkpointed node completes, the framework serializes its state output to a JSON file (e.g.,
  `.checkpoints/process_platforms.json`)
- On restart, `graph.invoke()` checks for existing checkpoints. If a node's checkpoint exists and `fresh=False`, the
  node is skipped and its output is loaded from disk
- The `--fresh` flag invalidates all checkpoints and forces full re-execution (important during development)
- Checkpoints are keyed by node name + input hash, so different inputs don't collide

This is lighter than LangGraph's database-backed checkpointing — no external database, just JSON files on disk.
Appropriate for CLI pipelines and batch jobs where the execution environment is ephemeral but the filesystem persists.
For distributed or server-based pipelines, the checkpoint backend can be swapped to S3 or a database.

Drawn from the Bird-Dog project (a creator sourcing pipeline) which uses this pattern across 4 stages with JSON
serialization — if stage 3 fails, stages 1-2 are loaded from checkpoints in seconds.

**8. Rate limiting.** Any pipeline or agent calling external APIs needs rate limiting — and every project implements its
own. The framework should provide a configurable rate limiter:

```python
from openarmature import ToolSet, RateLimit

tools = await ToolSet.from_mcp(
    url="...",
    config=MCPConfig(
        rate_limit=RateLimit(requests_per_second=2),  # per-server limit
    ),
)

# Or per-tool limits for different APIs
tools.set_rate_limit("process_impact_returns", RateLimit(requests_per_minute=15))
tools.set_rate_limit("generate_report", RateLimit(requests_per_second=5))

# For direct LLM calls
llm = LLM(LLMConfig(
    provider="gemini",
    rate_limit=RateLimit(requests_per_minute=15),
))
```

The rate limiter uses a token bucket algorithm — configurable per-tool, per-server, or per-LLM provider. When a call
would exceed the limit, it waits (with backoff) rather than failing. This prevents API throttling errors that are
otherwise discovered at runtime and handled ad-hoc with `asyncio.sleep()` sprinkled throughout pipeline code.

Rate limiting composes with retry policies: if a call is rate-limited, it waits and retries without counting against the
retry budget. If the call fails for other reasons (network error, server error), the retry policy handles it separately.

**9. Resource lifecycle management.** Pipelines that use ML models, GPU resources, or heavy shared objects (database
connections, large caches) need a load-once / reuse / cleanup lifecycle. The framework should manage this so developers
don't manually load models at the top of a loop and hope they get cleaned up:

```python
from openarmature.pipeline import Resource

@graph.resource
async def whisper_model(config) -> AsyncGenerator:
    """Loaded once before the pipeline runs, shared across all nodes,
    cleaned up after the pipeline completes."""
    model = load_whisper_model(config.model_name, device=config.device)
    yield model
    del model
    torch.cuda.empty_cache()

@graph.resource
async def diarization_pipeline(config) -> AsyncGenerator:
    """Another shared resource — loaded once, reused across files."""
    pipeline = load_diarization_pipeline(config.hf_token)
    yield pipeline
    del pipeline

@graph.node
async def transcribe(state, whisper_model, diarization_pipeline):
    """Resources are injected by name — framework manages the lifecycle."""
    result = whisper_model.transcribe(state.audio_file)
    segments = diarization_pipeline.diarize(state.audio_file)
    return {"transcription": result, "segments": segments}
```

Resources are:

- **Loaded once** before the first node that needs them
- **Injected by name** into nodes that declare them as parameters
- **Shared** across all nodes and all batch items (no re-loading per file)
- **Cleaned up** after the pipeline completes (via generator `yield` pattern)
- **Tracked** — peak memory usage and load time reported in `PipelineMetrics`

This pattern is drawn from the Audio Refinery project (a GPU-accelerated audio pipeline) where ML models (WhisperX,
Pyannote diarization, HuggingFace sentiment) are loaded once before the batch loop and reused across all files. Without
framework support, developers manually load models, pass them as parameters, and hope cleanup happens — or leak GPU
memory.

**10. Processing strategies: per-item vs per-stage.** Pipelines can process items in two fundamentally different orders,
each with distinct memory/throughput tradeoffs:

**Per-item (interleaved)**: Each item passes through all stages before moving to the next item.

```text
file_1: separate → diarize → transcribe → sentiment
file_2: separate → diarize → transcribe → sentiment
file_3: separate → diarize → transcribe → sentiment
```

**Per-stage (batch)**: All items pass through one stage, then all through the next.

```text
stage 1: separate(file_1), separate(file_2), separate(file_3)
stage 2: diarize(file_1), diarize(file_2), diarize(file_3)
stage 3: transcribe(file_1), transcribe(file_2), transcribe(file_3)
```

| Strategy  | Memory                                                      | Throughput                                                | Best for                                        |
|-----------|-------------------------------------------------------------|-----------------------------------------------------------|-------------------------------------------------|
| Per-item  | Low — only one item's data in memory at a time              | Lower — can't batch GPU operations across items           | Large files, GPU-constrained, memory-sensitive  |
| Per-stage | Higher — all items' stage-N output in memory simultaneously | Higher — can batch GPU operations, amortize model loading | Small items, GPU-abundant, throughput-optimized |

The framework should support both via a `processing_strategy` config:

```python
graph = pipeline_graph.compile()

# Per-item: each item completes all stages before next item starts
result = await batch_process(graph, items, strategy="per_item")

# Per-stage: all items complete stage N before any start stage N+1
result = await batch_process(graph, items, strategy="per_stage")
```

Audio Refinery uses per-item (bounds GPU memory for large audio files). Multivac uses per-stage (all transcripts through
product discovery, then all through benefit analysis). Both are valid — the choice depends on item size, available
memory, and whether stages can batch operations.

**11. Typed inter-stage contracts via Pydantic.** Pipeline stages should declare their input and output types. The
framework validates at compile time that stage N's output type matches stage N+1's input type:

```python
from openarmature.pipeline import Step
from pydantic import BaseModel

class SeparationResult(BaseModel):
    vocals_path: str
    instrumental_path: str
    processing_time: float
    peak_vram_mb: float

class TranscriptionResult(BaseModel):
    text: str
    segments: list[Segment]
    word_count: int
    language: str

# Steps declare their result types
steps = StepRegistry([
    Step(name="separate", method=separate, result_type=SeparationResult),
    Step(name="transcribe", method=transcribe, result_type=TranscriptionResult,
         depends_on=["separate"]),
])

# Framework validates: does transcribe's input expect fields from SeparationResult?
graph = steps.to_graph(PipelineState)  # compile-time type check
```

This catches integration bugs early — if you change `SeparationResult` to rename `vocals_path` to `vocal_file`, the
compile step flags that `transcribe` expects `vocals_path`. Drawn from Audio Refinery's pattern where each stage returns
a Pydantic model (`SeparationResult`, `DiarizationResult`, `TranscriptionResult`) serialized to JSON.

**12. Cascade failure propagation.** When a pipeline item fails at stage N, downstream stages should automatically skip
that item rather than attempting to process missing input:

```python
@graph.node(cascade_on_failure=True)
async def separate(state):
    """If this fails for a specific item, diarize and transcribe
    are automatically skipped for that item."""
    ...
```

Different from `on_error="continue"` (which continues the pipeline regardless): cascade propagation tracks *which items*
failed and filters them out of downstream stages. The pipeline continues processing other items normally, but failed
items don't produce cascade errors in every subsequent stage.

Audio Refinery implements this by filtering `succeeded_ids` before each stage — only items that passed separation are
eligible for diarization. The framework should handle this automatically based on the `cascade_on_failure` flag.

**Patterns to consider for future iterations:**

The following patterns have been observed in production projects but are not core framework capabilities yet. They're
worth tracking as the framework matures:

- **LLM batching (multiple records per call)**: Instead of sending one item per LLM call, batch N items into a single
  prompt (e.g., "verify these 5 candidates"). Reduces API call count and amortizes prompt overhead. The framework could
  provide a `batch_prompt()` utility that chunks items, renders a batch template, and de-multiplexes the response.
  Trade-off: batch size vs output quality — larger batches risk truncation and reduce per-item attention.

- **Multi-provider API orchestration**: A dispatch pattern that routes requests to different external APIs based on
  input characteristics (e.g., TikTok queries → Zyla API, YouTube queries → YouTube Data API). Similar to MCP tool
  dispatch but for non-MCP HTTP APIs. The `ToolSet` could support registering plain HTTP endpoints alongside MCP tools.

- **CLI-first pipeline control**: Argument-based control of stage selection (`--stage scout`), product filtering (
  `--product "Brand X"`), and fresh runs (`--fresh`). The framework's `pipeline()` helper could auto-generate CLI
  arguments from the step registry.

- **GPU/compute resource tracking**: Per-stage VRAM peak tracking, GPU ordering by compute capability (FP16 TFLOPS),
  pre-flight process detection (warn if other workloads are using the GPU). Niche but important for ML pipelines.

- **Notification hooks**: Pipeline completion callbacks for external notifications (Slack, email, webhook). The
  framework could provide a `on_pipeline_complete` hook with the `PipelineMetrics` payload.

- **Tiered decision-making (deterministic first, LLM fallback)**: For agents where many requests have predictable
  answers, try a cheap/fast deterministic path first (keyword matching, rule engine, lookup table) and only escalate to
  the LLM when confidence is below a threshold. Reduces cost and latency for the common case. The MBT Game Agent uses
  this: CSV-based intent matching handles most commands; LLM clarification only fires when confidence < 0.65. The
  framework could support this via a `@graph.node(fallback="llm_clarify")` pattern or a `TieredRouter` that chains
  decision strategies.

- **Conversation memory reconstruction**: Instead of storing full conversation text (which grows unboundedly), store
  prompt templates + variable snapshots and reconstruct conversations by re-applying variables to templates on demand.
  Enables multi-turn coherence without growing context windows. The MBT Game Agent uses this for NPC dialogues —
  conversation history is stored as `(step_index, template_name, variables)` tuples and replayed at render time. For
  long-running agents with persistent state, this could significantly reduce token usage.

- **Mixed sync/async tool execution**: Agents may have tools that are sync (CPU-bound local computation) alongside async
  tools (network I/O). Rather than forcing all tools to be async or wrapping sync tools in `asyncio.to_thread()`, the
  framework could detect callable type via `inspect.iscoroutinefunction()` and dispatch accordingly — `await` for async,
  direct call for sync. The MBT Game Agent uses this pattern in its tool registry.

- **"Calculate First, Reason Second" pipeline pattern**: A strict separation where deterministic computation (Pandas,
  SQL, business logic) runs first and produces verified numbers, then the LLM receives only the pre-calculated results
  for narrative synthesis — never raw data. This eliminates arithmetic hallucination risk and enables independent
  evolution of formulas vs prompts. The Manukora S&OP project uses this: 15+ supply chain metrics are computed in
  Pandas, then Claude synthesizes them into an executive briefing. Ground truth values (like air freight eligibility)
  are withheld from the LLM payload and used only in eval tests to validate reasoning. The framework could formalize
  this as a `compute_then_reason` pipeline helper that separates deterministic nodes (no LLM, pure computation) from
  reasoning nodes (LLM call on pre-computed context).

- **LLM provider factory with environment switching**: A factory pattern that selects between Anthropic SDK (production)
  and OpenAI-compatible client (local LM Studio) based on an environment variable, without framework overhead. The
  Manukora project uses `ENV=local` vs `ENV=production` to switch between local Mistral and cloud Claude with the same
  prompt interface. The framework's `LLMConfig(provider=...)` presets already handle this, but the factory pattern shows
  the value of making provider switching a deployment concern, not a code change.

- **Eval with withheld ground truth**: For "calculate first, reason second" pipelines, deterministic outputs (known
  correct answers) can be withheld from the LLM and used only in eval tests to validate whether the LLM's reasoning is
  faithful to the data it received. The Manukora project withholds `Air_Freight_Candidate` flags from the LLM payload
  and uses DeepEval to check whether the LLM correctly identifies air freight needs from the metrics alone. This is a
  powerful eval pattern for any pipeline where ground truth is computable.

**Subgraphs** (nested workflows):

```python
# A tool with its own multi-step workflow
upload_graph = Graph(UploadState)
# ... define nodes for: validate → transform → upload → verify

# Compose into the main graph
main_graph = Graph(MainState)
main_graph.add_subgraph("upload_pipeline", upload_graph)
```

**Composing patterns — the key differentiator:**

The framework doesn't prescribe a pattern. The same `Graph` + `State` + `@graph.node` + `@graph.edge` primitives compose
into whatever execution model the application needs. More importantly, **patterns mix within the same graph**.
Real-world agents rarely fit one pure pattern — they're composites shaped by domain requirements.

Rotas is already a mild hybrid: it's mostly single-shot tool-calling, but the `check_retry` node introduces a
human-in-the-loop element (asking the user whether to retry failed months) that a pure single-shot pattern wouldn't
have. That hybrid emerged naturally from the domain — it wasn't designed as "single-shot with human-in-the-loop." It was
designed as "what makes sense for processing monthly reports with potential failures."

A more complex example — a code review agent that blends three patterns in one graph:

```python
graph = Graph(ReviewState)

# --- Plan-and-execute: create review plan upfront ---
@graph.node
async def plan_review(state, llm):
    """LLM analyzes the diff and creates a multi-pass review plan."""
    plan = await llm.chat([SystemMessage("Create a review plan: security, style, logic")])
    return {"review_plan": parse_steps(plan), "current_pass": 0}

# --- ReAct loop: each review pass may need multiple tool calls ---
@graph.node
async def review_pass(state, llm, tools):
    """Execute one review pass. LLM can call tools (grep, read file, check CI)
    and loop until it has enough information to produce findings."""
    pass_name = state.review_plan[state.current_pass]
    response = await llm.chat([
        SystemMessage(f"Review pass: {pass_name}. Use tools as needed."),
        *state.messages,
    ], tools=tools)
    return {"messages": [response]}

@graph.edge(from_="review_pass")
def review_pass_route(state):
    if state.messages[-1].tool_calls:
        return "execute_tools"         # ReAct: loop back through tools
    return "collect_findings"          # pass complete, collect results

graph.add_edge("execute_tools", "review_pass")  # ReAct loop

@graph.node
async def collect_findings(state):
    """Accumulate findings from this pass, advance to next."""
    return {"current_pass": state.current_pass + 1}

@graph.edge(from_="collect_findings")
def next_pass(state):
    if state.current_pass < len(state.review_plan):
        return "review_pass"           # plan-and-execute: next step
    return "draft_review"

# --- Human-in-the-loop: approve before posting ---
@graph.node
async def draft_review(state, llm):
    """Synthesize all findings into a review comment."""
    review = await llm.chat([SystemMessage("Draft the review from findings...")])
    return {"draft": review.content}

@graph.edge(from_="draft_review")
def approve(state):
    return Graph.INTERRUPT             # pause for user approval

@graph.node
async def post_review(state, tools):
    """Post the approved review to GitHub."""
    await tools.call("github_comment", {"body": state.draft})
    return {"posted": True}
```

This graph uses plan-and-execute for the overall structure (plan → execute each pass → synthesize), ReAct within each
review pass (tool calls loop until the LLM has enough information), and human-in-the-loop at the end (user approves
before posting). Three patterns, one graph, no fighting the framework.

**Hybrid graphs — agent + pipeline in the same graph:**

The most practically important composition isn't mixing two agent patterns — it's mixing **agent and pipeline** in the
same graph. Many real-world applications have an LLM making decisions at the front (agent phase) followed by a fixed
sequence of data processing steps (pipeline phase). The LLM figures out *what* to do; the pipeline *does* it.

This matters because agents and pipelines have fundamentally different characteristics:

| Concern            | Agent phase                                     | Pipeline phase                                      |
|--------------------|-------------------------------------------------|-----------------------------------------------------|
| Routing            | LLM-driven (conditional edges)                  | Fixed (static edges)                                |
| Prompts            | Single system prompt + conversation history     | Prompt pairs per step with context from prior steps |
| State flow         | Messages accumulate                             | Structured data flows forward                       |
| LLM role           | Decision-maker (which tools? which parameters?) | Processor (analyze this data, score these results)  |
| Observability need | "Did the LLM understand the request?"           | "Did step 2's output match step 1's input?"         |

Rotas' planned full workflow is a natural hybrid:

```python
graph = Graph(RotasState)

# ═══════════════════════════════════════════════
# AGENT PHASE — LLM decides what to do
# ═══════════════════════════════════════════════

@graph.node
async def agent(state, llm, tools, prompts):
    """LLM interprets user request, decides which tools to call.
    Uses single system prompt with tool descriptions."""
    system = await prompts.get("system_prompt",
        current_date=today(), tool_description=tools.describe())
    response = await llm.chat(
        [SystemMessage(system.text), *state.messages], tools=tools)
    return {"messages": [response]}

@graph.edge(from_="agent")
def route(state):
    """LLM-driven routing — conditional based on what the LLM decided."""
    last = state.messages[-1]
    if last.tool_calls:
        tool_names = {tc["name"] for tc in last.tool_calls}
        if tool_names & {"process_impact_returns", "process_rakuten_returns", "process_cj_returns"}:
            return "process_platforms"    # enter pipeline phase
        if "generate_report" in tool_names:
            return "generate_report"
        if "sync_report_to_sheets" in tool_names:
            return "sync_to_sheets"
    return Graph.END

# ═══════════════════════════════════════════════
# PIPELINE PHASE — fixed order, context flows forward
# ═══════════════════════════════════════════════

@graph.node
async def process_platforms(state, tools):
    """Execute platform processing tools in parallel.
    No LLM routing — all three always run."""
    results = await tools.call_batch([
        ("process_impact_returns", {"month": state.report_month}),
        ("process_rakuten_returns", {"month": state.report_month}),
        ("process_cj_returns", {"month": state.report_month}),
    ], concurrency=3)
    return {"processing_results": results}

@graph.node
async def generate_report(state, tools, prompts):
    """Generate summary report using processing results as context.
    Uses prompt pair — system defines the task, user carries context."""
    pair = await prompts.get_pair("report_summary",
        processing_results=state.processing_results,  # from process_platforms
        report_month=state.report_month,
    )
    report = await tools.call("generate_report", {
        "report_month": state.report_month,
        "use_preview_db": state.use_preview_db,
    })
    return {"report_data": report}

@graph.node
async def sync_to_sheets(state, tools):
    """Sync report to Google Sheets. Fixed step, no LLM decisions."""
    result = await tools.call("sync_report_to_sheets", {
        "report_month": state.report_month,
    })
    return {"sync_result": result}

@graph.node
async def present_results(state, console):
    """Build Rich panel summary. Final step."""
    # ... Rich UI output
    return {"report_generated": True}

# Pipeline edges — static, deterministic
graph.add_edge("process_platforms", "generate_report")  # always
graph.add_edge("generate_report", "sync_to_sheets")     # always
graph.add_edge("sync_to_sheets", "present_results")     # always
graph.add_edge("present_results", Graph.END)
```

The visual structure makes the hybrid nature clear:

```text
                    Agent Phase                          Pipeline Phase
              (LLM decides what)                    (fixed order, does it)
              
User input → [agent] ─── route() ──→ [process_platforms] → [generate_report] → [sync_to_sheets] → [present_results] → END
                │                          (parallel)           (sequential)        (sequential)        (sequential)
                │
                ├── "just generate a report" ──→ [generate_report] → [present_results] → END
                │
                └── conversational response ──→ END
```

The agent phase uses conditional edges (the LLM's tool calls determine routing). The pipeline phase uses static edges (
every step always runs in order). Context flows through state: `process_platforms` writes `processing_results`,
`generate_report` reads it and writes `report_data`, `sync_to_sheets` reads it.

**Why the distinction matters for prompts and observability:**

In the agent phase, the LLM uses a single system prompt with tool descriptions and conversation history. There are no
prompt pairs — the LLM is making decisions, not processing data.

In the pipeline phase, each step can use `PromptPair` with context injection. The system prompt defines the step's
task ("analyze these processing results for anomalies"), the user prompt carries structured data from prior steps. Each
pair is independently versioned in Langfuse with dual trace observations, so you can debug exactly which prompt version
and which context produced each step's output.

This means the observability story is different for each phase:

- **Agent phase traces** answer: "Did the LLM understand the user's request? Did it pick the right tools?"
- **Pipeline phase traces** answer: "Did step N's context from step N-1 look correct? Did the prompt template render the
  data properly? Which version of the scoring prompt produced this result?"

**Why this matters:**

Most frameworks force a choice. `create_react_agent` gives you ReAct — if you need a fixed processing pipeline after the
agent decides, you build it outside the framework. CrewAI gives you task-based sequential/parallel — if one task needs
LLM-driven routing, you're on your own. The Anthropic Agents SDK gives you handoffs — there's no concept of "after the
agent decides, run these steps in order."

OpenArmature's graph primitives are **below** the pattern level. They're the joints in the armature — each one bends
independently, and the combination of bends produces the form. You don't pick "agent" or "pipeline"; you wire nodes and
edges that match your domain, and the hybrid emerges. The conditional edges handle the agent parts, the static edges
handle the pipeline parts, and the framework treats both the same.

This is especially valuable as applications evolve. Rotas started as a pure agent (single-shot tool-calling). The
planned expansion adds a pipeline phase (process → report → sync). With OpenArmature, that's adding nodes and static
edges — not migrating from an agent framework to a pipeline framework or trying to make one pretend to be the other.

**Prebuilt patterns as convenience, not constraint:**

Common topologies can be provided as helper functions that wire primitives into standard shapes:

```python
from openarmature.patterns import react_loop, plan_execute, pipeline, with_approval

# These return configured Graph instances — inspect, extend, override
graph = react_loop(llm, tools)                          # standard ReAct
graph = plan_execute(planner_llm, executor_llm, tools)  # plan-and-execute
graph = pipeline(step_1, step_2, step_3)                # fixed-order data pipeline
graph = with_approval(inner_graph, approve_fn)           # wrap any graph with HITL gate

# Hybrid: agent front-end with pipeline back-end
main = react_loop(llm, tools)
processing = pipeline(process_platforms, generate_report, sync_to_sheets)
main.add_subgraph("processing_pipeline", processing)
```

These are starting points, not cages. You can take a `react_loop()`, add a node, rewire an edge, and have a customized
hybrid. The helpers compose because they produce the same `Graph` object that hand-wired graphs produce.

**Important: pattern helpers wire topology, not prompts.** `react_loop()` creates the `agent → tools → agent` loop
structure, but it does **not** embed a ReAct prompt ("Thought → Action → Observation"). The developer supplies the
system prompt — the helper only wires the graph. This is a key distinction from LangChain's `create_react_agent`, which
embeds its own prompt logic. In OpenArmature, graph structure and prompt content are always independent concerns.

---

### 3.2 Native MCP Support

**What it replaces:** `rotas/mcp_client.py` (302 lines) in its entirety.

**Design:**

MCP is a first-class transport for tools. `ToolSet.from_mcp()` handles discovery, cold-start, retry, session lifecycle,
and schema generation — all configurable via declarative policy objects.

**API surface:**

```python
from openarmature import ToolSet, MCPConfig, RetryPolicy, ColdStartConfig, TimeoutConfig

tools = await ToolSet.from_mcp(
    url="https://mcp.example.com/mcp",
    token="bearer-token",
    config=MCPConfig(
        cold_start=ColdStartConfig(
            health_url="https://mcp.example.com/health",
            max_attempts=6,
            interval=5,        # seconds between health checks
            init_wait=5,       # seconds to wait after health check passes
        ),
        retry=RetryPolicy(
            max_retries=3,
            initial_delay=3.0,
            backoff_multiplier=1.2,
            max_delay=10.0,
        ),
        timeouts=TimeoutConfig(
            init=30,           # connection/initialization timeout
            operation=600,     # per-tool-call timeout
            discovery=15,      # list_tools() timeout
        ),
        transports=["streamable-http", "sse"],  # preferred transport order
    ),
)

# Tools are now ready — schemas auto-generated from MCP discovery
print(tools.schemas)  # OpenAI function-calling format, auto-converted

# Call a tool — routing is automatic
result = await tools.call("generate_report", {"report_month": "2025-03", "use_preview_db": False})
```

**What the framework manages internally:**

| Concern                         | Rotas (manual)                                                                     | OpenArmature (automatic)                             |
|---------------------------------|------------------------------------------------------------------------------------|------------------------------------------------------|
| Health check polling            | `wake_up_server()` — 30 lines                                                      | `ColdStartConfig` — declared, framework executes     |
| Retry with backoff              | `discover_tools()` — 70 lines                                                      | `RetryPolicy` — declared, framework executes         |
| Session lifecycle               | Manual `__aenter__`/`__aexit__`, cleanup on error                                  | Framework-managed; developer never sees sessions     |
| Fresh client on retry           | Manual recreation in retry loop                                                    | Automatic — each retry gets a fresh transport        |
| Error classification            | `HTTPStatusError` / `BrokenResourceError` / `ClosedResourceError` checked manually | Built-in error taxonomy with per-type retry behavior |
| Schema generation               | Hardcoded `ClassVar[dict]` in `nodes.py`                                           | Auto-generated from MCP `list_tools()` response      |
| Call retry with session refresh | Manual cleanup → rediscover → retry in `call_tool()`                               | `tools.call()` handles transparent retry             |

**Transport support:**

OpenArmature handles SSE, stdio, and streamable-HTTP MCP transports. The transport is selected automatically based on
the URL scheme or can be forced via config:

```python
# Remote server (auto-detects streamable-HTTP or SSE)
tools = await ToolSet.from_mcp(url="https://mcp.example.com/mcp", ...)

# Local process via stdio
tools = await ToolSet.from_mcp(command="python mcp_server.py", transport="stdio")
```

**Edge cases handled:**

- Fly.io cold starts (health check → wait → connect)
- Lambda cold starts (different timing profile, configurable via `ColdStartConfig`)
- Stale sessions after server restart (automatic session refresh on call failure)
- Partial discovery failure (retry logic with exponential backoff)
- Concurrent calls on the same session (internal session pooling)
- Server-side schema changes (schema refresh on configurable interval or manual `tools.refresh()`)

---

### 3.3 LLM Provider Abstraction

**What it replaces:** `rotas/llm_client.py` (185 lines), the `langchain-openai` dependency (`ChatOpenAI`).

**Design:**

Direct OpenAI-compatible HTTP via `httpx`. Provider presets handle endpoint quirks. Health checks, timeout handling, and
config composition are built-in.

**API surface:**

```python
from openarmature import LLM, LLMConfig

llm = LLM(LLMConfig(
    provider="vllm",                              # preset: knows health endpoint, auth pattern
    base_url="http://localhost:8000/v1",
    model="my-model",
    temperature=0,
    timeout=60.0,
))

# Health check — first-class operation
health = await llm.check_health()
# HealthResult(ok=True, models=["my-model"], latency_ms=23)

# Chat with tools
response = await llm.chat(
    messages=[SystemMessage("You are a helpful agent."), HumanMessage("Generate a report for 2025-03")],
    tools=tool_set,          # ToolSet from MCP or local registration
    tool_choice="auto",
)
# response is an AIMessage with .content and .tool_calls

# Config composition — apply overrides from prompt metadata
llm.apply_config({"temperature": 0.7, "max_tokens": 4096})
```

**Provider presets:**

| Provider    | Health endpoint  | Auth                | Quirks handled                                        |
|-------------|------------------|---------------------|-------------------------------------------------------|
| `vllm`      | `GET /v1/models` | None (dummy key)    | No API key required; health checks model availability |
| `openai`    | N/A (always up)  | `OPENAI_API_KEY`    | Standard OpenAI behavior                              |
| `anthropic` | N/A              | `ANTHROPIC_API_KEY` | Tool use block structure differs from OpenAI          |
| `bifrost`   | `GET /v1/models` | Token-based         | Proxy routing; model aliasing                         |
| `ollama`    | `GET /api/tags`  | None                | Different health endpoint; model pull detection       |
| `custom`    | Configurable     | Configurable        | Full manual control                                   |

**How it differs from ChatOpenAI:**

| ChatOpenAI                                   | OpenArmature LLM                                             |
|----------------------------------------------|--------------------------------------------------------------|
| `api_key=SecretStr("EMPTY")` for vLLM        | Provider preset handles this automatically                   |
| No pre-flight health check                   | `await llm.check_health()` validates model availability      |
| `max_retries` unreliable for timeouts        | `httpx` native timeout handling; explicit `timeout` config   |
| `bind_tools()` returns a new object          | `tools=` parameter on `chat()`; no object mutation           |
| Config patching via direct mutation          | `llm.apply_config()` merges declaratively                    |
| Streaming via `astream()` on a separate call | `await llm.chat(..., stream=True)` returns an async iterator |

**Edge cases handled:**

- vLLM model not loaded (health check catches before first call)
- Connection refused / timeout (clear error messages with provider context)
- Tool-calling format differences across providers (OpenAI parallel calls vs Anthropic `tool_use` blocks)
- Config override from prompt metadata without permanent mutation
- Bifrost proxy routing (model aliasing, failover between backends)

---

### 3.4 Tool System

**What it replaces:** `rotas/nodes.py` lines 589-673 (~85 lines of hardcoded schemas + `_tool_schemas()` method), plus
the dispatch logic in `call_tools()`.

**Design:**

`ToolSet` is the unified container for MCP-discovered tools and locally-registered tools. Schemas are generated from MCP
discovery or Python type hints — never hardcoded. Execution routing (MCP vs local) is handled by the `ToolSet`, not by
graph node code.

**API surface:**

```python
from openarmature import ToolSet

# MCP tools — schemas auto-discovered
tools = await ToolSet.from_mcp(url="...", config=MCPConfig(...))

# Local tools — schema auto-generated from type hints
@tools.local
async def sync_report_to_sheets(report_month: str) -> dict:
    """Sync a monthly returns report from S3 to Google Sheets.

    Args:
        report_month: Month in YYYY-MM format (e.g. 2025-05)
    """
    return await sheets_sync.sync(report_month)

# Or register with an explicit schema
tools.register("custom_tool", my_async_fn, schema={
    "type": "function",
    "function": {
        "name": "custom_tool",
        "description": "...",
        "parameters": {"type": "object", "properties": {...}},
    },
})

# Unified schema list (OpenAI function-calling format)
all_schemas = tools.schemas  # MCP + local, same format

# Execution — routing is automatic
result = await tools.call("generate_report", {"report_month": "2025-03"})
result = await tools.call("sync_report_to_sheets", {"report_month": "2025-03"})

# Batch execution with concurrency control
results = await tools.call_batch(
    [
        ("generate_report", {"report_month": "2025-01"}),
        ("generate_report", {"report_month": "2025-02"}),
        ("generate_report", {"report_month": "2025-03"}),
    ],
    concurrency=3,  # max parallel calls
)

# Tool description for prompt injection
desc = tools.describe()  # formatted text for system prompt inclusion

# Schema validation against MCP server
mismatches = await tools.validate_schemas()  # compares local expectations vs MCP reality
```

**How it differs:**

| Current (Rotas)                                                 | OpenArmature                                  |
|-----------------------------------------------------------------|-----------------------------------------------|
| `GENERATE_REPORT_SCHEMA = {...}` as ClassVar                    | Auto-generated from `list_tools()`            |
| `SYNC_TOOL_SCHEMA = {...}` as ClassVar                          | Auto-generated from `@tools.local` type hints |
| `_tool_schemas()` merges manually                               | `tools.schemas` returns unified list          |
| `if name in self.local_tools: ... else: mcp_client.call_tool()` | `tools.call(name, args)` routes automatically |
| No schema validation                                            | `tools.validate_schemas()` detects drift      |
| `build_tool_description()` formats schemas for prompt           | `tools.describe()` built-in                   |

**Edge cases handled:**

- MCP server schema changes between discovery and call (schema refresh)
- Local tool type hint edge cases (Optional params, Union types, default values)
- Tool name collisions between MCP and local (explicit error at registration time)
- Result normalization (MCP `ClientResult` vs local dict vs string — all normalized to consistent format)
- Concurrent call support with configurable batch size

---

### 3.5 Observability

**What it replaces:** `rotas/tracing.py` (154 lines), `rotas/logging_config.py` (137 lines), `rotas/cli.py` lines 66-78
and 123-139 (~50 lines of Langfuse setup).

**Package split:** The core (`openarmature`) defines observability interfaces and provides ambient instrumentation (
correlation IDs, span context, structured logging). Specific backends live in sibling packages: `openarmature-langfuse`
for Langfuse callbacks/prompt linking/session grouping, `openarmature-otel` for OTEL
TracerProvider/LoggerProvider/exporters. You install the backend you need; the core instruments regardless.

**Design:**

Observability is ambient — configured once, then automatic. The framework instruments graph execution, LLM calls, and
tool calls without decorator wiring or callback plumbing. Correlation IDs propagate automatically through async context.

**API surface:**

```python
from openarmature import Agent, ObserveConfig, OTELConfig

agent = Agent(
    ...,
    observe=ObserveConfig(
        # Langfuse — auto-reads LANGFUSE_* env vars when True
        langfuse=True,

        # OTEL — for HyperDX, Jaeger, Grafana, etc.
        otel=OTELConfig(
            endpoint="http://localhost:4318",
            api_key="your-key",
            service_name="rotas",
        ),
    ),
)

# Everything below is automatic:
# - Correlation ID generated per invoke(), propagated to all spans and logs
# - LLM calls traced with token usage, latency, model info
# - Tool calls traced with args, result, duration, error status
# - Graph node transitions traced
# - Langfuse traces linked to OTEL spans via correlation ID
# - All providers flushed on agent shutdown

result = await agent.invoke(state)

# Custom spans still available for domain logic
from openarmature.observe import traced

@traced
async def my_custom_operation():
    """This span nests under the current graph invocation automatically."""
    ...
```

**What the framework manages:**

| Concern                    | Rotas (manual)                                                                       | OpenArmature (automatic)                                                                |
|----------------------------|--------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| Correlation ID             | `ContextVar` + manual `set()`/`reset()` tokens per `ainvoke()`                       | Generated and propagated automatically per `invoke()`                                   |
| OTEL provider isolation    | Deliberately NOT calling `trace.set_tracer_provider()` (comment in tracing.py:69-72) | Framework creates isolated provider by default; Langfuse v3 span duplication impossible |
| Langfuse callback          | Manual `CallbackHandler()` + `config={"callbacks": [...]}` on every call             | Automatic when `langfuse=True`                                                          |
| Dual OTEL exporters        | `TracerProvider` + `LoggerProvider` configured separately                            | Single `OTELConfig`, framework sets up both                                             |
| Flush on exit              | Manual `langfuse.flush()` + `shutdown_telemetry()`                                   | Automatic via agent lifecycle                                                           |
| Library logger suppression | 9 loggers suppressed by name in `logging_config.py`                                  | Framework knows its dependency tree, suppresses automatically                           |
| Langfuse session grouping  | Manual `session_id` in `config={"metadata": {...}}`                                  | Automatic per-agent-session                                                             |

**OTEL provider isolation — solving the Langfuse v3 trap:**

When Langfuse v3 is installed and a global OTEL `TracerProvider` is set, Langfuse exports its LLM/graph spans through
it — duplicating data that's already in Langfuse's UI. Rotas discovered this the hard way and deliberately avoids
`trace.set_tracer_provider()` (tracing.py:69-72).

OpenArmature solves this by default: it creates an isolated `TracerProvider` for its own spans and never registers it
globally. The `@traced` decorator and internal instrumentation use this isolated provider explicitly. Langfuse v3 cannot
see it, so duplication is impossible.

**Edge cases handled:**

- Langfuse unavailable at startup (graceful degradation, observability disabled)
- OTEL endpoint unreachable (fallback to local file logging, same as Rotas's `_check_otel_endpoint`)
- Async context propagation across `asyncio.gather()` and `TaskGroup` (correlation ID preserved)
- Nested spans from `@traced` decorators nest correctly under graph invocation spans
- Cost tracking for custom/local models (configurable per-token pricing)

---

### 3.6 Prompt Management

**What it replaces:** `rotas/nodes.py` lines 370-583 (~210 lines) — the three `load_*_prompt()` functions,
`PromptResult` dataclass, `_get_prompt_label()`, `_load_local_*_template()` helpers, `prompt_labels.json`.

**Package split:** The core (`openarmature`) provides `PromptManager`, `PromptResult`, `PromptPair`, and
`PromptConfig` — the interfaces and local Jinja2 template loading. The Langfuse-specific backend (fetching prompts from
Langfuse, label resolution, trace linking) lives in `openarmature-langfuse`. When `openarmature-langfuse` is installed
and configured, `PromptManager` automatically uses it as the primary source with local templates as fallback. Without
it, prompts load from local templates only.

Companion tools like the Prompt Manager REPL (`scripts/prompt_mgr.py`) are separate workflow scripts, not library code.
They orchestrate between the framework's prompt loading and Langfuse's API, handling the development workflow (push,
label, diff, status) that doesn't belong in the framework itself.

**Design:**

Multi-source prompt loading with priority chain: Langfuse (via `openarmature-langfuse`) → local template → inline
default. Configured declaratively per-prompt. The identical try/catch/fallback pattern that Rotas implements three times
becomes a single framework call.

The prompt system supports two usage patterns:

1. **Single prompts** — load one prompt by name with variables (what Rotas does today)
2. **Prompt pairs** — system + user prompts loaded together, where the system prompt defines the task and the user
   prompt carries dynamic context from prior graph steps (inspired by the Multivac project's analysis pipeline pattern)

Both patterns use Jinja2 templates stored in Langfuse and rendered locally. Langfuse's built-in Mustache renderer can't
handle conditionals, loops, or filters (`tojson`, `join`) — so raw Jinja2 text is stored in Langfuse and the framework
renders it with full template features. This is the same approach used in both Rotas and Multivac, standardized as the
default.

Templates use `StrictUndefined` — missing variables fail loudly at render time rather than silently producing empty
strings. If a prompt expects `{{ discovered_products }}` and you don't pass it, you get an immediate error, not a broken
prompt that the LLM interprets unpredictably.

**API surface — single prompts:**

```python
from openarmature import PromptManager, PromptConfig

prompts = PromptManager(
    langfuse=True,                           # auto-reads env vars
    template_dir="rotas/templates/",         # local Jinja2 fallback
    prompts={
        "system_prompt": PromptConfig(
            label="production",              # Langfuse label
            variables=["current_date", "current_month", "tool_description"],
            template="system_prompt.j2",     # local fallback file
        ),
        "summarize_error": PromptConfig(
            label="staging",                 # different label for testing
            template="summarize_error.j2",
        ),
        "closing_message": PromptConfig(
            label="production",
            template="closing_message.j2",
        ),
    },
)

# Load a prompt — tries Langfuse first, falls back to local template
result = await prompts.get(
    "system_prompt",
    current_date="2025-04-11",
    current_month="2025-04",
    tool_description=tools.describe(),
)

# result.text         — the rendered prompt string
# result.source       — "langfuse" or "local"
# result.version      — Langfuse version number (None if local)
# result.config       — model params from Langfuse (temperature, max_tokens)
# result.prompt_ref   — Langfuse prompt client for trace linking (None if local)

# Apply prompt config to LLM
llm.apply_config(result.config)

# Get all current prompt versions (for eval tracking)
versions = await prompts.versions()
# {"system_prompt": {"source": "langfuse", "version": 5, "label": "production"}, ...}
```

**API surface — prompt pairs with context injection:**

For multi-step pipelines where each step's results feed into subsequent prompts, use `PromptPair`. Each pair has a
static system prompt (task instructions) and a dynamic user prompt (context from prior steps):

```python
from openarmature import PromptManager, PromptPair

prompts = PromptManager(
    langfuse=True,
    template_dir="templates/",
    prompts={
        # Prompt pair: system defines the task, user carries context
        "product_analysis": PromptPair(
            system=PromptConfig(label="production", template="product_analysis_system.j2"),
            user=PromptConfig(
                label="production",
                template="product_analysis_user.j2",
                variables=["transcript", "discovered_products"],
            ),
        ),
        "benefit_outcomes": PromptPair(
            system=PromptConfig(label="production", template="benefit_outcomes_system.j2"),
            user=PromptConfig(
                label="production",
                template="benefit_outcomes_user.j2",
                variables=["transcript", "discovered_products", "product_analysis_results"],
            ),
        ),
    },
)

# Load a prompt pair — both system and user loaded, traced separately
pair = await prompts.get_pair(
    "benefit_outcomes",
    transcript=chunk_text,
    discovered_products=["Product A", "Product B"],       # from prior step
    product_analysis_results=step_1_output,                # from prior step
)

# pair.system  — PromptResult for system prompt
# pair.user    — PromptResult for user prompt (with context rendered)
# Both have independent .source, .version, .prompt_ref for trace linking

response = await llm.chat([
    SystemMessage(pair.system.text),
    HumanMessage(pair.user.text),
])
```

**Context injection from graph state:**

In a graph-based agent, the natural source of context is the graph state. Nodes can declare which state fields their
prompts need, and the framework injects them at render time:

```python
@graph.node
async def analyze_results(state: PipelineState, llm, prompts) -> dict:
    """Step 2: analyze results from step 1, with step 1's output as context."""
    pair = await prompts.get_pair(
        "result_analysis",
        # Context from prior graph steps — available in state
        processing_results=state.processing_results,
        failed_platforms=state.failed_platforms,
        report_month=state.report_month,
    )
    response = await llm.chat([
        SystemMessage(pair.system.text),
        HumanMessage(pair.user.text),
    ])
    return {"messages": [response], "analysis_complete": True}
```

The context flow follows the graph:

```text
process_platforms (step 1)
  └─ state.processing_results = [...]
  └─ state.failed_platforms = [...]
       │
       ▼
analyze_results (step 2)
  └─ prompts.get_pair("result_analysis",
       processing_results=state.processing_results,  ← from step 1
       failed_platforms=state.failed_platforms)       ← from step 1
       │
       ▼
generate_report (step 3)
  └─ prompts.get_pair("report_generation",
       analysis=state.analysis,                      ← from step 2
       processing_results=state.processing_results)  ← from step 1
```

Each step's prompt templates can use full Jinja2 features on the injected context:

```jinja2
{# benefit_outcomes_user.j2 #}
Products discovered in prior analysis:
{{ discovered_products | join(', ') }}

{% if failed_platforms %}
Note: The following platforms had errors and may have incomplete data:
{% for platform in failed_platforms %}
- {{ platform.name }}: {{ platform.error }}
{% endfor %}
{% endif %}

Analyze the following transcript segment for benefit outcomes:
{{ transcript }}
```

**Dual trace observations:**

When using prompt pairs, the framework automatically creates separate Langfuse observations for system and user prompts.
This means you can see in the Langfuse UI:

- Which version of the system prompt was used (e.g., `benefit_outcomes_system` v3)
- Which version of the user prompt was used (e.g., `benefit_outcomes_user` v5)
- What context variables were injected into the user prompt
- The full rendered text of both prompts

This is critical for debugging multi-step pipelines — if step 2 produces bad results, you can inspect whether the issue
was the system prompt's instructions, the user prompt's template, or the context injected from step 1.

**How it differs:**

| Rotas (manual)                                                        | OpenArmature                                                            |
|-----------------------------------------------------------------------|-------------------------------------------------------------------------|
| 3 separate `load_*_prompt()` functions with identical structure       | Single `prompts.get(name, **vars)` or `prompts.get_pair(name, **vars)`  |
| `_get_prompt_label()` reads `prompt_labels.json`                      | Labels declared in `PromptConfig`                                       |
| `_load_local_*_template()` per prompt                                 | Template path in `PromptConfig`, framework handles Jinja2               |
| `PromptResult` dataclass defined manually                             | Framework provides `PromptResult` with `.source`, `.version`, `.config` |
| No prompt pairs — system prompt only                                  | `PromptPair` for system + user with independent versioning              |
| No context injection — variables are only dates and tool descriptions | Context from graph state injected into user prompt templates            |
| Jinja2 with default `Undefined` (missing vars → empty string)         | `StrictUndefined` default (missing vars → immediate error)              |
| Single Langfuse observation per prompt                                | Dual observations for prompt pairs (system + user traced separately)    |
| Prompt version tracking in eval runner queries Langfuse manually      | `prompts.versions()` returns all current versions                       |
| ~210 lines, 3x code duplication                                       | ~15 lines of config, zero duplication                                   |

**Edge cases handled:**

- Langfuse unavailable (falls back to local template per-prompt, not globally)
- Template file missing (clear error with file path)
- Missing variables (`StrictUndefined` fails loudly at render time — no silent empty strings)
- Caching with configurable TTL (avoid hitting Langfuse on every graph invocation)
- Label resolution per-prompt (test one prompt on staging while others use production)
- Prompt pair partial failure (system loads from Langfuse, user falls back to local — each is independent)
- Context type safety (Pydantic validation on injected context if schema is declared in `PromptConfig`)

---

### 3.7 Evaluation

**What it replaces:** `evals/run_eval.py` (897 lines), `evals/metrics.py` (1,191 lines), `evals/db.py` (439 lines),
`evals/charts.py` (85 lines) — 2,612 lines total.

**Package split:** Evaluation spans both the core and a sibling package:

- **`openarmature` (core)**: Metric base classes (`DeterministicMetric`, `LLMJudgeMetric`), `EvalCase` / `MeasureResult`
  data structures, and the `EvalSuite` interface. These define the contract that metric implementations and test runners
  use.
- **`openarmature-eval`**: Test runner, SQLite persistence, per-test delta tracking, terminal trend charts, CLI (
  `openarmature eval run`, `openarmature eval list`, etc.). This is where the heavy tooling lives — plotting libraries,
  database drivers, and batch execution logic.

This split keeps the core lightweight (no `plotext`, no `sqlite3` schema management) while making evaluation a
first-class citizen in the ecosystem. Metric authors `pip install openarmature` and subclass `DeterministicMetric`.
Teams running eval suites `pip install openarmature-eval` for the runner and persistence.

**Design:**

Metric types (deterministic and LLM-as-judge), test runner, SQLite persistence, per-test delta tracking, and
trend visualization. The developer defines domain-specific metric logic; the framework handles execution, storage, and
reporting.

**API surface:**

```python
from openarmature.eval import (
    EvalSuite, Dataset,
    DeterministicMetric, LLMJudgeMetric,
    EvalResult,
)

# --- Define metrics ---

class ToolCorrectness(DeterministicMetric):
    """Validates that the agent called the correct tools."""
    name = "tool_correctness"
    threshold = 1.0

    def measure(self, case: EvalCase) -> MeasureResult:
        expected_tools = set(t["tool_name"] for t in case.expected.get("tool_calls", []))
        actual_tools = set(t["name"] for t in case.actual.tool_calls)
        score = len(expected_tools & actual_tools) / max(len(expected_tools | actual_tools), 1)
        return MeasureResult(
            score=score,
            passed=score >= self.threshold,
            reason=f"Expected {expected_tools}, got {actual_tools}",
        )


class ArgumentCorrectness(DeterministicMetric):
    """Validates tool arguments (YYYY-MM format, boolean flags)."""
    name = "argument_correctness"
    threshold = 1.0

    def measure(self, case: EvalCase) -> MeasureResult:
        # ... domain-specific validation logic
        ...


# LLM-as-judge — configure with criteria, no metric subclass needed
clarification_quality = LLMJudgeMetric(
    name="clarification_quality",
    criteria="""Evaluate whether the agent correctly identifies missing parameters
    and asks for them using in-universe terminology (Temporal Window, Vector).
    Score 1.0 if the clarification is clear and thematic, 0.0 if generic or wrong.""",
    model="claude-sonnet-4-20250514",  # judge model
    threshold=0.7,
)

persona_consistency = LLMJudgeMetric(
    name="persona_consistency",
    criteria="Evaluate whether the agent maintains its Tenet-themed persona...",
    model="claude-sonnet-4-20250514",
    threshold=0.8,
)

# NOTE on no built-in prompts: LLMJudgeMetric requires the developer to supply
# the full judge prompt via `criteria`. The framework provides the scaffolding
# (calling the judge model, parsing the score, handling errors) but does NOT
# embed a hidden "You are an evaluator..." system prompt. The developer's
# criteria IS the prompt. If you want scoring instructions ("Score 0-1 where..."),
# include them in your criteria text. This avoids the opacity problem where
# DeepEval's GEval wraps user criteria in its own prompt template that the
# developer can't see or control.


# --- Define dataset ---

dataset = Dataset.from_json("evals/dataset.json")
# Or programmatically:
dataset = Dataset([
    EvalCase(
        id="single-month-prod",
        input="Generate a report for January 2025 using production",
        expected={
            "tool_calls": [{"tool_name": "generate_report", "args": {"report_month": "2025-01", "use_preview_db": False}}],
            "month_count": 1,
        },
    ),
    # ... more cases
])


# --- Run evaluation ---

suite = EvalSuite(
    agent=agent,                              # OpenArmature Agent instance
    dataset=dataset,
    metrics=[
        ToolCorrectness(),
        ArgumentCorrectness(),
        clarification_quality,
        persona_consistency,
    ],
    db_path="evals/results.db",               # SQLite persistence
)

results = await suite.run()                    # or suite.run(tests=[1, 5, 12]) for subset

# --- Output ---
results.print_summary()                        # rich table with per-metric scores
results.print_deltas()                         # changes vs previous run (per-test)
results.print_trends(n=10)                     # terminal charts (last 10 runs)
results.export_report("evals/report.json")     # comprehensive JSON export
```

**What the framework provides vs what Rotas builds:**

| Concern                 | Rotas (manual)                                                                                                 | OpenArmature (built-in)                                                             |
|-------------------------|----------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| Metric base class       | `deepeval.metrics.BaseMetric` (thin wrapper)                                                                   | `DeterministicMetric` / `LLMJudgeMetric` with built-in score/pass/reason            |
| LLM-as-judge            | `GEval` from DeepEval + `AnthropicModel` wiring + output suppression hack                                      | `LLMJudgeMetric(criteria=..., model=...)` — no output suppression needed            |
| Test runner             | Custom loop in `run_eval.py` (897 lines): agent init, output collection, metric evaluation, result aggregation | `suite.run()` — framework handles agent invocation, output capture, metric dispatch |
| SQLite persistence      | `EvalDatabase` class (439 lines): 4 tables, migrations, WAL mode, foreign keys                                 | Built-in; same schema (proven useful), zero boilerplate                             |
| Per-test deltas         | Custom query + diff logic in `run_eval.py`                                                                     | `results.print_deltas()`                                                            |
| Trend charts            | `charts.py` (85 lines) wrapping plotext                                                                        | `results.print_trends(n=10)`                                                        |
| Output suppression      | OS fd-level stdout/stderr redirect (metrics.py:26-52)                                                          | Framework controls its own output; no third-party stdout contamination              |
| Prompt version tracking | Manual Langfuse query in `run_eval.py`                                                                         | Automatic via `PromptManager.versions()`                                            |
| Dual-path evaluation    | Custom output capture for tool calls + text responses                                                          | `EvalCase.actual` provides `.tool_calls`, `.text`, `.messages` natively             |

**CLI:**

```bash
# Run all tests
openarmature eval run --dataset evals/dataset.json

# Run specific tests
openarmature eval run -t 1 5 12

# Skip LLM-as-judge (faster iteration)
openarmature eval run --no-judge

# Export report from a past run
openarmature eval export abc123 -o report.json

# List recent runs
openarmature eval list

# Show trend charts
openarmature eval trends --last 10
```

**Edge cases handled:**

- LLM-as-judge model unavailable (skip judge metrics with warning, run deterministic only)
- Agent execution failure on a test case (captured as error, doesn't crash the suite)
- Subset runs with delta tracking (compares against previous scores per `test_id`, not per run)
- Concurrent metric evaluation (independent metrics run in parallel)
- Cost tracking per LLM-as-judge evaluation

---

### 3.8 Logging

**What it replaces:** `rotas/logging_config.py` (137 lines).

**Design:**

Structured logging via structlog, pre-configured with sensible defaults. Multi-target output (OTEL + local file) with
automatic fallback. Library logger suppression is automatic — the framework knows its dependency tree.

**API surface:**

```python
from openarmature import Agent, ObserveConfig

# Logging is configured as part of ObserveConfig
agent = Agent(
    ...,
    observe=ObserveConfig(
        log_level="info",
        log_file="logs/agent.log",           # local JSON fallback
        otel=OTELConfig(...),                 # OTEL log export (optional)
        verbose_http=False,                   # suppress httpx/httpcore by default
    ),
)

# Structured logging works immediately
import structlog
log = structlog.get_logger()
log.info("Processing request", month="2025-03", tool="generate_report")
```

**What the framework manages:**

| Concern                     | Rotas (manual)                                              | OpenArmature (automatic)                     |
|-----------------------------|-------------------------------------------------------------|----------------------------------------------|
| Structlog configuration     | 20 lines in `setup_logging()`                               | Automatic at agent init                      |
| Dual backend (OTEL + file)  | Manual `_check_otel_endpoint()` + conditional handler setup | Automatic with fallback                      |
| Logger suppression          | 9 loggers individually listed by name                       | Framework suppresses its own dependency tree |
| `verbose_http` escape hatch | Manual per-logger override                                  | Config flag                                  |
| Correlation ID in logs      | `structlog.contextvars.merge_contextvars` + manual binding  | Automatic from observability layer           |

---

## 4. How Rotas Would Look

### 4.1 Before: Current Architecture

13 files, 5,284 lines. Dependencies: `langchain-core`, `langchain-openai`, `langgraph`, `langgraph-checkpoint`,
`fastmcp`, `langfuse`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `structlog`, `deepeval`, `plotext`, `httpx`,
`jinja2`, `pydantic`, `rich` — 15+ direct dependencies.

```
rotas/
├── cli.py              (294 lines)  — REPL loop, Langfuse init, callback wiring
├── config.py           (106 lines)  — AgentConfig dataclass
├── graph.py            (79 lines)   — StateGraph construction
├── llm_client.py       (185 lines)  — ChatOpenAI wrapper + health + timeout
├── logging_config.py   (137 lines)  — structlog + OTEL/file dual backend
├── mcp_client.py       (302 lines)  — MCP cold-start, retry, session lifecycle
├── nodes.py            (1,396 lines) — prompts, schemas, graph nodes, routing
├── state.py            (19 lines)   — AgentState TypedDict
├── tracing.py          (154 lines)  — OTEL setup, correlation IDs, @traced
└── templates/
    ├── system_prompt.j2
    ├── summarize_error.j2
    ├── closing_message.j2
    └── prompt_labels.json

evals/
├── run_eval.py         (897 lines)  — test runner, agent invocation, reporting
├── metrics.py          (1,191 lines) — 10 custom metrics + output suppression
├── db.py               (439 lines)  — SQLite persistence (4 tables)
├── charts.py           (85 lines)   — plotext trend charts
└── dataset.json                      — 22 test cases
```

### 4.2 After: OpenArmature Rewrite

The entire agent reduces to domain logic + configuration. Glue code disappears.

**`config.py`** (~40 lines) — Agent configuration, OpenArmature-native:

```python
from openarmature import AgentConfig, LLMConfig, MCPConfig, ObserveConfig, PromptConfig
from pydantic_settings import BaseSettings

class RotasConfig(BaseSettings):
    """Rotas configuration from environment variables."""
    llm_url: str
    llm_model: str
    mcp_url: str
    mcp_token: str
    mcp_health_url: str | None = None

    def to_agent_config(self) -> AgentConfig:
        return AgentConfig(
            llm=LLMConfig(provider="vllm", base_url=self.llm_url, model=self.llm_model),
            mcp=MCPConfig(
                url=self.mcp_url, token=self.mcp_token,
                cold_start=ColdStartConfig(health_url=self.mcp_health_url),
            ),
            observe=ObserveConfig(langfuse=True, log_level="info"),
            prompts={
                "system_prompt": PromptConfig(label="production", template="system_prompt.j2"),
                "summarize_error": PromptConfig(label="production", template="summarize_error.j2"),
                "closing_message": PromptConfig(label="production", template="closing_message.j2"),
            },
        )
```

**`agent.py`** (~200 lines) — Pure domain logic:

```python
from openarmature import Agent, Graph, State, Message, SystemMessage, AIMessage, ToolMessage
from rich.console import Console

class RotasState(State):
    messages: list[Message]
    temporal_window: list[str] = []
    month_reports: list[dict] = []
    failed_months: list[str] = []
    report_generated: bool = False

graph = Graph(RotasState)

@graph.node
async def agent(state: RotasState, llm, tools, prompts) -> dict:
    """Call the LLM with system prompt and tools."""
    system = await prompts.get("system_prompt",
        current_date=today(), current_month=this_month(),
        tool_description=tools.describe())
    llm.apply_config(system.config)
    response = await llm.chat(
        [SystemMessage(system.text), *state.messages],
        tools=tools,
    )
    return {"messages": [response]}

@graph.node
async def execute_tools(state: RotasState, tools) -> dict:
    """Execute tool calls from the LLM response."""
    last = state.messages[-1]
    messages = []
    for call in last.tool_calls:
        month = call["args"].get("report_month", "")
        if not validate_month(month):
            messages.append(ToolMessage(content=f"Invalid month: {month}", tool_call_id=call["id"]))
            state.failed_months.append(month)
            continue
        result = await tools.call(call["name"], call["args"])
        messages.append(ToolMessage(content=json.dumps(result), tool_call_id=call["id"]))
        state.month_reports.append({"month": month, "result": result})
    return {"messages": messages}

@graph.node
async def generate_summary(state: RotasState, console) -> dict:
    """Build Rich panel summary of all month reports."""
    # ... domain-specific Rich UI formatting (~80 lines)
    return {"report_generated": True}

@graph.edge(from_="agent")
def route(state: RotasState) -> str:
    last = state.messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "execute_tools"
    if state.failed_months:
        return "check_retry"
    if state.temporal_window and state.month_reports:
        return "generate_summary"
    return Graph.END

graph.add_edge("execute_tools", "generate_summary")
graph.add_edge("check_retry", "generate_summary")
graph.add_edge("generate_summary", Graph.END)
```

**`evals/metrics.py`** (~150 lines) — Domain-specific metric logic only:

```python
from openarmature.eval import DeterministicMetric, LLMJudgeMetric, MeasureResult

class ToolCorrectness(DeterministicMetric):
    name = "tool_correctness"
    threshold = 1.0

    def measure(self, case) -> MeasureResult:
        expected = set(t["tool_name"] for t in case.expected.get("tool_calls", []))
        actual = set(t["name"] for t in case.actual.tool_calls)
        score = len(expected & actual) / max(len(expected | actual), 1)
        return MeasureResult(score=score, passed=score >= self.threshold,
                             reason=f"Expected {expected}, got {actual}")

# ... 5 more deterministic metrics (~20 lines each)

clarification_quality = LLMJudgeMetric(
    name="clarification_quality",
    criteria="Evaluate whether the agent asks for missing parameters using Tenet terminology...",
    model="claude-sonnet-4-20250514",
    threshold=0.7,
)
# ... 3 more judge metrics
```

**`evals/run.py`** (~20 lines) — Just wiring:

```python
from openarmature.eval import EvalSuite, Dataset
from .metrics import ToolCorrectness, clarification_quality, ...

suite = EvalSuite(
    agent=agent,
    dataset=Dataset.from_json("evals/dataset.json"),
    metrics=[ToolCorrectness(), ..., clarification_quality],
    db_path="evals/results.db",
)

if __name__ == "__main__":
    suite.cli()  # handles --no-judge, -t, --report, --export-run, --trends
```

### 4.3 Reduction Summary

| Module            | Before (lines) | After (lines) | What changed                                   |
|-------------------|----------------|---------------|------------------------------------------------|
| MCP client        | 302            | 0             | `ToolSet.from_mcp()` with config               |
| LLM client        | 185            | 0             | `LLM(LLMConfig(...))` with provider preset     |
| OTEL/tracing      | 154            | 0             | `ObserveConfig(otel=...)` — ambient            |
| Logging           | 137            | 0             | `ObserveConfig(log_level=...)` — ambient       |
| Prompt management | 210            | 0             | `PromptManager` with per-prompt config         |
| Tool schemas      | 85             | 0             | Auto-generated from MCP discovery + type hints |
| Langfuse wiring   | 50             | 0             | `ObserveConfig(langfuse=True)` — ambient       |
| Graph definition  | 79 + 19        | ~30           | Decorator-based, same namespace                |
| Graph nodes       | 1,396          | ~200          | Domain logic only, no glue                     |
| CLI / REPL        | 294            | ~100          | Framework provides REPL scaffold               |
| Config            | 106            | ~40           | OpenArmature-native config composition         |
| Eval runner       | 897            | ~20           | `suite.cli()` handles everything               |
| Eval metrics      | 1,191          | ~150          | Domain logic only, no suppression hacks        |
| Eval DB           | 439            | 0             | Built-in persistence                           |
| Eval charts       | 85             | 0             | Built-in trend visualization                   |
| **Total**         | **5,284**      | **~540**      | **~90% reduction**                             |

The ~540 remaining lines are pure domain logic: graph node behavior, routing conditions, month validation, Rich UI
formatting, metric measurement logic, and Rotas-specific configuration. Everything else is framework responsibility.

---

## 5. Broader Use Cases

OpenArmature is not Rotas-specific. Any agent with remote tools, production observability, and evaluation needs faces
the same glue tax.

### Customer Support Agents

- **MCP tools** for CRM (Zendesk, Salesforce), ticketing systems, knowledge bases
- **Prompt management** for tone calibration across regions/brands (production vs staging labels)
- **Evaluation** for response quality (LLM-as-judge), tool correctness (deterministic), escalation accuracy
- **Observability** for latency tracking, cost per interaction, resolution rate
- **Graph** for multi-step workflows: classify → retrieve → draft → review → send

### Data Pipeline Agents

- **MCP tools** for database access, API integrations, S3/GCS operations
- **Graph** for multi-step ETL: extract → validate → transform → load → verify
- **Evaluation** for data quality metrics, transformation accuracy
- **Observability** for pipeline duration, failure tracking, data volume metrics
- **Cold-start handling** for serverless function backends (same pattern as Fly.io)

### Code Review Agents

- **MCP tools** for GitHub/GitLab APIs (PRs, diffs, comments)
- **LLM** for code analysis, vulnerability detection, style checking
- **Evaluation** for review quality (do suggestions improve code?), false positive rate
- **Prompt management** for per-repository style guidelines
- **Graph** for multi-pass review: security → style → logic → summary

### Internal Tooling Agents

- **MCP tools** for Slack, Jira, Confluence, internal APIs
- **Graph** for request routing: understand → route → execute → confirm
- **Observability** for usage tracking, popular tools, error rates
- **Evaluation** for task completion accuracy

### Multi-Agent Orchestration

- **Graphs that call other graphs** — a supervisor agent dispatches to specialized sub-agents
- **Shared tool sets** — all agents access the same MCP server, each with different permissions
- **Unified observability** — all agent invocations traced under one session, one correlation ID
- **Cross-agent evaluation** — test the entire multi-agent pipeline end-to-end

---

## 6. Local Developer Experience

A framework is only as good as the experience of building with it. OpenArmature should prioritize local development
tooling as a core part of the ecosystem — not as an afterthought. Agent development has a unique feedback loop problem:
the tools your agent calls are often remote, slow, and expensive. A great local dev experience means you can iterate on
agent behavior without waiting for cold starts, burning API credits, or debugging against flaky external services.

### Philosophy: Fast Local Iteration

The development loop for an agent looks like:

```text
Edit prompt/code → Start agent → Send test input → Wait for LLM + tools → See result → Repeat
```

Every second in "wait for LLM + tools" is a second you're not iterating. The framework should minimize that wait
through:

1. **Mock remote tools locally** — instant, deterministic responses instead of minutes-long API calls
2. **Explore MCP servers interactively** — understand what tools are available before writing agent code
3. **Manage prompts without redeploying** — push, label, diff, and test prompts in a REPL
4. **Run evals against mocks** — full eval suite in seconds, not hours

### Mock MCP Servers

When your agent calls remote MCP tools, every test run hits real servers with real latency. A mock server returns
instantly with deterministic data, making the edit-run-evaluate loop fast enough for real iteration.

The Rotas project demonstrates this with a mock MCP server for `generate_report` that:

- Returns synthetic but schema-identical data in milliseconds (vs minutes for the real server)
- Uses seeded RNG (`hash(report_month)`) so the same input always produces the same output — reproducible eval runs
- Supports the same MCP protocol (FastAPI + FastApiMCP), auth, and validation as the real server
- Requires zero changes in the agent — just change `MCP_URL` in `.env`

**OpenArmature should make mock server creation a supported workflow:**

```python
from openarmature.dev import MockMCPServer

mock = MockMCPServer()

@mock.tool("generate_report")
async def mock_generate_report(report_month: str, use_preview_db: bool) -> dict:
    """Mock implementation with deterministic output."""
    seed = hash(report_month)
    rng = random.Random(seed)
    return {
        "success": True,
        "report_month": report_month,
        "summary_stats": {
            "total_brands": rng.randint(30, 80),
            "total_platform_earnings": round(rng.uniform(200000, 500000), 2),
            # ... deterministic synthetic data
        },
    }

# Start the mock — MCP-compatible, discoverable, instant
mock.serve(port=8003, token="mock-test-token")
```

The framework provides the `MockMCPServer` scaffold; the developer provides the mock implementations. This lives in a
dev extras package or the core's dev utilities — it's not production code, but it's critical for development velocity.

### MCP Server Explorer

Before you can build an agent that uses MCP tools, you need to understand what the tools do — their names, parameters,
schemas, and response shapes. Connecting to an MCP server programmatically just to browse its tools is friction that
slows down the discovery phase of agent development.

The Forbin project ([github.com/chris-colinsky/Forbin](https://github.com/chris-colinsky/Forbin)) solves this with an
interactive CLI for exploring MCP servers:

- **Discover tools**: Connect to any MCP server, see all available tools with descriptions
- **Inspect schemas**: View full JSON Schema for any tool's parameters (types, descriptions, required fields, enums)
- **Test interactively**: Call tools with custom arguments and see formatted responses
- **Cold-start aware**: Handles Fly.io suspended servers with health check polling and extended timeouts
- **Rich terminal UI**: Syntax-highlighted JSON, formatted tables, color-coded status

The developer workflow becomes: `forbin` → connect to MCP server → browse tools → test with real calls → understand the
interface → start building the agent with confidence.

**OpenArmature should integrate or recommend MCP exploration as part of the development workflow.** This could be:

- A built-in `openarmature explore <mcp-url>` CLI command that wraps the exploration pattern
- A recommended companion tool (like Forbin) that's documented as part of the "getting started" experience
- Integration with the `ToolSet` — after `ToolSet.from_mcp()`, provide an interactive inspect mode: `tools.explore()`
  that launches a REPL for browsing and testing discovered tools

### Prompt Management REPL

Prompt iteration is another part of the dev loop that's typically slow: edit template → push to Langfuse → restart
agent → test → check Langfuse UI → repeat. The Rotas project's Prompt Manager REPL (`scripts/prompt_mgr.py`) collapses
this into an interactive session where you push, label, diff, and check status without leaving the terminal.

This pattern should be documented as a recommended companion tool for any OpenArmature project that uses Langfuse for
prompt management. The `openarmature-langfuse` package could ship a `prompt-mgr` CLI entry point or the pattern could be
part of the development guide.

### Local Development Stack

A complete local dev environment for an OpenArmature agent looks like:

```text
┌─────────────────────────────────────────────────────────┐
│                    Developer Machine                     │
│                                                         │
│  ┌─────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │  Agent   │  │  Mock MCP    │  │   Local LLM        │ │
│  │  (Rotas) │──│  Server      │  │   (vLLM/LM Studio) │ │
│  │          │  │  (port 8003) │  │   (port 8000)      │ │
│  └────┬─────┘  └──────────────┘  └────────────────────┘ │
│       │                                                  │
│  ┌────▼─────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ Prompt   │  │   Langfuse   │  │    HyperDX         │ │
│  │ Manager  │──│  (Docker)    │  │   (Docker)         │ │
│  │ REPL     │  │  (port 3000) │  │   (port 8080)      │ │
│  └──────────┘  └──────────────┘  └────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Eval Suite (against mock, fast + deterministic)  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

Everything runs locally. No cloud dependencies for the core development loop. Cloud services (Anthropic for judge evals,
Fly.io for real MCP server) are only needed for integration testing and production deployment.

---

## 7. Implementation Considerations

### 7.1 What Is Hard

**Graph engine correctness.** State management, message accumulation reducers, conditional edge resolution, error
propagation, cycle handling. LangGraph has years of edge-case fixes here. Rebuilding this from scratch means
re-discovering those edge cases.

**MCP transport diversity.** SSE, stdio, and streamable-HTTP all have different connection lifecycle semantics. Fly.io
cold starts are one pattern; AWS Lambda cold starts are another; local stdio processes have no cold start but have
process lifecycle concerns. The abstraction must handle all three without leaking transport details.

**LLM provider quirks.** vLLM's tool-calling format, Anthropic's `tool_use` block structure, OpenAI's parallel tool
calls, Ollama's partial tool support. The abstraction layer must normalize all of these into a consistent
`AIMessage.tool_calls` format without losing provider-specific capabilities.

**OTEL compatibility.** Provider isolation (the Langfuse v3 trap), span hierarchy correctness, baggage propagation
across async boundaries, batch processor flush semantics. Getting this wrong causes subtle data duplication or loss.

**Evaluation metric reliability.** LLM-as-judge metrics are inherently noisy. The framework needs to handle: judge model
unavailability, cost control (judge calls are expensive), output format validation (judge must return a score, not an
essay), and reproducibility (temperature=0, seed pinning where supported).

### 7.2 Build vs Extend vs Wrap

Three strategies, each with tradeoffs:

**Build from scratch.** Maximum control, highest cost. Appropriate if the thesis is that existing abstractions are
fundamentally wrong — not just incomplete. The graph engine and LLM client are the strongest candidates for building
from scratch because the abstraction mismatch is deepest there (LangGraph's multi-package split, ChatOpenAI's missing
health checks).

**Extend LangGraph.** Add observability and eval as plugins or extensions to LangGraph, and adopt
`langchain-mcp-adapters` for MCP. Lower cost, and the MCP adapter is already comprehensive (tool discovery, schema
conversion, transports, interceptors). But you'd still need custom code for production concerns (cold-start, retry,
timeouts) and you inherit the multi-package problem.

**Wrap existing libraries.** Thin orchestration layer over LangGraph + fastmcp + Langfuse + DeepEval. Least effort
upfront, but the glue still exists — it's just packaged in a library instead of every project. Fragile when upstream
libraries change.

**Recommended: Start with wrap, migrate to build.**

Phase 1 (wrap): Package the existing glue patterns into a library. Immediate value — every new agent project gets
Rotas-quality MCP handling, observability, and eval for free. Low risk because the patterns are battle-tested.

Phase 2 (build): Replace the graph engine and LLM client with purpose-built implementations. Higher effort, but
eliminates the LangChain/LangGraph dependency chain and the abstraction mismatches that cause the most pain.

### 7.3 Incremental Adoption Path

Each phase is independently valuable and can ship without the others. An existing LangGraph project can adopt
OpenArmature packages incrementally.

| Phase | Package                        | Replaces                                     | Value                                                                                   |
|-------|--------------------------------|----------------------------------------------|-----------------------------------------------------------------------------------------|
| 1     | `openarmature` (core: tools)   | `mcp_client.py` + hardcoded schemas          | MCP client with cold-start, retry, schema discovery. Drop-in replacement.               |
| 2     | `openarmature` (core: llm)     | `llm_client.py` + ChatOpenAI                 | Provider abstraction with health checks, timeout control, config composition.           |
| 3     | `openarmature` (core: prompts) | Prompt code in `nodes.py`                    | Multi-source prompt management with fallback. Eliminates 3x code duplication.           |
| 4     | `openarmature-langfuse`        | Langfuse setup in `cli.py` + callback wiring | Langfuse prompt backend, trace linking, session grouping. One config.                   |
| 5     | `openarmature-otel`            | `tracing.py` + `logging_config.py`           | OTEL export with provider isolation. Replaces manual TracerProvider setup.              |
| 6     | `openarmature-eval`            | `evals/` directory (2,600 lines)             | Test runner, persistence, trends. Domain metrics stay; infrastructure eliminated.       |
| 7     | `openarmature` (core: graph)   | LangGraph dependency                         | Full graph engine. Final step — eliminates langchain-core, langchain-openai, langgraph. |

A project could adopt phases 1-6 while still using LangGraph for graph orchestration, then migrate to phase 7 when the
graph engine is stable. Each sibling package (`openarmature-langfuse`, `openarmature-otel`, `openarmature-eval`) can be
adopted independently of the others.

### 7.4 Dependencies and Ecosystem Risk

**MCP specification is still evolving.** The transport layer (streamable-HTTP replacing SSE) is the most active area of
change. OpenArmature's transport abstraction must be pluggable so new transports can be added without breaking existing
code.

**Langfuse and DeepEval are optional but integral.** API changes in either require adapter updates. OpenArmature should
define interfaces (`ObservabilityBackend`, `JudgeModel`) that these libraries implement, rather than coupling directly
to their APIs. This allows swapping Langfuse for Arize, or DeepEval for Ragas, without touching framework code.

**OTEL is stable but verbose.** The SDK adds significant transitive dependencies (protobuf, grpcio for gRPC exporters).
OpenArmature should depend on `opentelemetry-api` (lightweight) and make the SDK optional via extras.

**Python async ecosystem.** The framework is async-first (`asyncio`). Sync wrappers should be available for simpler use
cases, but the primary API is async — matching the reality that MCP calls, LLM calls, and tool execution are all
I/O-bound.

---

## Appendix A: Rotas File-by-File Mapping

| Rotas File                | Lines | OpenArmature Equivalent                              | Status                                               |
|---------------------------|-------|------------------------------------------------------|------------------------------------------------------|
| `rotas/config.py`         | 106   | `RotasConfig` extends `openopenarmature.AgentConfig` | Simplified (~40 lines)                               |
| `rotas/state.py`          | 19    | `class RotasState(openarmature.State)`               | Same size, different base class                      |
| `rotas/graph.py`          | 79    | Decorator-based graph definition in `agent.py`       | Merged into agent file (~30 lines)                   |
| `rotas/llm_client.py`     | 185   | `openarmature.LLM`                                   | **Eliminated**                                       |
| `rotas/mcp_client.py`     | 302   | `openarmature.ToolSet.from_mcp()`                    | **Eliminated**                                       |
| `rotas/tracing.py`        | 154   | `openarmature.observe`                               | **Eliminated**                                       |
| `rotas/logging_config.py` | 137   | `openarmature.observe`                               | **Eliminated**                                       |
| `rotas/nodes.py`          | 1,396 | `agent.py` (~200 lines domain logic)                 | **90% eliminated** (prompts, schemas, dispatch gone) |
| `rotas/cli.py`            | 294   | `agent.py` (~100 lines) with framework REPL scaffold | **65% eliminated** (init, callbacks, flush gone)     |
| `evals/run_eval.py`       | 897   | `evals/run.py` (~20 lines) + `suite.cli()`           | **98% eliminated**                                   |
| `evals/metrics.py`        | 1,191 | `evals/metrics.py` (~150 lines domain logic)         | **87% eliminated** (base classes, suppression gone)  |
| `evals/db.py`             | 439   | Built-in `openarmature.eval` persistence             | **Eliminated**                                       |
| `evals/charts.py`         | 85    | Built-in `openarmature.eval` trends                  | **Eliminated**                                       |

## Appendix B: Configuration Schema

```python
from pydantic import BaseModel

class AgentConfig(BaseModel):
    """Top-level OpenArmature configuration."""

    llm: LLMConfig
    mcp: MCPConfig | None = None
    observe: ObserveConfig = ObserveConfig()
    prompts: dict[str, PromptConfig] = {}

class LLMConfig(BaseModel):
    provider: str = "openai"           # "vllm", "openai", "anthropic", "bifrost", "ollama", "custom"
    base_url: str = "https://api.openai.com/v1"
    model: str
    api_key: str | None = None         # auto-resolved from env for known providers
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: float = 60.0
    max_retries: int = 0

class MCPConfig(BaseModel):
    url: str | None = None
    token: str | None = None
    command: str | None = None         # for stdio transport
    transport: str | None = None       # "sse", "streamable-http", "stdio" (auto-detected if None)
    cold_start: ColdStartConfig = ColdStartConfig()
    retry: RetryPolicy = RetryPolicy()
    timeouts: TimeoutConfig = TimeoutConfig()

class ColdStartConfig(BaseModel):
    health_url: str | None = None
    max_attempts: int = 6
    interval: int = 5                  # seconds between health checks
    init_wait: int = 5                 # seconds after health check passes

class RetryPolicy(BaseModel):
    max_retries: int = 3
    initial_delay: float = 3.0
    backoff_multiplier: float = 1.2
    max_delay: float = 10.0

class TimeoutConfig(BaseModel):
    init: float = 30.0                 # connection/initialization
    operation: float = 600.0           # per-tool-call
    discovery: float = 15.0            # list_tools()

class ObserveConfig(BaseModel):
    langfuse: bool = False             # auto-reads LANGFUSE_* env vars
    otel: OTELConfig | None = None
    log_level: str = "info"
    log_file: str = "logs/agent.log"
    verbose_http: bool = False

class OTELConfig(BaseModel):
    endpoint: str
    api_key: str
    service_name: str

class PromptConfig(BaseModel):
    label: str = "production"
    template: str | None = None        # local Jinja2 fallback filename
    variables: list[str] = []
    cache_ttl: int = 300               # seconds
```

## Appendix C: Comparison Matrix

| Feature                   | OpenArmature                         | LangChain + LangGraph                         | CrewAI                     | Pydantic AI              | OpenAI Agents SDK           | Anthropic Agents SDK        |
|---------------------------|--------------------------------------|-----------------------------------------------|----------------------------|--------------------------|-----------------------------|-----------------------------|
| **Single package**        | Yes                                  | No (3+ packages)                              | Yes                        | Yes                      | Yes                         | Yes                         |
| **MCP native**            | Yes                                  | Official adapter (`langchain-mcp-adapters`)   | Community adapter          | Yes                      | Yes                         | Yes                         |
| **Local LLM (vLLM)**      | Yes (provider presets)               | Yes (ChatOpenAI hack)                         | Yes (LiteLLM)              | Yes                      | Partial                     | No                          |
| **LLM health checks**     | Built-in                             | No                                            | No                         | No                       | No                          | No                          |
| **Graph orchestration**   | Built-in (StateGraph)                | Yes (separate lib)                            | Task-based only            | No                       | No                          | Handoff-based               |
| **Custom routing**        | Conditional edges                    | Conditional edges                             | Limited                    | No                       | No                          | No                          |
| **Pattern composability** | Mix patterns in one graph            | Mix patterns in one graph                     | Single pattern per crew    | Single pattern per agent | Handoffs only               | Handoffs only               |
| **State reducers**        | Built-in                             | Yes (separate import)                         | No                         | No                       | No                          | No                          |
| **Ambient observability** | Yes (config only)                    | No (callback wiring)                          | Partial                    | Yes (Logfire)            | Partial                     | Partial                     |
| **OTEL native**           | Yes                                  | No                                            | No                         | Yes                      | Partial                     | No                          |
| **Langfuse native**       | Yes                                  | Via callbacks                                 | Via callbacks              | Via Logfire              | Via integration             | No                          |
| **Correlation IDs**       | Automatic                            | Manual ContextVar                             | No                         | Automatic                | No                          | No                          |
| **Prompt management**     | Multi-source + fallback              | No                                            | No                         | No                       | No                          | No                          |
| **Built-in eval**         | Yes (metrics, persist, trends)       | No                                            | No                         | No                       | No                          | No                          |
| **LLM-as-judge**          | Built-in                             | No (use DeepEval)                             | No                         | No                       | No                          | No                          |
| **Cold-start handling**   | Configurable policy                  | No                                            | No                         | No                       | No                          | No                          |
| **Tool schema discovery** | Auto from MCP                        | Auto via adapter                              | Manual                     | Auto from MCP            | Auto from MCP               | Auto from MCP               |
| **Structured logging**    | Built-in (structlog)                 | No                                            | No                         | Built-in (Logfire)       | No                          | No                          |
| **No built-in prompts**   | Yes — all prompts developer-authored | No — `create_react_agent` embeds ReAct prompt | No — task prompts embedded | Yes                      | No — agent prompts embedded | No — agent prompts embedded |
