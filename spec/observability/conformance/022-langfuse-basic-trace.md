# 022 — Langfuse Basic Trace

Smallest possible Langfuse trace: a linear three-node graph with default Langfuse-observer config
(no caller-supplied correlation ID, no caller-supplied invocation label, no detached subgraphs,
LLM-payload default). Verifies the fundamental Trace + Observation shape before nuances are tested
in 023-024.

Also documents the **Langfuse-mapping fixture format** — see the header comment in this fixture's
YAML.

**Spec sections exercised:**

- §1, §2 — Langfuse mapping is a sibling backend to OTel; same §6 event-stream substrate.
- §3 Cross-backend correlation ID — auto-generated UUIDv4 when caller doesn't supply one;
  §8.5 realization on Trace + Observation metadata.
- §8.3 Observation-type mapping — invocation → Trace (the container, no top-level Span);
  node spans → Span observations.
- §8.4.1 Trace-level mapping — `trace.id` from `invocation_id`, `trace.metadata.{correlation_id,
  entry_node, spec_version}`.
- §8.4.2 Observation-level mapping — `observation.name`, `metadata.{namespace, step,
  attempt_index, correlation_id}` on each Span observation.
- §8.6 Trace name — entry-node-name fallback when no caller-supplied invocation label.

**What passes:**

- Exactly one Trace emitted with id matching the framework's invocation_id (UUIDv4).
- Trace `name == "a"` (entry-node-name fallback per §8.6).
- Trace metadata carries `correlation_id` (auto-generated UUIDv4), `entry_node = "a"`,
  `spec_version` populated.
- Three Span observations emitted in execution order (a, b, c), each as a direct child of the
  Trace.
- Each Span observation has `name` matching the user's node name, `metadata.namespace = [<name>]`,
  `metadata.step` (0/1/2), `metadata.attempt_index = 0`, `metadata.correlation_id` matching the
  Trace's.
- All four entities (Trace + 3 Span observations) share the SAME `correlation_id` value.
- Trace `id` equals the framework's `invocation_id` (per §8.4.1's verbatim-reuse rule).

**What fails:**

- An extra top-level Span observation wrapping the three node observations (per §8.3, the
  invocation maps to the Trace container, NOT to an additional Span observation).
- Trace `name` is missing or differs from the entry-node name (no caller label supplied → must
  fall back to entry-node name per §8.6).
- `correlation_id` differs across the Trace and Observations (must be invocation-scoped per §8.5).
- `correlation_id` is missing on the Trace or on any Observation (must be cross-cutting per §8.5).
- Trace `id` differs from the framework's `invocation_id` (must be verbatim per §8.4.1).
- Span observation names are not the user's node names (e.g., `"openarmature.node"` constant —
  the Langfuse mapping uses the user's name for the same UI-readability reason §4.5 names it for
  OTel).
- `metadata.attempt_index` is missing or non-zero (no retry middleware in this fixture).
