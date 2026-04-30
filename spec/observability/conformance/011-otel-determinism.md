# 011 — Determinism Over Span Content

Verifies §8 determinism. The graph-engine §5 determinism guarantee covers the §6 event stream
(same input → same events → same payloads, in the same order). The OTel mapping is a function
of that event stream plus implementation-specific data (IDs, timestamps). The conformance
suite asserts determinism over the *deterministic* portion of span content only — hierarchy,
names, attributes (excluding timing-derived), and status — not over inherently nondeterministic
data like `trace_id`, `span_id`, or timestamps.

**Spec sections exercised:**

- §8 Determinism — span hierarchy, names, attributes (minus timing), and status are reproducible.
- §8 Carve-outs — `trace_id`, `span_id`, `invocation_id`, auto-generated `correlation_id`, and
  any `openarmature.timing.*` attributes are NOT covered by determinism.

**Cases:**

1. `same_input_same_deterministic_span_content` — same graph and initial state, run twice.
   The two runs' span trees match structurally with the documented carve-outs ignored.

**What passes:**

- Run 1 and run 2 produce identical hierarchies (same parent-child relationships).
- Span names match across runs.
- Span status (OK / ERROR / UNSET) matches across runs.
- Non-ignored attributes match across runs (e.g., `openarmature.node.name`,
  `openarmature.node.attempt_index`, `openarmature.error.category`).
- The conditional branch fires the same way in both runs (deterministic execution path).

**What fails:**

- Different hierarchy across runs — e.g., a node span appears under a different parent on
  one run, indicating a race or non-deterministic dispatch.
- Different span names or count — e.g., one run produced an extra retry attempt span,
  indicating non-deterministic failure injection.
- Status mismatch — e.g., one run had OK and the other ERROR.
- A user-facing attribute (excluding the documented carve-outs) varies across runs — the
  underlying §6 event payloads aren't actually deterministic, violating graph-engine §5.
