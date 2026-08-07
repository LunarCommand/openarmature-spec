# 157 — Langfuse Provider Isolation

Gates the two observability §6 provider-isolation MUSTs proposal 0114 shipped (made testable by proposal
0115), using the global-provider leak-capture pattern of fixture 005 extended to Langfuse observations. A
Langfuse v4 client emits its observations as OTel spans through its bound `TracerProvider`, so an exporter
on the global provider (installed by `caller_global_otel_active`) catches any that leak. The Langfuse
client is the provider-faithful fake of conformance-adapter §6.4 — it records observation content (for the
non-vacuity assertion) and emits through its bound provider (for the leak assertion).

**Spec sections exercised:**

- §6 mode-(b) MUST-isolate carve-out — when the implementation constructs the Langfuse client (owns the
  provider) and a composed OTel observer suppresses provider payload (its §5.5.4 default `True`) while the
  Langfuse observer emits it (`disable_provider_payload: false`), the implementation MUST build the client
  on an isolated `TracerProvider`; its observations MUST NOT reach the caller's global provider.
- §6 mode-(a) MUST-NOT-mutate — when the caller supplies the client (owns the provider), the
  implementation MUST NOT rebind it; the supplied client's observations continue to reach the caller's
  provider — the observable proof of non-mutation.

**Cases:**

- `mode_b_carveout_isolates` — credentials-in under the carve-out config; asserts the Generation
  observation was recorded (non-vacuity) **and** that none leaked to the global provider
  (`no_langfuse_observations_on_global`).
- `mode_a_supplied_not_mutated` — a caller-supplied client bound to the global provider; asserts its
  observation reached the global provider (`langfuse_observations_on_global`) — the implementation left the
  supplied client's provider alone.
