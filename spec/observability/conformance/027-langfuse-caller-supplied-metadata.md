# 027 — Langfuse Caller-Supplied Metadata Propagation

Verifies §8.4.1 + §8.4.2 Langfuse propagation of caller-supplied invocation metadata (per
§3.4). Entries are merged into the Langfuse Trace's `metadata` map AND into every
Observation's `metadata` map as top-level keys (sibling to existing OA-emitted keys like
`correlation_id`).

**Spec sections exercised:**

- §3.4 — caller-supplied invocation metadata accepted at invoke time.
- §8.4.1 — trace-level mapping: each entry `(key, value)` from caller metadata becomes
  `trace.metadata.<key>` at the top level.
- §8.4.2 — observation-level mapping: each entry becomes `observation.metadata.<key>` at the
  top level of every Observation (Span and Generation observations alike).
- §8.4 (Langfuse-Sessions distinction note): the propagation rules NOT promote keys to
  `trace.userId` / `trace.sessionId`; those are separately-spec'd surfaces (deferred to a
  future sessions capability).

**Cases:**

1. `caller_metadata_merges_to_langfuse_trace_and_observations` — invocation supplied with
   three metadata entries (`tenantId`, `seatCount`, `isCanary`); graph has two nodes and one
   LLM call; the harness asserts top-level merge on the Trace AND on all three Observations
   (two Span observations for the nodes, one Generation observation for the LLM call).

**Harness extensions:**

- `caller_metadata: {key: value, ...}` — same as fixture 026; configures the harness's
  `invoke()` call.
- `invariants.caller_metadata_top_level_on_trace: true` — harness asserts the entries appear
  at `trace.metadata.<key>` (not nested under `trace.metadata.user.<key>` or similar).
- `invariants.caller_metadata_top_level_on_every_observation: true` — harness asserts the
  entries appear at `observation.metadata.<key>` on every Observation in the tree.

**What passes:**

- `trace.metadata` carries the three caller entries at top level, alongside the OA-emitted
  `correlation_id`, `entry_node`, `spec_version`.
- Every Observation's `metadata` carries the three caller entries at top level, alongside the
  OA-emitted `correlation_id` and the per-observation OA fields (`namespace`, `step`, etc.).
- Value types are preserved (string / int / bool).

**What fails:**

- Caller entries are nested under a `metadata.user` sub-object — violates §8.4.1 / §8.4.2's
  top-level-keys requirement.
- Caller entries appear on the Trace but not on Observations — implementation missed §8.4.2's
  per-observation propagation rule (the rule is critical for detached subgraph / fan-out
  filtering per the rationale in §8.4.2).
- Caller entries promoted to `trace.userId` or `trace.sessionId` — violates §8.4's
  Langfuse-Sessions-distinction note (those fields are deferred).
- Value types coerced.
