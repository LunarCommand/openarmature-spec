# 074 — managed-field collision, reject arm: extras `model` vs the bound model (structural field)

Pins the **managed structural wire-field** arm of llm-provider §6 *Managed-field collision* on the OpenAI
mapping. §8.1 sets several request-body-root fields for its own correctness that a caller does **not** supply
as declared `RuntimeConfig` fields — `model` (the bound identifier), `messages` / `tools` (the `complete()`
arguments), `tool_choice` (the §5 parameter) — so an undeclared extras key of the same name collides with them
at the root (the OpenAI-SDK `extra_body`-style root merge §8.1 codifies would let the caller's value silently
win). Each is a managed non-additive field: a conflicting extras value is rejected pre-send.

This fixture exercises the mechanic on the clearest single-value case, `model` — the "silent re-route to a
different model" failure. `messages` / `tools` / `tool_choice` share the same managed-internal-wire-root reject
mechanic.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* (reject arm): a conflicting extras value on a managed field is
  rejected pre-send `provider_invalid_request`, never dropped or forwarded.
- llm-provider §8.1 — `model` is a managed structural field (set from the §3 / §5 per-instance binding); the
  managed structural set is `model` / `messages` / `tools` / `tool_choice`.
- llm-provider §7 — `provider_invalid_request` raised at pre-send validation, no request issued.

**Case:**

1. `extras_model_conflicts_with_bound_model_rejected_pre_send` — `complete(config={extras: {model:
   "other-model"}})`. The extras `model` collides with the bound `test-model`; honoring it would silently
   re-route the call. The mapping raises `provider_invalid_request` pre-send, issues **no** request, and
   neither drops nor forwards the value.

**What fails:**

- Forwarding a conflicting extras `model` onto the wire (silently re-routing the call), or silently dropping
  it, or issuing any request (the rejection is pre-send).

**Not managed here:** the `stop` wire field realizes the *declared* `stop_sequences` — a
declared-field-vs-extras question deferred with the residual per-mapping audit (`docs/open-questions.md`), not
the managed-internal structural rule.
