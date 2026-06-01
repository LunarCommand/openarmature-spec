# Open questions backlog

Unresolved open questions surfaced in Accepted proposals. Captured here so
they don't get lost between releases, and so a future proposal drafting in
a related area can find prior discussion of the topic in one place.

This page does not list open questions from Draft proposals — those are
in-flight and get resolved during the acceptance pass. Once a proposal is
Accepted, any remaining Open Questions section migrates here.

**Status tags:**

- **still-relevant** — unresolved, still defers cleanly. Likely addressed by
  a follow-on proposal when signal accumulates.
- **resolved-by-acceptance** — the proposal's acceptance pass effectively
  decided the question (e.g., by picking one of two alternatives in the
  proposal text). Kept on the page for retrieval, marked as closed.
- **inherited** — restates a constraint from an earlier proposal; not a
  novel question. Kept for cross-referencing only.
- **candidate-for-new-proposal** — signal has accumulated; this OQ should
  drive a new proposal. (None currently.)

**Grooming cadence:** trigger-based. The questions get classified here when
(a) a proposal is being drafted in a related area, (b) ~5 acceptance passes
have stacked since the last grooming, or (c) every 6 months as a fallback —
whichever fires first. This page is the load-bearing artifact; the cadence
is just "keep it not-too-stale."

---

## graph-engine

### 0010 — bounded drain timeout

- **Cancellation mechanism for an in-flight observer.**
  [resolved-by-acceptance] — the spec resolved this as "implementation-
  defined" with the constraint that "the hard deadline itself is not
  negotiable." Implementations document their cancellation mechanism
  (`task.cancel()` in Python, `AbortSignal` in TypeScript, refusing to
  hand the worker the next event once the deadline is within an
  observer's expected latency budget, etc.). The spec sets the
  behavioral contract; impls pick the how.
- **Summary shape across languages.**
  [resolved-by-acceptance] — the spec resolved this by mandating the
  minimum fields (`undelivered_count`, `timeout_reached`) and leaving
  the carrier shape (Python `dict`/dataclass, TypeScript object, etc.)
  to per-language ergonomics. Implementations MAY add richer fields.

### 0012 — completed event after edges

- **Existing fixture 014 sub-case for routing_error.**
  [resolved-by-acceptance] — proposal text resolved to "020 alone (keeps
  fixtures topical)." The decision is embedded in the conformance suite as
  fixture 020.
- **Edge_exception fixture coverage today.**
  [still-relevant] — the proposal noted a phase 6.1 investigation would
  potentially surface coverage gaps. Hasn't been swept since.

## pipeline-utilities

### 0004 — middleware

- **Per-conditional-branch middleware.**
  [still-relevant] — deferred at acceptance; workaround documented
  (set a state marker at the routing node and branch on it inside per-node
  middleware). Revisit if real workflows surface that the workarounds don't
  cover. No signal accumulated yet.

### 0009 — per-instance fan-out resume

- **Does configurable batching also apply to subgraph-internal saves?**
  [still-relevant] — subgraph internals fire saves per §10.3 (unchanged from
  0008), and a long-running subgraph with many inner nodes could face
  similar volume concerns to fan-outs. Proposal explicitly scopes the §10.11.4
  batching knob to fan-out internals only for clarity; a follow-on can
  extend if signal demonstrates the need.
- **Should `fan_out_progress` be visible in the `list()` summary?**
  [still-relevant] — a user inspecting saved invocations might want to see
  "fan-out X is at instance 800 of 1000" without loading the full record.
  Lean was NOT-in-v2; add as a separate optimization if backends want richer
  summaries.
- **What happens if the graph topology changed between crash and resume
  (e.g., the user edited the fan-out's inner subgraph)?**
  [inherited] — restates 0008's "out of scope" declaration for
  resume-after-code-change. The resumed graph MUST be structurally
  identical to the original. Not a novel question; kept for cross-reference.

### 0011 — parallel branches

- **Branch ordering source.**
  [resolved-by-acceptance] — proposal's "lean" became the spec: insertion-
  order semantics mandated; implementations may use any equivalent shape
  (§11.1).
- **Cancellation precision under `fail_fast`.**
  [still-relevant] — when branch A fails under fail_fast, branches B and C
  are cancelled. If branch B's subgraph was mid-checkpoint-save, does the
  cancellation interact with checkpointing? Proposal noted "need to verify
  when both proposals are accepted." Both (0008 and 0011) are now Accepted;
  the verification hasn't been done. Revisit if a real workload surfaces an
  inconsistency.
- **Concurrency bound for parallel branches.**
  [still-relevant] — deferred at acceptance; M is small in practice. No
  signal accumulated.
- **Top-level timeout for parallel-branches node.**
  [still-relevant] — deferred at acceptance; users wrap with their own
  middleware or wait for a future timeout-middleware proposal.

## llm-provider

### 0019 — multi-provider wire-format extension

- **Numbering convention for §8 subsections.**
  [resolved-by-acceptance] — proposal text picked §8.1, §8.2, … nesting;
  the alternative (§8 → §8 OpenAI-compatible + §8.6+ Anthropic) was rejected
  in the acceptance pass.
- **Per-mapping section structure for §8.X.**
  [resolved-by-0026] — proposal 0026 locked the canonical §8.X template
  (Request mapping / Response mapping / Error mapping / Concurrency /
  Structured output) as a SHOULD-level recommendation, with allowance
  for sub-subsections and provider-specific top-level additions. When a
  §8.X proposal diverges, the proposal text SHOULD explain why so
  reviewers can confirm the divergence is structural rather than
  ergonomic. Shipped in spec v0.20.1.
- **What "Cross-language ambition" means in practice.**
  [still-relevant] — the §8 default placement rule says any mapping with
  multi-language ambition lives in spec. The first concrete test will be
  whether the spec maintainer accepts a new §8.X proposal on the grounds of
  "TypeScript port anticipated" or requires a concrete TypeScript
  implementation in flight. Lean was "former is fine"; worth clarifying in
  the first §8.X follow-on if reviewers push.
- **Byte-stable wire-mapping assertions across implementations.**
  [candidate-for-new-proposal] — the §8.X wire mappings are end-to-end
  tested via `expected_wire_request` captures (each impl compares against
  its language-native JSON shape). A future cross-impl conformance dimension
  could assert that the wire body produced by two implementations for the
  same spec input is byte-stable (similar in spirit to §10.11.1's
  exactly-once reducer invariants). Surfaced during 0025's implementation
  work as an observation that the matcher infrastructure is already in place
  — what's missing is the fixture shape that exercises cross-impl byte
  equality. Defer until a real cross-impl scenario surfaces; today this is
  single-impl territory (only the Python impl ships an §8.X mapping).
  Note: proposal 0047 (Accepted 2026-06-01) landed intra-impl byte
  stability, which is a distinct concern from this OQ's cross-impl framing
  — cross-impl byte equality remains deferred per the §5.5.1 caveat.

### 0024 — LLM span payload + GenAI semconv

No remaining open questions. Four questions raised during scope discussion
(payload default-off framing, request-parameter namespacing, tool-call
bundling, `gen_ai.system` override mechanism) were resolved during proposal
draft and are normative in spec text.

### 0025 — tool_choice

No remaining open questions. Two draft-time questions (force-specific shape:
discriminated-union vs flat; interaction with `finish_reason: "error"`
responses) were resolved in pre-PR review — discriminated-union shape kept
for extensibility; constraint-applies-to-request framing (response is what
the provider sent) is the spec's normative position without an explicit
response-side clause.

### 0032 — RuntimeConfig surface refinements

- **Null-skip rule location.**
  [resolved-by-acceptance] — placed in §6 (general declared-field
  semantics); future §8.X wire mappings inherit uniform null-skip behavior
  without re-derivation. The rule expresses what `None` / `undefined` means
  semantically, not how a specific wire format serializes it.
- **Range validation timing.**
  [resolved-by-acceptance] — deferred to the provider, surfaced via
  `provider_invalid_request`. Vendor ranges differ and the framework's job
  is to forward intent untouched.
- **Stop-field naming.**
  [resolved-by-acceptance] — declared field is `stop_sequences` matching
  the cross-vendor OpenTelemetry GenAI semconv and Anthropic / Gemini
  wire-key convention; the §8.1 OpenAI-compatible wire mapping translates
  to OpenAI's shorter request-body key `stop`.

### 0037 — Anthropic Messages wire-format mapping (§8.2)

- **Six design decisions resolved at draft.**
  [resolved-by-acceptance] — structured-output approach (native via
  `output_config.format` with tool-call-coercion and prompt-augmentation
  fallbacks); `max_tokens` required (pre-send rejection when absent);
  multiple `system` messages (concatenated with `\n\n` separator);
  extended-thinking treatment (§3.1 thinking + redacted-thinking blocks
  added as spec-level types with provider-bound round-trip signatures);
  prompt caching scope (out of scope for 0037); `tool` role round-trip
  (translates to/from `tool_result` content blocks per §8.2.1.2).

### 0038 — Google Gemini wire-format mapping (§8.3)

- **Gemini `seed` / `frequency_penalty` / `presence_penalty` support.**
  [resolved-by-acceptance] — verified against current Gemini
  `GenerationConfig`; §8.3.1 direct-maps all seven §6 declared fields (no
  `provider_invalid_request` for sampling fields, matching §8.1).
- **Full `finishReason` enum coverage.**
  [resolved-by-acceptance] — §8.3.2 maps `BLOCKLIST` /
  `PROHIBITED_CONTENT` / `SPII` to `content_filter`;
  `MALFORMED_FUNCTION_CALL` / `UNEXPECTED_TOOL_CALL` / `LANGUAGE` /
  `OTHER` to `"error"`; image-generation-only variants out of scope and
  fall to the `"error"` fallback.

## observability

### 0034 — caller-supplied invocation metadata

- **Six design choices resolved at draft.**
  [resolved-by-acceptance] — namespace prefix on OTel
  (`openarmature.user.*`, reserving the prefix for caller-supplied
  metadata going forward); cross-cutting scope (every span — invocation,
  node, subgraph, fan-out instance, LLM provider, retry attempt —
  matching `correlation_id`'s cross-cutting pattern); Langfuse placement
  (top-level on both `trace.metadata` and `observation.metadata` for
  direct UI filtering); API-boundary validation (reject namespace
  collisions at `invoke()` before any work begins, per-language error
  idiom); detached trace propagation (invocation-scoped, flows through
  detached children unchanged); frozen at invoke time as the original
  baseline (mid-invocation augmentation added by follow-on proposal
  0040; read symmetry added by follow-on proposal 0048 — the
  `get_invocation_metadata()` primitive returns an immutable mapping
  snapshot scoped to the current async context, mirroring the
  write-side copy-on-write isolation).

### 0040 — mid-invocation metadata open-span update

- **Five design decisions resolved at draft.**
  [resolved-by-acceptance] — MUST-level mandate conditioned on backend
  SDK support for in-place update (universal across mapped backends
  today); scope of "open spans" (augmenting context's own open spans
  and open descendants sharing the mutated copy; never ancestor or
  sibling spans — the per-async-context COW boundary); framework-
  emitted augmentation-event mechanism (RECOMMENDED; alternatives
  producing the same spans are permitted); distinct event kind not a
  new node `phase` (carries no `pre_state` / `post_state` / `error`;
  not subject to phases-subscription filtering); 029 / 030 tree shape
  with inner-node level as a real node-execution span per §4.
  Subsequent follow-on proposal 0045 rewrote §3.4's ancestor / sibling
  boundary into a lineage-aware three-rule structure (call-stack
  ancestor chain MUST, sibling MUST NOT, shared-parent MUST NOT) to
  cover nested fan-out / parallel-branches cases the original 0040
  scope didn't address. Proposal 0048 added the read-side symmetric
  primitive (`get_invocation_metadata()`) that consumes the same
  copy-on-write state 0040's augmentation event signals to backends —
  reads do NOT emit augmentation events.

### 0041 — reserve OA-emitted Langfuse metadata keys

- **Four design decisions resolved at draft.**
  [resolved-by-acceptance] — reserve-at-API-boundary chosen over
  nesting (which breaks Langfuse top-level filtering) and over
  precedence (which silently drops caller data); reservation is
  universal / backend-set-independent (same caller code is valid
  against any wired backend); exact whole-key match (not prefix);
  list-maintenance rule requires future top-level OA metadata keys
  to extend the reserved set in the introducing proposal. Subsequent
  follow-on proposal 0042 extended the set with `branch_name`,
  `detached`, `detached_from_invocation_id` per the maintenance rule.

## prompt-management

### 0033 — prompt-management surface refinements

- **`sampling` field name.**
  [resolved-by-acceptance] — settled at `sampling`; bounds the field
  to its actual contents (sampling parameters mirroring
  `RuntimeConfig`). Alternatives `prompt_config` / `runtime` /
  `params` overpromise scope, are ambiguous out of context, or
  collide with `parameters` in llm-provider §4 (and `model_config`
  is Pydantic-reserved).
- **`LabelResolver` section placement.**
  [resolved-by-acceptance] — new §7 with existing §7-§13 renumbered
  to §8-§14. Sibling placement matches the dependency graph (the
  resolver is a first-class primitive `PromptManager` consumes) and
  gives the primitive its own discoverable section.
- **Langfuse Prompt-entity reference location.**
  [resolved-by-acceptance] —
  `Prompt.observability_entities['langfuse_prompt']` (typed field).
  Replaces proposal 0031's implementation-defined `metadata`-key
  placeholder; the `observability_entities` mapping accommodates
  future observability backends (Phoenix, Honeycomb LLM lens)
  without per-vendor pollution on Prompt's primary surface.

## sessions

### 0020 — sessions capability

- **Reducer semantics for §4.1 full-state load.**
  [still-relevant] — spec mandates REPLACE (loaded state replaces
  the supplied initial state). A caller needing merge logic can do
  it explicitly in user code. Revisit if a real workload
  demonstrates the recommendation is wrong; mild signal would
  warrant a follow-on.
- **`SessionRecord` field set RECOMMENDED extensions.**
  [still-relevant] — spec leaves backend extensions (`created_at`,
  `updated_at`, version counter) backend-defined. A follow-on could
  name extensions RECOMMENDED for cross-backend consistency in
  observability dashboards. Mild signal accumulated by writing the
  initial sessions backend; not yet enough to drive a follow-on.
- **Migration in core proposal vs spin-off.**
  [resolved-by-acceptance] — proposal included migration in core §7.
  Reviewers can split it out via a follow-on if migration grows
  complex enough to warrant its own spec; the §7 migration section
  lifts out cleanly.
- **`session_state_migration_chain_ambiguous` vs sharing checkpoint
  category.**
  [resolved-by-acceptance] — separate categories; the two lifecycle
  scopes benefit from distinct error surfaces for observability and
  operator tooling.
- **`with_session_store()` registration scope.**
  [resolved-by-acceptance] — per-graph registration, consistent with
  `with_checkpointer` from proposal 0008.

---

## How to use this page

**Drafting a proposal in an area touched by an OQ?** Reference the OQ in
the Motivation section. The OQ has prior discussion of constraints,
alternatives considered, and the deferral reason — better starting context
than re-deriving from scratch.

**Resolving an OQ via a new proposal?** When the new proposal is Accepted,
update the OQ here to `resolved-by-NNNN` (or remove the line and leave a
short pointer entry — author's call).

**Spotting an OQ that's actually stale (the spec evolved around it)?**
Update to `inherited` (if subsumed by another proposal's contract) or
`resolved-by-NNNN` (if a specific later proposal made it moot). If neither
applies and the question genuinely no longer matters, remove the entry
with a note in the commit message about why.

**Not seeing your OQ?** This page covers Accepted proposals only. Drafts
have their OQs in the proposal file itself, awaiting acceptance.
