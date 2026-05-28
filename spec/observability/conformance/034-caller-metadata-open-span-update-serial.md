# 034 — Caller-Metadata Open-Span Update (Outermost Serial Context)

Verifies §3.4's open-span update MUST for the outermost (serial) async context — the
complement to fixtures 029 / 030, which verify the ancestor / sibling NON-update half. A
single serial node augments the in-scope metadata mid-body; the spans already open in the
augmenting (outermost) context — the invocation span (the Langfuse Trace) and the calling
node's span — MUST be updated in place to carry the augmented key.

**Spec sections exercised:**

- §3.4 — mid-invocation augmentation via the framework helper (e.g., Python
  `set_invocation_metadata`).
- §3.4 — open-span update (MUST): spans open at the augmentation call that were opened from
  the augmenting async context are updated in place. For an outermost-serial-context call,
  the augmenting context's own open spans are the invocation span and the calling node's
  span.
- §6 — the observer-driven lifecycle reflects the augmentation onto open spans via the
  recommended metadata-augmentation event on the serial delivery queue (or an equivalent
  mechanism producing the same spans).
- §8.4.1 / §8.4.2 — Langfuse `trace.metadata` and the node observation's `metadata` carry
  the augmented key after the in-place update.

**Cases:**

1. `serial_node_augmentation_updates_open_context_spans` — invocation passes
   `{tenantId: "acme-corp"}` as baseline; the single `ask` node's body augments the metadata
   with `requestId = "req-xyz"` before its LLM call. The harness asserts `requestId` reaches
   the invocation span (Trace), the `ask` node span, and the LLM generation. Because
   `requestId` was NOT supplied at `invoke()`, its presence on the invocation and node spans
   demonstrates the in-place open-span update rather than forward emission.

**Harness extensions:**

- `caller_metadata: {key: value, ...}` — baseline at `invoke()`, same as fixtures 026–030.
- `nodes.<node>.augment_metadata: {key: value, ...}` — harness primitive: at the top of the
  named node's body (before its LLM call runs), the harness internally calls the framework's
  augment-metadata helper with the supplied entries. Equivalent to placing
  `set_invocation_metadata(requestId="req-xyz")` at the top of the node's body. (Node-level
  analogue of the `augment_metadata` primitive fixture 030 places under a branch.)
- `invariants.open_span_update_reaches_invocation_and_node_spans: true` — harness verifies
  the augmented key reached the already-open invocation span and node span (not only the
  later-opened generation).
- `invariants.baseline_caller_metadata_universal: true` — harness verifies every span /
  observation carries the baseline `tenantId`.

**What passes:**

- The invocation span (the Trace's `metadata`) carries `requestId` in addition to the
  baseline `tenantId`, applied in place after the augmentation call.
- The `ask` node span's observation `metadata` carries `requestId`.
- The LLM generation carries `requestId` (opened after the call, via forward propagation).

**What fails:**

- `requestId` appears only on the LLM generation, not on the invocation span or the `ask`
  node span — the observer didn't update the open spans in the augmenting context. Violates
  §3.4's open-span MUST.
- `requestId` is missing entirely — the augmentation helper or its observer notification
  path is not wired.
- The baseline `tenantId` is missing from any span — the augmentation reset rather than
  additively merged. Violates §3.4's additive-merge rule.
