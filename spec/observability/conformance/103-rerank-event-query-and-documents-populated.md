# 103 — `RerankEvent.query` and `.documents` populated

Verifies graph-engine §6's population contract for the rerank payload fields. `RerankEvent.query`
and `RerankEvent.documents` carry the call's inputs verbatim on the typed event (population is
unconditional; observer-side privacy gating per observability §5.5.4 is a rendering-boundary concern).

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent.query` / `.documents` populated unconditionally on every typed event.
- observability §5.5.4 / §5.5.14 — payload populated on the event; gated at the rendering boundary.

**Cases:**

1. `query_and_documents_carried_verbatim` — rerank call with a specific query + 3-document list. The
   `RerankEvent` carries `query` and `documents` matching the inputs.

**What passes:**

- `query` and `documents` carried verbatim on the typed event.

**What fails:**

- `query` or `documents` empty / null on the event when inputs were supplied — population contract
  broken (gating belongs at the rendering boundary, not the event population).
