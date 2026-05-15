---
hide:
  - navigation
  - toc
---

# OpenArmature

A workflow framework for LLM pipelines and tool-calling agents —
defined as a language-agnostic specification. Implementations conform
to the same behavior via canonical fixtures, so the same workload runs
the same way regardless of language or runtime.

[Read the charter](openarmature.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/LunarCommand/openarmature-spec){ .md-button target="_blank" rel="noopener" }

---

<div class="grid cards" markdown>

-   :material-graph:{ .lg .middle } &nbsp; __Typed graph engine__

    ---

    Typed state with per-field reducers, async nodes returning partial
    updates, static and conditional edges, subgraph composition, and
    observer hooks at every node boundary. Bad graph shapes fail at
    compile time, not at run time.

-   :material-pipe:{ .lg .middle } &nbsp; __Pipeline utilities__

    ---

    Canonical retry and timing middleware, parallel fan-out, parallel
    branches, checkpoint/resume with state migration hooks. The
    cross-cutting concerns every LLM pipeline keeps reinventing,
    specified once.

-   :material-brain:{ .lg .middle } &nbsp; __LLM provider__

    ---

    Stateless completion API with image content blocks for user
    messages, structured output via `response_schema`, canonical error
    categories, and an OpenAI-compatible wire mapping.

-   :material-eye:{ .lg .middle } &nbsp; __Observability__

    ---

    OpenTelemetry mapping with full span hierarchy (invocation → node →
    subgraph → fan-out instance → LLM call), cross-backend correlation
    IDs, log bridge, and detached trace mode for high-volume fan-outs.

-   :material-file-document-multiple:{ .lg .middle } &nbsp; __Prompt management__

    ---

    Named, versioned prompts fetched from composable backends.
    Strict-by-default variable handling. Composite-backend fallback
    that distinguishes infrastructure failure (fall back) from logical
    absence (don't).

-   :material-check-decagram:{ .lg .middle } &nbsp; __Conformance commitment__

    ---

    118 canonical fixtures across five capabilities lock behavior
    across implementations. Same input → same observable outcome,
    regardless of language or runtime.

</div>

---

Reference implementations live in sibling repositories.
[openarmature-python](https://github.com/LunarCommand/openarmature-python){target="_blank" rel="noopener"}
is currently in active development; a TypeScript implementation is on
the roadmap. New behavior lands through numbered RFC-style proposals
— see [Governance](governance.md) for the lifecycle, and
[Proposals](proposals/0017-prompt-management-core.md) for what's
recently shipped.
