# 081 — Managed-Field Merge: Malformed Extras `stop` Treated as Absent

Verifies the general §6 *Managed-field collision* **merge-arm malformed rule** (proposal 0113) at its
llm-provider home. `stop` (the OpenAI wire realization of the declared `stop_sequences`, §6 clause (b)) is
list-shaped / merge-managed while `stop_sequences` is set (fixture 076): a well-formed extras `stop` merges
with the declared value(s). This fixture pins the malformed edge.

A **malformed** extras `stop` — a list with a non-string element, or a non-string / non-list value — is
treated as **absent**: the wire `stop` carries only the value the mapping would send with no such extra, i.e.
the declared `stop_sequences` (`["STOP"]`). It is **all-or-nothing** (the well-formed element of a
partially-malformed list is not salvaged), no error is raised, and no diagnostic is emitted (§7's
malformed-ancillary principle on the request side). Malformation is **structural**: a scalar *string* extras
`stop` is well-formed (coerced to a one-element list, fixture 076 case 3) — only a non-string element or
non-list value is malformed.

**Spec sections exercised:**

- llm-provider §6 *Managed-field collision* — the merge arm's malformed-value rule (proposal 0113), the
  general instance (the retrieval `embedding_types` instance is retrieval fixture 053).
- §7 — the malformed-ancillary principle the rule applies to the request side.

**Cases:**

1. `partially_malformed_extras_stop_treated_as_absent` — extras `stop: ["END", 123]` (list with a non-string
   element) → wire `stop: ["STOP"]` (the `"END"` is not salvaged); no error.
2. `fully_malformed_extras_stop_treated_as_absent` — extras `stop: 5` (not a string or list) → wire
   `stop: ["STOP"]`; no error.

**What passes:**

- The wire `stop` is the declared `["STOP"]` only, and the call succeeds.

**What fails:**

- The wire `stop` carries the malformed value, or a salvaged union (`["STOP", "END"]`).
- The call raises on the malformed extras (it must fall back gracefully).
