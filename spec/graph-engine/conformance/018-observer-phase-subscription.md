# 018 — Observer Phase Subscription

Verifies the §6 per-observer phase-subscription filter added by proposal 0005. Three observers
register with different `phases` parameters; the engine MUST filter delivery so each receives
only events matching its subscription.

**Spec sections exercised:**

- §6 Registration `phases` parameter — default is both phases; `{"completed"}` and `{"started"}`
  are individually accepted.
- §6 phase filter applies at delivery — engine checks each observer's subscription before
  delivering.
- §6 empty phases set is a configuration error — implementations SHOULD raise at registration
  time.

**What passes:**

- `obs_both` (default — both phases) receives 6 events (3 nodes × 2 phases).
- `obs_completed` (`phases: [completed]`) receives 3 events, all `phase: "completed"`.
- `obs_started` (`phases: [started]`) receives 3 events, all `phase: "started"`.
- Empty phases set raises an error at registration time.

**What fails:**

- `obs_completed` receives `started` events (filter not honored).
- `obs_started` receives `completed` events (filter not honored).
- `obs_both` doesn't receive both phases (default subscription wrong).
- Empty phases registration is silently accepted instead of raising.
- Observers with different subscriptions receive duplicate copies of the same event (filtering
  applied incorrectly across observers).

## Note on the harness

The harness's `phases` parameter parsing is implementation-defined — YAML lists, sets, or
language-native sets are all acceptable as long as the resulting subscription matches the
behavioral contract. The phase strings are case-sensitive: `"started"` and `"completed"` are the
only valid values; any other string MUST cause a registration-time error.
