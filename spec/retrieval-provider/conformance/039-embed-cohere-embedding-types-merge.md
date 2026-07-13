# 039 — Cohere `/v2/embed` extras-supplied `embedding_types` merged with the managed `"float"`

Verifies the retrieval-provider §8.4 Cohere embedding mapping's `embedding_types` **merge** rule. Two
things want the same wire key: the mapping *manages* `embedding_types`, sending `["float"]` explicitly so
the type-keyed response is guaranteed to carry the `embeddings.float` key its own response consumer reads
(fixture 032); and the caller's other precisions (`int8` / `uint8` / `binary` / `ubinary` / `base64`) ride
the extras-pass-through bag. §8.4 pins the collision: the extras value is **merged** with `"float"`, never
substituted for it.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config*: the extras-pass-through bag for vendor-specific knobs
  (undeclared keys only).
- retrieval-provider §4 — `EmbeddingResponse.vectors` assembled from the consumed precision, in input
  order; `EmbeddingResponse.raw` carries the verbatim provider response (where the caller reads the extra
  precisions back).
- retrieval-provider §8.4 Cohere — *`output_dimension` / `embedding_types` / `truncate`*:
  `embedding_types` is a managed wire field, so an extras-supplied value MUST be **merged** with the
  mapping's mandatory `"float"`, never replace it. A mapping MUST NOT let an extras-supplied
  `embedding_types` drop `"float"` — doing so strips the `embeddings.float` key the mapping reads, failing
  the call `provider_invalid_response` (§7).

**Cases:**

1. `extras_embedding_types_merged_with_managed_float` — `embed(config={extras: {embedding_types:
   ["int8"]}})`. The wire request MUST carry `embedding_types: ["float", "int8"]` — not `["int8"]` (which
   strips the key the mapping reads) and not `["float"]` (which silently discards the caller's knob). The
   response is keyed by both types; `EmbeddingResponse.vectors` MUST still come from `embeddings.float`,
   and the `int8` block survives verbatim on `EmbeddingResponse.raw`.
2. `extras_embedding_types_multiple_precisions_merged` — `embed(config={extras: {embedding_types: ["int8",
   "uint8"]}})` over two inputs. The wire request MUST carry `embedding_types: ["float", "int8", "uint8"]`
   — the managed `"float"` plus *both* caller precisions, proving the merge is a general union rather than
   a two-element special case. Vectors still come from `embeddings.float` in input order; both extra
   precisions survive verbatim on `raw`.
3. `extras_embedding_types_naming_float_is_deduplicated` — the caller names `"float"` **explicitly**
   alongside a precision (`{extras: {embedding_types: ["float", "int8"]}}`). The merge is
   **de-duplicating**: the wire carries `["float", "int8"]` — `"float"` appears **once**, not twice. Pins
   the dedupe half of §8.4's merge rule; a naive concatenation would emit `["float", "float", "int8"]`.
   The managed `"float"` and the caller's `"float"` are the same request, not two.

**Merged-list ordering:** §8.4 pins it **normatively** — the managed `"float"` first, then the caller's
precisions in the order supplied, de-duplicated. The wire is order-insensitive here, so the ordering
carries no semantics; it is fixed purely so the outbound request is **deterministic** and therefore
decidable by an exact `expected_wire_request` assertion. Without a pinned order, an implementation emitting
`["int8", "float"]` would satisfy the merge rule yet fail this fixture — the fixture would be demanding
more than the spec requires.

**What passes:**

- The outbound `embedding_types` contains `"float"` **and** every caller-supplied precision.
- `EmbeddingResponse.vectors` is assembled from `embeddings.float` in input order; the extra precision keys
  are neither consumed nor treated as an error.
- The extra precision blocks are preserved verbatim on `EmbeddingResponse.raw`.
- `input_type: "search_document"` (the mandatory-field default — no OA `input_type` supplied),
  `truncate: "NONE"`, and the `Authorization: Bearer <api_key>` header on every request.

**What fails:**

- The extras value **replaces** the managed value (`embedding_types: ["int8"]` on the wire) — `"float"` is
  dropped, the response carries no `embeddings.float`, and the mapping's own response consumer breaks.
- The extras value is **ignored** (`embedding_types: ["float"]` on the wire) — the caller's knob silently
  discarded.
- Only the first extras precision survives the merge in the multi-precision case.
- The mapping reads vectors from an extra precision key instead of `embeddings.float`, or errors on the
  presence of the extra keys.
- The extra precision blocks are stripped from `raw`.
