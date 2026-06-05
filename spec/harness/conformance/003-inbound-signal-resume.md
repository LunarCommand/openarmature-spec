# 003 — Inbound signal-resume path (§3.3)

The harness receives a synthetic signal payload correlating to a
paused invocation and classifies it as the signal-resume inbound
path. The harness invokes
`invoke(resume_invocation=<id>, signal_payload=<payload>)`; the
engine reuses the suspended invocation_id per suspension §7 and
continues from the node after the suspending one.

**Spec sections exercised:**

- harness §3.3 — signal-resume inbound dispatch path
- harness §5.3 — suspended-outcome handling (signal subscription
  registered; harness does NOT block)
- harness §6 — signal-coordinator semantics (suspend-time
  subscription + signal-arrival lookup)
- suspension §3 + §5 + §7 — suspended outcome + reused invocation_id
  on resume

**What passes:**

- First transmission's invocation suspends; harness registers a
  signal subscription with the in-memory signal coordinator.
- Harness does NOT block after suspend (the second transmission can
  arrive and be handled).
- Second transmission classified as §3.3 signal-resume.
- Resume invocation threads signal_payload into the engine.
- Final state shows the merged payload (`approved=true`) plus the
  post-resume node's update (`completed_flag=true`).

**What fails:**

- Harness blocks after suspend — violates §5.3 step 4.
- Second transmission classified as §3.2 (existing-session) — would
  mean signal-arrival classification is broken.
- Resume invocation doesn't carry signal_payload — would mean
  threading from harness to engine broke.
