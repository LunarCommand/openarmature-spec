# 003 — Invalid signal payload raises resume_payload_invalid

The merged state MUST validate against the state schema at resume
time. If it does not, the engine MUST raise
`suspension_resume_payload_invalid` and the resume invocation outcome
is errored (not completed).

**Spec sections exercised:**

- §6 — schema validation on merge.
- §9 — `suspension_resume_payload_invalid` error category.

**What passes:**

- Initial invoke returns suspended.
- Resume invoke with a type-incompatible payload (`count="not_an_int"`
  against an `int`-typed field) raises
  `suspension_resume_payload_invalid`.

**What fails:**

- Resume completes silently with garbage state — would mean schema
  validation was skipped on the signal_payload merge.
- A different error category surfaces — would mean the error is
  miscategorized (e.g., as `state_validation_error` rather than the
  more specific suspension category).
