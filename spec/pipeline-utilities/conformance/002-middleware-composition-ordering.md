# 002 — Middleware Composition Ordering

Verifies the §2 chain composition rule (outer-to-inner pre-phase, inner-to-outer post-phase) and
the dual-phase model (each middleware function runs both pre-node code and post-node code).

Three trace_recorder middleware [m1, m2, m3] wrap node `a`. Each appends a unique pre-marker
before calling `next` and a unique post-marker after `next` returns. The accumulated `trace`
shows the exact execution order.

The trace_recorder used here accepts `pre_marker` and `post_marker` config strings and emits a
partial update `{trace: [<marker>]}` from each phase, accumulated by the parent's `append`
reducer.

**Spec sections exercised:**

- §2 Middleware chain — outer-to-inner composition.
- §2 Pre-node and post-node phases — pre-phase fires in declaration order; post-phase fires in
  reverse.
- §3 Per-node middleware registration order.

**What passes:**

The final `trace` is exactly:

```
["m1.pre", "m2.pre", "m3.pre", "a", "m3.post", "m2.post", "m1.post"]
```

**What fails:**

- Reverse order (m3 outer, m1 inner) — registration order ignored or inverted.
- Post-phases firing in declaration order instead of reverse — incorrect dual-phase model.
- Any middleware running both phases before passing to the next (e.g., m1 fully completing before
  m2 starts) — fundamentally wrong shape.
