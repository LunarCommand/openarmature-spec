# 007 — Signal coordinator roundtrip (§6)

Full end-to-end exercise of the signal-coordinator contract: a node
suspends, the harness registers a subscription via the in-memory
signal coordinator, a synthetic external signal arrives, the
coordinator looks up the paused invocation by signal_id, and the
harness dispatches a resume invocation that completes the graph.

**Spec sections exercised:**

- harness §6 — signal coordinator (both suspend-time subscription
  registration AND signal-arrival lookup)
- harness §5.3 — suspended outcome handling (subscription register)
- harness §3.3 — signal-resume inbound dispatch
- harness §6 *complete* requirement — every suspended invocation
  has a mechanism by which its awaited signal can reach the
  signal-resume path

**What passes:**

- Initial invoke suspends; harness reads descriptor; subscription
  registered with signal_id "roundtrip-approval-001".
- Signal arrival matches the subscription's signal_id; coordinator
  resolves to the paused invocation_id.
- Resume invocation threads signal_payload; graph completes.
- Final state shows the merged payload + post-resume node update.

**What fails:**

- Signal arrival doesn't correlate to the paused invocation — would
  mean the signal coordinator's lookup logic is broken.
- Resume invocation receives wrong signal_payload — would mean
  threading from coordinator → harness → engine broke.
- Final state doesn't show both the payload merge AND the
  post-resume node — would mean the resume flow didn't complete the
  graph.
