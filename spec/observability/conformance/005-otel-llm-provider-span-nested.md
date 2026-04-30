# 005 — LLM Provider Span Nested Under Calling Node

Verifies §5.5 (LLM-provider span MUST emit) and §6 (TracerProvider isolation MUST). The
`openarmature.llm.complete` span sits as a child of the calling node span, carries the §5.5
attributes, and — critically — is NOT visible to any external (global) OTel TracerProvider that
the caller's process may have configured for its own auto-instrumentation. Three sub-cases.

**Spec sections exercised:**

- §5.5 LLM-provider span — MUST emit one `openarmature.llm.complete` per `complete()` call;
  attribute set covers model, finish_reason, and usage breakdown.
- §5.5 `disable_llm_spans` opt-out — caller may suppress just the LLM-provider span when an
  external auto-instrumentation library (OpenInference, opentelemetry-instrumentation-openai,
  etc.) is already covering the same call.
- §6 TracerProvider isolation — openarmature MUST emit through its own private
  TracerProvider; spans MUST NOT appear on the global provider, preventing duplicate signals
  for callers running their own instrumentation pipelines.

**Cases:**

1. `default` — single node calls a mock OpenAI-compatible provider. The LLM span emits as a
   child of the node span with the full §5.5 attribute set.
2. `disable_llm_spans` — observer constructed with `disable_llm_spans=True`. Node span still
   emits; LLM span does not. The `no_llm_provider_span` invariant is asserted.
3. `external_auto_instrumentation_active` — harness installs a SECOND in-memory exporter on the
   global TracerProvider and emits an `external.llm.call` span through it (simulating an
   external auto-instrumentation library). openarmature's spans MUST appear only on the
   private exporter; the external span MUST appear only on the global exporter. The
   `no_openarmature_spans_on_global` invariant is the load-bearing check.

**What passes:**

- Case 1: span_tree shows `invocation → ask_llm → openarmature.llm.complete` with the listed
  attributes; status OK on every span.
- Case 2: `ask_llm` has zero children; `no_llm_provider_span: true`.
- Case 3: private exporter contains the openarmature tree; global exporter contains exactly one
  `external.llm.call` span and zero openarmature spans.

**What fails:**

- LLM span absent in case 1, or attached at the wrong parent (e.g., directly under
  `openarmature.invocation` instead of the node).
- Case 2: an LLM span still emits despite `disable_llm_spans=True` — the opt-out wasn't honored.
- Case 3: any `openarmature.*` span appears on the global exporter — TracerProvider isolation
  is broken and external instrumentation will see duplicate signals for every node, fan-out
  instance, retry attempt, and LLM call.
