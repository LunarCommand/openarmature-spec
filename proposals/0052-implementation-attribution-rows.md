# 0052: Implementation Attribution Attributes

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-01
- **Accepted:**
- **Targets:** spec/observability/spec.md (§5.1 *Invocation span attributes* — adds two new invocation-level attributes, `openarmature.implementation.name` and `openarmature.implementation.version`, emitted on every invocation span and sourcing the OA implementation's identity; §8.4.1 *Trace-level mapping* — adds two new `trace.metadata.*` rows mapping the §5.1 attributes onto Langfuse trace metadata; §3.4 — extends the reserved caller-metadata key set from 24 to 26 names with `implementation_name` and `implementation_version` to reject caller collision at the `invoke()` API boundary); plus one positive-control conformance fixture asserting the OTel attributes present on the invocation span + one positive-control fixture asserting the Langfuse rows present on every Trace + one negative-control extension on existing fixture 028 (caller-metadata namespace rejection) asserting both new names are rejected per the §3.4 reservation rule.
- **Related:** 0031 (observability §8 Langfuse mapping — established the §8.4 trace metadata mapping table this proposal extends), 0034 (caller-supplied invocation metadata — established the §3.4 reserved-key mechanism this proposal extends), 0041 (Langfuse reserved-key collision — established the reserved-key list maintenance rule this proposal follows), 0042 (reserved-keys extension — most recent prior maintenance-rule extension to the §3.4 reserved set)
- **Supersedes:**

## Summary

OpenArmature observability emissions today carry the spec version
on every invocation — `openarmature.graph.spec_version` per §5.1
on the OTel invocation span, and `trace.metadata.spec_version` per
§8.4.1 on the corresponding Langfuse Trace. Operators scanning any
OTel-consuming backend (Phoenix, Datadog, Honeycomb, HyperDX,
Grafana Tempo) or the Langfuse Traces list view can see which OA
spec contract a given trace conforms to. The spec version answers
"which contract" but not "which library, at which version,
actually produced this row." That second question is what
operators reach for first during triage:

- "Did the bug fix in 0.10.1 ship in this trace?" — answered by
  the library version, not the spec version.
- "Is this trace from openarmature-python or openarmature-typescript?"
  — answered by the library name, not the spec.

This proposal adds **two new invocation-level attributes** to
observability §5.1 — `openarmature.implementation.name` and
`openarmature.implementation.version` — emitted on every
invocation span. The §8.4.1 Langfuse mapping picks them up onto
`trace.metadata.implementation_name` / `trace.metadata.implementation_version`,
mirroring how `openarmature.graph.spec_version` (§5.1) maps to
`trace.metadata.spec_version` (§8.4.1). All other OTel-consuming
backends pick the attributes up from the invocation span directly
— no per-backend mapping work needed.

Both attributes are implementation-emitted (not caller-supplied),
always-emit regardless of privacy knobs (matching the existing
`spec_version` + `correlation_id` always-emit pattern — these are
runtime-identity constants, not runtime data), and reserved in
§3.4 so a caller-supplied metadata key with the same name is
rejected at the `invoke()` boundary (preventing silent clobber).

The §3.4 reserved-key set grows from 24 names (the post-0042 set)
to 26.

The change is additive at the spec level. No existing behavior
changes; the new attributes surface on every invocation span and
on every Langfuse Trace, and impls adopt by reading their own
package metadata.

## Motivation

The operator triage flow that motivates this proposal is the same
across OTel-consuming backends and Langfuse alike:

- An operator opens whichever observability backend they're using
  (Langfuse Traces list view, Phoenix dashboard, Honeycomb / Datadog
  query interface, Grafana Tempo, etc.) to investigate a recent
  failure.
- They want to know which library version emitted the trace so they
  can check release notes for the relevant bug fix.
- Today: `spec_version` tells them "v0.38.0 spec contract" — but
  they don't know if the trace is from openarmature-python v0.11.3
  (which has a fix) or v0.11.1 (which has the bug they're hunting).
- The library version is what makes the next investigative move
  unambiguous; the spec version doesn't.

Three signals point at this being load-bearing:

1. **Concrete operator triage flow.** The "did the 0.10.1 fix
   ship?" question is the typical first question; without the
   library version on the trace, operators have to look up
   deployment manifests separately. Putting the version on the
   span/trace eliminates the lookup.
2. **Cross-impl disambiguation.** OA's multi-language consistency
   framing (`GOVERNANCE.md`) anticipates multiple language ports.
   When multiple OA implementations coexist in a deployment —
   even within a single org running both — an operator's first
   triage question on an unfamiliar trace is "which language?"
   The `implementation_name` field answers this directly without
   requiring per-impl conventions about how language gets
   recorded elsewhere.
3. **Symmetry with `spec_version` on BOTH surfaces.** §5.1
   already mandates `openarmature.graph.spec_version` as an
   implementation-emitted attribute on every invocation span,
   and §8.4.1 maps it onto `trace.metadata.spec_version` for the
   Langfuse-side projection. The pattern of "library identifies
   itself on every invocation, mirrored to backend-specific
   fields" is established — extending it with name + version is
   the natural next move that benefits ALL OTel-consuming
   backends (since they read the §5 attribute surface) AND the
   Langfuse mapping (via the §8.4.1 row), not just one or the
   other.

The cost is small (two `__version__` lookups + two emitted
attributes per invocation; one constant string + one
package-metadata read at implementation startup). The operator-UX
improvement is the load-bearing payoff — and pinning the
attribution to the OTel attribute surface (rather than only to
the Langfuse mapping) means every OTel-consuming backend gets it
for free without per-backend mapping work.

## Proposed change

### observability §3.4 — extend the reserved-key set (24 → 26)

The §3.4 *Caller-supplied invocation metadata* reserved-key
enumeration extends with two new names:

> Add `implementation_name` and `implementation_version` to the
> §3.4 reserved-key set (post-0042 contained 24 names; this
> proposal brings it to 26). Both names MUST be rejected at the
> `invoke()` API boundary when a caller supplies them in the
> `invocation_metadata` mapping, with the same enforcement
> mechanism that rejects the other 24 reserved names. The
> rejection error category is the language-idiomatic API-boundary
> error type already used for the existing 24-name set (per
> proposal 0041's framing).

The expanded set (26 names total) becomes the new baseline; future
proposals that add new top-level OA metadata keys extend it
further per the maintenance rule from 0041.

### observability §5.1 — two new invocation-level attributes

Extend the §5.1 *Invocation span attributes* set (which currently
lists `openarmature.invocation_id`, `openarmature.graph.entry_node`,
and `openarmature.graph.spec_version`) with two new attributes:

> - `openarmature.implementation.name` — string. The OA
>   implementation that emitted the invocation. Examples:
>   `"openarmature-python"`, `"openarmature-typescript"` (canonical
>   values matching package-registry shapes — PyPI for Python, npm
>   for TypeScript; per-language idiomatic equivalents for future
>   ports under the `openarmature-<language>` convention).
>   Implementation-emitted; never caller-supplied (reserved per
>   §3.4). Stable per implementation; never null.
> - `openarmature.implementation.version` — string. The OA
>   implementation's release identifier, sourced from the
>   implementation library's package metadata in the
>   language-idiomatic way (Python: `openarmature.__version__`
>   or `importlib.metadata.version("openarmature")`; TypeScript:
>   `package.json` `version` field; per-language idiomatic
>   equivalents otherwise). Implementation-emitted; never
>   caller-supplied (reserved per §3.4). Never null. Pre-release
>   tags (e.g., `"0.12.0-rc.1"`) MAY appear; the spec does NOT
>   mandate semver vs CalVer vs any specific versioning
>   discipline — the value matches the package's release
>   identity in whatever shape the package registers under.

Both attributes are emitted on every invocation span. OTel-
consuming backends (Phoenix, Datadog, Honeycomb, HyperDX, Grafana
Tempo, etc.) read the attributes from the span directly without
needing per-backend mapping work.

### observability §8.4.1 — two new Trace metadata rows

Add two new rows to the §8.4.1 Trace-level mapping table,
sourcing from the new §5.1 attributes:

> | OA attribute | Langfuse Trace mapping |
> |---|---|
> | `openarmature.implementation.name` | `trace.metadata.implementation_name` |
> | `openarmature.implementation.version` | `trace.metadata.implementation_version` |

The mapping follows the existing precedent for §5.1 →
`trace.metadata.*` rows (e.g., `openarmature.graph.spec_version` →
`trace.metadata.spec_version` at line 1305 of observability
spec).

Add a new *Always-emit invariant* paragraph to §5.1, after the
existing `openarmature.graph.spec_version` attribute description:

> **Always-emit invariant.** `openarmature.implementation.name`
> and `openarmature.implementation.version` MUST be emitted on
> every invocation span regardless of the `disable_state_payload`,
> `disable_llm_payload`, or any other observer-level privacy
> knob. These attributes describe the OA runtime itself — they
> are runtime-identity constants, not runtime data. The
> privacy-knob framing applies to runtime data (caller state,
> LLM messages, etc.), not to runtime identity. The pattern is
> parallel to `openarmature.graph.spec_version` (§5.1) and
> `openarmature.correlation_id` (§3.1 / §5.6) — all three
> mandated, all three always-emit, all three implementation-
> emitted (not caller-supplied). The §8.4.1 Langfuse-mapping
> rows derived from these attributes inherit the same
> always-emit invariant.

### Canonical implementation name values

The `openarmature.implementation.name` values follow the
package-registry naming for each language:

| Implementation | `implementation_name` value | `implementation_version` source |
|---|---|---|
| openarmature-python | `"openarmature-python"` | `openarmature.__version__` or `importlib.metadata.version("openarmature")` |
| openarmature-typescript | `"openarmature-typescript"` | `package.json` `version` field |
| Future language ports | `"openarmature-<language>"` (matches PyPI / npm / cargo / etc. naming for that ecosystem) | language-idiomatic package-metadata source |

Future implementations follow the same `openarmature-<language>`
convention. The convention deliberately matches the package-
registry shape (PyPI / npm / etc.) so an operator can copy the
name directly into the registry's search box without
transliteration.

## Conformance test impact

### New fixtures

Two new positive-control fixtures (one OTel, one Langfuse) + one
negative-control extension to an existing fixture (numbers
assigned at acceptance):

**Observability (OTel):**

1. **Implementation attribution attributes present on the
   invocation span.** A graph invocation captured against an OTel
   test exporter. Asserts the invocation span carries
   `openarmature.implementation.name` and
   `openarmature.implementation.version` as non-empty string
   attributes, and `implementation.name` matches the implementation
   under test (`"openarmature-python"` for python conformance runs).
   The attributes appear once per invocation (on the invocation
   span only — they are NOT cross-cutting attributes per §5.6;
   they live in §5.1 alongside other invocation-level constants).

**Observability (Langfuse):**

2. **Implementation attribution rows present on every Trace.** A
   graph invocation against a fixture-mock Langfuse client. Asserts
   `trace.metadata.implementation_name` and
   `trace.metadata.implementation_version` are present, are non-
   empty strings, and `implementation_name` matches the
   implementation under test. The §8.4.1 rows source from the
   §5.1 attributes — the OTel-side fixture (#1) and the
   Langfuse-side fixture verify both surfaces consistently.

**Negative-control extension to existing fixture 028:**

3. **Extend `028-caller-metadata-namespace-rejection.yaml`** with
   two new rejection cases:
   - `rejects_reserved_oa_name_implementation_name` — caller
     passes `invocation_metadata={"implementation_name": "spoof"}`;
     asserts rejection at the `invoke()` API boundary.
   - `rejects_reserved_oa_name_implementation_version` — caller
     passes `invocation_metadata={"implementation_version": "9.9.9"}`;
     asserts rejection at the `invoke()` API boundary.

Existing fixture 028's structure (the pattern proposal 0042 used
when extending §3.4 to add `branch_name` / `detached` /
`detached_from_invocation_id`) is the precedent for this
extension.

### Unaffected fixtures

All other existing fixtures continue to pass unchanged on both
observability surfaces:

- **OTel side.** The two new attributes are additive on every
  invocation span; existing OTel fixtures that inspect the
  invocation span for specific attributes don't assert absence
  of `openarmature.implementation.*` attributes, so they aren't
  broken.
- **Langfuse side.** The two new rows are additive on every
  Trace; existing Langfuse fixtures don't assert absence of
  `implementation_*` keys in `trace.metadata`, so they aren't
  broken.

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- New `openarmature.implementation.name` +
  `openarmature.implementation.version` invocation-span attributes
  in observability §5.1 (additive — existing §5.1 attributes
  unchanged).
- New `trace.metadata.implementation_name` +
  `trace.metadata.implementation_version` rows in §8.4.1 sourcing
  from the §5.1 attributes (additive — existing §8.4.1 rows
  unchanged).
- §3.4 reserved-key set extends 24 → 26 names (additive — the
  enforcement mechanism is unchanged from 0041's framing).
- New always-emit invariant paragraph in §5.1 (informative-
  clarifying alongside the additive attributes; covers both the
  OTel surface and the §8.4.1 Langfuse projection).
- New conformance fixtures (two positive-control — one OTel, one
  Langfuse) + extension to existing fixture 028 (two new
  rejection cases). Existing fixture text otherwise unchanged.

The change is additive at the spec level. The new attributes
surface on every invocation span; OTel-consuming backends that
ignore unknown attributes see no behavioral change, and the
§8.4.1 Langfuse rows are similarly additive. A caller-supplied
`implementation_name` (or `implementation_version`) in
`invocation_metadata` is rejected at the `invoke()` API boundary
per the §3.4 reservation rule — collision protection prevents
silent shadowing of the implementation-emitted value.

## Alternatives considered

1. **Single combined string instead of two fields** (e.g.,
   `"openarmature-python@0.10.0"`). More compact but worse for
   the operator triage UX: dashboard filtering on "all python
   traces" requires `startswith("openarmature-python")` or
   split-on-`@`, both awkward in Langfuse's UI filter form.
   Split keys make `metadata.implementation_name ==
   "openarmature-python"` and
   `metadata.implementation_version == "0.10.0"` direct
   equality matches. Rejected.

2. **Naming the field `impl_name` (abbreviated) or
   `library_name`.** Rejected: `impl_name` reads like internal
   jargon and reduces searchability; `library_name` is
   ambiguous (could mean OA itself, OA's dependencies, or the
   consuming application). `implementation_name` is unambiguous
   and matches the spec verb usage ("the implementation MUST...").

3. **Implementation_name values like `openarmature.python` or
   `oa-python` instead of `openarmature-python`.** Rejected:
   matching the PyPI / npm package name is operationally right —
   operators are more likely to recognize the package-registry
   shape than alternatives. The triage flow ("did the 0.10.1 fix
   ship?" → look at version → check PyPI release notes) is
   friction-free when the names align.

4. **Langfuse-only (no §5.1 OTel attributes).** Add the rows
   only to §8.4.1 with descriptive source prose, deferring the
   §5.1 OTel attribute surface to a follow-on if an OTel-side
   use case surfaced. Rejected: the operator triage flow that
   motivates this proposal is the same across OTel-consuming
   backends (Phoenix, Datadog, Honeycomb, HyperDX, Grafana
   Tempo) as for the Langfuse Traces list view. Limiting to
   Langfuse would force every other OTel-consuming backend to
   either re-derive impl attribution from package manifests or
   wait for a follow-on proposal. The cost of adding §5.1
   attributes is two strings per invocation span; the benefit
   is symmetric attribution across the entire observability
   surface. Including both the §5.1 attributes and the §8.4.1
   rows in one proposal is the right scope.

5. **Runtime attribution** (Python interpreter version, OS, host).
   A distinct attribution axis from implementation identity;
   different lifecycle (per-process vs per-implementation). Out
   of scope; separate proposal if a use case emerges. The
   implementation identity proposal here is bounded to OA's own
   library; broader runtime context is a different concern.

6. **Compiled-graph identity** (which graph the trace was produced
   from, as distinct from the OA impl that ran it). Different
   axis again (graph identity, not runtime identity). Out of
   scope; separate proposal if a use case emerges.

7. **Optional fields instead of mandatory.** Make
   `implementation_name` and `implementation_version` optional
   (impls choose whether to emit them). Rejected: optional
   fields fragment the operator triage flow — the operator can't
   rely on the value being present, so the triage UX gets
   conditional ("if the field is present then ..."). Mandating
   them keeps the UX simple at the modest cost of two emitted
   strings per Trace.

## Open questions

None at draft time. The design choices are settled in the
proposal text above:

- **Two-field shape** (alternative 1) — `implementation_name` +
  `implementation_version` as separate keys for direct equality
  match in Langfuse UI.
- **Field naming** (alternative 2) — `implementation_name` /
  `implementation_version` (not `impl_*` or `library_*`).
- **Value convention** (alternative 3) — `openarmature-<language>`
  matching PyPI / npm package-registry shape.
- **OTel + Langfuse coverage** (alternative 4) — both surfaces
  in scope; §5.1 attributes for OTel-consuming backends, §8.4.1
  rows for Langfuse, sourced from the same §5.1 attributes.
- **Runtime + graph attribution** (alternatives 5 + 6) — out of
  scope; separate concerns.
- **Mandatory vs optional** (alternative 7) — mandatory; always-
  emit invariant pinned per §5.1 (with §8.4.1 Langfuse rows
  inheriting the invariant from the §5.1 attributes).

If reviewers surface a substantive question during PR review, it
gets resolved into the proposal text rather than left here as a
defer.

## Out of scope

- **Cross-cutting span emission.** The attributes emit on the
  **invocation span only** (per §5.1), not on every span in the
  invocation. Cross-cutting emission (the §5.6 attribute-family
  pattern used by `openarmature.user.*` etc.) is unnecessary
  for runtime-identity constants — the invocation span carries
  them once; OTel consumers correlate via trace_id /
  invocation_id to the invocation span for the lookup.
- **Runtime attribution** (alternative 5). Different axis; not
  bundled here.
- **Compiled-graph identity** (alternative 6). Different axis;
  not bundled here.
- **Pinning a versioning discipline** (semver vs CalVer vs
  custom). The spec mandates that `implementation_version`
  matches the package's release identity, not that the package
  uses semver. Impls choose their own versioning discipline.
- **Cross-impl version-string normalization.** Impls emit the
  raw `__version__` / `package.json` value; the spec does NOT
  mandate normalizing pre-release tags, build metadata, etc.
  across implementations. The operator-side triage UX accepts
  whatever the package registry emits.
- **Source verification.** The spec does NOT mandate that
  implementations verify the `__version__` value against the
  package they actually loaded from (vs an editable install,
  a forked build, etc.). Implementations report what
  `__version__` exposes; operator-side discipline handles
  unusual deployment shapes.
