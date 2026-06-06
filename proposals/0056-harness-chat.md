# 0056: Chat Harness Sub-Spec

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-05
- **Accepted:**
- **Targets:** spec/harness-chat/spec.md (creates — new sub-spec capability layering on top of the abstract harness contract (proposal 0022) to specify the chat-loop deployment shape); plus new conformance fixtures covering the canonical message I/O cycle, conversation-history threading, the `send()` callable, suspension handling for chat (HITL pause-and-prompt), and the error → user-facing reply mapping for each of the three harness error buckets; plus a small cross-spec edit to spec/harness/spec.md replacing two `0NNN-harness-chat` placeholder references in §1 and §9 with concrete proposal-number references to 0056 (the placeholders existed because 0022 was Accepted before 0056 was drafted; the `0NNN-harness-chat` references in 0022's own text stay verbatim per the post-Accept immutability rule).
- **Related:** 0022 (harness contract — the abstract foundation this sub-specs; Q1 *Per-harness-type behavior* committed the chat sub-spec to a follow-on, Q3 *Higher-level callable shape* committed the `harness.send(session_id, message)` surface to the chat sub-spec), 0020 (sessions — chat is sessioned-mode by default; conversation history lives in session state), 0017 (prompt management core — chat-prompt content-block shape this sub-spec inherits), 0046 (multi-message / chat prompt rendering — informs the message-shape composition rules), 0006 (LLM provider core — the underlying message + tool-call shapes the chat harness consumes), 0021 (graph suspension — chat agents commonly pause for HITL approvals; the chat harness needs a clean conversational surface for the suspended outcome)
- **Supersedes:**

## Summary

Create the `harness-chat` sub-spec capability, layering on top of the abstract harness contract
(proposal 0022) to ratify the chat-loop deployment shape. The chat sub-spec specifies the
canonical `ChatMessage` shape (reusing prompt-management §3.1's content-block model for
multimodal authoring), the conversation-history convention (`messages: list[ChatMessage]` in
session state with the `append` reducer), the higher-level `harness.send(session_id, message)`
callable surface (the chat-specific implementation of proposal 0022's Q3 resolution), the
inbound message → session → invoke wiring, the outbound assistant message → response wiring,
the suspension-handling pattern (HITL pause-and-prompt-the-user; the chat harness MUST NOT
block; the `send()` callable returns a `ChatTurnOutcome` distinguishing completed reply from
suspended-pending shapes), the error → user-facing reply mapping for each of harness §7's
three error buckets (terminating / retryable / user-correctable), and the forward-looking
composition with streaming (when the planned streaming proposal lands).

The sub-spec is sessioned-mode-only — chat without a conversation is not a coherent shape;
stateless completion endpoints are a different harness type. Cross-session memory (per-user
profiles, episodic memory, semantic / vector-indexed retrieval) is OUT of scope per the same
carve-out sessions §13 makes; the chat harness composes with a future memory capability when
its spec lands.

The first per-harness-type sub-spec landing per proposal 0022's Q1 resolution. Establishes the
sub-spec template subsequent per-harness-type sub-specs (FastAPI, Inngest, MCP, …) follow when
their cross-impl divergence risk warrants ratification.

## Motivation

The abstract harness contract (proposal 0022) handles the universals — dispatch path
classification, turn lifecycle, signal coordinator, error categorization, sessioned vs
stateless mode. Three things the abstract contract deliberately leaves to per-harness-type
sub-specs: the inbound transport shape, the outbound surface shape, and any higher-level
callable surface above raw `invoke()`. The chat harness is the highest cross-impl-divergence
risk among the harness types we know about; ratifying its sub-spec ahead of others closes the
biggest gap and lays down the template subsequent sub-specs follow.

**The cross-impl divergence problem for chat.** Every production OA chat agent will reinvent
the same handful of decisions: what does a chat message look like at the API boundary? Where
does conversation history live in session state? What's the function signature for "send a
message and get a reply"? What happens to the conversation when the graph suspends mid-turn
(HITL pattern)? How do harness-level errors (session terminating, retryable transient,
user-correctable) surface as conversational replies vs error responses? Without a sub-spec,
the Python chat harness, the TypeScript chat harness (when it lands), and every application's
in-house chat wrapper would each answer these questions slightly differently. Cross-impl
behavioral promise breaks at the chat boundary even though the abstract contract held
underneath.

**Q1 commitment from proposal 0022.** Proposal 0022's *Open questions* Q1 resolution
explicitly committed the chat sub-spec to a follow-on proposal — this proposal (0056) is
that follow-on; the `0NNN-harness-chat` placeholder in the quote below now resolves to
proposal 0056:

> "**Whether to spec per-harness-type behavior in follow-on proposals.** Resolved: **the
> chat harness gets a follow-on sub-spec** (planned proposal `0NNN-harness-chat`) that
> specifies the inbound message → session → invoke wiring, the outbound assistant message →
> session → response wiring, and the higher-level callable surface (`harness.send(session_id,
> message)` rather than hand-threading invoke arguments). Downstream demand surfaced during
> 0022's pre-Accept review (a reference chat agent in production would otherwise re-invent
> that contract per-deployment); a chat sub-spec ratifies the shape once for cross-impl
> consistency."

**Q3 commitment from proposal 0022.** The higher-level callable surface
(`harness.send(session_id, message)`) is the chat-specific implementation of proposal 0022's
Q3 resolution — abstract contract stays neutral on whether the harness wraps `invoke()` in
a higher-level callable; per-harness-type sub-specs MAY mandate one when their transport model
calls for it. Chat is the natural first case: hand-threading `invoke(session_id=..., initial_state=ChatState(messages=[...]))`
at every turn is cumbersome; `harness.send(session_id, message)` is the obvious shape.

**Cross-cutting alignment with existing capabilities.** The chat sub-spec inherits message
shape from prompt-management §3.1 (content-block-based multimodal authoring) — the same
content-block shape the prompt-management capability already specifies for chat-prompt
templates flows through unchanged. This keeps the chat harness aligned with how prompt
templates compose at the LLM-provider boundary: a prompt rendered against state produces
content blocks; the chat harness consumes content blocks at the message boundary; the
LLM-provider's `complete()` API per llm-provider §3.1 accepts content blocks verbatim.
One canonical message shape across the spec.

**Why now.** The chat sub-spec is the smallest committed work blocking the spec from claiming
end-to-end coverage for the chat agent use case. The abstract harness contract is ratified;
sessions + suspension + checkpointing all compose into it; the chat sub-spec slots the
chat-specific surface on top so a downstream Python chat agent has a single spec to target.

## Detailed design

### 1. Capability spec scope

The new `spec/harness-chat/spec.md` defines:

- **`ChatMessage` shape.** Canonical typed message at the chat-harness API boundary.
  Field shape: `role: "user" | "assistant" | "system" | "tool"`, `content: list[ContentBlock]`
  (reusing llm-provider §3.1 / prompt-management §3.1 content blocks — text, image_url,
  inline image, tool_call, tool_result). Optional fields per the existing prompt-management
  shape (`name`, `tool_call_id`, etc.).
- **Conversation history convention.** Per-session state field `messages: list[ChatMessage]`
  with the `append` reducer. Each user message appends to history; each assistant reply
  (plus any tool-call / tool-result messages from a tool-loop agent) appends to history.
  The chat harness reads + writes through this canonical field name. v1 mandates the
  canonical name; a follow-on proposal MAY add a configurable field-name option if real
  applications surface a naming conflict, but the v1 contract keeps the surface tight
  (one canonical name; zero-config against any sessioned graph using it).
- **The `send()` callable.**
  `harness.send(session_id: str, message: ChatMessage) -> ChatTurnOutcome` where
  `ChatTurnOutcome` discriminates between `completed` (assistant reply available),
  `errored` (error bucket per harness §7 + a user-facing reply per the §10 mapping), and
  `suspended` (the conversation is awaiting an external signal; the harness has registered
  the signal subscription per harness §5.3 + §6).
- **Inbound message → session → invoke wiring.** The chat harness's implementation of
  harness §3.1 (new-session) and §3.2 (existing-active-session) for chat-shaped
  transmissions. `send()` classifies based on session state (`messages` field empty +
  caller-supplied id → §3.1; non-empty → §3.2); the user message appends to history;
  `invoke()` runs the graph with the threaded session state.
- **Outbound assistant message → response wiring.** After `invoke()` returns completed,
  the chat harness extracts the new messages from the final state's `messages` field (the
  tail of the appended history — all new messages regardless of role, so tool-call /
  tool-result messages from a tool-loop agent surface alongside the assistant reply) and
  returns them on `ChatTurnOutcome.completed.replies: list[ChatMessage]` (always a list;
  length 1 in the common single-message case). Multi-message replies (tool-calling agents
  that emit multiple turns within one invocation; a typical pattern is an assistant message
  with `tool_call` content blocks → a tool-role message with `tool_result` content blocks
  → a final assistant text reply) surface as the full new-message sequence in
  graph-execution order, deterministic per harness §11 (the `messages` field's `append`
  reducer preserves order naturally). Chat UIs decide how to render tool-role messages
  (typically with "thinking" / "calling X" / "got result" affordances).
- **Suspension handling for chat.** When `invoke()` returns suspended (per harness §5.3),
  the chat harness returns a `ChatTurnOutcome` with the suspended discriminator carrying
  the signal descriptor + optional "pending" assistant message (a synthetic message the
  graph MAY append to state via the standard `messages` reducer before calling
  `suspend()` to inform the user — "I'm waiting for approval to send this email"; the
  chat harness extracts it from the suspended outcome's `state.messages` tail and
  surfaces it on the `ChatTurnOutcome`, no chat-specific engine hook needed). The caller
  (chat UI) renders the pending message and shows a waiting state. When the resume
  signal arrives, the chat harness dispatches the signal-resume invocation per harness
  §3.3 and the post-resume assistant reply fires through a subscribed listener the
  caller registered against the chat harness (see §8 for the listener-callback contract).
- **Error → user-facing reply mapping.** Each of harness §7's three error buckets gets a
  conversational shape:
  - **Session-terminating** (§7.1): `ChatTurnOutcome.errored` with a system-message-shaped
    reply ("This conversation can't continue. Please start a new one."). The chat UI MAY
    refuse further `send()` calls on this `session_id`.
  - **Retryable transient** (§7.2): `ChatTurnOutcome.errored` with a system-message-shaped
    reply ("I had trouble responding. Try again in a moment."). The chat UI MAY auto-retry
    once per the application's retry policy.
  - **User-correctable** (§7.3): `ChatTurnOutcome.errored` with a system-message-shaped
    reply incorporating the upstream error's diagnostic ("That request couldn't be
    processed: <diagnostic_message>. Please adjust your message and try again."). The chat
    UI invites the user to retry with corrected input.
- **Composition with streaming (forward-looking).** When the planned streaming proposal
  lands, the chat sub-spec specifies a streaming variant of `send()` that yields
  token-level partial assistant content (`ChatChunk` values) ending with a final
  `ChatTurnOutcome`. The streaming surface is defined here but the actual hooks the graph
  engine uses to emit token-level events come from the streaming proposal. The exact
  return shape — whether the iterator yields the final `ChatTurnOutcome` as its last
  value, returns a tuple `(AsyncIterator[ChatChunk], Awaitable[ChatTurnOutcome])`, or
  uses a different shape — is deferred to the streaming proposal so the chat sub-spec
  doesn't lock in a shape before the streaming proposal can validate it against the
  engine-side hook surface. For v1, `send()` is non-streaming; the streaming variant
  arrives when the streaming proposal does.
- **Mode constraint.** The chat sub-spec is **sessioned-mode only**. Chat without
  conversation history is not a coherent shape — every turn would lose context. Stateless
  completion endpoints ("send one message, get one reply, no memory") are a different
  harness type and belong in a separate sub-spec if anyone wants one (likely a "completion
  harness" sub-spec for inference services).
- **Errors.** Adds one new error category beyond harness §10: `chat_message_shape_invalid`
  for inbound `ChatMessage` instances that fail validation (missing required fields,
  unsupported content-block types, role-content-shape mismatches). Surfaces as a §7.3
  user-correctable error.

### 2. Spec section structure (13 sections, matching the established capability-spec template)

- **§1 Purpose** — chat sub-spec's relationship to the abstract harness contract; the
  sessioned-mode-only constraint; cross-references prompt-management for shared message
  shapes and 0022 for the abstract foundation.
- **§2 Concepts** — `ChatMessage`, `ContentBlock` (cross-ref to prompt-management),
  `ConversationHistory`, `ChatTurnOutcome`, the `send()` callable surface.
- **§3 Message shape (`ChatMessage`)** — full field enumeration: `role`, `content` (list of
  content blocks per prompt-management §3.1), optional `name`, optional `tool_call_id`.
  Validation rules (each `role` value mandates / forbids specific content-block types per
  llm-provider §3.1's wire contracts). Cross-reference to prompt-management for the
  authoritative content-block definitions.
- **§4 Conversation history convention** — the canonical `messages: list[ChatMessage]`
  session-state field with the `append` reducer (v1 mandates this canonical name; a
  follow-on proposal MAY add field-name configurability if applications surface real
  naming conflicts). Scoping rules: history is per-session; cross-session memory is out
  of scope per §13.
- **§5 The `send()` callable** — full signature, parameter semantics, `ChatTurnOutcome`
  return shape (three-way discriminator: completed / errored / suspended), thread-safety
  rules (consistent with harness §11 determinism). Concurrent `send()` calls under the
  same `session_id` MUST serialize (the second call awaits the first's outcome) — the
  chat sub-spec layers a stricter rule than sessions §8.1's last-write-wins default
  because chat-shaped concurrent interleaving is particularly user-visible (out-of-order
  replies, stale-history reads). Serialization happens at the chat-harness layer (a
  per-`session_id` lock around the `send()` body); no change to the abstract sessions
  capability. Apps wanting parallel turns under one user use two sessions.
- **§6 Inbound message → session → invoke wiring** — the chat harness's implementation of
  harness §3.1 + §3.2 + §3.3 in chat-shaped form. Path classification rule: empty history +
  no caller-supplied id → §3.1; non-empty history → §3.2; signal-resume → §3.3 (per the
  harness signal coordinator). Initial-state construction (append user message to loaded
  history, hand to invoke).
- **§7 Outbound assistant message → response wiring** — extracting the full new-message
  tail from the final state's history field (all roles — assistant text replies, tool-call
  messages, tool-result messages); supporting multi-message replies for tool-calling
  agents (the typical assistant-tool-call → tool-result → assistant-final pattern surfaces
  as three new messages on one outcome); populating
  `ChatTurnOutcome.completed.replies: list[ChatMessage]` (always-list shape; multi-message
  replies in graph-execution order, deterministic per harness §11).
- **§8 Composition with suspension** — chat-specific handling of harness §5.3's suspended
  outcome. Pending-message protocol (a graph node MAY append a synthetic assistant message
  to state via the standard `messages` reducer before calling `suspend()` to inform the
  user; the chat harness extracts it from the suspended outcome's `state.messages` tail
  and surfaces it on the `ChatTurnOutcome` — no chat-specific engine hook needed; the
  pattern composes from existing graph primitives). Signal-resume flow: when the resume
  signal arrives, the chat harness dispatches the resume invoke and the post-resume
  assistant reply fires through a **subscribed listener** the caller registered against
  the chat harness
  (`harness.subscribe(session_id, callback)` or equivalent per-language surface). The
  listener mechanism is the default because chat UX is fundamentally asynchronous
  post-suspend — the user shouldn't have to send another message to receive the resume
  reply. Implementations MAY ALSO support a "next `send()` returns the resume reply"
  shape for synchronous-style callers, but the listener path MUST be available. The
  spec defines the listener-callback contract (it fires with the post-resume
  `ChatTurnOutcome`); the mechanism (channels, callbacks, async iterators) is
  per-language idiomatic.
- **§9 Composition with streaming (forward-looking)** — defines the contract surface for a
  streaming variant of `send()` (`send_streaming()` returning async-iterator of
  `ChatChunk` plus final `ChatTurnOutcome`); the actual graph-engine hooks the streaming
  variant uses come from the planned streaming proposal. v1 ships the non-streaming
  `send()` only; streaming MAY be added later without breaking the v1 contract.
- **§10 Error → user-facing reply mapping** — three-bucket mapping (terminating /
  retryable / user-correctable per harness §7) → conversational shape on
  `ChatTurnOutcome.errored`. Includes the new `chat_message_shape_invalid` category as a
  §7.3 user-correctable error.
- **§11 Determinism** — chat sub-spec inherits harness §11's determinism rules. The
  `send()` callable adds no nondeterminism beyond what the underlying graph + harness
  layers introduce.
- **§12 Cross-spec touchpoints** — references to harness (abstract foundation), sessions
  (conversation-history persistence), suspension (HITL composition), prompt-management
  (shared content-block model), llm-provider (downstream consumers of the message shape),
  observability (turn-level span attributes for chat turns), and the future memory
  capability (forward-referenced composition point).
- **§13 Out of scope** — explicit non-goals: cross-session memory (separate future
  capability), specific chat-platform integrations (Slack / Discord / Teams adapters are
  sibling-package work), multimodal output beyond text/image content blocks for v1, voice
  input/output (separate streaming / voice proposals), rich-media compose UI (application
  concern), conversation-summary / context-window-management (application concern; chat
  harness exposes the raw history field — apps decide compaction strategy), per-turn
  user-facing error tone customization beyond the three-bucket-default mapping
  (applications customize via wrapping the chat harness).

### 3. Conformance test impact

New fixtures under `spec/harness-chat/conformance/` (numbers assigned at acceptance):

1. **Basic send-and-reply cycle.** Sessioned chat harness, single-node graph that appends a
   constant assistant message. `send(session_id, user_message)` returns
   `ChatTurnOutcome.completed` with the assistant reply; session state now has both
   messages.
2. **Multi-turn conversation.** Sequential `send()` calls under the same `session_id`;
   conversation history accumulates; each turn observes the prior turn's messages in the
   loaded state.
3. **Multi-message reply (tool-calling agent).** Graph fires three new messages within
   one invocation: an assistant-role message with `tool_call` content blocks, a tool-role
   message with the `tool_result`, and a final assistant-role text reply.
   `ChatTurnOutcome` surfaces all three on the new-message tail (all roles included; the
   chat UI decides how to render the tool-role intermediate).
4. **Multimodal user message.** `send()` receives a `ChatMessage` with a mix of text and
   image content blocks; the graph processes it (e.g., a vision-LLM node); assistant reply
   threads cleanly into history.
5. **Suspension with pending message.** Graph emits a synthetic "I'm waiting for approval"
   assistant message then calls `suspend()`; `ChatTurnOutcome.suspended` carries the
   pending message + the signal descriptor; the chat harness does NOT block.
6. **Suspension-resume flow.** After fixture 5's suspend, a signal arrives via the harness
   signal coordinator; the next `send()` (or subscribed listener) returns the post-resume
   assistant reply.
7. **Session-terminating error mapping.** `session_load_failed` (sessions §10) → §7.1 →
   `ChatTurnOutcome.errored` with the "this conversation can't continue" system-message
   reply.
8. **Retryable transient error mapping.** `provider_unavailable` → §7.2 →
   `ChatTurnOutcome.errored` with the "try again in a moment" system-message reply.
9. **User-correctable error mapping.** `provider_invalid_request` → §7.3 →
   `ChatTurnOutcome.errored` with the diagnostic-message reply.
10. **`chat_message_shape_invalid` error.** Inbound `ChatMessage` with an unsupported
    content-block type → new chat-specific §7.3 user-correctable error.

The chat sub-spec introduces a new fixture suite directory; per the conformance-adapter
spec's §3.2 *per-directory harness notes* rule, the fixture suite's per-directory contract
(synthetic chat-message transport, `send()`-shaped assertions vs the harness suite's
`transmissions[]`-shaped assertions) is documented in fixture 001's header comment.

## Versioning

**MINOR bump (pre-1.0).** On acceptance the whole-spec SemVer increments:

- New `harness-chat` capability spec at `spec/harness-chat/spec.md`.
- New conformance fixtures under `spec/harness-chat/conformance/` (ten minimum).
- New error category `chat_message_shape_invalid` in the chat-harness layer.
- No changes to harness §10's abstract error set (the new category is sub-spec-level,
  routed through harness §7.3 user-correctable on surfacing).
- No changes to other capability specs — chat sub-spec is purely additive; sessions /
  suspension / prompt-management / llm-provider / harness all stay as-is.

The change is backwards-compatible. Existing applications that don't use the chat harness
see no behavioral change. Applications opting into the chat harness get a single
ratified surface for the chat-loop deployment shape.

## Alternatives considered

**1. Don't ratify chat at the spec level; let each chat-harness implementation define its
own surface.** The Q1 path explicitly rejected in 0022's pre-Accept review. Rejected here
for the same reason: cross-impl divergence at the chat boundary is the highest-risk surface;
ratifying once preserves the cross-impl behavioral promise.

**2. Roll chat sub-spec into the harness capability proposal (0022) itself.** Considered
during 0022 design. Rejected: kept 0022 abstract per the chat-as-prototype alternative the
proposal rejected (chat-as-prototype builds in conversational turn semantics that don't
generalize). The chat sub-spec layers on top of the abstract contract rather than
contaminating it.

**3. Spec stateless-mode chat alongside sessioned-mode.** A "send one message, get one
reply, no memory" surface. Rejected: stateless chat is a degenerate case (every turn loses
context); the surface is essentially "LLM completion endpoint with no conversation."
That's a different harness type (a "completion harness" sub-spec) and shouldn't
contaminate the chat sub-spec's sessioned-by-default contract. Applications wanting
single-turn completion use raw `invoke()` against a stateless harness per harness §3.0.

**4. Define a chat-specific `ChatMessage` type rather than reusing prompt-management's
content blocks.** Considered for v1 simplicity (text-only `ChatMessage` with a `text:
str` field). Rejected: would force the chat harness's message shape to diverge from
prompt-management's chat-prompt content-block model + llm-provider's wire shapes, creating
three different multimodal message types across the spec. Reusing the existing
content-block shape keeps one canonical multimodal message type across prompt-management
→ chat-harness → llm-provider boundaries.

**5. Specify a particular streaming protocol now rather than forward-referencing the
streaming proposal.** Considered to land the chat sub-spec with full streaming support.
Rejected: the streaming proposal is separate per harness §13's *Out of scope* + the v1
graph-engine has no token-level hook surface. Defining a streaming protocol here without
the underlying engine hooks would mandate an interface that no implementation can
satisfy yet. The chat sub-spec defines the streaming-`send()` contract shape forward-
referentially; the engine-side hooks come from the streaming proposal; both compose when
both land.

## Open questions

All design questions raised during drafting were resolved at draft and locked into the
spec-text bullets above (§§1, 5, 7, 8). Captured here for the design-decision audit
trail; these migrate to `docs/open-questions.md` as `resolved-by-acceptance` entries at
Accept time.

- **Pending-message protocol shape.** Resolved: **reuse existing graph primitives.** A
  graph node appends the synthetic pending message to state via the standard `messages`
  reducer before calling `suspend()`; the chat harness extracts it from the suspended
  outcome's `state.messages` tail. A dedicated `chat.emit_pending()` hook was considered
  for discoverability but rejected — it would add chat-specific engine surface,
  contradicting the "thin layer over harness" framing. Locked in §1 (suspension handling
  bullet) and §8 (composition with suspension).
- **Multi-message reply ordering.** Resolved: **graph-execution order, deterministic per
  harness §11.** When a tool-loop agent fires multiple assistant / tool messages in one
  invocation, they arrive in `ChatTurnOutcome.completed.replies` in graph-execution
  order; the `messages` field's `append` reducer preserves order naturally with no
  additional ordering rule needed. Locked in §1 (outbound bullet) and §7.
- **Concurrent `send()` calls under one `session_id`.** Resolved: **chat sub-spec
  mandates serialization.** Concurrent `send()` calls under one `session_id` MUST
  serialize (the second call awaits the first's outcome). The chat sub-spec layers a
  stricter rule than sessions §8.1's last-write-wins default because chat-shaped
  concurrent interleaving is particularly user-visible (out-of-order replies,
  stale-history reads — the second user message arriving while the first is still being
  processed). Serialization happens at the chat-harness layer (a per-`session_id` lock
  around the `send()` body); no change required to the abstract sessions capability.
  Apps wanting parallel turns under one user use two sessions. Locked in §5.
- **Forward-compatibility with the streaming proposal's exact hook shape.** Resolved at
  draft: **API-surface contract / implementation contract split.** The chat sub-spec
  specifies the streaming `send()` API-surface contract (signature, return type) and
  defers the implementation contract (which engine hooks get called) to the planned
  streaming proposal. The chat sub-spec locks the surface shape; the streaming proposal
  fills in the engine-side hooks. Both compose when streaming lands; no v2 chat sub-spec
  revision needed. Locked in §1 (composition-with-streaming bullet) and §9.
- **Capability naming.** Resolved: **`harness-chat`.** Parallels `conformance-adapter`
  for sub-spec naming (parent capability noun first, then subtype). Alternatives
  `chat-harness`, `chat`, `harness.chat` rejected: `harness-chat` keeps the sub-spec
  relationship visible in the directory name and sorts alphabetically near the parent
  `harness` capability. Locked in the *Targets* field and throughout.
- **`ChatTurnOutcome` field shape — `.replies` vs `.reply` + `.replies` union.**
  Resolved: **always-`.replies: list[ChatMessage]`.** The field is always a list; length
  1 in the common single-message case; multi-message tool-loop agents populate as
  needed. A `.reply` + `.replies` union was considered for single-message ergonomics;
  rejected because the conditional-inspection cost of the union (callers writing
  `if outcome.reply: ... elif outcome.replies: ...`) outweighs the one-character savings
  of `.reply` in the common case. The always-list shape also nudges callers to handle
  the multi-message tool-loop case, which is increasingly common. Apps wanting a
  single-message shortcut wrap with `outcome.completed.replies[0]` or `[-1]` depending
  on semantics. Locked in §1 (outbound bullet) and §7.

## Out of scope

- **Cross-session memory.** Per-user profiles, episodic memory, semantic / vector-indexed
  retrieval, "agent remembers things across conversations" — all out of scope, deferred
  to a future memory capability per sessions §13's existing carve-out. The chat sub-spec
  scopes to per-session conversation history.
- **Specific chat-platform adapters.** Slack, Discord, Microsoft Teams, WhatsApp,
  customer-platform integrations — all sibling-package work that builds on the chat
  sub-spec. Each platform's message routing (mentions, threads, channels, attachments)
  is the platform-adapter's concern.
- **Multimodal output beyond text/image.** Audio, video, file outputs are deferred; v1
  ships text + image content blocks per prompt-management §3.1's existing set. Adding
  audio / video content blocks is a prompt-management or LLM-provider proposal; the
  chat harness inherits the additions when they land.
- **Voice input / output.** A voice agent harness is a different harness type entirely
  (streaming-first, low-latency, with VAD turn detection). Future sub-spec if demand
  surfaces.
- **Rich-media compose UI.** What the chat UI looks like, how the user types / sends, how
  attachments are picked — application concern.
- **Conversation summary / context-window-management.** When conversation history gets
  long enough to exceed LLM context windows, applications use summarization or windowing
  strategies. The chat sub-spec exposes the raw history field; the strategy lives in
  application code or a future memory-adjacent capability.
- **Per-turn user-facing error tone customization.** The §10 mapping defines a
  three-bucket default; applications that want different tone (more / less verbose,
  branded language, localized) wrap the chat harness with their own error-mapping layer.
- **Streaming protocol details.** The chat sub-spec defines the API-surface contract for
  a streaming `send()` variant; the actual streaming protocol (token format, chunk
  boundaries, backpressure, cancellation) lives in the planned streaming proposal.
- **Stateless completion harness.** "Send one message, get one reply, no memory" is a
  different harness type; if anyone wants it, it gets its own sub-spec.
