# 101 — `RerankEvent` / `RerankFailedEvent` mutual exclusion

Verifies graph-engine §6's mutual-exclusion rule for the rerank typed-event pair. A given `rerank()`
call emits exactly one of the two variants, never both.

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent` and `RerankFailedEvent` are mutually exclusive on a given
  `rerank()` call; implementations MUST NOT emit both.

**Cases:**

1. `success_emits_only_rerank_event` — one successful call; exactly one `RerankEvent`, zero
   `RerankFailedEvent`.
2. `failure_emits_only_rerank_failed_event` — one failed call (`provider_unavailable`); exactly one
   `RerankFailedEvent`, zero `RerankEvent`.

**What passes:**

- The success path produces only the success event; the failure path produces only the failure event.

**What fails:**

- Both variants observed for one call — mutual-exclusion violation.
- The wrong variant is emitted for the outcome.
