# 026 — OTel Caller-Supplied Metadata (cross-cutting)

Verifies §5.6's `openarmature.user.*` cross-cutting attribute family. Caller-supplied
invocation metadata (per §3.4) propagates to every span emitted during the invocation:
invocation span, node spans, LLM provider span, retry attempt spans (when applicable).

**Spec sections exercised:**

- §3.4 — caller-supplied invocation metadata accepted at invoke time, propagated via the
  language's context primitive.
- §5.6 — `openarmature.user.<key>` cross-cutting attribute family on every span.
- §5.6 — values are OTel-attribute-compatible scalars (string, int, bool exercised here;
  float and homogeneous arrays follow the same contract).

**Cases:**

1. `caller_metadata_emits_on_every_span` — invocation supplied with three metadata entries
   (`tenantId: "acme-corp"`, `seatCount: 42`, `isCanary: true`); graph has two nodes and one
   LLM call; the harness asserts every span carries the full `openarmature.user.*` set.

**Harness extensions:**

- `caller_metadata: {key: value, ...}` — configures the harness's `invoke()` call with the
  supplied metadata mapping. Values are scalars per §3.4.
- `invariants.caller_metadata_cross_cutting: true` — the harness asserts that the full set of
  `openarmature.user.*` attributes specified at the invocation span is also present on every
  descendant span (no span is missing any metadata entry).

**What passes:**

- Every span — invocation, both node spans (`prep` and `ask_llm`), and the LLM provider span
  — carries `openarmature.user.tenantId`, `openarmature.user.seatCount`, and
  `openarmature.user.isCanary` with the supplied values.
- The value types are preserved (string stays string, int stays int, bool stays bool).

**What fails:**

- Any span is missing one or more `openarmature.user.*` attributes — implementation didn't
  propagate to that span type. Common miss: forgetting to add the cross-cutting set to LLM
  provider spans (§5.5) since those are emitted via the LLM provider's `complete()` call site
  rather than via the §6 observer event stream directly.
- Attribute names are emitted without the `openarmature.user.` prefix — implementation
  promoted caller keys to the root attribute namespace, violating §5.6's reserved-prefix rule.
- Value types are coerced (int → string, bool → string) — violates §5.6's
  OTel-attribute-compatible-scalar contract.
