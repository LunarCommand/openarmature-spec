# 034 — Cohere `/v2/embed` unrecognized `input_type` rejected pre-send

Verifies the retrieval-provider §8.4 Cohere embedding mapping's **reject-unrecognized** `input_type`
behavior: an OA `input_type` value outside the recognized `query` / `document` / `classification` /
`clustering` set is a **pre-send** `provider_invalid_request` (§7) — raised by the implementation's pre-send
validation layer **before any** `/v2/embed` request is issued. The embed analogue of the §8.2
reject-unrecognized path, exercising the corner unique to Cohere's mandatory-wire-field design: the mapping
picks a value for *absent* `input_type` (`search_document`, fixture 033), but an *unrecognized supplied*
value is rejected, not silently coerced to that default.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `input_type`: a **declared** field; an unrecognized
  value is `provider_invalid_request` (§7) at a mapping that recognizes a fixed set.
- retrieval-provider §7 — the exception-flow contract: the category exception MUST raise out of `embed()`
  whether raised by the provider or by the implementation's pre-send validation layer.
- retrieval-provider §8.4 Cohere — *`input_type` (mandatory wire field)*: the recognized set is `query` /
  `document` / `classification` / `clustering` (fixture 033); a value outside it is a pre-send
  `provider_invalid_request`. There is **no wire path** for an unrecognized value: `input_type` is a
  declared field, and the extras-pass-through bag carries only *undeclared* keys, so an unrecognized value
  cannot ride the bag onto the wire. Cohere's `image` value stays unrecognized — it names an input
  *modality*, not a purpose for embedded text (§3 / §11 scope v1 to text).

**Cases:**

1. `unrecognized_input_type_rejected_pre_send` — `embed(config={input_type: "summarization"})`, a value
   outside the recognized set. The mapping MUST raise `provider_invalid_request` at the pre-send validation
   layer and MUST NOT issue any `/v2/embed` request (no silent coercion to the `search_document` default —
   that default is only for the *absent* case). The exception raises out of the embed node.

**What passes:**

- `provider_invalid_request` raised out of the embed node, sourced from the pre-send validation layer.
- No `/v2/embed` request is issued (the rejection precedes the wire).

**What fails:**

- The unrecognized value is silently coerced to `search_document` (the absent-case default) and a request
  is sent.
- The unrecognized value is passed through verbatim onto the wire `input_type`.
- A different §7 category is raised, or the request reaches the wire before the validation fails.
