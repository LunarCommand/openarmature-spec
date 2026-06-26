# 0084: Observability — Orphaned Provider/Tool Span Parent Fallback

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-26
- **Targets:** spec/observability/spec.md (the LLM (§5.5), embedding (§5.5.8), tool-execution (§5.5.11), and rerank (§5.5.13) spans each state their parent as "the calling node's span" unconditionally; add a shared fallback for when that calling-node span is not open — the span parents under the nearest enclosing wrapper span per the §4.3 namespace-ancestry-depth parent-child rules, i.e. the wrapper the calling node's own span parents under; reconcile the §5.5 per-attempt-span framing sentence; add a confirming note that the §8 Langfuse observation parent follows the same resolution). spec/conformance-adapter/spec.md (a harness primitive to issue a provider call with no open calling-node span inside a fan-out instance, so a fixture can pin the fallback). New observability conformance fixtures pinning the orphan-fallback parent inside a fan-out instance in both the OTel and Langfuse mappings. (See Open Questions — a graph-engine §6 change may be required if the orphaned event does not already carry the calling node's enclosing lineage.)
- **Related:** 0007 (observability §4 span hierarchy + §4.3 parent-child rules this fallback reuses), 0005 (parallel fan-out — the fan-out instance span), 0045 (lineage-aware augmentation — the per-instance containment principle), 0049 / 0058 (typed LLM events — carry the `(namespace, fan_out_index, branch_name)` lineage), 0061 (detached-trace invocation span).
- **Supersedes:**

## Summary

§5.5 specifies that an LLM provider span parents under "the node span of the node that invoked the provider," and §5.5.8 / §5.5.11 / §5.5.13 say the same — unconditionally — for the embedding, tool-execution, and rerank spans. None defines a fallback for when that calling-node span is not open at emission time (a provider call from middleware or a wrapper rather than a node body). The case is rare but real, and inside a fan-out instance it has no canonical answer: the spec's two backend mappings can legitimately disagree on whether the orphaned span parents under the per-instance fan-out instance span or falls through to the shared subgraph / invocation span. This proposal adds the missing rule for all four span types at once — when the calling-node span is not open, the span parents under the **nearest enclosing wrapper per §4.3's parent-child rules** (the wrapper the calling node's own span parents under) — and pins it with conformance fixtures so the OTel and Langfuse mappings agree. The change is additive: the common case (calling-node span open) is unchanged.

## Motivation

§5.5's parent rule is unconditional ("*is* the node span of the node that invoked the provider") and presumes that span is open. It normally is — a provider call from a node body runs while the node span is on the in-flight stack. But a call issued outside node-body execution — from middleware in its pre- or post-phase, or a wrapper around the node — has no open calling-node span at emission time, and the rule says nothing about where the span then parents. The embedding (§5.5.8), tool-execution (§5.5.11), and rerank (§5.5.13) spans carry the identical "parented under the calling node's span" wording, so the gap is shared across all four span types.

Inside a fan-out instance the gap is consequential. §4.3 already parents node, subgraph, fan-out-instance, and per-branch-dispatch spans by their `(namespace, fan_out_index, branch_name)` lineage, and — for the mixed-nesting case (a node with both `fan_out_index` and `branch_name`) — by the **innermost containing wrapper, determined by namespace-ancestry depth**. A provider span whose calling-node span is closed has no stated parent, so two mappings can resolve it differently (one to the per-instance instance span, the other falling through to the shared subgraph / invocation span), yielding divergent trace shapes for the same workload — which the cross-implementation contract is meant to prevent.

The right answer is the rule §4.3 already defines for spans. A provider/tool span's natural parent, when its calling-node span is gone, is the same wrapper that calling node's span parents under — the nearest enclosing wrapper by namespace-ancestry depth. This keeps the per-instance / per-branch attribution an in-node call would have had (the containment principle proposal 0045 also rests on), without inventing a new resolution mechanism.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive — only the previously-undefined orphan case is newly specified; the common case is unchanged.

### Shared orphan fallback (§5.5, applied to §5.5.8 / §5.5.11 / §5.5.13)

Add a shared fallback clause governing the LLM, embedding, tool-execution, and rerank provider spans — stated once in §5.5 and cross-referenced from §5.5.8 / §5.5.11 / §5.5.13, each of which currently reads "parented under the calling node's span":

> **Parent fallback when the calling-node span is not open.** A provider or tool call MAY be issued when the calling node's span is not open — for example, from middleware in its pre- or post-phase, or a wrapper around the node, rather than the node body. In that case the provider/tool span (and, under call-level retry, its per-attempt sibling spans) parents under the **nearest enclosing wrapper span determined by the §4.3 parent-child rules** — the span the calling node's own span would parent under, selected as the innermost containing wrapper by namespace-ancestry depth. Concretely this is the fan-out instance span when the call is inside a fan-out instance, the per-branch dispatch span inside a parallel branch, the innermost of the two when both are nested (per §4.3's mixed-nesting rule), the subgraph span inside a subgraph, otherwise the invocation span. The span MUST NOT parent under a shared fan-out node span, a shared parallel-branches node span, or the invocation span when a more-specific enclosing wrapper (per §4.3) is open.

Reusing §4.3 — rather than a standalone ladder — is deliberate: §4.3 already resolves the mixed fan-out+branch case by innermost depth, so a fixed instance-first ordering would contradict it.

### §5.5 per-attempt framing — reconcile

The §5.5 framing sentence "the per-attempt spans are siblings parented under the calling node's span" and §4.3's retry bullet (which already qualifies attempt-span parents as "the invocation span, subgraph span, fan-out instance span, or per-branch dispatch span depending on context") are consistent with this fallback: when the calling-node span is closed, the per-attempt sibling spans parent under the same nearest enclosing wrapper. Add a cross-reference so the two read together.

### §8 — Langfuse observation parent follows the same resolution

The Langfuse mapping parents the LLM `Generation` observation (and the embedding / rerank / tool observations) under the same hierarchy. Add a confirming sentence to the §8 mapping: when the calling-node observation is not open, the observation parents under the nearest open ancestor observation resolved by the same §4.3 rule — so the OTel span tree and the Langfuse observation tree produce the same parent for the orphan case. (Exact §8 placement settled at accept against the current §8 text.)

## Conformance test impact

A new observability fixture pins the orphan-fallback parent inside a fan-out instance, asserting the LLM span / observation parents under the per-instance fan-out instance span in **both** the OTel `span_tree` and the Langfuse observation tree (so the two mappings agree). The rule is shared with the embedding / tool / rerank spans; the LLM fixture is the representative case.

Pinning the orphan case requires the harness to issue a provider call with **no open calling-node span** inside a fan-out instance — a call from a wrapper / middleware rather than a node body. Today's fixtures model provider calls only via a node's `calls_llm`, which always runs with the node span open. This proposal adds a conformance-adapter harness primitive for a wrapper/middleware-issued provider call (the exact directive shape settled at accept). The common case (calling-node span open → parents under the calling-node span, itself under the instance span per §4.3) is already covered by existing fan-out + LLM fixtures.

## Versioning

**MINOR bump** (pre-1.0): §5.5 / §5.5.8 / §5.5.11 / §5.5.13 gain a shared fallback for a previously-undefined case; §8 gains a confirming note; no existing (calling-node-span-open) behavior changes. The concrete version is the maintainer's call at acceptance.

## Out of scope

- **Provider/tool calls with an unknown calling node.** The event model carries a non-null calling-node identity (`node_name` / `namespace`); this handles the calling node's *span* not being open, not a call with no node identity.
- **Changing the common-case parent.** When the calling-node span is open, the parent is unchanged (the calling-node span).
- **New span types.** The fallback reuses the §4 hierarchy's existing wrappers (fan-out instance / per-branch dispatch / subgraph / invocation); no new span is introduced.

## Alternatives considered

- **A new "walk the lineage outward" mechanism with a fixed instance → branch → subgraph → invocation ladder.** Rejected: §4.3 already defines parent resolution by innermost-containing-wrapper (namespace-ancestry depth), including the mixed fan-out+branch case; a fixed ladder contradicts §4.3 for a branch nested in a fan-out instance (it would pick the instance span where §4.3 selects the innermost branch span). Reusing §4.3 is correct and introduces no new mechanism for an implementation (or a fixture) to interpret.
- **Fixing only the LLM span (the reported divergence).** Rejected: §5.5.8 / §5.5.11 / §5.5.13 carry the identical unconditional parent rule, so the embedding / tool / rerank spans have the same latent orphan gap; one shared fallback closes all four and prevents three future repeats.
- **Do nothing (leave it undefined).** Rejected: the orphan case is reachable (middleware/wrapper-issued calls), and the two mappings already diverge on it — the cross-implementation divergence the spec exists to prevent.

## Open questions

- **Does the orphaned provider event carry the calling node's enclosing lineage for non-node-body calls?** The fallback parents by the calling node's `(namespace, fan_out_index, branch_name)`, which the typed events carry for node-body calls. It must be confirmed that a middleware/wrapper-issued call's event still carries the enclosing fan-out / branch lineage; if it does not, a graph-engine §6 change (surfacing that lineage on such events) is required and must be added to Targets. To confirm with the implementation before accept — the twin of 0085's save-time-lineage question.
- **The exact conformance-adapter directive** for issuing a provider call with no open calling-node span (a wrapper vs a middleware-phase call) — settled at accept with the fixture authoring.
- **Whether §8 needs an explicit parent-resolution clause** or already inherits the hierarchy such that a confirming note suffices — verified against the current §8 text at accept.
