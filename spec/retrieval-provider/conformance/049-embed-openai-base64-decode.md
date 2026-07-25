# 049 — §8.3 OpenAI-compatible base64 output-encoding decode (proposal 0106)

Pins the **base64 decode** path added by 0106. §8.3's response consumer decodes `data[].embedding` by its **wire
shape**: a JSON number array is the float vector verbatim (the default float path, fixture 023); a **base64
string** is decoded as a base64-encoded array of **little-endian IEEE-754 single-precision (float32)** values,
yielding the same float vector. A caller opts into base64 through the extras bag (`encoding_format: "base64"`),
which forwards to the wire untouched — `encoding_format` stays an **unmanaged** extras key because the consumer
keys on the response *shape*, not the request parameter.

**Spec sections exercised:**

- retrieval-provider §8.3 — base64 `data[].embedding` is decoded (little-endian float32) to the float vector;
  `encoding_format: "base64"` rides the extras bag untouched; the wire default stays `"float"`.
- retrieval-provider §4 — the cross-impl invariants (input-order, uniform dimensionality, `dimensions` = inner
  length) apply to the **decoded** vectors; `raw` is the verbatim provider response (the base64 strings).
- llm-provider §6 (inherited) — `encoding_format` is **not** a *Managed-field collision* key (shape-driven
  decode, not a read-back dependency on the request param).

**Case:**

1. `base64_encoding_decodes_to_float_vectors_in_input_order` — `embed(config={extras: {encoding_format:
   "base64"}})` over three inputs. The wire request carries `encoding_format: "base64"`. The mock returns
   `data[].embedding` as base64 strings encoding exactly-representable float32 vectors, emitted out of natural
   order (`index` 2, 0, 1). The adapter decodes each string to a little-endian float32 array and returns
   `vectors` in **input** order (`[0.5, 0.25, 0.125, 0.75]`, `[1.0, 0.0, -0.5, 2.0]`, `[0.375, -0.125, 0.625,
   -1.5]`), with `raw` carrying the base64 strings **verbatim** (decoded on `vectors`, not on `raw`).

**What passes:**

- `encoding_format: "base64"` present on the wire (forwarded untouched); the three base64 strings decode to the
  intended float vectors; `vectors` in input order; `raw.data[].embedding` retains the base64 strings; `usage`,
  `dimensions`, and `response_id` (null — OpenAI embeddings carry no id) as for the float path.

**What fails:**

- Reading a base64 string as a float array directly (the pre-0106 break — dimensionality invariant violation),
  or decoding with the wrong endianness / width; returning `vectors` in `data` array order rather than `index`
  order; or rewriting `raw`'s embeddings to the decoded floats instead of preserving the base64 strings.
