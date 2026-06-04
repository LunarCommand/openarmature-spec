# 007 — Suspend inside collect-mode fan-out is rejected

`suspend()` called inside a fan-out instance whose containing node is
configured with `error_policy="collect"` MUST raise
`suspension_in_unsupported_context`. The collect-mode contract aggregates
partial results across multiple concurrent instances; spec'ing the
multi-suspend aggregate-descriptor case is deferred to a future
proposal.

**Spec sections exercised:**

- §8.2 — collect + suspend incompatibility rule.
- §9 — `suspension_in_unsupported_context` error category (case b in
  the enumeration).

**What passes:**

- Invoke errors with `suspension_in_unsupported_context`.

**What fails:**

- Invoke returns suspended — would mean the collect-mode incompatibility
  was not enforced; the fan-out would silently lose the awaited-signal
  attribution.
- A different error category surfaces — would mean the
  collect-mode-rejected case is miscategorized.

**Notes:**

- Implementations SHOULD detect this at compile / registration time
  when feasible (the configuration is known statically); runtime
  detection is the spec-mandated minimum, which this fixture
  exercises.
