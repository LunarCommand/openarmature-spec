# External-dependency compatibility

**Last refreshed:** 2026-05-31

OpenArmature normatively references several external specifications and APIs.
This page is the **operational tracking artifact** for those references:
pinned versions, last-verified dates, and per-dependency adoption notes.

The **normative policy** governing how OA adopts upstream changes lives in
[Governance — External-dependency adoption](governance.md). In brief:

- OA normatively adopts upstream attribute names / wire shapes **only when
  the upstream marks them Stable** (or equivalent maturity marker per
  upstream governance).
- Pre-stable upstream attributes (Development, Experimental, Beta, etc.)
  are mirrored to the `openarmature.*` namespace until they stabilize.
- OA implementations MUST emit the OA-namespace names when this spec
  mandates OA-namespace mirroring — they MUST NOT jump ahead to
  upstream pre-stable attribute names.

**Stability vocabulary.** Each upstream uses its own maturity vocabulary —
OA tracks whatever marker the upstream itself uses (OpenTelemetry semconv
uses `Stable` / `Development` / `Experimental` / `Deprecated`; semver SDKs
use pre-release tags vs. stable releases; IETF uses publication track —
Standards Track, Best Current Practice, Informational, etc.). The
**Upstream status** column below records the marker as the upstream
publishes it.

## Compatibility matrix

| Dependency | OA-tracked version / scope | Upstream status | Last verified | Notes |
|---|---|---|---|---|
| [OpenTelemetry semantic conventions](https://github.com/open-telemetry/semantic-conventions) | v1.41.1 (release) | Mixed (per attribute) | 2026-05-31 | Stable attributes adopted directly via `gen_ai.*` / `otel.*`. Development attributes (e.g., `gen_ai.usage.cache_read.input_tokens`) are NOT normatively adopted; OA mirrors them to `openarmature.*` until upstream stabilization per the governance rule. |
| [OpenTelemetry trace + span core spec](https://opentelemetry.io/docs/specs/otel/trace/) | Tracking v1.41.x line | Stable | 2026-05-31 | Span / attribute / status semantics referenced in observability §3–§7. |
| [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat) | URL-path `v1`; ChatCompletions shape | Stable (continuously updated) | 2026-05-31 | Wire shape per llm-provider §8.1. `usage.prompt_tokens_details.cached_tokens` confirmed present for prompt caching (≥1024-token threshold). |
| [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) | URL-path `v1`; Responses shape | Stable (continuously updated) | 2026-05-31 | Newer companion API shape; `usage.input_tokens_details.cached_tokens` rather than `prompt_tokens_details`. Not currently referenced by llm-provider §8.X. |
| [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) | Header `anthropic-version: 2023-06-01` | Stable (date-versioned) | 2026-05-31 | Wire shape per llm-provider §8.2. **No implicit caching** — `cache_read_input_tokens` / `cache_creation_input_tokens` fire only under explicit `cache_control` annotations. |
| [Google Gemini API](https://ai.google.dev/api) | URL-path `v1`; model `gemini-2.5+` for implicit caching | Stable (URL-path versioned) | 2026-05-31 | Wire shape per llm-provider §8.3. Implicit caching default-on for Gemini 2.5+ models; `cachedContentTokenCount` populated in `usageMetadata` for both implicit and explicit cache hits. |
| [Langfuse Python SDK](https://github.com/langfuse/langfuse-python) | v4.7.1 | Stable v4.x | 2026-05-31 | Used by observability §8 Langfuse mapping. v5 announcement watched; `set_current_trace_io` marked deprecated in v4 per observability §8.4.1 caveat. |
| [JSON Schema](https://json-schema.org/specification) | draft-2020-12 | Released (latest draft) | 2026-05-31 | Used in llm-provider §4 `Tool.parameters` and §5 `response_schema`. |
| [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119) — keyword conventions | RFC 2119 (Best Current Practice) | Published | 2026-05-31 | MUST / SHOULD / MAY usage across normative spec text. |
| [RFC 2397](https://datatracker.ietf.org/doc/html/rfc2397) — data URI scheme | RFC 2397 | Published | 2026-05-31 | Used by llm-provider §3.1.3 inline-image source shape. |

## Per-dependency detail

### OpenTelemetry semantic conventions

OpenArmature observability §3–§7 reference the OpenTelemetry semantic
conventions for cross-vendor attribute naming. The semconv has a
per-attribute stability model — individual attributes carry their own
status (Stable, Development, Experimental, Deprecated) independent of the
release tag.

OA's adoption pattern:

- **Stable attributes**: adopted directly via the `gen_ai.*` / `otel.*`
  namespace (e.g., `gen_ai.system`, `gen_ai.request.model`,
  `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`).
- **Development / Experimental attributes**: mirrored to the
  `openarmature.*` namespace until upstream stabilization. As of
  2026-05-31, the cache-token attributes
  (`gen_ai.usage.cache_read.input_tokens` /
  `gen_ai.usage.cache_creation.input_tokens`) are marked Development.
  OA uses the OA-namespaced equivalents
  (`openarmature.llm.cache_read.input_tokens` /
  `openarmature.llm.cache_creation.input_tokens`) until they stabilize
  upstream; a follow-up OA proposal will migrate to the upstream
  `gen_ai.usage.*` names once they reach Stable.
- **`gen_ai.operation.name`** (with documented well-known values
  including `"chat"`, `"embeddings"`, etc.) is at Development status
  as of 2026-05-31. Per the policy above, OA does NOT normatively
  adopt this attribute in v1; operation discrimination is via span
  name + provider (observability §5.5 `openarmature.llm.complete` for
  LLM completion and §5.5.8 `openarmature.embedding.complete` for
  embedding). A follow-on proposal will add `gen_ai.operation.name`
  to the attribute surface once upstream reaches Stable, per the
  §5.5.3.1 / 0047 mirror pattern.

### LLM provider APIs (OpenAI / Anthropic / Google Gemini)

These APIs do not semver their wire shapes. They version via:

- **URL path** (e.g., `v1` for OpenAI / Gemini)
- **Header date** (e.g., `anthropic-version: 2023-06-01`)
- **Model identifier** (e.g., `gpt-4o-2024-08-06`, `claude-sonnet-4-5`)

Per-row "Last verified" dates carry the drift-detection weight for these
dependencies. The wire mappings under llm-provider §8.X are written against
the API shape verified as of that date; spec proposals that update an
existing §8.X mapping include a re-verification step.

### Langfuse SDK

Langfuse has a public Python SDK that OA's observability §8 Langfuse mapping
implementations rely on. The SDK semvers; OA tracks the latest stable v4.x
release.

A vendor-side deprecation of `set_current_trace_io` / `Span.set_trace_io`
(used to populate `trace.input` / `trace.output` per §8.4.1) is documented
in observability §8.4.1 (caveat paragraph). When Langfuse v5 ships, OA
re-verifies the §8 mapping; if the migration requires normative spec
changes, a follow-up proposal lands.

## Maintenance

### When to update this page

- An OA proposal adds or changes a normative reference to an external
  artifact (the proposal's Accept-phase work includes a row update or new
  row, plus refreshing the page-level **Last refreshed** date).
- A periodic re-verification round confirms the existing rows still match
  current upstream documentation (the per-row "Last verified" date updates
  in place; if drift is detected, a follow-up proposal addresses the
  change).
- An upstream announcement (e.g., the Langfuse SDK v4 → v5 transition)
  warrants pre-emptive tracking. Drift discovered between verifications
  is logged with an additional note rather than silently absorbed.

### Verification cadence guidance

Per-dependency drift rates vary; suggested starting cadences:

- **LLM provider APIs** (OpenAI / Anthropic / Gemini): quarterly, plus
  any spec proposal touching the relevant §8.X mapping.
- **OpenTelemetry semconv**: per upstream release-tag bump (the upstream
  publishes a [release feed](https://github.com/open-telemetry/semantic-conventions/releases)
  worth watching).
- **Vendor SDKs** (Langfuse, etc.): per upstream minor release.
- **IETF RFCs** (2119, 2397, etc.): opportunistic — these rarely change.

These are starting points, not rules. Adjust as the dependency's actual
drift rate becomes apparent.

### How to add a new dependency

When OA's spec adds a new normative reference to an external artifact:

1. **Add a row to the compatibility matrix.** Required columns: dependency
   name (with link), OA-tracked version / scope, upstream status, last
   verified date (today), notes (which spec sections reference it, any
   adoption nuances).
2. **Add a per-dependency detail section** under *Per-dependency detail*
   if the adoption has nuance — per-attribute stability rules, partial
   adoption, vendor-specific framing, etc. Simple dependencies (a single
   stable artifact) can stay matrix-only.
3. **Refresh the page-level Last refreshed date** at the top of this
   page.
4. **Cite the new entry** in the proposal text that added the reference
   (the proposal links to this page for the operational tracking; the
   normative reference itself lives in the spec text).

The page is freely editable per the governance "charter / docs" carve-out
([Governance](governance.md)) — small re-verification updates do not
require a proposal. Normative spec changes that flow from a re-verification
(e.g., adopting a newly-Stable upstream attribute) DO require a proposal
per the standard discipline.
