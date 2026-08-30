# 054 — Cohere `output_dimension` Declared-Field Collision (the rename arm)

Verifies llm-provider §6 clause (b) on §8.4 Cohere, where the declared
`EmbeddingRuntimeConfig.dimensions` is realized on the wire under a **different** name,
`output_dimension`.

**Spec sections exercised:**

- **llm-provider §6** — *Managed-field collision*, clause (b): a wire field a mapping produces as the
  realization of a declared field is managed **only while the declared field is set**.
- **retrieval-provider §8.4** — its managed-key enumeration, corrected by proposal 0122 from two keys to
  three.
- **retrieval-provider §10** — the inheritance of §6 and the realization list, now marked illustrative with
  the per-mapping enumerations authoritative.

**Why 052 does not cover this.** Fixture 052 pins the **same-name** arm on §8.3 OpenAI, where the declared
`dimensions` is realized as a wire `dimensions`. A rename has a failure mode a same-name case cannot expose:
an implementation can realize the declared field correctly and still fail to recognize that the **renamed**
wire key is the one under management. A fixture is also bound to one wire mapping by its `mapping:` key, so
052 cannot reach §8.4 at all.

**Why cases 1 and 2 are a behavior change.** Before proposal 0122, §8.4 stated it managed exactly two wire
keys, `embedding_types` and `truncate`, and that every other undeclared extras key kept the untouched
pass-through. That contradicted §10, which already named `dimensions` → `output_dimension` as a §8.4
realization. Under §8.4's own wording an extras `output_dimension` rode untouched even while `dimensions` was
set. The enumeration is now three keys, so these cases pin new behavior and cannot inherit coverage.

**Cases:**

1. `conflicting_extras_output_dimension_rejected_pre_send` — declared `dimensions: 4` with extras
   `output_dimension: 8`. Rejected pre-send with `provider_invalid_request`; no request issued.
2. `matching_extras_output_dimension_is_no_op` — declared `dimensions: 4` with extras
   `output_dimension: 4`. A redundant no-op: the wire carries `output_dimension: 4` exactly once.
3. `extras_output_dimension_rides_untouched_when_declared_absent` — declared `dimensions` **absent**, extras
   `output_dimension: 8`. The mapping produces no `output_dimension` of its own, so the key is not managed on
   this call and the extras value rides untouched.

**What passes:**

- Case 1 raises at pre-send validation with no wire request.
- Cases 2 and 3 issue exactly one request carrying the expected single `output_dimension`, and vectors
  assemble from `embeddings.float`.

**What fails:**

- The mapping treats `output_dimension` as unmanaged while `dimensions` is set, forwarding the conflicting
  extras value or silently dropping one of the two. That is the pre-0122 behavior, and case 1 is what pins
  the correction.
- The mapping recognizes the collision only under the **declared** name `dimensions` and misses the renamed
  wire key. It would pass fixture 052 and fail case 1 here.
- The mapping over-applies the correction and reserves `output_dimension` unconditionally, rejecting or
  dropping it when `dimensions` is absent. It passes cases 1 and 2 and fails case 3, which is why case 3
  exists.
- A matching value is rejected rather than treated as a no-op, or the key is emitted twice.
