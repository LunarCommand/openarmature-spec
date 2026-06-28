# 0088: Observability — Langfuse Parallel-Branches Mapping Parity

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-27
- **Targets:** spec/observability/spec.md §8 (a Langfuse **per-branch dispatch-Span synthesis** statement, mirroring the OTel §6 synthesis — likely a new §8.4 subsection); §8.3 *Observation-type mapping* (rows for the parallel-branches **node span** and the **per-branch dispatch span**, mirroring the existing Fan-out node / Fan-out instance rows); §8.4.2 *Observation-level mapping* (rows for the §5.7 parallel-branches attributes `branch_count` / `error_policy` / `parent_node_name`, mirroring the four `fan_out_*` rows — `branch_name` already exists per 0042). A new dedicated Langfuse parallel-branches dispatch-span conformance fixture.
- **Related:** 0044 (parallel-branches dispatch span — the OTel synthesis §4.3/§5.7/§6 + fixtures 030/038 this brings the Langfuse side level with), 0011 (parallel branches), 0042 (the §8.4.2 `observation.metadata.branch_name` row), 0075 (callable-branch §5.7 note), 0084 (whose #188–#194 consolidated review — `review-fixture-harness-catchup` `13`/`14` — surfaced this asymmetry; also added the §8.4.3/§8.4.6 lineage-parent notes).
- **Supersedes:**

## Summary

The parallel-branches dispatch span has a complete **OTel** mapping — §4.3 parents inner-branch spans under a synthesized per-branch dispatch span, §5.7 defines its attributes, §6 specifies the observer synthesis, and fixtures 030/038 pin it. The **Langfuse** mapping is asymmetric with the analogous fan-out mapping: §8.3 has no observation-type row for the parallel-branches node span or per-branch dispatch span (fan-out has both), §8.4.2 maps none of the §5.7 parallel-branches node attributes (`branch_count` / `error_policy` / `parent_node_name`) where it maps all four `fan_out_*` attributes, and there is no dedicated Langfuse parallel-branches fixture (fan-out has `032`). The Langfuse three-level tree is currently pinned only **incidentally** by fixture `030` (a §3.4 caller-metadata fixture) and the §1/§8 cross-backend-equivalence framing. This proposal brings the Langfuse parallel-branches mapping to first-class parity with the OTel side and the fan-out Langfuse mapping.

## Motivation

The OTel observer synthesizes a per-branch dispatch span (one per `branch_name` within a parallel-branches node's execution) between the parallel-branches NODE span and the inner-node spans (§4.3 / §6), carrying the §5.7 attributes. A Langfuse observer must produce the **same three-level Observation tree** for cross-backend equivalence (§1: "the OTel mapping is the reference shape for cross-backend equivalence"). python's #190 brought its Langfuse observer into line — but it had to, against an under-specified spec:

- **§8.3** maps `Fan-out node span` and `Fan-out instance span` to Span observations, but has **no row** for the parallel-branches node span or the per-branch dispatch span. A reader implementing the Langfuse mapping from §8.3 alone would not know the per-branch dispatch Span exists.
- **§8.4.2** maps the four fan-out node attributes (`fan_out_item_count` / `fan_out_concurrency` / `fan_out_error_policy` / `fan_out_parent_node_name`) to `observation.metadata.*`, but maps **none** of the §5.7 parallel-branches node attributes beyond `branch_name` (added by 0042). `branch_count`, `error_policy`, and `parent_node_name` have no Langfuse mapping row.
- **No §8 synthesis statement.** The per-branch dispatch span is *synthesized* by the observer (unlike a fan-out instance span, which corresponds to a real instance subgraph execution). §6 specifies the synthesis for the OTel observer; §8 says nothing about the Langfuse observer synthesizing the equivalent Span observation — it is implied only by fixture 030 + the equivalence framing.
- **No dedicated fixture.** Fan-out has `032-langfuse-fan-out-per-instance-spans`; parallel-branches has the OTel-side `038` but no Langfuse analog — the Langfuse tree rides on `030`, whose stated purpose is §3.4 caller-metadata isolation.

This is a cross-implementation under-specification: the contract a second Langfuse implementation must satisfy lives in a fixture's incidental expectations rather than in §8's prose + a dedicated pin.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive Langfuse-mapping rows + a synthesis statement + a fixture; brings the spec into line with already-conformant behavior (python #190), so no conforming Langfuse observer changes.

### §8 — Langfuse per-branch dispatch-Span synthesis

Add a statement (a new §8.4 subsection — *Parallel-branches dispatch-span mapping*, exact number settled at accept) that the Langfuse observer synthesizes a **per-branch dispatch Span observation** between the parallel-branches NODE's Span observation and the branch's inner-node observations — one per `branch_name` value within the node's execution — mirroring the OTel synthesis (§4.3 / §6): lazy creation on the first inner observation of each branch, the §5.7 attributes attached, closed in declaration order on the parallel-branches NODE's completion (children-before-parents). This is the Langfuse counterpart of §6's observer-driven synthesis; the contract is the emitted Observation tree, not the driver mechanism (per §6's framing).

### §8.3 — observation-type rows

Add rows mirroring the fan-out pair:

> | Parallel-branches node span (§4.3) | Span observation (the dispatcher; contains the per-branch dispatch Span observations) |
> | Per-branch dispatch span (§4.3 / §5.7) | Span observation, child of the parallel-branches node Span (one per `branch_name`) |

### §8.4.2 — observation-level attribute rows

Add the §5.7 parallel-branches attributes (mirroring the `fan_out_*` rows), e.g.:

> | `parallel_branches.branch_count` | `observation.metadata.branch_count` (on the parallel-branches node Span observation) |
> | `parallel_branches.error_policy` | `observation.metadata.error_policy` |
> | `parallel_branches.parent_node_name` | `observation.metadata.parent_node_name` (on the per-branch dispatch Span observation) |

(`branch_name` already maps to `observation.metadata.branch_name` per 0042; exact key names + which observation each rides settled at accept against the §5.7 attribute placement.)

## Conformance test impact

A new dedicated Langfuse parallel-branches fixture (`NNN-langfuse-parallel-branches-dispatch-span`) pins the three-level Observation tree (parallel-branches node Span → per-branch dispatch Span → inner-node observations), the per-branch `branch_name`, and the new node-level attribute rows — the Langfuse analog of fan-out's `032` and the OTel `038`. Fixture `030`'s incidental coverage stands but is no longer the only pin. No new directive vocabulary (the parallel-branches modeling + Langfuse-trace assertion shapes already exist).

## Versioning

**MINOR bump** (pre-1.0): additive §8.3 / §8.4.2 rows + a §8 synthesis statement + a fixture; no change to any conforming Langfuse observer (the behavior matches python #190). The concrete version is the maintainer's call at acceptance (sequenced relative to 0087).

## Out of scope

- **The OTel side.** Already complete (§4.3 / §5.7 / §6, fixtures 030/038) — unchanged.
- **New parallel-branches attributes.** This maps the existing §5.7 attribute surface onto Langfuse; it adds no new attribute.
- **Other §8 deferrals** (Scoring / Cost, §8.10) — untouched.

## Alternatives considered

- **Do nothing — leave the Langfuse tree pinned incidentally by fixture 030.** Rejected: a second Langfuse implementation has no §8 prose stating the per-branch dispatch Span exists or which attributes it carries; the contract should be in the mapping, not inferred from a §3.4 fixture's expectations.
- **A §8 cross-reference to §6 instead of a Langfuse-specific statement.** Rejected: §6 is the OTel observer's driving-span lifecycle; the Langfuse observer has its own observation model, and the fan-out precedent (§8.3 has dedicated fan-out rows, not a §6 cross-ref) is to state the Langfuse mapping explicitly.
- **Fold into a future broader §8 cleanup.** Rejected: the asymmetry is concrete and already surfaced by a real implementation (#190); pinning it now (the prefer-now disposition) keeps the cross-backend contract honest while it is fresh.

## Open questions

- **Which observation carries which attribute.** `branch_count` / `error_policy` are §5.7 parallel-branches **node**-span attributes; `parent_node_name` is a **dispatch**-span attribute. The §8.4.2 rows should place each on the correct observation (node Span vs per-branch dispatch Span) — confirm against the §5.7 placement at accept.
- **Exact §8.4 subsection number** for the synthesis statement (sibling to §8.4.5 Embedding / §8.4.6 Tool / §8.4.7 Rerank) — settle at accept.
