# 055 — TEI Declared-Field Collisions (the same-name and production-condition arms)

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
3. `conflicting_extras_prompt_name_rejected_when_produced` — the **production-condition** arm. §8.1 is the
   one retrieval mapping where "the declared field is set" and "the mapping emits the wire key" come apart,
   because `prompt_name` is produced only on the server-side-prompt path through the construction
   `input_type → prompt_name` map. With `input_type: query` set the mapping produces `prompt_name: "query"`,
   so a conflicting extras `prompt_name` is rejected pre-send.
4. `extras_prompt_name_rides_untouched_when_not_produced` — the same extras key with `input_type` absent. The
   mapping emits no `prompt_name`, so the key is not managed and the value rides untouched.

Cases 3 and 4 do **not** by themselves distinguish §6's production test from declared-field presence: this
fixture's provider block configures the prompt map, so the mapping produces `prompt_name` exactly when
`input_type` is set and the two readings coincide. Fixture **056** carries that distinction, on the
client-side-prefix path where they diverge. A provider block is fixture-level rather than per-case, which is
why it could not be a fifth case here.

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
