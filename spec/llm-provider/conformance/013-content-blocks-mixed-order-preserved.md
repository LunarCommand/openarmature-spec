# 013 — Content Blocks Mixed Order Preserved

User message with four content blocks in the order
`[image, text, image, text]`. Verifies §3.1.4 — the wire format preserves
block order; providers vary in semantic interpretation of order, so the
framework MUST NOT reorder.

**Spec sections exercised:**

- §3.1.4 Mixing blocks — "The wire format preserves block order."

**What passes:**

- The wire content-array's four entries are in exactly the order
  `[image_url, text, image_url, text]`, matching the spec block order.

**What fails:**

- Blocks are reordered (e.g., images grouped together, then text grouped
  together) — would mean §3.1.4 ordering is being broken.
- Any block dropped or duplicated.
