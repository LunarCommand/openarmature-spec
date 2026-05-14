# 012 — PromptResult Rendered Hash Stability

Verifies the cache-key contract on `rendered_hash`: same template
plus same variables produces the same hash; same template plus
different variables produces different hashes. This is the
equivalence relation a memoization layer wants — two calls that
would produce the same LLM output share a hash.

Cross-implementation stability is also asserted (when the harness
supports it) to lock in the determinism guarantee across language
ports.

**Spec sections exercised:**

- §4 PromptResult — `rendered_hash` is "a stable content-derived hash
  of the rendered output."
- §4 cache-key use case — "two calls with the same template AND the
  same variables produce the same rendered_hash, which is exactly the
  equivalence relation a memoization layer wants."
- §12 Determinism — same Prompt + same variables → bytewise-identical
  messages AND rendered_hash.

**What passes:**

- `r_alice_1.rendered_hash == r_alice_2.rendered_hash` (same template,
  same variables).
- `r_alice_1.rendered_hash != r_bob.rendered_hash` (same template,
  different variables).
- Cross-implementation: the same template + variables across two
  implementations produces the same rendered_hash (when the harness
  exercises the cross-implementation case).

**What fails:**

- Identical inputs produce different hashes — would mean the
  implementation injected nondeterministic content into the hash
  computation.
- Different inputs produce identical hashes — would mean variables
  weren't actually folded into the hash, defeating the cache-key
  purpose.
- Cross-implementation hashes differ for canonical test inputs — would
  mean implementations diverged on the hash algorithm or canonical
  serialization (the spec recommends SHA-256 over canonical
  serialization; implementations must agree on both).
