# 053 — Cohere `/v2/embed`: Malformed `embedding_types` Extras Falls Back to `["float"]`

Verifies the general llm-provider §6 merge-arm **malformed** rule (proposal 0113), inherited by
retrieval-provider §10 / §8.4, on the concrete `embedding_types` instance. `embedding_types` is a
merge-managed wire field: a well-formed extras value merges with the mapping's mandatory `"float"` (fixture
039). This fixture pins the malformed edge 0099 / 0105 left open.

A **malformed** extras value — not a list, or a list carrying an element that is not of the expected element
type/shape (here, not a precision string) — is treated as **absent**: the wire request carries
`embedding_types: ["float"]` only (the mapping's mandatory value). It is **all-or-nothing** — a
partially-malformed list is **not** salvaged (the well-formed `"int8"` is not sent), because salvaging would
send a precision set the caller never wrote and the caller reads the effective set off the verbatim response
(§4 `raw`). No error is raised and no diagnostic is emitted — the request-side application of §7's treatment of
a malformed *ancillary* figure as not-reported. Malformation is **structural** (shape/type): a well-typed but
provider-unrecognized precision string is not malformed (out of scope here — it merges, and the provider
rejects it if unsupported).

**Spec sections exercised:**

- llm-provider §6 *Managed-field collision* — the merge arm's malformed-value rule (proposal 0113).
- retrieval-provider §8.4 (`embedding_types` merge) / §10 (inheritance of §6).
- §7 — the malformed-ancillary principle the rule applies to the request side.

**Cases:**

1. `partially_malformed_embedding_types_falls_back_to_float` — extras `embedding_types: ["int8", {"x": 1}]`
   (a list with a malformed object element) → wire `embedding_types: ["float"]` (the `"int8"` is **not**
   salvaged); no error.
2. `fully_malformed_embedding_types_falls_back_to_float` — extras `embedding_types: 5` (not a list) → wire
   `embedding_types: ["float"]`; no error.
3. `unrecognized_precision_strings_merge_rather_than_malform` — extras `embedding_types: ["banana", ""]`,
   both well-typed strings the provider does not recognize, one empty → wire
   `embedding_types: ["float", "banana", ""]`. The malformed test is **structural**, never a vocabulary
   check, so neither element is malformed and both merge. The empty string is included deliberately: it is
   the element an implementation reading the test as a vocabulary check is most likely to reject.

**What passes:**

- Cases 1 and 2: the wire request carries `embedding_types: ["float"]` only, the call succeeds, and vectors
  assemble from `embeddings.float` as usual.
- Case 3: the wire request carries the merged list in the mapping-value-first order, and the call succeeds.

**What fails:**

- The wire carries the malformed value, or a salvaged subset (`["float", "int8"]`), or drops `"float"`.
- The call raises on the malformed extras (it must fall back gracefully, not error).
- An implementation reads the element test as a **vocabulary** check and treats `"banana"` or `""` as
  malformed, sending `["float"]` in case 3. Proposal 0122 changed the spec's own wording from "not a
  precision string" to "not a string" because that wording invited exactly this reading, and case 3 is what
  pins the corrected rule.
