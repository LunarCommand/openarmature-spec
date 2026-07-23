# 072 — managed-field collision, reject arm: extras `response_format` vs the mapping's schema-derived one

The **first llm-provider** managed-field-collision fixture. Proposal 0105 defined the general *Managed-field
collision* rule in llm-provider §6, but its concrete managed keys were all in retrieval (`embedding_types`,
`truncate`); this pins the llm-provider instance.

Per §8.1.5, when a `response_schema` is supplied the OpenAI mapping constructs a `response_format` wire field
from the schema, and its own response consumer (§6 `parsed`, §7 `structured_output_invalid` validation)
depends on the model being constrained to that schema. So `response_format` is a **conditionally-managed
non-additive object** field — the reject arm, which 0105 broadened from "scalar" to any value the caller's and
the mapping's are mutually exclusive on (a scalar mode-switch, or an object the mapping constructs wholesale).

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* (reject arm), the conditionally-managed object variant: a
  conflicting extras value on a managed non-additive field is rejected pre-send `provider_invalid_request`;
  when the mapping is not producing the field, it is unmanaged and rides untouched.
- llm-provider §8.1.5 — `response_format` constructed from `response_schema`; omitted for free-form calls.
- llm-provider §7 — `provider_invalid_request` raised at pre-send validation, no request issued.

**Cases:**

1. `extras_response_format_conflicts_with_schema_rejected_pre_send` — `complete(response_schema=…,
   config={extras: {response_format: {type: "json_object"}}})`. The extras `response_format` collides with the
   mapping's schema-derived one; `{type: "json_object"}` (unconstrained JSON) is mutually exclusive with the
   schema-constrained format. The mapping raises `provider_invalid_request` pre-send, issues **no** request,
   and neither drops nor forwards the value.
2. `extras_response_format_without_schema_rides_untouched` — `complete(config={extras: {response_format: {type:
   "json_object"}}})` with **no** `response_schema`. The mapping produces no `response_format`, so it is
   **unmanaged**: the extras value rides untouched onto the wire, the call proceeds normally. Proves
   `response_format` is **conditionally** managed.

**Why two cases.** Case 2 discriminates an implementation that **always** rejects an extras `response_format`
(even with no schema) — that over-rejects and fails case 2, because with no schema the field is unmanaged and
must ride untouched. The reject keys on the mapping *producing* the field, not on the mere presence of an
extras `response_format`.

**What fails:**

- Forwarding a conflicting `response_format` onto the wire when a schema is present (breaking structured
  output), or silently dropping it — case 1.
- Rejecting the extras `response_format` when no schema is present, or omitting it from the wire — case 2.
