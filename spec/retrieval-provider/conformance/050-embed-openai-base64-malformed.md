# 050 — §8.3 base64 malformed / non-conforming embedding shape (proposal 0106)

Pins the **fail-loud boundary** of 0106's §8.3 decode. The shape dispatch is **exhaustive** — a
`data[].embedding` is either a JSON number array (float) or a base64 string (decoded as a little-endian float32
array), and **anything else** is malformed — and a base64 string that cannot form a whole float32 vector is
malformed too. Both raise `provider_invalid_response` (§7), fail-loud; the mapping MUST NOT salvage a truncated
or padded vector. Unlike the pre-send rejects (046/047), the request **is** issued — the corruption is in the
response, so the error is raised out of the embed call on decode.

**Spec sections exercised:**

- retrieval-provider §8.3 — the exhaustive shape dispatch and the malformed-base64 rule: a decoded byte length
  that is not a whole multiple of 4, and a non-conforming (non-array, non-string) `data[].embedding`, each raise
  `provider_invalid_response`.
- retrieval-provider §7 — `provider_invalid_response` is the payload-corruption category, raised at decode.

**Cases:**

1. `base64_byte_length_not_multiple_of_4_raises` — `encoding_format: "base64"`, and `data[0].embedding` is the
   base64 string `"AAAAPwAA"` (decodes to **6** bytes). 6 is not a multiple of 4, so the bytes do not partition
   into float32 values → `provider_invalid_response`. The mapping MUST NOT return a truncated (one-float) or
   zero-padded (two-float) vector.
2. `non_conforming_embedding_shape_raises` — `data[0].embedding` is an object `{}`, neither a number array nor a
   base64 string → the exhaustive-dispatch "any other shape" arm → `provider_invalid_response`.

**What passes:**

- Both cases: exactly one `/embed` request issued, then `provider_invalid_response` raised out of the embed
  node; no partial/padded vector returned.

**What fails:**

- Salvaging `"AAAAPwAA"` into a 1- or 2-element vector (truncate/pad) instead of raising; or treating a non-array,
  non-string `embedding` as empty / null / zero-length instead of raising (the divergence the exhaustive dispatch
  closes).
