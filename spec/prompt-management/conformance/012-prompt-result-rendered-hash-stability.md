# 012 — PromptResult Rendered Hash Stability

Verifies the cache-key contract on `rendered_hash`: same template
plus same variables produces the same hash; same template plus
different variables produces different hashes. This is the
equivalence relation a memoization layer wants — two calls that
would produce the same LLM output share a hash.

Cross-implementation stability is NOT verified here. The v1 spec
guarantees within-implementation determinism (§12) but does not
mandate a normative hash algorithm or canonical serialization, so
two conforming implementations could produce different
`rendered_hash` values for the same rendered messages. A
follow-on proposal can tighten those (e.g., SHA-256 hex over
RFC 8785 JCS) when cross-implementation cache-key portability
becomes a concrete need.

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
  same variables — within-implementation determinism per §12).
- `r_alice_1.rendered_hash != r_bob.rendered_hash` (same template,
  different variables).

**What fails:**

- Identical inputs produce different hashes — would mean the
  implementation injected nondeterministic content into the hash
  computation.
- Different inputs produce identical hashes — would mean variables
  weren't actually folded into the hash, defeating the cache-key
  purpose.
