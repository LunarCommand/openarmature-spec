# 066 — Failure-isolation event structured cause chain

Verifies proposal 0068's §6.3 rule that the failure-isolation event's
`caught_exception` carries a structured **`chain`** of cause links plus a
**derived** `category` / `message`. Supersedes 0065's single-"originating
cause" representation: the derived `category` reproduces 0065's resolved value
(so fixture 064 stays valid), and the `chain` adds the full provenance —
carriers included and flagged.

**Spec section exercised:** §6.3 — `caught_exception.chain` (ordered cause
links `{category, message, carrier}`, outermost→innermost) and the derivation
(`category` = the outermost non-carrier link with a non-empty category, else
`null`; `message` = that link's message, else the outermost non-carrier link's).

**Cases:**

1. `instance_site_chain_resolves_to_originating` — a single-instance fan-out
   with `instance_middleware: [failure_isolation]`. The engine wraps the
   instance failure as one §4 `node_exception` carrier over the originating
   `provider_unavailable`. Asserts `chain = [{carrier, node_exception},
   {non-carrier, provider_unavailable}]` and the derived `category` /
   `message` = the originating link (not the masking carrier).
2. `node_level_chain_single_non_carrier_link` — a node-level
   `failure_isolation` middleware catches the **raw** error (no carrier is
   present inside the node's own chain), so the chain is a single non-carrier
   link and the derived `category` is that link's.
3. `uncategorized_cause_chain_null_derived_category` — the only non-carrier
   link has no category, so the derived `category` is `null` and the derived
   `message` is that link's message (`"boom"`).

**What passes:**

- `caught_exception.chain` lists the caught exception and its cause chain,
  outermost→innermost, with `carrier: true` on each §4 `node_exception` wrapper.
- The derived `category` is the outermost non-carrier link's category (else
  `null`); the derived `message` is that same link's (else the outermost
  non-carrier's).
- The node-level placement yields a single non-carrier link (no carrier).

**What fails:**

- Reporting the masking carrier's identity as the derived `category` instead of
  the originating non-carrier link's.
- Omitting carriers from the `chain` (the chain must include them, flagged), or
  dropping the derived `category` / `message`.
- A `null`-category derivation that loses the originating `message`.

**Carrier-link assertion:** carrier links assert `{carrier, category}` only;
their engine-internal `message` is not pinned (subset-match), since wrapper
messages are implementation detail.

**Out of strict scope (this fixture):**

- **Multi-carrier walk** (e.g. a parent-node middleware on a parallel-branches
  node catching a `parallel_branches_branch_failed` carrier over the branch's
  `node_exception` carrier — two carriers). The single-carrier case establishes
  the carrier-skipping derivation; a 2-carrier case depends on parent-node
  middleware on a parallel-branches node being expressible in the adapter.
- **Outermost-wins discrimination** (two *non-carrier* links with different
  categories, where the derivation picks the outermost). Producing two
  categorized non-carrier links requires mock exception-chaining beyond the
  current `flaky` vocabulary; this behavior is carried by §6.3 text and
  implementation unit tests until the adapter can express it.
