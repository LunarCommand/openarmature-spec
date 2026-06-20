# 012 — Per-result document-echo variance preserved

Verifies retrieval-provider §6's document-echo cross-impl invariant. When a provider echoes
`document` text for some results but not others, the adapter MUST preserve the per-result variance
(populated where the provider echoed, null where it omitted) and MUST NOT auto-fill the missing echo
from the input `documents` list — conflating the provider's echo with the caller's input would mask
provider-side document transformations (deduplication, truncation).

**Spec sections exercised:**

- retrieval-provider §6 — `ScoredDocument.document` echo invariant; implementations MUST surface the
  provider's echo verbatim when present, MUST NOT fabricate it when the provider omits it.

**Cases:**

1. `rerank_preserves_per_result_echo_variance` — `return_documents=True` over 3 documents; mocked
   response echoes `document` for indices 0 and 2 but omits it for index 1. The adapter MUST return
   `document` populated for the two echoed results and `null` for the omitted one.

**What passes:**

- Echoed `document` values preserved verbatim; the omitted one surfaced as `null`.

**What fails:**

- The omitted `document` is auto-filled from the input `documents` list (`documents[1]`) — masking
  the provider's omission.
- An echoed `document` is dropped or altered.
