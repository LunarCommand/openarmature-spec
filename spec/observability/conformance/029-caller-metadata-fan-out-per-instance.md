# 029 — Caller-Metadata Mid-Invocation Augmentation (Fan-Out Per-Instance)

Verifies §3.4's mid-invocation augmentation + per-async-context scoping rules against the
canonical fan-out-with-per-item-id pattern. Three fan-out instances each augment the
in-scope metadata with a per-product `productId`; the per-instance augmentations MUST NOT
leak to sibling instances, AND the baseline caller metadata supplied at `invoke()` MUST
reach every instance's spans + observations.

**Spec sections exercised:**

- §3.4 — mid-invocation augmentation via the framework helper (e.g., Python
  `set_invocation_metadata`).
- §3.4 — per-async-context scoping: each fan-out instance receives its own copy of the
  metadata mapping at dispatch time; augmentations in one instance MUST NOT leak to siblings.
- §5.6 — `openarmature.user.*` cross-cutting attributes reflect the in-scope metadata at span
  emission time (so per-instance spans carry the per-instance augmentation).
- §8.4.1 — Langfuse `trace.metadata` carries only the baseline (the Trace closes after
  every instance, and no augmentation was applied to the parent context).
- §8.4.2 — Langfuse `observation.metadata` on each instance's observations carries the
  per-instance augmentation alongside the baseline.

**Cases:**

1. `fan_out_instances_augment_metadata_independently` — invocation passes
   `{tenantId: "acme-corp"}` as baseline; fan-out runs over three product items; each
   instance's body augments the metadata with `productId = <its product's id>` before
   making its LLM call. The harness asserts per-instance isolation and baseline ubiquity.

**Harness extensions:**

- `caller_metadata: {key: value, ...}` — same as fixtures 026 / 027; baseline at `invoke()`.
- `fan_out.augment_metadata_from_field: {<metadata_key>: <item_field>}` — harness
  primitive: for each fan-out instance, harness internally calls the framework's
  augment-metadata helper with `{<metadata_key>: item.<item_field>}` before any LLM call
  in that instance's subgraph runs. (Equivalent to placing
  `set_invocation_metadata(productId=item["id"])` at the top of the instance's body node;
  the harness primitive avoids requiring a real user-defined body function.)
- `invariants.fan_out_per_instance_metadata_isolation: true` — harness verifies no
  instance's observation metadata contains another instance's per-item-id value.
- `invariants.baseline_caller_metadata_universal: true` — harness verifies every span and
  observation carries the baseline (`tenantId`).

**What passes:**

- Each instance's observations carry both `tenantId` AND its own `productId`.
- No instance's observations carry a sibling instance's `productId`.
- The Trace's top-level `metadata` carries the baseline `tenantId` but NOT any
  `productId` (the augmentations were applied inside fan-out instances, in their separate
  per-async-context copies; they don't bubble back up to the parent invocation context).

**What fails:**

- Sibling instances see each other's `productId` — implementation didn't use a
  copy-on-write per-async-context primitive (Python `ContextVar`, TypeScript
  `AsyncLocalStorage`) for the metadata storage. Common miss: using a module-level dict or
  a process-global to store the metadata.
- The Trace's `metadata` ends up with one of the per-instance `productId` values (or
  all of them merged) — implementation applied per-instance augmentations to the parent
  context. Violates §3.4's per-async-context scoping rule.
- Some instances' observations are missing the baseline `tenantId` — implementation
  reset the metadata to only the augmentations within fan-out instances instead of
  additively merging. Violates §3.4's "additive merge" rule.
- The Langfuse observer applies augmentations only to spans emitted strictly after the
  helper call but does NOT update the already-open ancestor instance-subgraph span —
  acceptable per §5.6's SHOULD (not MUST), but lossy for the use case. Implementations
  SHOULD use `trace.update(metadata=...)` / `span.set_attribute(...)` to update open spans
  where the SDK supports it.
