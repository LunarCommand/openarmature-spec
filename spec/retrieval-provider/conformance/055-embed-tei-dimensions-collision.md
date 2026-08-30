# 055 — TEI `dimensions` Declared-Field Collision (the same-name arm)

Verifies llm-provider §6 clause (b) on §8.1 TEI, where the declared
`EmbeddingRuntimeConfig.dimensions` is realized on the wire under the **same** name.

**Spec sections exercised:**

- **llm-provider §6** — *Managed-field collision*, clause (b).
- **retrieval-provider §8.1** — its managed-key enumeration, added by proposal 0122.
- **retrieval-provider §10** — the realization list, which names `dimensions` → `dimensions` for both §8.1
  and §8.3.

**Why 052 does not cover this.** A fixture is bound to one wire mapping by its `mapping:` key, and §6 clause
(b) is realized independently by each §8.x mapping. An implementation can wire the collision check into one
mapping's pre-send path and not another's. §10 named this realization for both §8.1 and §8.3, but before
proposal 0122 neither mapping carried the enumeration §6 requires, and only §8.3 had a fixture.

**Cases:**

1. `conflicting_extras_dimensions_rejected_pre_send` — declared `dimensions: 4` with extras `dimensions: 8`.
   Rejected pre-send with `provider_invalid_request`; no `/embed` request issued.
2. `matching_extras_dimensions_is_no_op` — declared `dimensions: 4` with extras `dimensions: 4`. A redundant
   no-op: the wire carries a single `dimensions: 4` and `prompt_name` stays absent, since `input_type` is
   unset and §8.1 keeps the body minimal.

**What passes:**

- Case 1 raises at pre-send validation with no wire request.
- Case 2 issues exactly one `/embed` request carrying `inputs` and a single `dimensions: 4`, with
  `prompt_name` absent, and assembles one vector from the bare array response.

**What fails:**

- The collision check exists only in the §8.3 mapping. Such an implementation passes fixture 052 and fails
  case 1 here, which is the whole reason this fixture is separate.
- A matching value is rejected rather than treated as a no-op, or `dimensions` is emitted twice.
- The mapping adds `prompt_name` to the body when `input_type` is unset, which case 2 catches through
  `expected_wire_request_absent_keys`.
