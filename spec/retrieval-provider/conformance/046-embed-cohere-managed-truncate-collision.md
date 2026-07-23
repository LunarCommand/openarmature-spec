# 046 — managed-field collision, reject arm: extras `truncate` vs Cohere's managed `truncate: "NONE"`

The reject-arm counterpart to fixture 039's merge arm (`embedding_types`). 0105 generalizes 0099's
mapping-managed-field rule into llm-provider §6 *Managed-field collision*: an undeclared extras key that
**names a wire field the mapping manages** does **not** get untouched pass-through. For a **scalar** managed
field whose override would break the mapping's contract, an extras value **equal** to the managed value is a
redundant no-op, and a **conflicting** value is **rejected pre-send** with `provider_invalid_request` (§7) —
never silently dropped, never silently forwarded to override the managed value.

§8.4 Cohere `/v2/embed` manages `truncate: "NONE"` — its fail-loud posture (an over-length input errors
rather than being silently truncated). So `truncate` is a managed scalar.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* (reject arm): a conflicting extras value on a managed scalar is
  rejected pre-send `provider_invalid_request`; a matching value is a no-op; the mapping MUST NOT silently
  drop or silently override.
- retrieval-provider §8.4 Cohere — `truncate: "NONE"` is a managed scalar (the enumerated managed keys are
  `embedding_types` [merge] and `truncate` [reject]).
- retrieval-provider §7 — `provider_invalid_request` raised at the pre-send validation layer (exception-flow
  contract: the category exception raises out of `embed()` whether from the provider or from client-side
  validation), with no wire request issued.

**Cases:**

1. `conflicting_extras_truncate_rejected_pre_send` — `embed(config={extras: {truncate: "END"}})`. `"END"`
   conflicts with the managed `"NONE"`; honoring it would silently truncate an over-length input the mapping
   fails loud on. The mapping raises `provider_invalid_request` at the pre-send layer and issues **no**
   `/v2/embed` request. It does **not** silently drop the value and does **not** forward it to the wire.
2. `matching_extras_truncate_is_noop` — `embed(config={extras: {truncate: "NONE"}})`. `"NONE"` equals the
   managed value, so it is a redundant no-op: the normal `/v2/embed` request goes out with `truncate: "NONE"`
   (unduplicated, byte-identical to a call with no extras `truncate`) and returns vectors normally.

**Why two cases.** They discriminate three wrong implementations: one that **always rejects** any extras
`truncate` fails case 2 (a matching value must be a no-op); one that **forwards it untouched** fails case 1
(it would send `truncate: "END"` and defeat fail-loud); one that **silently drops** it fails case 1 (it must
reject, not swallow). The reject arm keys on **conflict**, not on the mere presence of an extras `truncate`.

**What passes:**

- Case 1: `provider_invalid_request` raised out of the embed node, no `/v2/embed` request issued, the
  conflicting value neither dropped nor forwarded.
- Case 2: exactly one `/v2/embed` request with `truncate: "NONE"` (the managed value, unduplicated), vectors
  returned normally.

**What fails:**

- Rejecting a matching extras `truncate` (case 2), or forwarding / dropping a conflicting one (case 1).
- Issuing a wire request in case 1 (the rejection is pre-send), or sending `truncate: "END"` on the wire.
