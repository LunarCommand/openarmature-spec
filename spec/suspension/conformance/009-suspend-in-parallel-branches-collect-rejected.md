# 009 — Suspend inside collect-mode parallel-branches is rejected

Peer to fixture 007 (fan-out collect rejected). `suspend()` called
inside a parallel-branches branch whose containing node is configured
with `error_policy="collect"` MUST raise
`suspension_in_unsupported_context`.

**Spec sections exercised:**

- §8.3 — collect + suspend incompatibility for parallel-branches.
- §9 — `suspension_in_unsupported_context` error category (case b in
  the enumeration).

**What passes:**

- Invoke errors with `suspension_in_unsupported_context`.

**What fails:**

- Invoke returns suspended — would mean the collect-mode
  incompatibility was not enforced for parallel-branches.
- A different error category surfaces — would mean the rejected case
  is miscategorized.
