# 058 — Implementation attribution attributes on the invocation span (OTel)

Verifies §5.1's `openarmature.implementation.name` and `openarmature.implementation.version`
attributes appear on every invocation span as non-empty strings, with `implementation.name`
matching the implementation under test (`"openarmature-python"` for python conformance runs,
`"openarmature-typescript"` for typescript, etc.). Companion to fixture 059 which verifies the
Langfuse-side projection of the same data.

**Spec sections exercised:**

- §5.1 — Two new invocation-level attributes; always-emit invariant; runtime-identity-constants
  framing.
- §3.4 reserved-key set — `implementation_name` and `implementation_version` are reserved (the
  rejection side is exercised by fixture 028's two new cases).

**Cases:**

1. `implementation_attribution_attributes_present_on_invocation_span` — Any graph invocation
   captured against an OTel test exporter. Asserts:
   - The invocation span carries `openarmature.implementation.name` as a non-empty string.
   - The invocation span carries `openarmature.implementation.version` as a non-empty string.
   - `openarmature.implementation.name` matches the implementation under test (the harness
     parameterizes this with the canonical name per §5.1's per-language table).
   - The two attributes appear ONLY on the invocation span (not cross-cutting per §5.6) — the
     inner node span does NOT carry them (the §5.1 invocation-span-only rule applies to all
     inner-span types — node, subgraph, fan-out, LLM provider — but this fixture demonstrates
     the node case; broader inner-span coverage is inherent in the spec rule, not the fixture).

2. `detached_subgraph_attribution_propagates_to_child_trace_invocation_span` — A graph that
   dispatches a subgraph in detached mode (per §4.4). Asserts both the parent invocation span
   AND the detached child trace's invocation span carry the attribution attributes. Verifies
   the attributes propagate to detached invocation spans (every invocation span emits them
   regardless of whether the invocation is the outermost graph or a detached child).

**What passes:**

- Both attributes present on the invocation span; both non-empty strings.
- `implementation.name` matches the per-language canonical value (`"openarmature-python"` etc.).
- The inner node span does NOT carry the attributes (the §5.1 invocation-span-only rule).
- The detached child trace's invocation span ALSO carries both attributes (the rule applies to
  every invocation span, not only the outermost graph's).

**What fails:**

- Either attribute missing on the invocation span — §5.1 always-emit invariant violated.
- Either attribute is empty / null — §5.1 says "never null".
- The attributes appear on the inner node span — they live in §5.1 (invocation span only), not
  §5.6 (cross-cutting attribute family).
- `implementation.name` carries a non-canonical value (e.g., `"oa-python"`, `"openarmature.python"`)
  — §5.1 mandates the `openarmature-<language>` PyPI/npm-shape convention.
- The detached child trace's invocation span lacks the attribution attributes — detached-mode
  invocation spans MUST carry them too.
