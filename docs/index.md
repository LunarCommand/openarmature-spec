---
hide:
  - toc
---

# OpenArmature

**A workflow framework for LLM pipelines and tool-calling agents — defined as
a language-agnostic specification.** Implementations conform to the same
behavior via canonical fixtures, so the same workload runs the same way
regardless of language or runtime.

[Read the charter](openarmature.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/LunarCommand/openarmature-spec){ .md-button target="_blank" rel="noopener" }

---

## Pipelines and agents — one substrate

Most frameworks pick a side: deterministic LLM pipelines or autonomous
tool-calling agents. OpenArmature treats both as applications of the same
primitives — typed graphs, conditional edges, middleware, checkpointing.
A multi-stage content-extraction pipeline and a tool-loop agent are both
just compiled graphs.

<div class="grid cards" markdown>

-   :material-pipe-leak:{ .lg .middle } &nbsp; __Deterministic LLM pipelines__

    ---

    Topology pinned at compile time. Each node does one thing — LLM call,
    parse, validate, persist. Per-node retries with explicit budgets;
    observability captures every step.

    *Use cases: content extraction, classification cascades, multi-stage
    analysis, document refinery.*

-   :material-robot:{ .lg .middle } &nbsp; __Tool-calling agents__

    ---

    Same primitives, different shape: LLM node + tool-dispatch node +
    conditional edge back to the LLM. Tool-call envelope is normalized;
    multi-turn agents resume mid-conversation via checkpoint/resume.

    *Use cases: research agents, code-generation loops, data-extraction
    bots, multi-turn assistants.*

</div>

---

## What sets it apart

<div class="grid cards two-col" markdown>

-   :material-eye-check:{ .lg .middle } &nbsp; __Transparency over abstraction__

    ---

    Provider responses surface verbatim alongside normalized fields.
    Internal events are observable via hook points at every node
    boundary. The framework adds structure; it never hides what the
    underlying tools returned.

-   :material-shield-check:{ .lg .middle } &nbsp; __Compile-time safety__

    ---

    Bad graph shapes fail at compile, not at run. Reducer conflicts,
    dangling edges, multiple outgoing edges from a non-conditional
    node — all caught before the first LLM call.

-   :material-puzzle:{ .lg .middle } &nbsp; __Composable, not prescriptive__

    ---

    Middleware is a primitive. Retry and timing ship canonical;
    everything else composes from the same protocol. No magic
    decorators, no global state — just explicit composition.

-   :material-radar:{ .lg .middle } &nbsp; __Observability built in__

    ---

    OpenTelemetry mapping is normative, not bolt-on. Span hierarchy
    mirrors graph structure; cross-backend correlation IDs flow with
    every invocation; detached trace mode keeps high-volume fan-outs
    readable.

</div>

---

## Reference implementation

!!! abstract "openarmature-python — currently in active development"

    The canonical reference implementation. Ships the full API for graph
    engine, pipeline utilities, LLM provider, observability, and prompt
    management — all driven by the conformance fixtures defined in this
    repo.

    [Visit the repo on GitHub :octicons-link-external-16:](https://github.com/LunarCommand/openarmature-python){ .md-button target="_blank" rel="noopener" }

A TypeScript implementation is on the roadmap. Both will pin behavior to
this spec.

---

## Why a spec, not a library?

LLM workflow frameworks usually ship as opinionated libraries. Pick the
wrong one and you're rewriting your pipeline; ship in two languages and
you're maintaining two divergent codebases that drift over time.
OpenArmature flips the model: the contract lives here as a spec with
conformance fixtures, and reference implementations in each language port
to the same behavior. Same workload, multiple runtimes, no behavioral
drift.

<div class="grid cards" markdown>

-   :material-check-decagram:{ .lg .middle } &nbsp; __Behavior pinned by fixtures__

    ---

    119 conformance fixtures across five capabilities. Implementations run
    them; if they pass, behavior matches every other conforming runtime.
    No "implementation-defined" footguns.

-   :material-cube-unfolded:{ .lg .middle } &nbsp; __One contract, many runtimes__

    ---

    Reference implementations in Python (active) and TypeScript (planned).
    The same pipeline definition, the same observable trace shape, the
    same retry semantics — across languages.

-   :material-arrow-decision:{ .lg .middle } &nbsp; __Open evolution__

    ---

    New behavior lands through numbered RFC-style proposals reviewed in
    the open. Once accepted, a proposal's text is immutable; superseding
    proposals link the chain forward. No silent drift between releases.

</div>

---

## How it evolves

OpenArmature is governed by a numbered proposal system: every behavioral
change starts as a Draft RFC, is reviewed in the open, lands with a
SemVer bump, and is frozen in proposal text once accepted. The capability
specs are the source of truth; proposals are the change history.
