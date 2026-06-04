# 011 — Suspended span status + suspension attributes

The OTel observer marks both the invocation span and the suspending
node's span with the logical `SUSPENDED` status (per observability
§4.2 *Suspended status mapping* — OTel `OK` plus
`openarmature.outcome = "suspended"` attribute, since OTel's status
code field lacks a third state). The suspending node's span
additionally carries the §5.8 suspension-attribute set
(`openarmature.suspension.signal_id` + flattened
`openarmature.suspension.metadata.*`).

**Spec sections exercised:**

- observability §4.2 — `SUSPENDED` row in status mapping table;
  *Suspended status mapping* paragraph defining the OTel physical
  mapping.
- observability §5.8 — suspension span attributes
  (`openarmature.suspension.signal_id` + flattened
  `openarmature.suspension.metadata.*`).

**What passes:**

- Invocation span has OTel `status = OK` and the
  `openarmature.outcome = "suspended"` attribute.
- Suspending node's span has the same status + outcome attribute, PLUS
  `openarmature.suspension.signal_id = "span-status-test-12345"` and
  the flattened metadata attributes
  (`openarmature.suspension.metadata.kind = "approval"`,
  `openarmature.suspension.metadata.approver_pool = "finance"`).

**What fails:**

- Invocation span status is `ERROR` — would mean suspension was
  incorrectly mapped to OTel ERROR (suspensions are intentional, not
  failures).
- Missing `openarmature.outcome` attribute — would mean the spec's
  logical SUSPENDED status was not physically realized on OTel.
- Missing or malformed `openarmature.suspension.*` attributes — would
  mean §5.8 attribute emission failed.
