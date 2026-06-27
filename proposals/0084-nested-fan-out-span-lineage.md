# 0084: Observability — Nested-Fan-Out Span Lineage Chain and Provider/Tool Parent Resolution

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-26
- **Accepted:** 2026-06-27
- **Targets:** spec/graph-engine/spec.md §6 (the observer event surface carries only the scalar `fan_out_index` / `branch_name` today; add a **fan-out-index chain** and a **branch-name chain** — the enclosing fan-out / branch lineage, outermost→innermost, aligned to the `namespace` path — to `NodeEvent`, the provider/tool events `LlmCompletionEvent`, `LlmFailedEvent`, `LlmTokenEvent`, and the embedding / rerank / tool events, and the framework metadata-augmentation event (so its observer scoping stays consistent with the chain-keyed span stack); note the chains in the event-source identity discussion). spec/observability/spec.md (§4.1 / §4.3 / §6 — the driving-span key plus the node / subgraph / fan-out-instance / per-branch parent-child rules become lineage-chain-aware so concurrent nested instances do not collide; §5.5 and the embedding §5.5.8 / tool §5.5.11 / rerank §5.5.13 spans — the calling-node-span parent rule gains the orphan fallback **and** uses the chain to resolve the correct *inner* wrapper; §5.5.7 typed-event note; §8 Langfuse observation parent follows the same resolution). spec/conformance-adapter/spec.md (a harness primitive to issue a provider call with no open calling-node span inside a fan-out instance, plus nested-fan-out modeling under concurrency). New graph-engine fixture(s) for the event chains and new observability fixtures pinning span keying / nested-LLM exact-match / the orphan fallback inside a nested instance, in both the OTel and Langfuse mappings.
- **Related:** 0005 (parallel fan-out — the fan-out instance span), 0007 (observability §4 span hierarchy + §4.3 parent-child rules this builds on), 0045 (nested-lineage augmentation — the observer-computed lineage boundary this formalizes onto the event surface), 0049 / 0058 (typed LLM events — carry the scalar `(namespace, fan_out_index, branch_name)` lineage extended here), 0061 (detached-trace invocation span), 0085 (the sibling nested-fan-out surface — the checkpoint record's `enclosing_fan_out_lineage`; this is its observer-event-surface counterpart).
- **Supersedes:**

## Summary

The observer event surface (graph-engine §6) carries only the **scalar** `fan_out_index` and `branch_name`. For a fan-out nested inside an outer fan-out instance, an inner node's `fan_out_index` is the **innermost** instance index — identical across outer instances — so under concurrency two outer instances' inner-node events collide on the observer's span key and the second instance's spans are dropped. The same scalar blind spot defeats §5.5's provider-span parenting: an orphaned provider span (calling-node span not open) cannot tell a nested instance from a coincidentally-indexed sibling, so it mis-parents.

This proposal adds the missing mechanism — an **enclosing-lineage chain on the event surface** — and the observer rules it enables, as one coherent change:

1. **graph-engine §6** gains a `fan_out_index_chain` and a `branch_name_chain` on `NodeEvent`, the provider/tool events, and the framework metadata-augmentation event: the outermost→innermost lineage of enclosing fan-out instances and parallel branches, aligned to the `namespace` path. (This formalizes onto the spec's event surface the lineage 0045 previously left observer-computed.)
2. **observability §4.3** keys node / subgraph / fan-out-instance / per-branch spans by the chain, so concurrent nested instances stop colliding (no dropped spans).
3. **observability §5.5** (and the embedding / tool / rerank spans) gains (a) **nested-LLM exact-match** — a provider span parents under its own lineage-disambiguated calling-node span — and (b) an **orphan fallback** — when the calling-node span is not open, the span parents under the nearest enclosing wrapper per §4.3, resolved via the chain to the correct *inner* instance, not the top-level one.

The change is additive: the scalars are retained (the innermost values), and the common single-level case is unchanged.

## Motivation

Two linked gaps, both rooted in the scalar-only event surface:

**Nested span dropping (concurrency).** §4.3 keys spans by `(namespace, fan_out_index, branch_name)`. Inside a fan-out nested in an outer fan-out instance, the inner node's `fan_out_index` is the inner index — the same value for every outer instance. Under concurrent outer execution, two outer instances' inner-node `started`/`completed` events therefore carry identical keys, and an observer maintaining a span stack keyed by that tuple collides them — the second instance's spans are silently dropped. The lineage that disambiguates them (which outer instance) exists in the engine but is not on the event.

**Orphan / nested provider-span mis-parenting.** §5.5 parents an LLM provider span under "the node span of the node that invoked the provider," and §5.5.8 / §5.5.11 / §5.5.13 say the same unconditionally for embedding / tool / rerank. None defines a fallback for when that calling-node span is not open (a call from middleware or a wrapper, not the node body). Inside a nested fan-out the gap compounds: even the common case (calling-node span open) needs the chain to *exact-match* the provider span to its lineage-disambiguated calling-node span; and the orphan case's top-level shortcut (`namespace[:1]` + scalar index) cannot distinguish a nested instance from a sibling top-level instance whose index coincides. Two backend mappings can then resolve the same workload differently — the cross-implementation divergence the spec exists to prevent.

Both are cured by the same addition: the enclosing-lineage chain on the event surface, plus the §4.3 resolution already defined for spans. The chain keeps the per-instance / per-branch attribution an in-node call would have had — the containment principle 0045 also rests on — without inventing a new resolution mechanism.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive — new optional event fields and a newly-specified resolution for previously-undefined / scalar-ambiguous cases; the scalars and the common single-level case are unchanged.

### graph-engine §6 — event lineage chain

`NodeEvent`, `LlmCompletionEvent`, `LlmFailedEvent`, `LlmTokenEvent`, and the embedding / rerank / tool events each gain two fields (`ToolCallFailedEvent` inherits them by reference from `ToolCallEvent`):

> - `fan_out_index_chain` — an ordered sequence aligned position-by-position to the event's `namespace` path (one entry per namespace segment / dispatch boundary). At each position, the `fan_out_index` of the fan-out instance entered at that boundary, or **null** when that boundary is not a fan-out instance (a plain subgraph wrapper, or a parallel-branch boundary). Empty for an event with no enclosing fan-out / branch lineage (a top-level event).
> - `branch_name_chain` — the same shape, carrying the `branch_name` of the parallel branch entered at each boundary, or **null** when that boundary is not a parallel branch.

At any one position at most one of the two chains is non-null (a dispatch boundary is a fan-out instance, a parallel branch, or a plain subgraph). The existing scalar `fan_out_index` / `branch_name` are **retained unchanged**, carrying the innermost (deepest non-null) value of the respective chain; an implementation that does not nest fan-outs / branches reads the scalars exactly as before. The chains are the spec event-surface formalization of the per-depth lineage 0045 described as observer-computed; the event-source identity discussion (§6) notes that, for a node nested inside multiple fan-out / branch boundaries, the scalars alone do not uniquely identify the source — the chains do.

The framework-emitted metadata-augmentation event (graph-engine §6, proposals 0040 / 0045) also carries the chains, for the same reason: an observer scopes a mid-invocation augmentation to the augmenting context's open spans by lineage, and under nested concurrency the innermost scalar coincides across enclosing instances — so a scalar-only scope would leak the augmentation into a coincidentally-indexed sibling subtree. `NodeEvent` and the provider/tool events are the primary surface; the augmentation event is included so its scoping stays consistent with the now-chain-keyed span stack.

### observability §4.1 / §4.3 / §6 — lineage-chain-aware span keying

The driving-span key (§4.1 / §6) is today the scalar tuple `(namespace, attempt_index, fan_out_index, branch_name)`, and §4.3 parents node / subgraph / fan-out-instance / per-branch-dispatch spans by `(namespace, fan_out_index, branch_name)`, resolving mixed nesting by the innermost containing wrapper (namespace-ancestry depth). Both become **chain-aware**: the driving-span key and the §4.3 parent resolution key by the full `fan_out_index_chain` / `branch_name_chain` rather than the innermost scalar, so the inner-node spans of two concurrent outer instances — identical innermost `fan_out_index`, distinct chains — no longer collide (the second instance's spans stop being dropped). The common single-level case (chain length ≤ 1) keys identically to today.

### observability §5.5 — nested-LLM exact-match and orphan fallback

The calling-node-span parent rule in §5.5 (and §5.5.8 / §5.5.11 / §5.5.13) gains a shared clause, stated once in §5.5 and cross-referenced from the three sibling sections:

> **Lineage-resolved parent.** A provider or tool span parents under the calling node's span identified by the event's full lineage chain — for a node nested inside one or more fan-out instances / parallel branches, the calling-node span disambiguated by `fan_out_index_chain` / `branch_name_chain`, not the innermost scalar (which can coincide across concurrent enclosing instances). When the calling node's span is **not open** — a call issued from middleware (pre- or post-phase) or a wrapper rather than the node body — the provider/tool span (and, under call-level retry, its per-attempt sibling spans) parents under the **nearest enclosing wrapper span per the §4.3 parent-child rules**, resolved via the chain: the fan-out **instance** span (the correct *inner* instance, identified by the chain — not the top-level instance, and not a coincidentally-indexed sibling), the per-branch dispatch span inside a parallel branch, the innermost of the two when both are nested (per §4.3's mixed-nesting rule), the subgraph span inside a subgraph, otherwise the invocation span. The span MUST NOT parent under a shared fan-out node span, a shared parallel-branches node span, or the invocation span when a more-specific enclosing wrapper (per §4.3) is open.

Reusing §4.3 — rather than a standalone instance→branch→subgraph→invocation ladder — is deliberate: §4.3 already resolves the mixed fan-out+branch case by innermost depth, so a fixed ordering would contradict it for a branch nested in a fan-out instance.

### §5.5 per-attempt framing — reconcile

§5.5's "the per-attempt spans are siblings parented under the calling node's span" and §4.3's retry bullet (attempt-span parents are "the invocation span, subgraph span, fan-out instance span, or per-branch dispatch span depending on context") read together with the fallback: when the calling-node span is closed, the per-attempt sibling spans parent under the same nearest enclosing wrapper, chain-resolved. A cross-reference is added so the three read consistently.

### §5.5.7 typed-event note

§5.5.7 renders the LLM span from `LlmCompletionEvent`. A note records that the event now carries `fan_out_index_chain` / `branch_name_chain` and that the span parent is resolved from the chain per §4.3 (above), not the innermost scalar.

### §8 — Langfuse observation parent follows the same resolution

The Langfuse mapping parents the LLM `Generation` (and the embedding / rerank / tool observations) under the same hierarchy. A confirming sentence is added: the observation parents under the ancestor observation resolved by the same chain-aware §4.3 rule — exact-match to the lineage-disambiguated calling-node observation, and, when that is not open, the nearest open ancestor observation — so the OTel span tree and the Langfuse observation tree produce the same parent for the nested and orphan cases.

## Conformance test impact

A new **graph-engine** fixture pins the event surface: events from a node inside a fan-out nested in an outer fan-out instance carry the correct `fan_out_index_chain` / `branch_name_chain` (and the scalars unchanged as the innermost values).

New **observability** fixtures pin the chain's three consumers, inside a fan-out nested in an outer fan-out instance under concurrency, asserted in **both** the OTel `span_tree` and the Langfuse observation tree:

1. **Span keying** — two concurrent outer instances' inner-node spans both appear (no dropped spans), each under its own outer-instance lineage.
2. **Nested-LLM exact-match** — a provider span inside a nested instance parents under its own lineage-disambiguated calling-node span, not a sibling's.
3. **Orphan fallback** — a provider call with no open calling-node span inside a nested instance parents under the correct *inner* fan-out instance span (not the top-level one).

The orphan case requires a conformance-adapter primitive to issue a provider call with **no open calling-node span** inside a fan-out instance (a wrapper / middleware-issued call); today's fixtures model provider calls only via a node's `calls_llm`, which always runs with the node span open. The nested-fan-out modeling reuses existing fan-out directives under concurrent dispatch. The common single-level case (calling-node span open → parents under the calling-node span) is already covered by existing fan-out + LLM fixtures.

## Versioning

**MINOR bump** (pre-1.0): graph-engine §6 gains optional event fields; observability §4.3 / §5.5 / §5.5.8 / §5.5.11 / §5.5.13 / §8 gain a chain-aware resolution and the orphan fallback; conformance-adapter gains the orphan-call primitive. No existing single-level behavior changes (the scalars and the calling-node-span-open path are unchanged). The concrete version is the maintainer's call at acceptance.

## Out of scope

- **Provider/tool calls with an unknown calling node.** The event model carries a non-null calling-node identity (`node_name` / `namespace`); this handles the calling node's *span* not being open and the *nested* disambiguation, not a call with no node identity.
- **Changing the single-level parent.** When the calling-node span is open and nesting is ≤ 1 level, the parent is unchanged (the calling-node span).
- **New span types.** The resolution reuses the §4 hierarchy's existing wrappers (fan-out instance / per-branch dispatch / subgraph / invocation); no new span is introduced.
- **The checkpoint-record lineage.** The persisted `enclosing_fan_out_lineage` on `fan_out_progress` is the sibling surface, specified by proposal 0085; this proposal is the observer-event-surface counterpart.

## Alternatives considered

- **A separate proposal for the §6 chain, leaving 0084 as the orphan fallback only.** Rejected: the orphan fallback, the nested-LLM exact-match, and the §4.3 keying fix all depend on the same chain, and the implementation designs the node-key fix and the LLM-resolver fix together against one surface; splitting them would ship an interim mis-parent (node-key fixed, resolver still on the scalar fallback).
- **A richer per-entry chain shape** (each entry a record of the enclosing fan-out node's position plus its index). Rejected in favor of two parallel sequences aligned to the `namespace` path: it mirrors `namespace` (a flat path indexed by depth), a `null` entry cleanly marks a non-fan-out / non-branch boundary, and it matches the lineage the reference implementation already carries on `NodeEvent` — formalizing it is a rename, not a reshape.
- **A fixed instance → branch → subgraph → invocation fallback ladder.** Rejected: §4.3 already resolves parent by innermost-containing-wrapper (namespace-ancestry depth), including the mixed fan-out+branch case; a fixed ladder contradicts §4.3 for a branch nested in a fan-out instance.
- **Fixing only the LLM span (the reported divergence).** Rejected: §5.5.8 / §5.5.11 / §5.5.13 carry the identical unconditional parent rule, so the embedding / tool / rerank spans have the same latent gap; one shared resolution closes all four.
- **Do nothing.** Rejected: nested spans drop under concurrency (lost observability) and the two mappings already diverge on the orphan case — both are cross-implementation correctness holes.

## Open questions

Resolved at acceptance (the items the Draft carried):

- **Event lineage availability** — confirmed with the implementation that the enclosing fan-out / branch lineage is available when `NodeEvent` and the provider/tool events are emitted (the reference implementation already carries `fan_out_index_chain` on `NodeEvent`); this proposal formalizes it onto the spec event surface and extends it to the provider/tool events. The twin of 0085's save-time-lineage question, likewise confirmed.
- **Field shape** — pinned to the two parallel `namespace`-aligned sequences above (the implementation's de-facto shape), with `null` at non-applicable depths and the scalars retained as the innermost values.
- **The conformance-adapter orphan-call directive** and the **exact §8 placement** — settled in this accept against the current conformance-adapter and §8 text, with the fixture authoring.
