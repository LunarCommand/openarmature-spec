# 001 — OTel Basic Trace

Smallest possible OTel trace: a linear three-node graph with default observer config (no
caller-supplied correlation ID, no detached subgraphs, no disabled LLM spans). Verifies the
fundamental span shape before nuances are tested in 002-011.

Also documents the **conformance fixture format** for the `observability` capability — see the
header comment in this fixture's YAML.

**Spec sections exercised:**

- §1 Purpose, §2 Concepts — span / trace / correlation_id basics.
- §3 Cross-backend correlation ID — auto-generated UUIDv4 when caller doesn't supply one.
- §4 Span hierarchy — invocation → node spans, in execution order.
- §4.1 Span timing — opening at `started`, closing at `completed`.
- §4.2 Status mapping — `OK` for successful nodes.
- §4.5 Span names — node spans use the node's registered name.
- §5.1 / §5.2 / §5.6 — invocation/node attributes; cross-cutting `correlation_id` on every span.

**What passes:**

- Four spans emitted: one invocation span, three node spans (`a`, `b`, `c`) in execution order.
- Invocation span has `openarmature.invocation_id` (UUIDv4), `openarmature.correlation_id`
  (auto-generated UUIDv4), `openarmature.graph.entry_node == "a"`,
  `openarmature.graph.spec_version` populated.
- Each node span has `openarmature.node.name`, `openarmature.node.namespace == [<name>]`,
  `openarmature.node.step` (0/1/2), `openarmature.node.attempt_index == 0`.
- All four spans share the SAME `openarmature.correlation_id` value (the framework's
  auto-generated UUIDv4).
- All spans have status `OK`.
- Span names are the user's node names (`"a"`, `"b"`, `"c"`).

**What fails:**

- `correlation_id` differs across spans (must be invocation-scoped, not per-span).
- `correlation_id` is missing on a span (must be cross-cutting per §5.6).
- `invocation_id` is not a UUIDv4 (per §5.1 MUST UUIDv4).
- Node span names are not the user's node names (e.g., `"openarmature.node"` constant — that's
  rejected per §4.5).
- `attempt_index` is missing or non-zero (no retry middleware in this fixture).
