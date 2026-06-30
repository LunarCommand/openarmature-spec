# 036 — Cohere `/v2/embed` `truncate: "NONE"` fail-loud

Verifies the retrieval-provider §8.4 Cohere embedding mapping's *fail-loud* contract: the mapping sends
`truncate: "NONE"` explicitly, so an over-length input makes Cohere **error** (HTTP 400) rather than
silently truncating. The Cohere error MUST map to `provider_invalid_request` (§7); the adapter MUST raise
that category, not return a silently truncated vector. This is the point where §8.4's embed half diverges
from its rerank half — `/v2/rerank` has no fail-loud option (Cohere truncates rerank documents server-side
to `max_tokens_per_doc`), but `/v2/embed` exposes `truncate`, and the mapping picks `"NONE"` (the §8.2 Jina
embed posture). The embed analogue of the TEI / Jina rerank fail-loud fixtures 016 / 021.

**Spec sections exercised:**

- retrieval-provider §7 — `provider_invalid_request` for a malformed / over-length request; the
  exception-flow contract (the category exception raises out of `embed()`).
- retrieval-provider §8.4 Cohere — *`output_dimension` / `embedding_types` / `truncate` (fail-loud)*: the
  mapping sends `truncate: "NONE"` so an over-length input errors. *Errors*: `400` →
  `provider_invalid_request` (Cohere uses `400`, not the `422` Jina §8.2 returns).

**Cases:**

1. `over_length_400_maps_to_provider_invalid_request` — an input exceeds the model's context. Because the
   mapping sends `truncate: "NONE"`, Cohere returns HTTP 400. The adapter MUST classify it as
   `provider_invalid_request` and raise out of the embed node — not return a truncated vector. The wire
   request still carries `truncate: "NONE"`, `input_type: "search_document"` (the mandatory default),
   `embedding_types: ["float"]`, and the `Authorization: Bearer` header.

**What passes:**

- `provider_invalid_request` raised out of the embed node on the HTTP 400.
- The wire request carried `truncate: "NONE"` (the fail-loud directive) and `embedding_types: ["float"]`;
  the `Authorization: Bearer` header present.

**What fails:**

- The over-length input yields a (silently truncated) vector instead of an error.
- The error is misclassified (e.g. `provider_unavailable`) instead of `provider_invalid_request`.
- The wire request omits `truncate: "NONE"` or sends a different truncate value (which would let Cohere
  truncate server-side rather than fail loud).
