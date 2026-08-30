# 056 — TEI `prompt_name` Not Produced (the production test)

Verifies that llm-provider §6 clause (b) keys management to whether the mapping **produces** the wire key,
not to whether the declared field is set.

**Spec sections exercised:**

- **llm-provider §6** — *Managed-field collision*, clause (b): a wire field is managed only **while the
  mapping is producing it**.
- **retrieval-provider §8.1** — the `input_type` realization, and its two paths: the server-side prompt
  lookup through the construction `input_type → prompt_name` map, and the client-side `query_prefix` /
  `document_prefix` fallback for a model without configured prompts.

## Why this is a separate fixture

For every other retrieval realization, production and declared-field presence coincide: the mapping emits
the wire key exactly when the caller supplies the declared field, so the two readings of clause (b) cannot
be told apart. §8.1's `prompt_name` is the exception. On the client-side-prefix path `input_type` is set and
`prompt_name` is **not** produced.

Fixture 055 cannot reach that path. Its provider block configures the prompt map, and a provider block is
**fixture-level** rather than per-case, so every case there sits on the server-side path. Hence a separate
fixture with a differently-configured provider.

**Cases:**

1. `extras_prompt_name_rides_untouched_on_client_side_prefix_path` — `input_type: query` with extras
   `prompt_name: "passage"`, against a provider with prefixes and no prompt map. The mapping prefixes the
   input and sends no `prompt_name`, so the key is unmanaged and the extras value rides untouched.
2. `no_extras_prompt_name_absent_on_client_side_prefix_path` — the control. The same call without extras,
   asserting the mapping genuinely produces no `prompt_name`. Without it, case 1 could pass against an
   implementation that produced `prompt_name` and happened to agree with the extras value.

**What passes:**

- Both cases prefix the input client-side. Case 1's wire carries the caller's `prompt_name`; case 2's
  carries none.

**What fails:**

- An implementation keying management to the **declared field's presence** rejects case 1 as a collision.
  That is the reading this fixture exists to rule out, and no other fixture can.
- An implementation that produces `prompt_name` on this path anyway fails case 2, and case 1's assertion
  then no longer means what it claims.
