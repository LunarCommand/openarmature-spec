# 157 — Langfuse Provider Isolation

Gates the two observability §6 provider-isolation MUSTs proposal 0114 shipped (made testable by proposal
0115), using the global-provider leak-capture pattern of fixture 005 extended to Langfuse observations. A
Langfuse v4 client emits its observations as OTel spans through its bound `TracerProvider`, so an exporter
on the global provider (installed by `caller_global_otel_active`) catches any that leak. The Langfuse
client is the provider-faithful fake of conformance-adapter §6.4 — it records observation content (for the
non-vacuity assertion) and emits through its bound provider (for the leak assertion).

**Spec sections exercised:**

- §6 mode-(b) payload-leak invariant (isolate-by-default) — when the implementation constructs the Langfuse
  client (owns the provider), the Langfuse observer emits payloads (`disable_provider_payload: false`), and
  openarmature constructs first, its isolated `TracerProvider` takes effect; its observations MUST NOT reach
  the caller's global provider. (Proposal 0116 generalizes the trigger to any payloads-would-reach-a-shared-
  provider configuration and adds the raise/suppress arms for when isolation is defeated; fixture 158 gates
  those.)
- §6 mode-(a) MUST-NOT-mutate — when the caller supplies the client (owns the provider), the
  implementation MUST NOT rebind it; the supplied client's observations continue to reach the caller's
  provider — the observable proof of non-mutation.

**Cases:**

- `mode_b_carveout_isolates` *(detection-capable adapters)* — credentials-in, openarmature constructs first
  (`preexisting_same_key_client: false`); asserts the Generation observation was recorded with its payload
  (non-vacuity) **and** that none leaked to the global provider (`no_langfuse_observations_on_global`). Gated
  on `langfuse_bound_provider_detection` because the payload-present outcome requires the implementation to
  confirm isolation took effect; a non-detection-capable adapter suppresses its payload here per §6 (its
  suppress-floor behavior is gated by fixture 158 `singleton_preexists_suppresses`).
- `mode_a_supplied_not_mutated` — a caller-supplied client bound to the global provider; asserts its
  observation reached the global provider (`langfuse_observations_on_global`) — the implementation left the
  supplied client's provider alone.
