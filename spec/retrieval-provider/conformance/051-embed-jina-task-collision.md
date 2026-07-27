# 051 — Jina `task` collision: managed while `input_type` is set, escape hatch when absent

Pins the load-bearing retrieval case of proposal 0108 — Jina's `task`, the wire realization of the declared
`input_type` (§8.2). Under the extended §6 *Managed-field collision* clause (b) (inherited via §10), a wire key
realizing a declared field is managed **while the mapping is producing it**:

- While `input_type` is **set**, the mapping produces `task`, so `task` is managed non-additive — a conflicting
  extras `task` is rejected pre-send.
- While `input_type` is **absent**, the mapping produces no `task`, so an extras `task` is unmanaged and rides
  the extras bag untouched onto the wire. This is the escape hatch that carries a model-specific `task` value
  (e.g. Jina's `text-matching`) the closed `input_type` set does not model — reconciling 0099's §8.2 note.

**Spec sections exercised:**

- llm-provider §6 clause (b) (inherited by retrieval §10) — a wire key realizing a declared field is managed
  while produced; conflicting reject, and unmanaged (untouched) when the declared field is absent.
- retrieval-provider §8.2 — the `input_type` → `task` realization; the absent-`input_type` escape hatch.
- retrieval-provider §7 — `provider_invalid_request` at pre-send validation, no request issued.

**Cases:**

1. `conflicting_extras_task_with_input_type_rejected_pre_send` — `embed(config={input_type: "query", extras:
   {task: "text-matching"}})`. The realized `task` is `retrieval.query`; the extras `text-matching` conflicts →
   `provider_invalid_request` pre-send, **no** `/v1/embeddings` request issued.
2. `extras_task_without_input_type_rides_untouched` — `embed(config={extras: {task: "text-matching"}})` with no
   `input_type` → the mapping emits no managed `task`, so the extras `task: "text-matching"` rides untouched onto
   the wire (the escape hatch).

**What fails:**

- Rejecting or dropping the escape-hatch `task` when `input_type` is absent (regressing the 0099 pattern), or
  forwarding/letting-win a conflicting `task` when `input_type` is set (the silent double-set), or issuing a
  request on the reject case.
