# 075 — managed-field collision, clause (b): extras `temperature` vs the declared sampling field

Pins the **declared-field-realization** arm (llm-provider §6 clause (b), proposal 0108) on a **non-additive
scalar** — the OpenAI `temperature` sampling field. A declared `RuntimeConfig` field is realized on the wire
under its own name, and while the caller sets it the wire key is **managed**: a matching extras value is a
redundant no-op, a conflicting one is rejected pre-send. This closes the silent double-set where an extras
`temperature` would override the declared one.

`temperature` is the representative case; `top_p` / `max_tokens` / `seed` (and retrieval `dimensions`) share the
scalar mechanic.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* clause (b): a wire key realizing a declared field is managed while
  produced; the reject arm (non-additive) rejects a conflicting extras value pre-send, the matching arm is a no-op.
- llm-provider §8.1 — the declared sampling fields (`temperature` / `top_p` / `max_tokens` / `seed` /
  `frequency_penalty` / `presence_penalty`) are managed non-additive realizations while the caller sets them.
- llm-provider §7 — `provider_invalid_request` raised at pre-send validation, no request issued.

**Cases:**

1. `extras_temperature_conflicts_with_declared_rejected_pre_send` — `complete(config={temperature: 0.7, extras:
   {temperature: 0.2}})`. The extras `temperature` conflicts with the declared `0.7`; the mapping raises
   `provider_invalid_request` pre-send, issues **no** request, and neither drops nor forwards the value.
2. `extras_temperature_matching_declared_is_no_op` — `complete(config={temperature: 0.7, extras: {temperature:
   0.7}})`. The extras equals the declared value: a redundant no-op; the wire carries `temperature: 0.7` once and
   the call proceeds.

**What fails:**

- Letting a conflicting extras `temperature` override the declared value (silent double-set), silently dropping
  it, forwarding it untouched, or issuing any request on the conflict case (the rejection is pre-send).
