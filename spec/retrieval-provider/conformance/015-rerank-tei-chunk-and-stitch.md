# 015 — TEI `/rerank` mandatory chunk-and-stitch (load-bearing)

The load-bearing fixture for the retrieval-provider §8.1 rerank contract. Verifies *Mandatory rerank
batch chunking*: when `len(documents)` exceeds the instance `chunk_size`, the mapping MUST split the
documents into consecutive `≤ chunk_size` chunks, issue one `/rerank` request per chunk (same query),
re-base each chunk's response `index` to its absolute position in the original `documents` list,
concatenate all `(index, score)` pairs, globally sort by score descending, and honor `top_k`.

**Spec sections exercised:**

- retrieval-provider §8.1 TEI — *Mandatory rerank batch chunking* (consecutive `≤ chunk_size` slices,
  one request per chunk, absolute-position re-basing, global re-sort, `top_k` honored). The validity
  rests on a cross-encoder scoring each `(query, document)` pair independently of the others in its
  batch.
- retrieval-provider §6 — results sorted by `relevance_score` descending; each `index` a valid
  position in the input list; no duplicate `index`; `len(results) ≤ top_k`. `RerankResponse.raw` is
  the **list of the per-chunk verbatim `/rerank` responses**, in request order — each entry that
  chunk's bare result array with its **chunk-local** indices in provider order (NOT re-based to
  absolute positions, NOT re-sorted — that is the stitched `results`).

**Case:**

1. `nine_documents_three_chunks_global_sort_top_k` — 9 documents, `chunk_size: 4`, `top_k: 4`. The
   mapping issues exactly THREE `/rerank` requests with `texts` sizes `[4, 4, 1]` over the consecutive
   slices `docs[0:4]`, `docs[4:8]`, `docs[8:9]` (same query each). Each chunk's mocked TEI response
   uses chunk-local indices; the mapping re-bases them to absolute positions (chunk B local `i` →
   absolute `4 + i`; chunk C local `0` → absolute `8`). Scores are laid out so the global descending
   order interleaves across all three chunks:
   `abs1(0.95) > abs6(0.88) > abs4(0.80) > abs8(0.65) > abs3(0.55) > abs5(0.30) > abs0(0.20) >
   abs2(0.10) > abs7(0.05)`. With `top_k: 4`, the result is the four highest globally —
   `[{1, 0.95}, {6, 0.88}, {4, 0.80}, {8, 0.65}]` — drawn from chunks A, B, B, C, so a per-chunk sort
   could not produce this order. All four `index` values are absolute positions into the original
   9-document list.

**What passes:**

- Exactly three `/rerank` requests with `texts` sizes `[4, 4, 1]`, consecutive slices, same query on
  each.
- Chunk-local indices re-based to absolute positions; the merged results globally sorted by score
  descending across chunks; `top_k` applied after the global sort.
- The final `results[].index` are absolute positions into the original 9-document list (not
  chunk-local); no duplicate index.
- `raw` is the list of the three per-chunk result arrays in request order, each preserving its
  chunk-local indices and provider order — the raw per-chunk responses, distinct from `results`.

**What fails:**

- An un-chunked single over-cap request (the chunking is mandatory, not optional), or a wrong chunk
  count / non-consecutive slices.
- Per-chunk sorting instead of a global re-sort (would surface a different top-4 order).
- Chunk-local indices left un-rebased (e.g. a result `index` of `0` for the chunk-B top scorer
  instead of its absolute `4`).
- `top_k` ignored, or a duplicate `index` across stitched chunks.
