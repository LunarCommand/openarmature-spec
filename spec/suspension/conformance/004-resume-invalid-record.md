# 004 — Resume for invalid invocation_id raises record_invalid

Resume requested for an `invocation_id` that is not in `suspended`
status (completed, errored, never-existed, or already-resumed) MUST
raise `suspension_record_invalid`.

**Spec sections exercised:**

- §7 — resume API validates loaded record status before merging
  payload.
- §9 — `suspension_record_invalid` error category covers the
  not-suspended cases enumerated in §7 step 2.

**What passes:**

- Case 1: resume against a completed invocation's id raises
  `suspension_record_invalid`.
- Case 2: resume against a fabricated id (no backing record) raises
  `suspension_record_invalid`.

**What fails:**

- A different error category surfaces — would mean the not-suspended
  case is miscategorized.
- The resume silently succeeds — would mean the status check at §7
  step 2 was skipped.
