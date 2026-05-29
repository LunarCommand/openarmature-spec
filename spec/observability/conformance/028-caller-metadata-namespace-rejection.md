# 028 — Caller-Metadata Namespace Rejection

Verifies §3.4's reserved-key rejection at the `invoke()` API boundary. Caller metadata keys
under the reserved `openarmature.*` / `gen_ai.*` namespaces, OR exactly matching a reserved
OA-emitted metadata key name (the §8.4 Langfuse set), MUST cause the framework to raise an
error BEFORE any work begins — no spans emitted, no observability backend artifacts produced.

**Spec sections exercised:**

- §3.4 — reserved-namespace rule: keys under `openarmature.*` and `gen_ai.*` MUST be rejected
  at the `invoke()` API boundary. Error category is implementation-defined per the language's
  API-boundary error idiom (Python `ValueError`, TypeScript `RangeError`, etc.), same shape
  as §6 of graph-engine's drain-timeout-input validation.
- §3.4 — reserved exact-name rule: a caller key that exactly matches an OA-emitted top-level
  metadata key name (the §8.4 set — `correlation_id`, `step`, `system`, `branch_name`,
  `detached`, `detached_from_invocation_id`, etc.) MUST be rejected at the same boundary, by
  whole-key match (not prefix), regardless of which backends are wired.
- §3.4 cross-backend portability paragraph: rejection happens before observer emission, NOT
  at the backend's emission layer.

**Cases:**

1. `rejects_openarmature_prefix` — caller metadata includes `openarmature.user.malicious: "x"`.
   The framework MUST reject at `invoke()` entry. No spans, no Langfuse observations produced.
2. `rejects_gen_ai_prefix` — caller metadata includes `gen_ai.system: "openai"`. The
   framework MUST reject at `invoke()` entry. Same negative assertions.
3. `rejects_reserved_oa_name_step` — caller key `step` (an OA observation-metadata name,
   §8.4.2). Rejected at `invoke()` entry.
4. `rejects_reserved_oa_name_correlation_id` — caller key `correlation_id` (§8.4.1 / §8.5).
   Rejected at `invoke()` entry.
5. `rejects_reserved_oa_name_system` — caller key `system` (an OA generation-metadata name,
   §8.4.3; distinct from the `gen_ai.*` prefix case — here the bare key `system` collides).
   Rejected at `invoke()` entry.
6. `rejects_reserved_oa_name_branch_name` — caller key `branch_name` (an OA observation-
   metadata name, §8.4.2 — per-branch Span observation; added by proposal 0042). Rejected
   at `invoke()` entry.
7. `rejects_reserved_oa_name_detached` — caller key `detached` (an OA observation-metadata
   name, §8.4.2 — dispatching-observation flag for detached subgraph / fan-out instance per
   §4.4; added by proposal 0042). Rejected at `invoke()` entry.
8. `rejects_reserved_oa_name_detached_from_invocation_id` — caller key
   `detached_from_invocation_id` (an OA trace-metadata name, §8.4.1 — detached child trace's
   pointer back to the parent invocation; added by proposal 0042). Rejected at `invoke()` entry.
9. `rejects_reserved_name_via_set_invocation_metadata` — a node body calls the mid-invocation
   helper with the reserved name `step` (via the `augment_metadata` primitive). The helper
   MUST raise at the call site — the reservation is enforced at the helper, not only at the
   `invoke()` boundary.

**Harness extensions:**

- `expected.invoke_rejects_at_api_boundary: true` — harness asserts `invoke()` raised the
  language-idiomatic API-boundary error before returning. Error category is per-language; the
  harness asserts the error is raised, not the specific error class.
- `expected.no_spans_emitted: true` — harness verifies the OTel exporter received no spans
  for this invocation (work didn't begin).
- `expected.no_langfuse_observations_emitted: true` — harness verifies the Langfuse recorder
  received no Trace or Observation entries.
- `nodes.<node>.augment_metadata: {key: value}` — harness primitive (per fixture 034): calls
  `set_invocation_metadata(...)` at the top of the named node's body. Used in case 6 to drive
  the mid-invocation helper with a reserved name.
- `expected.augment_rejects_at_call_site: true` — harness asserts the `set_invocation_metadata`
  helper raised (the language-idiomatic error) at the call site, before the reserved key
  reached any emission.

**What passes:**

- All `invoke()`-boundary cases (1–8): `invoke()` raises an API-boundary error immediately on
  entry. No spans, no Langfuse observations, no provider calls. The error propagates up to
  the harness.
- Helper case (9): `set_invocation_metadata` raises at the call site with the same per-language
  error idiom; no spans / observations follow.

**What fails:**

- Framework accepts the invalid metadata and proceeds with the invocation, emitting spans /
  observations that carry the colliding key. Either the rejection rule isn't implemented or
  it's checked too late (after observer emission has begun).
- Framework rejects only one of the two reserved prefixes — implementation enforces
  `openarmature.*` but missed `gen_ai.*` (or vice versa).
- Framework rejects at the backend's emission layer rather than at `invoke()` entry —
  violates §3.4's "before any work begins" rule; would still produce partial work (some spans
  emitted before the backend's per-emission check fires).
- Framework's expand-rejected-keys option (§3.4 MAY-expand) introduces additional keys to the
  rejected set; that's permitted per §3.4 but the two reserved-namespace cases MUST always
  be rejected regardless of any expansion.
- Framework rejects reserved names only at the `invoke()` boundary but NOT in the
  `set_invocation_metadata` helper — a caller can still inject a reserved name mid-invocation
  and collide with OA-emitted Langfuse metadata (the gap case 6 guards against).
