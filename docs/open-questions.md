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
- **resolved-by-NNNN** — a *later* numbered proposal settled the question.
  Kept on the page for retrieval, marked as closed, with a pointer to the
  proposal that decided it.
- **inherited** — restates a constraint from an earlier proposal; not a
  novel question. Kept for cross-referencing only.
- **candidate-for-new-proposal** — signal has accumulated; this OQ should
  drive a new proposal.

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

### 0054 — per-invocation event drain

- **Ambient-scope drain helper (implicit `invocation_id`).**
  [still-relevant] — v1 chose an explicit `invocation_id` parameter for
  `drain_events_for`; an ambient-scope helper that infers the current
  invocation can land later if ergonomics warrant. No signal accumulated.

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

### 0050 — retry and degradation primitives

- **Multiplicative retry-budget cap.**
  [still-relevant] — per-call and per-node retry budgets can compound
  multiplicatively; v1 leaves this uncapped and documents it in the
  common-mistakes list rather than enforcing a combined ceiling. Revisit
  if a real workload is bitten by the compounding.
- **Typed middleware-event variant.**
  [still-relevant] — retry / degradation emit a framework-emitted event in
  v1; a future proposal MAY promote it to a typed variant family (like the
  LLM / tool event variants) if accumulation warrants.

### 0068 — failure-isolation event structured cause chain

- **§6.1 retry classification stays single-level while §6.3 cause resolution
  walks the full chain.** [still-relevant] — 0068's §6.3 cause chain walks the
  entire cause chain (skipping all `node_exception` carriers) to derive the
  reported category, while §6.1's default retry classifier checks only the
  exception and its direct cause (single-level). The asymmetry is deliberate,
  not an oversight: retry's usual placement is the inner node body (≤1 wrap), so
  single-level suffices there, and having an *outer* retry (e.g. at an instance /
  branch placement) re-run an entire subgraph because of a deeply-nested
  transient is the wrong grain. After 0068, the failure-isolation *event* can
  report a nested originating cause that an outer retry at the same placement
  would not itself have retried — the event and the retry decision answer
  different questions. Revisit only if retry-at-a-non-node-placement-over-
  deeply-nested-carriers becomes a real workload need; the fix would be a shared
  "resolve actionable category through carriers" primitive used by both §6.1 and
  §6.3 (a §6.1 behavior change, its own proposal). 0065's acceptance already
  flagged the §6.1 nested-wrapper wording as a separate §6.1 concern; this
  records the post-0068 shape.

### 0074 — failure-isolation cause-chain catch

- **Richer §6.4 classification surface (predicates over the cause chain).**
  [still-relevant] — 0074's catch matches against a category set with a
  predicate escape hatch; a future proposal could promote a richer
  predicate-over-the-full-chain classification surface if usage
  accumulates. The category-set + escape hatch suffice for now.

### 0075 — parallel lightweight / conditional branches

- **"At least one branch must dispatch" guard.**
  [still-relevant] — an all-branches-skipped parallel node is a silent
  no-op in v1; a small additive follow-on (a node-level flag asserting at
  least one branch dispatches) can add the guard if workflows want it. Not
  a v1 concern.

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

### 0062 — LLM completion streaming

- **Direct node-body stream consumption.**
  [still-relevant] — v1 streaming is observer-only (token events on the
  event stream); a direct consumption mode (incremental parsing, early
  stop, an async-iterator return shape from `complete()`) is purely
  additive and deferred until a consumer needs it.
- **Tool-call argument delta token events.**
  [still-relevant] — v1 streams content and reasoning deltas only; the
  `delta_kind = "tool_call"` value is reserved for a follow-on that
  streams tool-call argument deltas.

## retrieval-provider

### 0059 — embedding provider

- **Tiered payload preview mode.**
  [still-relevant] — embedding payloads are all-or-nothing under
  `disable_provider_payload`; a future observability proposal MAY add a
  tiered preview (truncated input strings + first-N vector dimensions).
  Out of scope for 0059.
- **`gen_ai.operation.name` adoption.**
  [still-relevant] — not adopted in v1 (upstream Development); operation
  discrimination rides span name + provider. MAY be added in a follow-on
  when upstream reaches Stable, per the stable-only adoption policy.

### 0078 — Jina wire-format mapping

- **Widening `input_type`'s normative value space.**
  [resolved-by-0099] — the framing was wrong: recognition is **per-mapping,
  not protocol-level**. §2 already types `input_type` as an extensible string
  and already delegates the decision ("additional well-known values MAY be
  recognized by mappings whose backend supports them"), so no §2 change is
  needed for a mapping to accept `classification` / `clustering`. 0099
  exercised that for §8.4 Cohere, whose backend supports them uniformly.
  What survives is the reason a mapping may still decline: **model-dependent
  backend support**. Jina's `task` values differ across its embedding models
  (some accept `classification` but not `clustering`; some accept neither),
  and a provider is bound to a model identifier with no capability registry,
  so §8.2 keeps its closed set and its non-retrieval tasks continue to ride
  the extras bag — which works there because `task` is an *undeclared* key
  and is omitted when `input_type` is absent.

### Cross-cutting — `model` / `response_model` response-vs-event consistency

- **A provider that returns a malformed, absent, or empty-string model
  identifier is handled inconsistently between a response and its own typed
  event.** [candidate-for-new-proposal] — surfaced drafting 0100 / 0101, which
  scoped it out to keep the ancillary-figure rule clean; 0104 added the
  **empty-string** dimension by pinning that an empty-string `response_id` is
  absent (not present-as-`""`) — the parallel empty-string question for the
  non-nullable `model` / `response_model` is left to this same pass (does the
  bound-id fallback treat `""` as absent, the way `response_id` now does?).
  `EmbeddingResponse.model` / `RerankResponse.model` (retrieval §4 / §6) are
  **non-nullable**, with an established fallback to the bound model
  identifier where the provider returns none (§8.4). But the typed events
  carry a separately-declared `response_model` (graph-engine §6,
  `string | null`), and the OTel span sources `gen_ai.response.model` from
  it — so the response and its own event already disagree about whether the
  provider's returned model can be absent. llm-provider is worse: its §6
  `Response` declares **no** `response_model` at all, yet
  `LlmCompletionEvent.response_model` and `gen_ai.response.model` both exist
  and are sourced from `raw`. So a provider returning `model: 7` has no
  defined outcome on any of these surfaces. 0100 / 0101 pin the *usage* and
  *response_id* figures and deliberately leave `model` / `response_model` to
  a dedicated pass, because reconciling it means deciding whether the
  bound-id fallback applies to a *malformed* (not merely absent) value, and
  aligning the non-nullable response field with the nullable event field —
  a model-identity question, not a usage-figure one.

### Cross-cutting — should §7's payload enumeration generalize?

- **A type-malformed payload field outside the four enumerated invariants has
  no defined outcome.** [candidate-for-new-proposal] — surfaced drafting 0100,
  which deliberately declined to answer it. retrieval-provider §7 defines
  `provider_invalid_response` by a **closed list**: "missing required fields,
  or a violation of the capability's cross-impl invariants (embedding §4 —
  mismatched vector count, inconsistent dimensions; rerank §6 — out-of-range
  or duplicate `index`, more results than `top_k`)". A `relevance_score`
  returned as the string `"0.9"`, or an `index` as `"2"`, is neither missing
  nor an enumerated invariant violation — so nothing today forbids a tolerant
  implementation from coercing it, and nothing requires a strict one to raise.
  Two conforming implementations diverge.
  Evidence the general rule does not already exist: **0097 had to add a
  per-field raise rule** for a malformed `document` echo. If §7's enumeration
  were general, it would not have needed to.
  0100 pins the *ancillary* side (a malformed `usage` counter or `response_id`
  is not reported → absent, never a raise) and explicitly adds **no** payload
  obligation, precisely so this question is not smuggled into it. The payload
  side wants its own answer: generalize §7 to "any type-malformed payload
  field raises", field-by-field like 0097, or state that tolerant coercion is
  permitted. Whichever, it needs fixtures — today there are none for a
  type-malformed payload field outside the four invariants.

### Cross-cutting — extras key vs mapping-managed wire field

- **What happens when an extras-bag key collides with a wire field the
  mapping itself manages?** [resolved-by-0105] — 0105 added the general rule
  to llm-provider §6 (*Managed-field collision*, inherited by retrieval §10):
  posture **(a)** below — a managed field governs a colliding key, **merged**
  where list-shaped, **rejected pre-send** where a conflicting **non-additive**
  value — a scalar mode-switch or an object the mapping constructs wholesale (a
  matching value is a no-op); each §8.x mapping MUST enumerate its managed
  keys. It ratified 0099's `embedding_types` merge as an instance and declared
  the fail-loud `truncate` / `truncation` flags managed scalars (§8.1 / §8.2 /
  §8.4). Kept below for retrieval. Original framing (deferred by 0099, which
  pinned one instance and explicitly declined the general rule):
  llm-provider §6 says an *undeclared* field is forwarded to the wire body
  **untouched** and "MUST NOT translate, rename, or otherwise transform" it —
  but scopes that to what "the wire-format mapping (§8)" defines, and says
  nothing about a key the mapping also **manages**. Two conforming
  implementations can therefore diverge: one forwards untouched, one lets the
  mapping win, one silently drops the extra.
  0099 resolved the §8.4 Cohere `embedding_types` instance as an explicit,
  **mapping-local exception**: the mapping manages the key (it must request
  `"float"` for its own response consumer), so an extras-supplied value is
  *merged* with `"float"` rather than replacing it — an override would strip
  the very key the mapping reads and fail the call. The same shape recurs
  wherever a mapping manages a wire field and also advertises extras (§8.4's
  `truncate` / `input_type`, §8.2's `truncation` / `task`, §8.3's note that a
  server extending the wire "with its own `input_type`-style field" takes it
  through the bag — which is impossible if that field is literally named
  `input_type`, since a *declared* field can never ride the bag).
  A general rule belongs in llm-provider §6 with an §8 pointer. Candidate
  postures: (a) a managed field always wins — a colliding extras key is
  merged where the field is list-shaped, else rejected pre-send; (b) extras
  always win (maximally transparent, but lets a caller break a mapping's own
  response consumer — exactly the failure 0099 prevented); (c) per-field,
  declared by each mapping (precise, but re-derived per vendor and leaves the
  default undefined). Auditing every §8.x mapping for managed-field-vs-extras
  interactions is most of the work.
- **Remaining follow-on (post-0105): the *declared-field-vs-extras* collision,
  and the `encoding_format` scalar.** [candidate-for-new-proposal] — 0105 added
  the general managed-field rule and enumerated the *managed-internal* keys
  across both capabilities (retrieval `embedding_types` merge + the §8.1 / §8.2 /
  §8.4 truncation-flag reject; llm-provider §8.1 structural `model` / `messages` /
  `tools` / `tool_choice`, §8.1.5 `response_format`, §8.1.6 `stream_options`
  reject). What it **deferred** is a structurally different collision: a wire key
  that **realizes a declared OA field** shadowed by an extras key of the wire
  name — **§8.2 Jina `task`** (from the declared `input_type`), llm **`stop`**
  (from `stop_sequences`), and llm **`stream`** (from `complete(stream=…)`). These
  are *not* the managed-internal-field rule (the caller has a declared way to set
  the field; the extras key uses the wire name); the design question — does the
  wire-name extras override the declared-field realization, or is it rejected /
  merged — needs its own pass and must be settled uniformly for all three, since
  they share the mechanism. Also open: **§8.3's `encoding_format`** (a scalar
  mode-switch structurally parallel to the reject arm — see the §8.3 base64 entry
  below, and the deferred output-encoding work; a reject-now would become a
  reject-then-reverse once base64 output support lands). Each needs a per-field
  decision.

### Cross-cutting — §8.3 `encoding_format: "base64"` advertised via extras

- **§8.3 advertises a knob that would break its own response consumer.**
  [candidate-for-new-proposal] — surfaced auditing 0099. §8.3 says the mapping
  "does not send `encoding_format` by default (OpenAI's wire default is
  `\"float\"`); `\"base64\"` rides the extras-pass-through bag." Unlike 0099's
  `embedding_types` case this is *not* a managed-field collision — the key is
  undeclared and unmanaged, so it reaches the wire untouched exactly as
  llm-provider §6 requires. That is the problem: OpenAI then returns
  `data[].embedding` as base64 **strings**, which this mapping consumes as
  float vectors, blowing §4's dimensionality invariants and failing the call
  `provider_invalid_response`. So the sentence advertises a working knob that
  cannot work — the same false-promise shape 0099 purged from §8.4, and now
  the one left unpinned. Options: state that the mapping requires `float` and
  define what happens when `base64` is supplied (reject pre-send, or decode
  it), or stop advertising the knob. Needs a proposal either way, since it
  changes §8.3 behavior.

### Cross-cutting — §8 embedding-mapping per-call input caps

- **Chunk-and-stitch when input exceeds the vendor per-call cap.**
  [resolved-by-0092] — surfaced drafting 0091 (Cohere embeddings).
  Cohere `/v2/embed` caps inputs at 96 per request, and 0091 specs mandatory
  client-side chunk-and-stitch for it (the §8.1 TEI rerank-chunking argument
  applied to embeddings, where each vector is independent of the others in its
  batch). But the other accepted embedding mappings — §8.1 TEI `/embed`, §8.2
  Jina, §8.3 OpenAI — do not address their own per-call input caps (OpenAI's
  ~2048-input limit, Jina's batch limits, TEI's `max-client-batch-size`), so a
  caller embedding more inputs than a mapping's cap has undefined behavior
  there. A follow-on could settle this uniformly — either a general §8 rule
  ("an embedding mapping MUST chunk-and-stitch when input exceeds the vendor
  per-call cap, preserving input order") or per-mapping additions — rather than
  each vendor mapping re-deriving it. 0091 closed only the Cohere instance;
  **proposal 0092 (Accepted, v0.87.0) added the general §8 *Batch chunking*
  rule** — every embedding mapping now chunk-and-stitches over its provider's
  documented per-call cap (TEI `max-client-batch-size`, OpenAI 2048, Cohere 96;
  Jina is cap-free), with the caps recorded in `docs/compatibility.md`.

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

### 0051 — Langfuse trace I/O deprecation caveat

- **Langfuse SDK v5 migration.**
  [still-relevant] — no proposal for a v5 migration ahead of vendor
  publication, and no placeholder Draft; deferred until Langfuse publishes
  v5 migration guidance. Tracked against `docs/compatibility.md`. An
  external trigger, not a planned follow-on.

### 0053 — shared-parent boundary clarification

- **Dedicated pure-serial-lineage conformance fixture.**
  [still-relevant] — the shared-parent rule is exercised by existing
  fixtures; an optional follow-on MAY add a dedicated pure-serial-lineage
  fixture if cross-impl coverage warrants. Minor.

### 0061 — detached-trace invocation span

- **Detached-trace subgraph-wrapper span naming vs §4.5.**
  [still-relevant] — surfaced during the 0061 acceptance review. §4.5's
  span-names table names a subgraph span after *the SubgraphNode's name in
  the parent graph* (e.g. `dispatch`), but the detached-trace fixtures name
  the subgraph-wrapper span at the detached trace's root after the *compiled
  subgraph* (`long_running_workflow` in fixture 008, `detached_workflow` in
  fixture 058), not the dispatching node. This is pre-existing in fixture 008
  and is now pinned for 058 by 0061's acceptance; 0061 deliberately did not
  touch it (its charter was the invocation-span root, not subgraph-span
  naming). A future observability proposal could clarify §4.5 to state the
  naming rule *per trace* — the detached trace's outermost subgraph renders
  under its own compiled name while the parent trace's dispatch span keeps the
  SubgraphNode name — or reconcile the fixtures the other way. Low-stakes (a
  cosmetic span label, no identity or correlation impact), so it defers
  cleanly until a related observability proposal is in flight.

### 0063 — tool-execution observability

- **Upstream GenAI tool semconv adoption.**
  [still-relevant] — v1 mirrors tool attributes under the `openarmature.*`
  namespace (the upstream `execute_tool` span / `gen_ai.tool.*` surface is
  Development); a follow-on adopts the upstream names when they become
  recognized-core / Stable, per the stable-only policy. Related to the
  0073 `gen_ai.system` migration question.
- **Independent per-operation tool-payload privacy gating.**
  [still-relevant] — tool payloads reuse `disable_provider_payload` for
  now; a future proposal can introduce per-operation gating if a consumer
  demonstrates the need.

### 0073 — GenAI semconv adoption reconciliation

- **Timing of the `gen_ai.system` → `gen_ai.provider.name` migration.**
  [still-relevant] — 0073's post-adoption retention rule keeps OA emitting
  `gen_ai.system` even though upstream removed it in favor of
  `gen_ai.provider.name` (itself Development). A future proposal decides when to
  migrate — when `gen_ai.provider.name` reaches Stable, or when the ecosystem
  has demonstrably moved to it. Tracked in `docs/compatibility.md`.
- **Whether the core-vs-peripheral `gen_ai.*` classification should be enumerated
  normatively.** [still-relevant] — 0073 uses a descriptive criterion
  ("recognized by the broad installed base") applied per attribute as proposals
  add them, rather than a fixed list of "core" names. A future proposal MAY
  enumerate the core set if the criterion proves ambiguous in practice.

### Cross-cutting — Langfuse observation-type coverage

- **§8 maps onto a subset of Langfuse's observation types; the
  remaining types are each gated on an OA construct that doesn't yet
  exist.** [still-relevant] — surfaced during proposal 0059 drafting via
  verification against current Langfuse docs. Langfuse exposes 10
  observation types: `Event`, `Span`, `Generation`, `Agent`, `Tool`,
  `Chain`, `Retriever`, `Evaluator`, `Embedding`, `Guardrail`. The
  existing `spec/observability/spec.md` §8 mapping uses `Trace`,
  `Generation`, `Span`, `Event`; proposal 0059 adds `Embedding`;
  proposal 0060 adds `Retriever`; proposal 0063 adds `Tool`. The other
  four (`Agent`, `Chain`, `Evaluator`, `Guardrail`) are unmapped.

  **"Full coverage" is not a single mapping proposal.** The structural
  reason: OA's observability types its spans by *execution role*
  (invocation / node / subgraph / fan-out / LLM / embedding / rerank),
  while these five Langfuse types are typed by *application semantics*
  (this is an agent step / a tool call / a guardrail). OA has no
  semantic-role layer, so each unmapped type needs an OA construct that
  doesn't exist — it can't be conjured by a Langfuse mapping alone. Per-type
  verdict (after verifying each type's Langfuse semantics against current docs):

  - **Tool** ("a tool call, e.g. to a weather API") — **mapped by
    proposal 0063 (tool-execution observability), Accepted.** 0063 adds the
    `ToolCallEvent` / `ToolCallFailedEvent` typed variants (graph-engine
    §6) + a node-body instrumentation scope, and maps tool execution onto
    Langfuse's dedicated `Tool` observation type. OA supplies the
    observability primitive; the tool-loop itself stays a user-authored
    graph (orchestration is not an OA primitive). This closed the `Tool`-type
    gap on 0063's acceptance.
  - **Evaluator** ("assess relevance/correctness/helpfulness") — needs
    an OA **evaluation capability** that doesn't exist. Out of scope until
    such a capability is proposed on its own merits (its Langfuse mapping
    rides on it).
  - **Guardrail** ("protects against malicious content or jailbreaks") —
    needs an OA **guardrail capability** that doesn't exist. Same posture
    as Evaluator.
  - **Agent / Chain** — **declined.** OA's structural span typing is
    deliberate; an OA agent *is* a graph (already `Trace` + spans) and an
    OA subgraph *is* a `Span`. Mapping these semantic-role types would
    require a user-facing annotation surface ("mark this subgraph as an
    agent / chain") that OA does not have and does not want. The dedicated
    Langfuse types add no semantic precision over the existing `Trace` /
    `Span` mapping for OA's model.

### 0083 — a declared `token_budget` bound of `0`

- **What should a `0` token-budget bound signal?** [candidate-for-new-proposal]
  — surfaced implementing 0083. prompt-management §3 declares the bounds
  **non-negative**, so `0` is a legal `input_max_tokens` / `total_max_tokens`,
  but the observability text never defines the `0` case, and `0` makes the §11.2
  utilization ratio (`actual / 0`) undefined. §5.5.15's `exceeded` attribute is a
  strict `>` (`usage.prompt_tokens > input_max_tokens`), so a `0` bound is
  **already** exceeded by any positive usage — the `exceeded` span attribute and
  the §11.2 exceeded **counter** are therefore defined for `0` (they fire). The
  only genuinely-undefined surface is the **utilization histogram** (no ratio for
  a `0` denominator). Two things to pin, either of which needs a fixture and so a
  proposal:
  1. **Normatively define the utilization `÷0` handling** — the recommended
     interim is to **skip the histogram sample** for a `0` denominator (an omitted
     sample beats a synthesized sentinel bucket), while `exceeded` and the counter
     fire per §5.5.15. Without a fixture, two impls could diverge (skip vs
     sentinel vs skip-everything).
  2. **Consider tightening prompt-management §3 to positive bounds (`>= 1`)** —
     which would make `0` invalid at the source and moot the whole question. This
     is a **breaking** §3 change and would need its own proposal; noted as the
     cleanest long-term option, not a commitment.

## Forward-looking provider capabilities

Each new provider domain lands as its own capability following the
`<domain>-provider` naming convention (`llm-provider`,
`retrieval-provider`, etc.) — new domains land as separate capabilities
rather than as extensions to existing ones. Two domains in the
short-horizon roadmap below.

### Cross-cutting — `voice-provider` capability

- **`SpeechToTextProvider` + `TextToSpeechProvider` protocols on a new
  voice-provider capability.** [candidate-for-new-proposal] — voice
  agents (real-time chat with ASR transcription + TTS replies) are a
  growing OA-relevant use case. ASR shape: audio → transcript text;
  TTS shape: text → audio bytes. Both fit Langfuse's `Generation`
  observation type cleanly (each carries model + usage + input + output).
  Capability follows the retrieval-provider pattern: per-protocol typed
  events (`SpeechToTextEvent` + `SpeechToTextFailedEvent`,
  `TextToSpeechEvent` + `TextToSpeechFailedEvent`); per-model binding;
  error categories inherited from llm-provider §7; privacy posture
  inherits the `disable_provider_payload` flag established in proposal
  0059. Audio payloads have their own privacy framing (audio is
  directly intelligible as speech; same threat-model weight as raw
  text). Probably a 2-proposal batch like retrieval-provider, or one
  combined proposal — to be decided when the capability is drafted.
- **Composes with a real-time runtime; does not replace one.** OA owns
  the provider contracts, typed events, and observability; the real-time
  media runtime — audio transport (WebRTC / WebSocket), frame processing,
  buffer management, and barge-in *mechanics* — is out of scope. A
  voice-provider capability composes *underneath* a runtime like Pipecat
  (which already plugs swappable vendor STT / TTS stages), the way
  `llm-provider` composes under an application's own control flow.
  Deepgram is a natural first `§8` realization: it spans STT, TTS, and
  endpointing in one vendor, so modeling its contract exercises the whole
  surface and generalizes to AssemblyAI / Speechmatics / Cartesia /
  ElevenLabs. Deepgram's bundled *Voice Agent API* (STT+LLM+TTS in one
  socket) is a useful counterpoint — OA models the *component* providers that the
  caller composes, not an all-in-one turnkey.
- **Streaming shape is duplex / continuous, not request / response.** The
  "audio → transcript text" shape above under-models real ASR: streaming
  STT is a persistent bidirectional stream (client → server audio frames,
  server → client `interim → final` transcript events, plus endpointing /
  VAD signals) — a different shape than 0062's unidirectional LLM token
  stream. Typed events would carry the interim / final distinction (an
  interim transcript event superseded by a final one). This grows the
  queued *full streaming wire* discussion with a duplex case it doesn't
  yet cover.
- **Latency is the first-class observable.** Voice UX turns on
  time-to-first-audio, endpoint-to-first-token, TTS time-to-first-byte,
  and turn duration. The OA-shaped contribution is a speech extension of
  the GenAI / OTel semconv (§11-style metrics + spans for the STT / TTS /
  turn latencies), which no runtime standardizes across vendors.
- **Interruption / barge-in is mostly runtime, with one contract sliver.**
  The mechanics (detecting the interrupt, flushing audio) belong to the
  runtime, but *cancelling the in-flight turn* — the LLM completion + TTS
  synthesis — maps onto OA's existing middleware cancellation-propagation
  (0004); the voice case is a concrete driver for that contract.
- **Turn boundaries are a separate cross-cutting question** — endpointing
  is the voice trigger for a turn abstraction shared with the chat harness
  and event-driven runtimes; see *Forward-looking turn model* below.

### Cross-cutting — `multimodal-provider` capability

- **`ImageGenerationProvider` + `ImageEditProvider` protocols on a new
  multimodal-provider capability.** [candidate-for-new-proposal] —
  image generation in agent + content workflows; image-edit + vision
  for multimodal pipelines (text+image → image, or image+text → text
  for image understanding). Shape: text prompt → image output for
  generation; image+prompt → image for edit. Both fit Langfuse's
  `Generation` observation type with binary-payload outputs. Capability
  follows the retrieval-provider pattern: per-protocol typed events,
  per-model binding, inherited error categories, inherited privacy
  flag. Image payloads are payload-bearing under the same threat
  model as text (images are directly intelligible content; same
  default-suppression posture as `input_messages` /
  `EmbeddingResponse.vectors`). Video generation NOT in scope under
  this capability — different cost / latency / streaming-shape; lands
  separately if downstream demand surfaces.

## Forward-looking turn model

### Cross-cutting — modality-agnostic turn boundary

- **A "turn" recurs across surfaces with different boundary triggers.**
  [candidate-for-new-proposal] — a *voice* turn ends at audio endpointing
  / utterance-end (a provider-emitted signal), a *chat* turn ends at
  message submit (harness-chat, 0056), an *event-driven* turn ends at an
  external event boundary (an event-driven runtime's turn edge). If OA
  models the turn boundary abstractly — a contract independent of what
  produces it — the voice harness, the chat harness, and event-driven
  runtimes all compose on the same abstraction: the framework owns the
  turn *contract*, not the transport that produces it. Ties to
  harness-chat (0056), sessions (0020 — cross-invocation state and
  checkpoint points), and HITL. Open sub-questions: what a turn-boundary
  event is and who emits it (provider vs harness vs external runtime);
  how in-turn cancellation (voice barge-in) relates to the boundary; how
  the boundary lines up with session / checkpoint persistence points.
  Surfaced exploring a Deepgram / Pipecat voice harness; belongs to the
  harness / voice work queued behind the discussion set. Captured so it
  isn't re-derived — not proposal-ready.

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

## conformance-adapter

### 0089 — embedding / rerank failure-mock error-field vocabulary

- **No `raises: {error_type, message}` equivalent for embedding / rerank failure
  mocks.** [candidate-for-new-proposal] — surfaced authoring 0089's
  failure-observation fixtures (137 / 138). The tool failure mock supplies literal
  `error_type` / `error_message` via a `raises: {error_type, message}` directive,
  so the tool failure fixture pins those values literally; the embedding / rerank
  failure path is HTTP-mock-triggered (a status code mapped to a §7
  `error_category`), with no directive to supply a literal `error_type` /
  `error_message`. So fixtures 137 / 138 assert those two fields by format
  (`<any-string>`) rather than literal — the deterministic `error_category` (via the
  observation `statusMessage`) is the literal-pinned contract. A follow-on could
  either add an embedding / rerank failure-mock directive carrying literal
  `error_type` / `error_message`, or state normatively that the provider error
  body's `type` / `message` map deterministically onto the event's `error_type` /
  `error_message` — either enables cross-impl literal assertion of those fields.
  Neither exists today; deferred to a dedicated conformance-adapter follow-on
  after 0089 — part of the same consolidating **directive-documentation pass**
  as the `typed_observers` / `contains_event` and `cause` gaps below.

### Cross-cutting — `typed_observers` / `contains_event` directives undocumented

- **The two directives that assert typed-event fields are load-bearing across
  the suite yet have no entry in conformance-adapter §5.**
  [candidate-for-new-proposal] — surfaced repeatedly through the observability
  and retrieval fixture work (most recently the 0100 / 0101 malformed-figure
  fixtures, which lean on `contains_event` to assert a counter is *present but
  null* rather than absent). `typed_observers` registers one or more collectors
  on a fixture (`- name: <collector>`, `kind: typed_event_collector`);
  `contains_event` then asserts, under `expected.observers.<collector>`, that a
  typed event was emitted with a given `event_type` and a `fields:` map (matched
  by value, with the §5.10 value-matcher vocabulary — `<any-string>`, null,
  etc.). Together they are the primary way the suite pins the graph-engine §6
  typed-event families (`LlmCompletionEvent`, `LlmFailedEvent`, `EmbeddingEvent`,
  `RerankEvent`, …). Many fixtures across the suite use `contains_event` and
  `typed_observers` (concentrated in observability, with a retrieval
  cluster), yet neither key appears anywhere in `spec/conformance-adapter/spec.md`
  — an adapter author reverse-engineers both from the fixtures.
  This is the same gap `carries` had before proposal 0098 gave it a normative
  §5.12 home, and it wants the same treatment: a conformance-adapter §5.x
  subsection defining the collector-registration directive, the `contains_event`
  assertion shape, and — the point the malformed-figure work made sharp — the
  **present-but-null vs absent** field semantics (a `fields:` entry asserting an
  explicit `null` value MUST distinguish "field present and null" from "field
  omitted", the exact distinction fixture 149's event-mirror assertion turns on).
  Needs a proposal since it adds normative conformance-adapter text; deferred
  until the conformance-adapter directive-documentation debt (this plus the
  0089 failure-mock gap and the undocumented `cause` directive) is worth a
  consolidating pass. The related `carries` naming-convention cleanup is
  handled separately by proposal 0102.

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
