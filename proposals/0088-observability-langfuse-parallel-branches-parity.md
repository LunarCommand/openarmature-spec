# 0088: Observability — Langfuse Parallel-Branches Mapping Parity

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-27
- **Targets:** spec/observability/spec.md §8 (a Langfuse **per-branch dispatch-span synthesis** statement — including the synthesized span's `observation.name`, resolving §5.7's dangling forward-reference to "the Langfuse mapping's per-branch Span observation naming"; likely a new §8.4 subsection); §8.3 *Observation-type mapping* (a row for the synthesized **per-branch dispatch span**, plus a parallel-branches **node-span** row for symmetry with the Fan-out node row); §8.4.2 *Observation-level mapping* (rows for the §5.7 parallel-branches attributes — node-span `branch_count` / `error_policy` and dispatch-span `parent_node_name` — flattened with the `parallel_branches_` prefix, mirroring the `fan_out_*` rows; `branch_name` already exists per 0042); §3.4 *reserved caller-metadata-key set* (reserve the new `parallel_branches_*` metadata keys, as the `fan_out_*` keys and `branch_name` are reserved). A new dedicated Langfuse parallel-branches dispatch-span conformance fixture.
- **Related:** 0044 (parallel-branches dispatch span — the OTel synthesis §4.3 / §5.7 / §6 + fixtures `030`/`038` this brings the Langfuse side level with), 0011 (parallel branches), 0042 (the §8.4.2 `branch_name` metadata row + its §3.4 reservation — the precedent this follows), 0075 (callable-branch §5.7 note), 0084 (added the §8.4.3 / §8.4.6 lineage-parent notes; a cross-implementation conformance review during that work surfaced this asymmetry).
- **Supersedes:**

## Summary

The parallel-branches dispatch span has a complete **OTel** mapping — §4.3 parents inner-branch spans under a synthesized per-branch dispatch span, §5.7 defines its attributes, §6 specifies the observer synthesis, and fixtures `030`/`038` pin it. The **Langfuse** mapping is asymmetric with the analogous fan-out mapping: §8.3 has no observation-type row for the synthesized per-branch dispatch span (fan-out has a dedicated row for each of its span types), §8.4.2 maps none of the §5.7 parallel-branches attributes (`branch_count` / `error_policy` / `parent_node_name`) where it maps all four `fan_out_*` attributes, the synthesized dispatch span's `observation.name` is unspecified (yet §5.7 already forward-references it), and there is no dedicated Langfuse parallel-branches fixture (fan-out has `032`). The Langfuse three-level tree is currently pinned only **incidentally** by fixture `030` (a §3.4 caller-metadata fixture) and the §1/§8 cross-backend-equivalence framing. This proposal brings the Langfuse parallel-branches mapping to first-class parity with the OTel side and the fan-out Langfuse mapping.

## Motivation

The OTel observer synthesizes a per-branch dispatch span (one per `branch_name` within a parallel-branches node's execution) between the parallel-branches NODE span and the inner-node spans (§4.3 / §6), carrying the §5.7 attributes. A Langfuse observer must produce the **same three-level Observation tree** for cross-backend equivalence (§1: "the OTel mapping is the reference shape for cross-backend equivalence"). An implementation already produces it — it has to, for equivalence — but against an under-specified spec:

- **§8.3** maps `Fan-out node span` and `Fan-out instance span` to Span observations, but has **no row** for the **synthesized per-branch dispatch span**. (The parallel-branches *node* span is an ordinary node span already covered by the generic `Node span → Span observation` row; the *synthesized dispatch span* is the genuinely-unmapped one — a reader implementing §8.3 alone would not know it exists.)
- **§8.4.2** maps the four fan-out node attributes (`fan_out_item_count` / `fan_out_concurrency` / `fan_out_error_policy` / `fan_out_parent_node_name`) to `observation.metadata.*`, but maps **none** of the §5.7 parallel-branches attributes beyond `branch_name` (added by 0042): the node-span `branch_count` / `error_policy` and the **dispatch-span** `parent_node_name` have no Langfuse mapping row.
- **No §8 synthesis statement, and an unspecified dispatch-span name.** The per-branch dispatch span is *synthesized* by the observer (unlike a fan-out instance span, which corresponds to a real instance subgraph execution); §6 specifies the synthesis for the OTel observer, but §8 says nothing about the Langfuse observer synthesizing the equivalent Span observation. And §5.7's dispatch-span-name rule already states it "matches the Langfuse mapping's per-branch Span observation naming" — a forward-reference to a Langfuse rule that does not exist.
- **No dedicated fixture.** Fan-out has `032-langfuse-fan-out-per-instance-spans`; parallel-branches has the OTel-side `038` but no Langfuse analog — the Langfuse tree rides on `030`, whose stated purpose is §3.4 caller-metadata isolation.

This is a cross-implementation under-specification: the contract a second Langfuse implementation must satisfy lives in a fixture's incidental expectations rather than in §8's prose + a dedicated pin.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive Langfuse-mapping rows + a synthesis statement + a fixture; the emitted Langfuse tree already matches the cross-backend reference shape, so no conforming Langfuse observer changes. The one behavior touch is the §3.4 reservation below (see Versioning).

### §8 — Langfuse per-branch dispatch-span synthesis (incl. the span name)

Add a statement (a new §8.4 subsection — *Parallel-branches dispatch-span mapping*, exact number settled at accept) that the Langfuse observer synthesizes a **per-branch dispatch Span observation** between the parallel-branches NODE's Span observation and the branch's inner-node observations — one per `branch_name` value within the node's execution — mirroring the OTel synthesis (§4.3 / §6): lazy creation on the first inner observation of each branch, the §5.7 attributes attached, closed in declaration order on the parallel-branches NODE's completion (children-before-parents). The synthesized Span's `observation.name` is the `branch_name`, which resolves §5.7's existing dangling forward-reference. The contract is the emitted Observation tree, not the driver mechanism (per §6's framing).

### §8.3 — observation-type row

Add the genuinely-missing dispatch-span row, plus (for symmetry with the dedicated Fan-out node-span row) a parallel-branches node-span row noting it contains the per-branch dispatch Spans:

> | Parallel-branches node span (§4.3) | Span observation (contains the per-branch dispatch Span observations) |
> | Per-branch dispatch span (§4.3 / §5.7) | Span observation, child of the parallel-branches node Span (one per `branch_name`); `observation.name` = the `branch_name` |

### §8.4.2 — observation-level attribute rows

Add the §5.7 parallel-branches attributes, flattened with the `parallel_branches_` prefix (mirroring the `fan_out_*` flattening of `openarmature.fan_out.*`):

> | `openarmature.parallel_branches.branch_count` | `observation.metadata.parallel_branches_branch_count` (parallel-branches node Span observation) |
> | `openarmature.parallel_branches.error_policy` | `observation.metadata.parallel_branches_error_policy` (node Span observation) |
> | `openarmature.parallel_branches.parent_node_name` | `observation.metadata.parallel_branches_parent_node_name` (per-branch dispatch Span observation) |

The placement is fixed by §5.7 (no open question): `branch_count` / `error_policy` are parallel-branches **node**-span attributes; `branch_name` (already mapped to `observation.metadata.branch_name` per 0042) and `parent_node_name` are **per-branch dispatch-span** attributes.

### §3.4 — reserve the new metadata keys

§8.4 writes these as top-level `observation.metadata.*` keys, so — exactly as `fan_out_item_count` / `fan_out_error_policy` / … and `branch_name` (0042) are reserved — §3.4's reserved caller-metadata-key set gains `parallel_branches_branch_count` / `parallel_branches_error_policy` / `parallel_branches_parent_node_name`, so a caller passing one of those as invocation metadata cannot shadow the OA-emitted field.

## Conformance test impact

A new dedicated Langfuse parallel-branches fixture (`NNN-langfuse-parallel-branches-dispatch-span`) pins the three-level Observation tree (parallel-branches node Span → per-branch dispatch Span → inner-node observations), the dispatch-span `observation.name` = `branch_name`, and the new node-level + dispatch-level attribute rows — the Langfuse analog of fan-out's `032` and the OTel `038`. Fixture `030`'s incidental coverage stands but is no longer the only pin. No new directive vocabulary (the parallel-branches modeling + Langfuse-trace assertion shapes already exist).

## Versioning

**MINOR bump** (pre-1.0): additive §8.3 / §8.4.2 rows + a §8 synthesis statement + a fixture; the emitted Langfuse tree is unchanged for a conforming observer (it already matches the cross-backend reference shape). The one behavior touch is the §3.4 reservation: a caller currently passing `parallel_branches_branch_count` / `_error_policy` / `_parent_node_name` as invocation metadata would newly be rejected at the `invoke()` boundary — additive in spirit (these are OA-namespaced keys callers should not be setting), but noted rather than claimed as zero-impact. The concrete version is the maintainer's call at acceptance (sequenced relative to 0087).

## Out of scope

- **The OTel side.** Already complete (§4.3 / §5.7 / §6, fixtures `030`/`038`) — unchanged.
- **New parallel-branches attributes.** This maps the existing §5.7 attribute surface onto Langfuse; it adds no new attribute.
- **Other §8 deferrals** (Scoring / Cost, §8.10) — untouched.

## Alternatives considered

- **Do nothing — leave the Langfuse tree pinned incidentally by fixture `030`.** Rejected: a second Langfuse implementation has no §8 prose stating the per-branch dispatch Span exists, what it's named, or which attributes it carries; the contract should be in the mapping, not inferred from a §3.4 fixture's expectations — and §5.7's dangling forward-reference stays dangling.
- **A §8 cross-reference to §6 instead of a Langfuse-specific statement.** Rejected: §6 is the OTel observer's driving-span lifecycle; the Langfuse observer has its own observation model, and the fan-out precedent (§8.3 has dedicated fan-out rows, not a §6 cross-ref) is to state the Langfuse mapping explicitly.
- **Fold into a future broader §8 cleanup.** Rejected: the asymmetry is concrete and already surfaced by a cross-implementation conformance review; pinning it now (the prefer-now disposition) keeps the cross-backend contract honest while it is fresh.

## Open questions

- **Exact §8.4 subsection number** for the synthesis statement (sibling to §8.4.5 Embedding / §8.4.6 Tool / §8.4.7 Rerank) — settle at accept.
