# 047 — managed-field collision, reject arm: extras `truncate` vs TEI `/embed`'s relied-upon default

The materially-distinct sibling of fixture 046 (Cohere). The llm-provider §6 *Managed-field collision* reject
arm binds the three retrieval vendor mappings' fail-loud truncation flags (embed and rerank surfaces) — §8.1
TEI, §8.2 Jina, §8.4 Cohere — but TEI `/embed` is the sharpest case:
unlike Cohere (`truncate: "NONE"` sent explicitly, 046) and Jina `/v1/embeddings` (`truncate: false` sent
explicitly, 020), TEI `/embed` does **not** send `truncate` at all — it relies on TEI's `false` default,
keeping the body minimal. So its reject arm keys on a **relied-upon default the mapping never emits**.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* (reject arm), the relied-upon-default variant: `truncate` is a
  managed scalar on both TEI endpoints regardless of whether the flag is sent; a conflicting extras value is
  rejected pre-send `provider_invalid_request`, a matching value is a no-op.
- retrieval-provider §8.1 TEI — `/embed` relies on TEI's `false` `truncate` default and keeps the body minimal
  (`{inputs[, prompt_name][, dimensions]}`); the fail-loud contract depends on that default.
- retrieval-provider §7 — `provider_invalid_request` raised at the pre-send validation layer, no wire request.

**Cases:**

1. `conflicting_extras_truncate_rejected_pre_send` — `embed(config={extras: {truncate: true}})`. `true`
   conflicts with the relied-upon `false`; honoring it would flip the default at the wire and silently
   truncate an over-length input. The mapping raises `provider_invalid_request` pre-send, issues **no** `/embed`
   request, and neither drops nor forwards the value. This is the reject with no wire field to intercept — the
   mapping special-cases a key it never otherwise sets.
2. `matching_extras_truncate_is_noop_body_stays_minimal` — `embed(config={extras: {truncate: false}})`. `false`
   equals the relied-upon default, so it is a redundant no-op: the normal `/embed` request goes out with the
   body still **minimal** — `truncate` is **not** added to the wire (asserted via `expected_wire_request_absent_keys`),
   byte-identical to a call with no extras `truncate`. This pins the matching-value wire outcome for a
   relied-upon-default field: **omit, not forward** — the equivalent-but-opposite-looking outcome to 046 case 2,
   where Cohere's always-sent `truncate: "NONE"` stays on the wire unduplicated.

**What passes:**

- Case 1: `provider_invalid_request` raised out of the embed node, no `/embed` request, value neither dropped
  nor forwarded.
- Case 2: exactly one `/embed` request with `truncate` **absent** from the wire body, vectors returned normally
  (`usage` null, `response_id` null — TEI surfaces neither).

**What fails:**

- Forwarding a conflicting `truncate: true` onto the wire (the pre-0105 untouched-pass-through behavior,
  defeating fail-loud), or silently dropping it, in case 1.
- Adding `truncate: false` to the wire body in case 2 (a matching value must be omitted, keeping the body
  minimal), or rejecting the matching value.
