# 015 — LabelResolver Fallback Chain

Verifies §7 `LabelResolver` and §6 `PromptManager.fetch()` label-resolution chain. The
three precedence levels (per-name override, resolver default, spec-fallback `"production"`)
plus the explicit-label-bypass case and the no-resolver-configured case.

**Spec sections exercised:**

- §6 fetch label-resolution chain: explicit > resolver > spec-fallback `"production"`.
- §7 LabelResolver.resolve fallback chain: per-name override > default override > spec
  fallback `"production"`.
- §6 default `label` parameter shift from v0.15.0's `"production"` to v0.26.0's `None` /
  sentinel.

**Cases (single fixture with six fetch calls):**

1. `fetch("segment_semantic", label=None)` with resolver mapping `{default: "production",
   segment_semantic: "staging", extract_claims: "variant-a"}` → resolver returns `"staging"`
   (per-name override).
2. `fetch("extract_claims", label=None)` → resolver returns `"variant-a"` (per-name
   override).
3. `fetch("classify", label=None)` — no per-name override → resolver returns `"production"`
   (default override).
4. `fetch("segment_semantic", label="production")` — EXPLICIT label → resolver NOT
   consulted; manager passes `"production"` verbatim to backend.
5. `fetch("unknown_prompt", label=None)` against a second manager that has NO LabelResolver
   configured → spec-fallback returns `"production"`.
6. `fetch("unknown_prompt", label=None)` against a third manager that HAS a LabelResolver
   configured but the resolver's mapping has NO `default` key (only unrelated per-name
   overrides) → resolver is consulted, misses per-name, misses default, spec-fallback
   returns `"production"`. Distinct code path from case 5 (resolver IS consulted here).

**Harness extensions:**

- `label_resolver.mapping: {default: ..., <name>: ..., ...}` — configures a static
  mapping-backed LabelResolver. The `default` key (when present) becomes the resolver's
  default override.
- `manager.label_resolver_ref: <name>` — wires the named LabelResolver into the manager.

**What passes:**

- All five fetches return Prompts at the expected `label` / `version` shown in the YAML.
- The manager does NOT consult the resolver when an explicit label is passed (verified
  by the explicit-label case returning the `production`-labeled record despite the
  resolver having a `staging` override).
- A manager constructed without a LabelResolver falls back to `"production"` directly
  (verified by the no-resolver case).

**What fails:**

- `r_seg` returns the production-labeled record — resolver wasn't consulted (manager
  defaulted to `"production"` despite a resolver being configured).
- `r_classify` returns something other than `"production"` — resolver's default override
  not applied.
- `r_seg_explicit` returns the staging-labeled record — manager consulted the resolver
  despite an explicit label argument. Violates the explicit-bypasses-resolver rule.
- `r_unknown_no_resolver` errors or returns non-`production` — the no-resolver path
  didn't fall back to `"production"` per §6 step 3.
- Resolver's `default` key is treated as a per-name override (would match a prompt named
  `"default"`) — implementation conflated the default-override path with the per-name
  override path.
