# 076 — managed-field collision, clause (b): extras `stop` merges with the declared `stop_sequences`

Pins the **merge arm** of llm-provider §6 clause (b) (proposal 0108) on a declared-field realization whose
**wire name differs from the declared name** — OpenAI's `stop`, the realization of the declared `stop_sequences`.
Because `stop` is **list-shaped / additive**, a colliding extras `stop` (the wire name) merges with the declared
value(s) rather than being rejected: declared value(s) first, de-duplicated first-occurrence-wins. OpenAI's
`stop` accepts string-or-array, so a scalar-string extras value is coerced to a one-element list before the merge.

The merged lists here stay under OpenAI's four-sequence cap, so every case sends the request and asserts the wire
`stop`. (An over-cap merged list is not clamped client-side — it is sent and the provider's rejection surfaces
`provider_invalid_request`, the §8 fail-loud posture.)

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* clause (b), merge arm: an additive/list-shaped declared-field
  realization merges the caller's value(s) with the declared value(s), mapping-first, de-duplicated.
- llm-provider §8.1 — `stop_sequences` is realized as the wire key `stop` (the OpenAI rename); the colliding
  extras key is the **wire** name `stop`; scalar-string coercion; over-cap sent fail-loud.

**Cases:**

1. `extras_stop_merges_with_declared_stop_sequences` — `stop_sequences: ["STOP"]` + extras `stop: ["END"]` → wire
   `stop: ["STOP", "END"]` (the union, declared first).
2. `matching_extras_stop_collapses_dedup` — `stop_sequences: ["STOP"]` + extras `stop: ["STOP"]` → wire `stop:
   ["STOP"]` (de-duplicated to one element).
3. `scalar_string_extras_stop_coerced_then_merged` — `stop_sequences: ["STOP"]` + extras `stop: "END"` (scalar
   string) → coerced to `["END"]`, merged → wire `stop: ["STOP", "END"]`.

**What fails:**

- Rejecting the merge (treating `stop` as non-additive), letting the extras value win outright, dropping the
  declared value, emitting a duplicated list on the matching case, or failing to coerce the scalar-string form.
