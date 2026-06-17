# 068 — Failure-mock `cause` chain (outermost-wins derivation)

Verifies proposal 0070's `cause` field on failure mocks (conformance-adapter
§5.1) and the resulting pipeline-utilities §6.3 / proposal 0068 **outermost
non-carrier wins** cause derivation with **two** non-carrier links — the case
fixture 066 explicitly left out of scope for lack of mock exception-chaining.

**Spec sections exercised:** conformance-adapter §5.1 (`cause`);
pipeline-utilities §6.3 (`caught_exception.chain` and the derived `category`).

**Case:**

1. `outermost_non_carrier_wins_over_originating_cause` — a single-instance
   fan-out with `instance_middleware: [failure_isolation]`. The `flaky` mock
   raises `provider_invalid_response` **caused by** `provider_unavailable`
   (via `cause`). The engine wraps the instance failure as one `node_exception`
   carrier, so the chain is `[{carrier, node_exception}, {non-carrier,
   provider_invalid_response}, {non-carrier, provider_unavailable}]`. The
   derived `category` is `provider_invalid_response` — the **outermost**
   non-carrier link — so a deliberate surface re-categorization wins over the
   originating cause.

**What passes:**

- The mock's `cause` produces a chained exception the failure-isolation event
  walks: two non-carrier links plus the flagged engine carrier.
- The derived `category` / `message` are the outermost non-carrier link's
  (`provider_invalid_response`), not the originating cause's
  (`provider_unavailable`).

**What fails:**

- Deriving the category from the originating (innermost) cause instead of the
  outermost non-carrier link.
- Dropping the originating cause link from the chain, or failing to flag the
  engine carrier.

**Carrier-link assertion:** the carrier link asserts `{carrier, category}`
only; its engine-internal `message` is not pinned (subset-match), per
fixture 066.
