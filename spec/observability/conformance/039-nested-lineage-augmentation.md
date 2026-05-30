# 039 — Nested-Lineage Augmentation Containment Scope

Verifies §3.4's lineage-aware boundary rule from [proposal 0045](../../../proposals/0045-observability-nested-lineage-augmentation.md)
against three nested-dispatch shapes: inner fan-out inside outer fan-out instance, parallel-
branches inside fan-out instance, and fan-out inside serial subgraph. The new rule is that
the augmenter's **full call-stack ancestor chain** — every outer dispatch context the
augmenter crossed via `descend_into_fan_out_instance`, `descend_into_branch`, or
`descend_into_subgraph` — MUST be updated by the augmentation, not only the augmenter's
immediate dispatch context.

Single-level scope (one fan-out instance OR one parallel branch on the augmenter's path) is
verified by [029](029-caller-metadata-fan-out-per-instance.md),
[030](030-caller-metadata-parallel-branches-per-branch.md), and
[034](034-caller-metadata-open-span-update-serial.md); their assertions remain correct under
the lineage-aware rule (call-stack ancestor chain of length one reduces to the existing
single-level rule).

**Spec sections exercised:**

- §3.4 — *Augmenter's call-stack ancestor chain (MUST)*: every dispatch ancestor on the
  augmenter's call-stack path receives the augmentation in place.
- §3.4 — *Sibling boundary (MUST NOT)*: siblings at every dispatch depth (outer-instance
  siblings, inner-instance siblings under the same outer, branch siblings, fan-out instance
  siblings under a shared parent) do NOT cross-pollinate.
- §3.4 — *Shared-parent boundary (MUST NOT)*: fan-out NODE spans, parallel-branches NODE
  spans, and the invocation span MUST NOT carry the augmentation.
- §3.4 — *Per-async-context scoping* + *Per-depth lineage tracking*: implementations must
  preserve the dispatch-context lineage as a list (one entry per dispatch depth), not a
  single scalar identifier that gets clobbered at each nested descent.
- §5.6 — `openarmature.user.*` cross-cutting attributes reflect the in-scope metadata at
  span-emission time on every span; the lineage rule means the same metadata also lands on
  the open ancestor dispatch spans via in-place update.
- §8.4.2 — Langfuse `observation.metadata` on each dispatch ancestor on the augmenter's path
  carries the augmented key.

**Cases:**

1. `inner_fan_out_augmenter_propagates_to_outer_dispatch_span` — outer fan-out over two
   products; each outer instance runs an inner fan-out over a single-element list (one
   inner instance per outer, avoiding last-writer races on the outer dispatch span). Each
   leaf augments `note=<inner_seed.value>` via `augment_metadata_from_field`. Asserts each
   outer-instance dispatch span carries the inner-leaf's augmentation (lineage-aware
   propagation across two fan-out boundaries), sibling outer subtrees remain isolated, and
   the outer / inner fan-out NODE spans + invocation MUST NOT carry the augmentation.
2. `parallel_branch_augmenter_propagates_to_outer_fan_out_instance` — outer fan-out over
   two products; each outer-instance subgraph runs a `dispatcher` parallel-branches node
   with two branches (`probe`, `baseline`); only the `probe` branch augments
   `note=<outer.id>`. Asserts the augmentation reaches the probe branch's dispatch span
   (existing single-level rule) AND the outer fan-out instance's dispatch span (the new
   lineage-aware rule), while the sibling `baseline` branch, the parallel-branches NODE
   span, the outer fan-out NODE span, sibling outer-instance subtrees, and the invocation
   span do NOT.
3. `fan_out_in_serial_subgraph_augmenter_propagates_to_wrapper_span` — outer graph has a
   `wrap` subgraph-call node that descends into the serial subgraph `wrapped_fan_out`; the
   wrapper contains a `pick` fan-out over two products. Each fan-out instance's leaf
   augments `note=<product.id>` via `augment_metadata_from_field`. Asserts the outer
   serial subgraph wrapper span (the `wrap` node span) carries the augmentation — the new
   lineage-aware rule across a `descend_into_subgraph` boundary, distinct from a fan-out
   fork. The wrapper span's `note` resolves to the last instance's value
   (last-writer-wins) because both inner instances write the same key with distinct
   values. The fan-out NODE inside the wrapper (shared parent of the instances) and the
   invocation span (shared parent above the wrapper) MUST NOT carry the augmentation.

**Harness extensions:**

- `caller_metadata: {key: value, ...}` — same as fixtures 029 / 030 / 034; baseline at
  `invoke()`.
- `fan_out.augment_metadata_from_field: {<metadata_key>: <item_field>}` — same as fixture
  029; for each fan-out instance, harness internally calls the framework's augment-metadata
  helper with `{<metadata_key>: item.<item_field>}` before any LLM call in that instance's
  subgraph runs.
- `parallel_branches.branches.<name>.augment_metadata_from_outer_item: {<metadata_key>:
  <item_field>}` — case-2 extension; the per-branch primitive sources its value from the
  surrounding outer-fan-out item rather than from a static literal, so each outer-instance's
  augmenting branch writes a distinct value (avoiding ambiguity when asserting per-outer-
  instance dispatch spans). Equivalent to placing
  `set_invocation_metadata(note=outer_item["id"])` at the top of the probe branch's body
  inside an outer-instance's subgraph context.
- `nodes.<name>.subgraph_call: {subgraph: <name>, outputs: {...}}` — case-3 primitive that
  declares a serial subgraph wrapper (the outer graph descends into `wrapped_fan_out` via a
  `descend_into_subgraph` dispatch boundary). The wrapper subgraph contains the inner
  fan-out; the augmenter inside the fan-out has the wrapper span as a dispatch ancestor on
  its call-stack path.
- `invariants.outer_dispatch_span_carries_inner_augmentation: true` — case-1 invariant; the
  outer-instance dispatch span receives the augmentation that originated in the inner-
  instance's body.
- `invariants.outer_fan_out_instance_carries_branch_augmentation: true` — case-2 invariant;
  the outer fan-out instance's dispatch span receives the augmentation that originated in
  one of the parallel-branches branches.
- `invariants.serial_subgraph_wrapper_carries_inner_augmentation: true` — case-3 invariant;
  the wrapper span receives augmentations originating in the inner fan-out instances.
- `invariants.{outer_dispatch_spans_isolated, sibling_outer_instances_isolated,
  sibling_fan_out_instances_isolated, sibling_branch_isolated_from_probe_augmentation}:
  true` — sibling-boundary invariants per case.
- `invariants.{shared_parent_spans_not_augmented, fan_out_node_shared_parent_not_augmented,
  invocation_span_not_augmented}: true` — shared-parent-boundary invariants per case.

**What passes:**

- For each augmenting leaf, every dispatch ancestor on the leaf's call-stack path (every
  outer fan-out instance dispatch span, every outer parallel-branches branch dispatch span,
  every outer serial-subgraph wrapper span) carries the augmented metadata key alongside
  the baseline `tenantId` — in-place update via `update_observation` / `set_attribute` on
  the still-open ancestor span.
- Sibling dispatch contexts at every depth (other outer instances, other inner instances
  under the same outer, the sibling parallel-branches branch under the same outer, other
  fan-out instances inside the serial subgraph) carry only their own augmentations and the
  baseline — no cross-pollination.
- Shared-parent spans (fan-out NODE, parallel-branches NODE, invocation) carry only the
  baseline `tenantId` and no augmented metadata.

**What fails:**

- An outer-instance / outer-branch / wrapper dispatch span carries only the baseline and is
  missing the inner leaf's augmentation — implementation applied the augmentation only to
  the immediate dispatch context and did not walk the lineage. The lineage-aware rule
  requires walking every dispatch ancestor on the augmenter's call-stack path.
- A shared-parent span (fan-out NODE, parallel-branches NODE, invocation) carries an
  augmented metadata key — implementation walked past the fork point or pushed the
  augmentation up to the invocation. Shared parents are by definition visible to multiple
  siblings, and updating them would propagate augmentations across sibling boundaries
  indirectly.
- Sibling instances or sibling branches at any depth carry each other's augmentations —
  implementation didn't isolate the metadata mapping per dispatch context (e.g., used a
  single shared mapping reference instead of copy-on-write), OR walked across the sibling
  boundary when applying lineage updates.
- The lineage identifier is tracked as a single scalar (e.g., a lone `fan_out_index`
  ContextVar that gets overwritten at each nested descent) — implementation cannot identify
  the full ancestor chain at augmentation time, so deeper ancestors get missed or wrong
  ones get updated. The §3.4 *Per-depth lineage tracking* paragraph requires the chain to
  be stored as a list (one entry per dispatch depth).
- In case 3, the wrapper span lacks `note` but the fan-out NODE has it — the implementation
  inverted the boundary rule, treating the fan-out NODE (a shared parent) as the dispatch
  ancestor and skipping the actual wrapper.
