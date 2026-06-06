# Harness — Chat

Canonical behavioral specification for the OpenArmature chat harness sub-spec.

- **Capability:** harness-chat
- **Introduced:** spec version 0.50.0
- **History:**
  - created by [proposal 0056](../../proposals/0056-harness-chat.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The `harness-chat` capability defines the behavioral contract for chat-shaped harnesses — the
sub-spec layer on top of the abstract harness capability (`spec/harness/spec.md`) specifying
the canonical chat-loop deployment shape. Chat harnesses are the first per-harness-type sub-spec
landing per proposal 0022's *Open questions* resolution.

The cross-impl divergence risk for chat-shaped deployments is the highest among the harness
types OpenArmature knows about — every production chat agent reinvents message shape, history
convention, send-and-reply surface, suspension handling, and error mapping. Ratifying the
contract once preserves the cross-impl behavioral promise.

The capability composes with:

- **harness** — the chat harness is a harness; everything in
  `spec/harness/spec.md` applies (turn semantics, dispatch path classification,
  outcome handling, signal coordinator, error categorization). This sub-spec layers chat-shaped
  surfaces over that abstract contract.
- **sessions** — chat is sessioned-mode only (per §1 *Mode constraint* below); conversation history
  lives in session state per `spec/sessions/spec.md`.
- **suspension** — chat agents commonly pause for human-in-the-loop approvals; the chat harness
  composes with `spec/suspension/spec.md` via §8 below.
- **prompt-management** — the canonical `ChatMessage` shape reuses the content-block model from
  `spec/prompt-management/spec.md` §3.1 (and llm-provider §3.1
  unchanged); chat-prompt templates render into messages chat harnesses consume.
- **llm-provider** — the chat message shape mirrors llm-provider §3 unchanged
  (`spec/llm-provider/spec.md` §3); chat-harness messages flow through
  to provider `complete()` calls without translation.
- **observability** — chat turns inherit harness §4.6 (turn-level wrapper span); no chat-specific
  span attributes are introduced.

**Mode constraint.** The chat sub-spec is **sessioned-mode only**. Chat without conversation
history is not a coherent shape — every turn would lose context. Stateless completion endpoints
("send one message, get one reply, no memory") are a different harness type. Implementations
constructing a chat harness MUST resolve `session_id` per harness §3.1 / §3.2 / §3.3 for every
inbound turn; harness §3.0 *Stateless transmission path* does NOT apply.

This capability does NOT define:

- **Cross-session memory.** Per-user profiles, episodic memory, semantic / vector-indexed retrieval.
  Out of scope per §13; deferred to a future memory capability.
- **Specific chat-platform adapters.** Slack, Discord, Microsoft Teams, WhatsApp, customer-platform
  integrations — sibling-package work that builds on this spec.
- **Voice input / output.** A voice harness is a different harness type (streaming-first,
  low-latency, with voice-activity-detection turn boundaries). Future sub-spec if real.
- **Rich-media compose UI.** Application concern.
- **Conversation summarization / context-window management.** Application concern; this spec
  exposes the raw history field.

## 2. Concepts

**ChatMessage.** The canonical typed message at the chat-harness API boundary. Mirrors
llm-provider §3's message shape unchanged. See §3.

**ContentBlock.** Per llm-provider §3.1 — `text` / `image` / `thinking` / `redacted_thinking`.
Imported by reference; the chat sub-spec adds none.

**ConversationHistory.** The per-session field carrying the ordered message list. See §4.

**ChatTurnOutcome.** The discriminated return type of the chat harness's `send()` callable;
distinguishes completed reply, errored turn, and suspended turn. See §5.

**The `send()` callable.** The higher-level convenience surface above raw `invoke()`. Takes a
session id and an inbound user message; returns a `ChatTurnOutcome`. See §5.

**Pending message.** A synthetic assistant message a graph node MAY append to state before
calling `suspend()` to inform the user the turn is awaiting an external signal. See §8.

**Subscribed listener.** The default mechanism by which a chat harness surfaces the post-resume
assistant reply to the caller after a suspend → signal → resume cycle. See §8.

## 3. Message shape (`ChatMessage`)

A `ChatMessage` mirrors the llm-provider §3 message shape unchanged. The fields:

| Field | Required | Description |
|---|---|---|
| `role` | yes | One of `"system"`, `"user"`, `"assistant"`, `"tool"`. Discriminator per llm-provider §3. |
| `content` | conditional | Per llm-provider §3's per-role constraints (a non-empty string OR a non-empty ordered sequence of content blocks per llm-provider §3.1 — `text` / `image` / `thinking` / `redacted_thinking`; `content` MAY be empty on `assistant` messages with non-empty `tool_calls`). |
| `tool_calls` | only on `assistant` | Ordered list of `ToolCall` records per llm-provider §3 (top-level message field — NOT a content-block type). |
| `tool_call_id` | required on `tool` | The `id` of the matching `assistant` tool call. |

Per-role constraints, validation timing, and `ToolCall` shape follow llm-provider §3 verbatim.
Tool calls are top-level message fields (assistant messages with `tool_calls` populated); tool
results are `tool`-role messages with `tool_call_id` and string `content`. The chat sub-spec
adds no message-shape divergence — chat messages ARE llm-provider messages.

**Cross-cutting alignment.** A `ChatMessage` flowing through the chat harness MAY be passed
directly to an llm-provider `complete()` call without translation. A chat-prompt template rendered
per prompt-management §3.1 produces content blocks that compose into a `ChatMessage` without
adaptation. The one canonical message shape across the spec is enforced at the chat boundary.

### 3.1 Message validation

Implementations MUST validate inbound `ChatMessage` instances at the `send()` API boundary
before any session load or invoke dispatch. Validation MUST check:

- `role` is one of the four enumerated values.
- The per-role content shape constraints from llm-provider §3 hold (e.g., assistant `content` MAY
  be empty when `tool_calls` is non-empty; `tool` role requires a non-empty `tool_call_id`).
- Content blocks (when present) are valid instances of one of the four llm-provider §3.1 types.

A `ChatMessage` failing validation MUST surface as a `chat_message_shape_invalid` error (per
§10) — this is a user-correctable error per harness §7.3 (the caller supplied a malformed
message).

## 4. Conversation history convention

Sessioned chat graphs store conversation history in a canonical session-state field:

- **Field name.** `messages` (lowercase, plural). The chat harness reads + writes through this
  exact field name.
- **Field type.** `list[ChatMessage]`, ordered.
- **Reducer.** `append`. Each turn appends one or more new messages to the tail.

**Canonical name (v1).** v1 MANDATES the canonical field name. A follow-on proposal MAY add a
field-name configurability option if real applications surface naming conflicts, but the v1
contract keeps the surface tight (one canonical name; zero-config against any sessioned graph
using it). Applications with pre-existing state fields named `messages` whose semantics
conflict MUST migrate before adopting the chat harness, or wait for the field-name configurability
follow-on if it lands.

**Scoping.** History is per-session. Cross-session memory (per-user profiles, episodic recall,
semantic-indexed retrieval) is OUT of scope per §13 — the `messages` field carries only the
conversational turns within one `session_id`.

**Reducer composition.** The chat harness does NOT register a reducer on its own; the application's
graph state schema declares `messages: list[ChatMessage]` with the `append` reducer per
graph-engine's canonical state-reducer conventions. Implementations MAY ship a helper that
defines this field on a state schema for convenience (a "ChatStateMixin" or equivalent
per-language idiom), but the spec contract requires only that a sessioned chat graph carries the
correctly-shaped field; the construction mechanism is per-language.

## 5. The `send()` callable

The chat harness exposes a higher-level callable surface above raw `invoke()`:

```
send(session_id: <string>, message: ChatMessage) -> ChatTurnOutcome
```

**Spec-normative identifier.** `send` is the spec-normative method name. Implementations MAY
adjust casing per language idiom (`send` in Python / Rust / Go; `Send` in C# / Pascal-case
contexts) while keeping the identifier recognizable. Asynchronous variants follow the language's
async idiom (Python `async def send(...)`, TypeScript `async send(...)` returning a Promise,
etc.) — the callable contract is the same.

### 5.1 Parameter semantics

- `session_id` — the session identifier per sessions §3. Implementations MUST validate it is
  non-empty before any session load.
- `message` — the inbound `ChatMessage` per §3. MUST be validated per §3.1 before any session
  load.

### 5.2 Return type — `ChatTurnOutcome`

`ChatTurnOutcome` is a discriminated outcome carrying one of three variants:

- **`completed`** — the turn returned a normal completion. Carries:
  - `replies: list[ChatMessage]` — the new messages added to history during the turn, in
    graph-execution order. Always a list (length 1 in the common single-message case; longer for
    tool-loop agents that emit assistant-tool-call → tool-role → assistant-final sequences). The
    list MUST contain only messages newly added during this turn — pre-existing history MUST NOT
    surface here.
  - `final_state` (OPTIONAL) — the final state of the session after the turn. Implementations MAY
    expose this for callers that need to read other state fields the chat graph populated.
- **`errored`** — the turn errored at the harness boundary. Carries:
  - `error_bucket` — one of harness §7's three buckets: `session_terminating` / `retryable_transient` /
    `user_correctable`. (Matches the harness conformance vocabulary's `error_bucket` field for the
    three-way classification.)
  - `error_category` (OPTIONAL) — the underlying concrete error category from harness §10 /
    sessions §10 / suspension §10 / llm-provider §7 / etc. (e.g., `provider_unavailable`,
    `session_load_failed`, `chat_message_shape_invalid`). Matches the harness vocabulary's
    `error_category` for the concrete error name.
  - `reply: ChatMessage` — a system-shaped reply per §10's mapping; the application's chat UI
    surfaces this directly to the user.
- **`suspended`** — the turn called `suspend()` mid-invocation. Carries:
  - `signal_descriptor` — the suspension descriptor per suspension §4 (signal id, metadata).
  - `pending_messages: list[ChatMessage]` — messages the graph appended to `state.messages`
    before reaching the suspending node (per §8.1), in graph-execution order. Empty list when
    the graph suspended without pre-emitting any pending message; one or more entries when it
    did. Always a list (matches `ChatTurnOutcome.completed.replies`'s always-list shape; same
    rationale per the proposal's Open Questions resolution).
  - `invocation_id` — the paused invocation's identifier per harness §3.3 (needed by the caller
    when the resume-via-listener pattern is not used and `invoke(resume_invocation=...)` is called
    explicitly).

**Discriminator mechanism is per-language.** Implementations MAY use a tagged-union shape (Python
discriminated dataclass union; TypeScript discriminated interface union), a sealed-class hierarchy
(Kotlin / Scala), a result-type with three variants (Rust enum), or any equivalent shape the
language idiomatically expresses discriminated outcomes through. The field set above is normative;
the discriminator's surface is not.

### 5.3 Concurrency

Concurrent `send()` calls under the same `session_id` MUST serialize. The second call awaits
the first's outcome before beginning its own session load + invoke dispatch.

The chat sub-spec layers this stricter rule on top of sessions §8.1's last-write-wins concurrency
default because chat-shaped concurrent interleaving is particularly user-visible — two user
messages arriving in rapid succession could otherwise produce out-of-order replies (the second
turn reads pre-first-turn history) and reply-interleaving (both invocations writing assistant
messages concurrently).

The serialization happens at the chat-harness layer: a per-`session_id` lock around the `send()`
body. No change is required to the abstract sessions capability. Applications wanting parallel
turns under one logical user construct multiple sessions.

Concurrent `send()` calls under DIFFERENT `session_id` values MAY proceed in parallel; the
serialization rule scopes to a single `session_id`.

## 6. Inbound message → session → invoke wiring

The chat harness implements harness §3.1 / §3.2 / §3.3 in chat-shaped form. Path classification at
`send()` entry follows these rules:

- **Harness §3.1 (new-session) path.** The session's `messages` field is empty (either the
  session record does not exist yet or its history is empty). The chat harness loads (or
  initializes) the session, appends the inbound user message to history, and invokes the graph.
- **Harness §3.2 (existing-active-session) path.** The session's `messages` field is non-empty.
  The chat harness loads the session, appends the inbound user message to the existing history,
  and invokes the graph.
- **Harness §3.3 (signal-resume) path.** Inbound traffic carries a resume signal (per harness §6's
  signal coordinator). The chat harness dispatches the signal-resume invocation as harness §3.3
  specifies; `send()` is NOT the entry point for signal-resume (subscribed listeners per §8 are).
  An inbound `send()` call MUST NOT be classified as signal-resume.

**Initial-state construction.** For both §3.1 and §3.2 paths, the chat harness constructs the
graph's initial state by:

1. Loading the session state per sessions §4.1 (full-state load on existing sessions; default
   initial state on new sessions).
2. Appending the inbound user message to the `messages` field via the `append` reducer.
3. Threading the resulting state into `invoke()` along with the `session_id`.

The invoke call follows the harness §4 turn lifecycle (start, body, terminal). The chat harness
does NOT mutate any session-state field other than `messages` during initial-state construction;
graph-internal nodes are responsible for any further state evolution.

## 7. Outbound assistant message → response wiring

After `invoke()` returns `completed`, the chat harness extracts the new messages from the final
state's `messages` field and surfaces them on the `ChatTurnOutcome.completed.replies` list.

**New-message extraction.** "New messages" means messages appended during this turn — the tail
of the post-invoke `messages` list that was NOT present in the pre-invoke loaded state. The chat
harness MUST extract by index (track the pre-invoke history length; everything at that index and
beyond is new), NOT by content matching (content matching is brittle and would misclassify a
node that appends a message identical to one earlier in history).

**Ordering.** Multi-message replies preserve graph-execution order. The `messages` field's `append`
reducer composes appends in graph-execution order naturally; the chat harness MUST NOT re-order
the extracted tail. Determinism follows harness §11.

**All-roles inclusion.** The extracted tail includes messages of ALL roles — assistant text
replies, assistant messages with `tool_calls`, tool-role messages with `tool_call_id` + string
`content`. Tool-loop agents typically emit a three-message sequence within one invocation
(assistant with `tool_calls` → tool-role with the result → assistant with the final text reply
per llm-provider §3's canonical shape); all three surface on `replies`. Chat UIs decide how to
render tool-role intermediates (typically with "thinking" / "calling X" / "got result"
affordances); the spec contract does not constrain rendering.

**Empty tail.** A turn that adds NO new messages (e.g., a graph that handles the user message
purely via side effect and returns the state unchanged) surfaces as a `ChatTurnOutcome.completed`
with `replies = []` (empty list). Implementations MUST surface this case as `completed` (NOT
`errored`); the chat UI decides whether to expose the empty reply to the user (display a "no
response" affordance, retry, etc.).

## 8. Composition with suspension

When `invoke()` returns `suspended` (per harness §5.3), the chat harness returns a
`ChatTurnOutcome.suspended` carrying the signal descriptor, optional pending message, and the
paused invocation's id (per §5.2).

### 8.1 Pending message protocol

The graph MAY include an **upstream** node that returns a partial update appending a synthetic
assistant message to the `messages` state field via the standard `append` reducer; a
**downstream** node then calls `suspend()`. (The two are separate nodes because the
graph-engine node-body contract has a node either return a partial update OR call `suspend()`,
not both — `suspend()` raises before any return value is captured. The two-node composition
expresses "compose pending message, then suspend" as a graph topology.)

The synthetic messages typically inform the user the turn is awaiting an external signal —
"I'm waiting for approval to send this email," "Approve transferring $500 to Bob's account?",
etc. The chat harness MUST extract the pending-message tail from the suspended outcome's
`state.messages` (the same extraction rule from §7; the tail past the pre-invoke history
length) and surface it on the `ChatTurnOutcome.suspended.pending_messages` list. The engine
persists the post-update state at suspend time per suspension §4, so the upstream node's
appended messages are in the captured state by the time the chat harness reads the tail.

**Always-list shape.** `pending_messages` is always a `list[ChatMessage]` — empty when the
graph suspended without pre-emitting any message, one or more entries (in graph-execution
order) when it did. The always-list shape matches the OQ-6 resolution for
`ChatTurnOutcome.completed.replies`; per-language singular-or-list ergonomics is not a
spec-level concern, the shape is fixed.

**No chat-specific engine hook.** The pending-message pattern composes from existing graph
primitives — partial-update + edge + `suspend()`. The chat harness extracts the appended
messages via the same tail-extraction rule §7 uses for completed replies. Implementations
MUST NOT introduce a chat-specific engine hook (`chat.emit_pending()` or equivalent) for this
purpose — the graph-primitive composition is the canonical pattern.

**Multi-message pending tails.** Multiple synthetic messages MAY appear in the tail (e.g., an
assistant text-explanation message AND an assistant tool-call message describing the action
awaiting approval, then `suspend()`). All surface on `pending_messages` in graph-execution
order.

### 8.2 Signal-resume flow

When the resume signal arrives (per harness §6's signal coordinator):

1. The chat harness dispatches the signal-resume invocation per harness §3.3 (`invoke(resume_invocation=<paused_id>, signal_payload=<payload>)`).
2. The resumed invocation continues from the post-suspend node per suspension §7.
3. The post-resume turn's new messages (extracted per §7's tail rule) flow to the caller via a
   **subscribed listener** the caller registered against the chat harness.

**Subscribed-listener primitive.** The chat harness exposes a subscription primitive whose
per-language shape is implementation-defined (Python: `harness.subscribe(session_id, callback)`
returning a subscription handle; TypeScript: `harness.subscribe(session_id, callback)` returning
an unsubscribe function; equivalent in other languages). The subscription's callback fires
exactly once per resumed turn with the post-resume `ChatTurnOutcome.completed` (or
`ChatTurnOutcome.errored` if the resumed invocation errors).

**Listener-default rationale.** Chat UX is fundamentally asynchronous post-suspend — the user
should NOT have to send another message to receive the resume reply. A synchronous "next `send()`
returns the resume reply" shape would force the user to manually trigger reply delivery, which
contradicts the conversational UX expectation. The subscribed listener is therefore the default
path.

**Optional synchronous-next-`send()` alternative.** Implementations MAY ALSO support a shape where
the NEXT `send()` call on the same `session_id` (after the resume signal arrives) returns the
post-resume `ChatTurnOutcome` ahead of processing the next user message. Useful for
synchronous-style integrations (CLI agents, batch processors) that don't have a long-lived
subscription path. The subscribed-listener path MUST be available; the synchronous alternative is
OPTIONAL.

**Listener contract.** The listener callback fires after the post-resume `invoke()` returns,
with the same `ChatTurnOutcome` shape `send()` would return for a normal completed or errored
turn. The listener does NOT fire on the original suspending turn (which `send()` already returned
for); it fires only on the post-resume completion.

## 9. Composition with streaming (forward-looking)

The chat sub-spec defines the API-surface contract for a streaming variant of `send()` without
prescribing the engine-side hook implementation:

```
send_streaming(session_id: <string>, message: ChatMessage) -> <streaming-return-shape>
```

The exact streaming return shape — whether the iterator yields the final `ChatTurnOutcome` as
its last value, returns a tuple `(<async-iterator-of-chunks>, <awaitable-final-outcome>)`, or
uses a different shape — is deferred to the planned streaming proposal so the chat sub-spec
doesn't lock in a return shape before the streaming proposal can validate it against the
engine-side hook surface.

**v1 ships non-streaming only.** The non-streaming `send()` per §5 is the only callable v1
mandates. `send_streaming()` becomes mandatory when the streaming proposal lands and ratifies
the engine-side hook surface; until then, implementations MAY ship a non-conformant streaming
variant (or skip streaming entirely) without violating the chat-harness contract.

**Forward-compatibility.** This section defines only the method name and parameter semantics
today (`send_streaming(session_id, message)`); the return shape — including any discriminator
between chunks and the final outcome — is the streaming proposal's contract surface. The split
keeps the chat sub-spec from over-claiming a return type that hasn't been validated against the
engine-side hooks yet. The streaming proposal will fill in both the return shape and the engine
hooks (`token_chunk` / `tool_call_progress` / equivalent observer events) the streaming variant
consumes. Both compose when streaming lands; no v2 chat sub-spec revision is needed.

## 10. Error → user-facing reply mapping

Each of harness §7's three error buckets maps to a `ChatTurnOutcome.errored` shape with a
system-message-style reply:

### 10.1 Session-terminating errors (harness §7.1)

Categories: `session_load_failed`, `session_save_failed`, `session_state_migration_chain_ambiguous`
(sessions §10), `suspension_persistence_failed` (suspension §10), `harness_session_id_unresolved`
(harness §10).

Mapping: `ChatTurnOutcome.errored` with `error_bucket = "session_terminating"` and a reply
shaped:

> "This conversation can't continue. Please start a new one."

The chat UI MAY refuse further `send()` calls on this `session_id`. Implementations MAY customize
the reply text (i18n, brand voice); the bucket semantics — conversation cannot continue, user
should start a new session — MUST be preserved.

### 10.2 Retryable transient errors (harness §7.2)

Categories: `provider_unavailable`, `provider_timeout`, `provider_rate_limited` (llm-provider §7),
network-layer transient failures the underlying transport surfaces, observer-side transients.

Mapping: `ChatTurnOutcome.errored` with `error_bucket = "retryable_transient"` and a reply
shaped:

> "I had trouble responding. Try again in a moment."

The chat UI MAY auto-retry once per the application's retry policy. Implementations MAY customize
the reply text; the bucket semantics — transient failure, retry is appropriate — MUST be preserved.

### 10.3 User-correctable errors (harness §7.3)

Categories: `provider_invalid_request`, `provider_invalid_response`,
`chat_message_shape_invalid` (this sub-spec; see below), other user-input-shape failures.

Mapping: `ChatTurnOutcome.errored` with `error_bucket = "user_correctable"` and a reply
incorporating the upstream error's diagnostic detail, shaped:

> "That request couldn't be processed: <diagnostic>. Please adjust your message and try again."

The chat UI invites the user to retry with corrected input. Implementations MUST surface enough
of the underlying error's diagnostic message that the user can act on it; over-redaction
("an error occurred") defeats the user-correctable bucket's purpose.

### 10.4 New error category: `chat_message_shape_invalid`

Introduced by this capability. Surfaces when the inbound `ChatMessage` at `send()` entry fails
the §3.1 validation (missing required fields, unsupported content-block types, role-content
shape mismatches, malformed `tool_call_id` references). Routes through harness §7.3 (user-
correctable) on surfacing.

No change to harness §10's abstract error set; the new category lives in the chat sub-spec
layer and maps to a §7.3 bucket entry on the abstract surface.

## 11. Determinism

The chat sub-spec inherits harness §11's determinism rules unchanged. The `send()` callable adds
no nondeterminism beyond what the underlying graph + harness layers introduce. The
per-`session_id` serialization rule from §5.3 is a determinism-preserving constraint at the
chat-harness boundary; without it, concurrent `send()` calls under one session could produce
non-deterministic message-interleaving in history.

## 12. Cross-spec touchpoints

- **harness** (`spec/harness/spec.md`) — abstract foundation; this sub-spec
  layers chat-shaped surfaces over harness's contract. Specifically: §3 (dispatch paths), §4
  (turn lifecycle), §5 (outcome handling), §7 (error categorization), §8 (composition with
  sessions / suspension / checkpointing / observability).
- **sessions** (`spec/sessions/spec.md`) — sessioned-mode chat threads
  `session_id` per sessions §3; conversation history persists in session state.
- **suspension** (`spec/suspension/spec.md`) — chat composes with
  suspension via §8 above (pending-message protocol + subscribed-listener resume).
- **prompt-management** (`spec/prompt-management/spec.md`) —
  chat-prompt templates render into messages chat harnesses consume; content-block model shared
  with llm-provider §3.1.
- **llm-provider** (`spec/llm-provider/spec.md`) — `ChatMessage`
  mirrors llm-provider §3 unchanged; chat-harness messages pass through to `complete()` calls
  without translation.
- **observability** (`spec/observability/spec.md`) — turn-level
  wrapper spans per harness §4.6; no chat-specific span attributes introduced.
- **graph-engine** (`spec/graph-engine/spec.md`) — chat graphs are
  graph-engine graphs; the `messages: list[ChatMessage]` field follows canonical state-reducer
  conventions.
- **future memory capability** — cross-session memory (per-user profiles, episodic memory,
  vector retrieval) deferred to a future sub-spec; chat composes with it when its spec lands.

## 13. Out of scope

- **Cross-session memory.** Per-user profiles, episodic memory, semantic / vector-indexed
  retrieval. Per-session conversation history is in scope; anything spanning sessions is OUT.
  Deferred to a future memory capability that builds on this spec.
- **Specific chat-platform adapters.** Slack, Discord, Microsoft Teams, WhatsApp, customer-platform
  integrations. Each platform's message routing (mentions, threads, channels, attachments) is the
  platform-adapter package's concern; the chat sub-spec ratifies what the platform-adapters
  build on.
- **Multimodal output beyond text/image.** Audio, video, file outputs deferred to future
  prompt-management or llm-provider proposals that extend the content-block set; this sub-spec
  inherits additions automatically (the `ContentBlock` reference is unscoped).
- **Voice input / output.** A voice agent harness is a different harness type entirely
  (streaming-first, low-latency, with voice-activity-detection turn boundaries). Future sub-spec
  if real.
- **Rich-media compose UI.** What the chat UI looks like, how the user composes messages, how
  attachments are picked — application concern.
- **Conversation summary / context-window management.** Application strategies (summarization,
  sliding-window, vector retrieval over old turns) for managing long conversations against LLM
  context-window limits. The chat sub-spec exposes the raw `messages` field; the management
  strategy lives in application code or a future memory-adjacent capability.
- **Per-turn user-facing error tone customization.** The §10 mapping defines a three-bucket
  default; applications that want different tone (more / less verbose, branded language,
  localized) wrap the chat harness with their own error-mapping layer above the chat-harness
  surface.
- **Streaming protocol details.** The chat sub-spec defines the API-surface contract for the
  streaming `send_streaming()` variant; the actual streaming protocol (token format, chunk
  boundaries, backpressure, cancellation) lives in the planned streaming proposal.
- **Stateless completion harness.** "Send one message, get one reply, no memory" is a different
  harness type; if anyone wants it, it gets its own sub-spec ("harness-completion" or similar).
