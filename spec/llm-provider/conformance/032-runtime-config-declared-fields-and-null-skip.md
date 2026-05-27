# 032 — RuntimeConfig Declared Fields and Null-Skip

Verifies the §6 surface refinements introduced by proposal 0032: three new declared fields
(`frequency_penalty`, `presence_penalty`, `stop_sequences`) reach the OpenAI wire body under the
expected keys, the §8.1 `stop_sequences` → `stop` rename happens at the wire layer, undeclared
keys land at the request-body root per §8.1's formalized convention, and unset declared fields
are omitted from the wire body per §6's null-skip contract.

**Spec sections exercised:**

- §6 RuntimeConfig declared-fields table — all seven declared fields are recognized at the API
  boundary.
- §6 extras-pass-through contract — `repetition_penalty=1.05` (undeclared) reaches the wire body
  untouched.
- §6 null-skip contract — declared fields with value `None` (unset) MUST be omitted from the
  wire body; MUST NOT appear as JSON `null`.
- §8.1 declared-field mapping — `frequency_penalty` / `presence_penalty` map directly;
  `stop_sequences` renames to OpenAI body field `stop`.
- §8.1 undeclared-field placement — undeclared keys appear at the request-body root.

**Cases:**

1. `all_declared_fields_plus_extra` — all seven declared fields set + one undeclared field
   (`repetition_penalty=1.05`). Verifies every declared field reaches the wire body under the
   right key, `stop_sequences` becomes `stop` on the wire (and `stop_sequences` is NOT present),
   and `repetition_penalty` lands at the request-body root.
2. `partial_config_null_skip` — only `temperature` and `max_tokens` set; the remaining five
   declared fields are unset (`None` / `undefined`). Verifies the wire body contains exactly the
   two declared fields the caller set; the five unset declared fields are absent (no `null`-valued
   entries), including both `stop` and `stop_sequences`.

**Harness extensions:**

- `expected_wire_request_checks.<key>_absent` — boolean assertion that the named key is not
  present in the outbound wire body. (Pattern already established by fixtures 027 / 029.)

**What passes:**

- Case 1: outbound wire body contains all seven declared-field values at the expected keys,
  `stop` instead of `stop_sequences`, and `repetition_penalty` at the root.
- Case 2: outbound wire body has only `temperature`, `max_tokens`, `model`, `messages`. No
  `top_p` / `seed` / `frequency_penalty` / `presence_penalty` / `stop` / `stop_sequences`
  appear.

**What fails:**

- Case 1: `stop_sequences` appears in the wire body (rename to `stop` not performed) — violates
  §8.1's declared rename.
- Case 1: `repetition_penalty` is missing or wrapped in a sub-object — violates §6
  extras-pass-through + §8.1 root-placement.
- Case 1: any declared field carries a different key on the wire (e.g., `frequency-penalty`
  with a hyphen) — violates §8.1's "maps directly" rule.
- Case 2: any unset declared field appears in the wire body, especially as `null` — violates
  §6's null-skip rule.
