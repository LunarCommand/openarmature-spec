# OpenArmature Specification

Language-agnostic behavioral specification for **OpenArmature**, a workflow
framework for LLM pipelines and tool-calling agents. This repository holds the
specification text, conformance fixtures, governance rules, and numbered
RFC-style proposals. **No implementation code lives here.** Implementations
are in sibling repositories.

**Current spec version:** [v0.21.0](CHANGELOG.md)

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

| Capability | Introduced | Latest | Fixtures | Scope |
|---|---|---|---|---|
| [graph-engine](spec/graph-engine/spec.md) | 0.1.0 | 0.19.0 | 25 | Typed state, async nodes, conditional/static edges, reducers, subgraph composition, observer hooks (with bounded `drain` — optional caller-supplied timeout + summary of undelivered events) |
| [pipeline-utilities](spec/pipeline-utilities/spec.md) | 0.5.0 | 0.21.0 | 53 | Middleware (canonical retry + timing), parallel fan-out, checkpointing (per-instance fan-out resume with explicit success/error discrimination, state migration, configurable backend batching for fan-out internal saves), parallel branches |
| [llm-provider](spec/llm-provider/spec.md) | 0.4.0 | 0.20.1 | 31 | Stateless LLM-provider abstraction with canonical error categories, image content blocks for user messages, structured output via `response_schema`, request-side tool-calling control via `tool_choice`, and a wire-format-mapping catalog (§8.1 OpenAI-compatible; in-spec default for cross-language provider mappings) |
| [observability](spec/observability/spec.md) | 0.7.0 | 0.17.0 | 21 | Cross-backend correlation IDs, OpenTelemetry mapping (spans, log correlation, detached trace mode), LLM-span payload + GenAI semconv attributes (default-off payload, request parameters under `gen_ai.request.*`, GenAI semconv response attributes for LLM-aware backends) |
| [prompt-management](spec/prompt-management/spec.md) | 0.15.0 | 0.15.0 | 12 | Named/versioned template fetch + render; composite backends with infrastructure-only fallback; PromptGroup tracing primitive; strict-undefined-by-default variable injection |

### In the pipeline

Proposals currently in flight. Status is Draft; contracts may change before
they are Accepted.

| Proposal | Status | Targets | Summary |
|---|---|---|---|
| [0020](proposals/0020-sessions-capability.md) | Draft | spec/sessions/spec.md (new), observability §5, pipeline-utilities §10 | Sessions capability — typed cross-invocation state under a stable caller-supplied identity |
| [0021](proposals/0021-graph-suspension.md) | Draft | spec/suspension/spec.md (new), graph-engine §3 + §6, observability §4 + §5, pipeline-utilities §10 | Graph suspension and external-signal resume — generalized pause primitive (HITL + async-job-wait + scheduled wakeup as flavors of one suspend) |
| [0022](proposals/0022-harness-contract.md) | Draft | spec/harness/spec.md (new) | Harness contract — abstract behavioral contract for any harness wrapping the OA engine to serve a deployment runtime (three inbound dispatch paths, turn lifecycle, error categorization, runtime-neutral) |
| [0023](proposals/0023-canonical-state-reducers.md) | Draft | graph-engine §2 | Canonical state reducers — extend baseline reducers with `bounded_append`, `dedupe_append`, `merge_by_key` (factory-style closures for chat-agent and tool-loop patterns) |

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

## Where it's going

Active design areas. These are questions the next round of proposals will
address, not scheduled deliverables.

- **Per-provider wire-format mappings.** §8 of llm-provider is now a catalog
  of wire-format mappings (§8.1 OpenAI-compatible is the first; the v0.17.1
  reframing established the default rule that any mapping intended for
  cross-language implementation lives in spec). Follow-on proposals will add
  §8.2+ subsections for Anthropic Messages, Google Gemini, and Mistral as
  their concrete implementations take shape — wire-format consistency across
  language siblings is part of OA's cross-language promise.
- **Observability backend mappings.** The observability spec currently
  defines the OpenTelemetry mapping (§4). Backend-specific mappings —
  Langfuse first, others as demand surfaces — would ship as sibling
  sections of the observability spec, each mapping OA's normative event
  stream onto the backend's native model. Follows the same pattern as
  the per-provider wire-format catalog: one spec section per backend,
  cross-language consistency guaranteed at the mapping layer.
- **Multimodal LLM support — audio and video.** Proposal 0015 added image
  content blocks (§3.1) and 0019's framing reserves §8.X subsections for
  per-provider mappings. Audio and video each warrant their own follow-on
  proposal (different wire shapes per provider, different format /
  duration constraints, different streaming semantics for long video).
  Input-only in v1, mirroring the image rollout; assistant-output audio /
  video are separate, smaller workloads with their own scoping.
- **Tool-call observability on LLM spans.** v0.17.0 (proposal 0024)
  landed the LLM input/output payload + GenAI semconv attributes for
  the request and response sides of an LLM call. The natural follow-on
  is tool-call attributes on the same span — `gen_ai.tool.calls` style
  attributes that capture which tools were invoked with what arguments
  and what the results were, surfaced for LLM-aware OTel backends
  (Langfuse, Phoenix, Honeycomb LLM lens) that already render tool-call
  traces.

Beyond these active areas, broader directions on the design horizon
include agent memory (cross-session knowledge stores — per-user
profiles, episodic / semantic / procedural memory — distinct from
sessions and queried mid-graph rather than loaded at invoke entry) and
an evaluation framework with persistent history. Each lands when
there's a clear behavior to specify, not before.

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
