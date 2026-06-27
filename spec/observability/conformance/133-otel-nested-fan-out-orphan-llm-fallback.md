# 133 — OTel Nested Fan-Out Orphan LLM-Span Fallback

Verifies the **orphan fallback** in the §5.5 *Lineage-resolved parent* rule added by
[proposal 0084](../../../proposals/0084-nested-fan-out-span-lineage.md): when an LLM provider call is
issued with **no open calling-node span** (a middleware / wrapper call, not the node body) inside a
nested fan-out instance, its provider span parents under the nearest enclosing wrapper per §4.3 —
the correct *inner* fan-out instance span, resolved via the lineage chain — not the top-level fan-out
node / invocation span, and not a coincidentally-indexed sibling inner instance.

**Spec sections exercised:**

- §5.5 *Lineage-resolved parent* (orphan fallback) — the calling node's span is not open, so the
  provider span parents under the nearest enclosing wrapper span (here the inner fan-out instance
  span), chain-resolved to the correct inner instance; it MUST NOT parent under a shared fan-out
  node span or the invocation span when a more-specific enclosing wrapper is open.
- §4.3 — the enclosing-wrapper resolution the fallback reuses; the fan-out instance span is the
  nearest enclosing wrapper of the wrapper-issued call.
- §4.1 / §6 — the lineage chain that routes the orphan span to the correct inner instance when the
  innermost scalar `fan_out_index` coincides across the two inner instances.

## Orphan-call primitive (NEW)

Today's fixtures model provider calls only via a node's `calls_llm`, which always runs with the node
span open. The orphan case needs a call issued with the node span **not** open. This fixture defines:

```yaml
calls_llm_from_wrapper:
  phase: pre            # pre | post (default pre)
  messages: [ ... ]
```

The adapter wraps the node in a middleware that issues exactly one real `complete()` call against the
mock provider in the named phase:

- `pre` — before `next()`; the node's span is not yet open.
- `post` — after `next()` returns; the node's span has already closed.

Either way the calling node's span is **not open** when the provider span / `LlmCompletionEvent` is
emitted, exercising the §5.5 orphan fallback. The call's response is **not** written to state (it
models a wrapper-issued side call such as a guardrail or classifier). The node's own body still runs
inside `next()` — here a trivial `update: {marker: 1}` so the fan-out `collect_field` has a value.
This fixture uses `phase: pre`.

This primitive is reported for normative addition to conformance-adapter §5.1.

## Topology

Standard nested fan-out, two outer instances each with a single inner instance:

```
outer_fan_out  -- fan-out over outer_seeds = [[0], [0]], concurrent --> subgraph `mid`
  inner_fan_out -- fan-out over inner_seeds (1 int) --> subgraph `leaf_sg`
    guard       -- body: update marker=1; wrapper: orphan LLM call (pre-phase)
```

Each outer instance has exactly **one** inner instance, so both inner instances carry inner
`fan_out_index` 0. The chain is what distinguishes them:

| outer instance | inner instance | lineage chain | inner-instance span `fan_out_index` |
| -------------- | -------------- | ------------- | ----------------------------------- |
| 0              | 0              | `[0, 0]`      | `0`                                 |
| 1              | 0              | `[1, 0]`      | `0`                                 |

`concurrent_mode: concurrent` forces both outer instances in-flight together (the same directive
pipeline-utilities 076 uses for nested concurrent outer execution; first observability use, parsed by
the shared adapter).

## Parenting outcome

Each `guard` node issues its LLM call from the wrapper pre-phase, before its own node span opens. The
orphan `openarmature.llm.complete` span therefore:

- parents under its **inner fan-out instance span** (the nearest enclosing open wrapper), appearing
  as a **sibling** of the later-opened `guard` node span — not a child of `guard`;
- routes via the chain to the correct inner instance — outer 1's orphan span under `[1, 0]`, not
  outer 0's `[0, 0]` (which shares inner `fan_out_index` 0);
- never parents under the outer fan-out node span or the invocation span.

## Fixture-specific invariant predicates

Per conformance-adapter §5.9, documented here.

- `orphan_llm_span_parents_under_inner_fan_out_instance` — each orphan provider span's parent is the
  inner fan-out instance span, not the `guard` node span.
- `orphan_llm_span_not_under_coincidentally_indexed_sibling` — outer 1's orphan span parents under
  the `[1, 0]` inner instance, not the `[0, 0]` one (same innermost `fan_out_index`).
- `orphan_llm_span_not_under_fan_out_node_or_invocation` — neither orphan span parents under a
  fan-out NODE span or the invocation span.
- `orphan_llm_span_sibling_of_calling_node_span` — each orphan span is a sibling of its `guard` node
  span under the inner instance span, not its child.
- `llm_provider_span_count` — exactly two orphan provider spans.

**What passes:**

- Two `openarmature.llm.complete` spans, each a child of the inner fan-out instance span in its own
  lineage and a sibling of that instance's `guard` node span.

**What fails:**

- An orphan span parents under the top-level outer fan-out node span or the invocation span (the
  pre-0084 top-level shortcut), losing inner-instance attribution.
- Outer 1's orphan span parents under outer 0's inner instance (coincident innermost
  `fan_out_index`) — the mis-parent the chain prevents.
- An orphan span parents under the `guard` node span (treating it as a normal in-body call), which is
  not open when the pre-phase call fires.
