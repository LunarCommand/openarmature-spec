# 003 — Per-Graph vs Per-Node Composition

Verifies the §3 composition rule: per-graph middleware MUST wrap outside per-node middleware.

Two per-graph and two per-node trace_recorders combine to produce a 9-marker trace with the exact
nesting:

```
pg1.pre → pg2.pre → pn1.pre → pn2.pre → a → pn2.post → pn1.post → pg2.post → pg1.post
```

This is the rule the spec gives in §3: "per-graph middleware is more general (timing, logging)
and should observe the *full* elapsed time including retries; per-node middleware is more specific
and should run closest to the node it knows about." Putting per-graph timing/logging on the
outside is the basis for that operational decision.

**Spec sections exercised:**

- §3 Per-graph and per-node registration.
- §3 Composition: `[per_graph_outer_to_inner...] → [per_node_outer_to_inner...] → node`.

**What passes:**

The final `trace` is the 9-element sequence above.

**What fails:**

- Per-node wrapping per-graph (reversed nesting) — composition rule inverted.
- Per-graph and per-node interleaved instead of strictly nested — wrong contract.
