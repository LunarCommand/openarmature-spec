# 0046: Prompt-Management — Multi-Message / Chat Prompt Rendering

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-30
- **Accepted:** 2026-05-30
- **Targets:** spec/prompt-management/spec.md (§3 *Prompt shape* — additive Chat-prompt variant alongside the existing Text-prompt variant; content segments support either a text-template `content` or a content-blocks `content` mirroring llm-provider §3.1 for multimodal user-message authoring; §6.render — render contract for chat prompts including a `placeholders` parameter for variable-length message-list injection, per-block render for content-blocks segments, and a narrowing of the Text-prompt render clause to exactly one text Message; §8 *Variable injection* — per-segment + per-block strict-undefined clarification; §11 *Errors* — empty-segment error, unfilled-placeholder error, and role-block compatibility error (image blocks user-only); §5 *PromptBackend protocol* — signature note that returned Prompts may be either variant; §12 *Cross-spec touchpoints* — observability §8.4.4 linkage unaffected); new conformance fixtures covering per-segment render, placeholder list-injection (including empty-list valid case), per-segment strict-undefined, empty-segment error, unfilled-placeholder error, content-blocks render (text + image-URL with variable substitution; inline image), role-block compatibility rejection, and observability linkage on a chat-shape prompt.
- **Related:** 0017 (prompt-management core — established the Text-prompt `template: str` shape and the single-`UserMessage` render contract that this proposal generalizes), 0015 (llm-provider multimodal images — defined the §3.1 ContentBlock shapes that this proposal's content-blocks chat segments mirror in template form), 0033 (prompt-management surface refinements — added `Prompt.observability_entities` for backend-keyed entity references; the §8.4.4 Langfuse Prompt-entity linkage is unaffected by message count and remains unchanged here)
- **Supersedes:**

## Summary

`Prompt` today carries a single `template: str` and `PromptManager.render`
produces a single `UserMessage`. Multi-role chat prompts (system + user,
or system + few-shot exchange + user) have no representation in the
prompt-management spec — a chat-shaped prompt sourced from a backend
that natively supports them (Langfuse `ChatPromptClient`, OpenAI-style
message arrays, hand-authored multi-turn templates) has nowhere to land
without collapsing it into a single user message and losing role
boundaries.

This proposal adds a **Chat-prompt variant** to `Prompt` alongside the
existing Text-prompt variant. The Chat variant carries a list of
role-tagged segments and (optionally) variable-length placeholder slots
for injecting message lists at render time. A content segment's
`content` MAY be either a text template (renders to a Message with text
content — the common case) or a list of content-block templates
mirroring llm-provider §3.1 — for authoring multimodal user messages
(text + image) inside a chat prompt. `PromptManager.render` renders
each segment in order and maps the result to `PromptResult.messages` —
which already permits a sequence per §4. The existing Text-prompt path
is unchanged at the data-model level and tightened at the §6 boundary
to render to exactly one text Message: multi-message and multimodal
prompts go through `chat_template`, keeping Text-prompt the simple,
single-string lane and `chat_template` the lane where structure lives.

`PromptBackend.fetch` keeps its signature — backends now return either
variant. The §3 shape choice (structure in the data model, not in a
parsed template string) keeps render trivial: per-segment substitution
with the existing strict-undefined rule applying independently per
segment (and per block within a content-blocks segment), and no cross-
implementation parser to keep in sync.

## Motivation

OA's chat-agent and multi-turn pipeline patterns require role-tagged
prompts. Two concrete shapes drive v1:

1. **Static role-tagged prompts** — a system preamble plus a user
   instruction, or a system preamble plus a few-shot exchange plus a
   user instruction. These are fixed-arity at author time; the variable
   substitution happens per segment.
2. **Variable-length chat history injection** — a chat-history layer
   that accumulates `Annotated[list[Message], append]` (or per-language
   equivalent) state across turns and re-feeds the full history to the
   model on each turn. The accumulated list is variable-length at
   render time; the prompt itself declares a placeholder slot at the
   position where the history should be injected.

Both shapes are first-class on backends that support them (Langfuse
chat prompts have role-tagged segments AND a placeholders mechanism for
message-list injection at compile time; OpenAI-style message arrays
have the role-tagged segment shape natively; many hand-authored
multi-turn templates carry both). Without the §3 Chat-prompt variant,
either shape has to be flattened into a single user-message string —
which loses the role boundaries chat-tuned models are trained on, and
loses the grounding for meta-references like "the second example
above" or "the user's prior question."

The cost of NOT specifying this is a per-implementation flattening
convention that diverges across backends and across language ports.
The cost of specifying it is a one-time additive extension to the
Prompt shape plus a corresponding render rule — both small, both
parallel to existing primitives, and both forward-compatible.

## Proposed change

### §3 *Prompt shape* — Chat-prompt variant (additive)

A `Prompt` is one of two variants:

- **Text prompt** — the existing shape; carries `template: <template
  representation>` per the §3 table, renders to a single `UserMessage`
  per §6.render. Unchanged.
- **Chat prompt** — new; carries `chat_template: list[ChatSegment]` in
  place of `template`. The ChatSegment record is one of:
  - **Content segment** — `{role: "system" | "user" | "assistant",
    content: <text-template OR content-blocks-template>}`. The `role`
    matches the canonical message roles from llm-provider §3 (Message
    shape). The `content` is one of:
    - **Text template** — the per-segment unrendered text in the
      implementation's chosen template representation (analogous to
      the Text-prompt `template` field — Jinja2 `Template` instance,
      string, AST, etc.). Renders to a Message with text content. The
      common case; valid for any role.
    - **Content-blocks template** — a non-empty ordered list of
      `ContentBlockTemplate` records mirroring llm-provider §3.1
      ContentBlock shapes (see *ContentBlockTemplate shapes* below).
      Renders to a Message with a content-blocks `content` per
      llm-provider §3. Image blocks are user-only per llm-provider
      §3.1.2 — a content-blocks segment containing any image block
      MUST have `role: "user"`; a non-user role with an image-block-
      containing template is a `prompt_render_error` (§11).
  - **Placeholder segment** — `{placeholder: str}`. The `placeholder`
    is a name identifying a slot that the caller fills at render time
    with a `list[Message]` (per llm-provider §3). Placeholder names
    MUST be unique within a single chat_template; a duplicate name is
    a `prompt_render_error` (§11).

**ContentBlockTemplate shapes.** A `ContentBlockTemplate` mirrors an
llm-provider §3.1 ContentBlock with variable-substitutable text fields.
The v1 set covers the user-message-authoring blocks (text + image);
thinking and redacted-thinking blocks are assistant-side round-trip
content (§3.1.4, §3.1.5) and are not author-template content — they
are out of scope for v1 author templates (see *Out of scope*).

- **Text block template** — `{type: "text", text: <template
  representation>}`. The `text` is a per-block template (same kind of
  representation as the segment's text-template alternative above).
  Renders by applying `variables` substitution per §6 / §8, producing
  an llm-provider §3.1.1 text block.
- **Image block template (URL source)** — `{type: "image", source:
  {type: "url", url: <template representation>}, media_type?,
  detail?}`. The `url` field is a per-block template; variable
  substitution produces the final URL. `media_type` and `detail` are
  literal values per llm-provider §3.1.2 / §3.1.3 (not templates) —
  they're fixed at authoring time and don't typically vary per render.
  Renders to an llm-provider §3.1.2 image block with `url`-source per
  §3.1.3.
- **Image block template (inline source)** — `{type: "image", source:
  {type: "inline", base64_data: <template representation>}, media_type:
  <template representation>, detail?}`. The `base64_data` and
  `media_type` fields are per-block templates (variable substitution
  lets a caller supply pre-encoded bytes and the media type at render
  time). `detail` is literal as above. Renders to an llm-provider
  §3.1.2 image block with `inline`-source per §3.1.3.

A ContentBlockTemplate's `type` discriminator matches the corresponding
llm-provider §3.1 ContentBlock `type`; the rendered ContentBlock shape
matches the llm-provider §3.1 shape exactly. Implementations MAY accept
any image `media_type` llm-provider §3.1.2 declares supported, with the
same minimum-set guarantee (`image/png`, `image/jpeg`, `image/webp`).

A given Prompt is exactly one variant — `template` and `chat_template`
are mutually exclusive on the same Prompt record. The variant is
implementation-discriminable (presence of `chat_template` versus
`template`; an explicit type tag; a discriminated-union shape — per
the language idiom).

The remaining §3 fields (`name`, `version`, `label`, `template_hash`,
`fetched_at`, `sampling`, `observability_entities`, `metadata`) are
identical across variants. `template_hash` for a Chat prompt is
computed over a canonical serialization of `chat_template` (segment
order, segment kind, role + content for content segments — and for
content-blocks segments, the full block sequence including each block's
type, source variant, and template fields — and name for placeholder
segments); two distinct chat_templates MUST hash to distinct values,
and two structurally-identical chat_templates (same segments in the
same order with the same roles + content / blocks + placeholder names)
MUST hash to identical values.

### §6.render — chat render contract + `placeholders` parameter

The signature gains an optional parameter:

```
render(prompt, variables=None, placeholders=None)
```

- `placeholders` — optional mapping of placeholder name → `list[Message]`
  (each `Message` per llm-provider §3). Default empty.

Render semantics for the Chat-prompt variant:

- For each segment in `chat_template`, in order:
  - **Content segment, text-template `content`.** Apply per-segment
    variable substitution to `content` using `variables` (§8 strict-
    undefined rule applies per segment, per §8 clarification below).
    The rendered text becomes a single `Message` whose `role` matches
    the segment's `role` and whose `content` is the rendered text. The
    resulting Message appends to `PromptResult.messages`.
  - **Content segment, content-blocks-template `content`.** For each
    block in the segment's content-blocks list, in order:
    - **Text block template.** Apply variable substitution to the
      block's `text` field; produce an llm-provider §3.1.1 text
      block with the rendered text.
    - **Image block template.** Apply variable substitution to the
      block's template fields per the *ContentBlockTemplate shapes*
      enumeration in §3 (URL form: substitute into `url`; inline
      form: substitute into `base64_data` and `media_type`); produce
      an llm-provider §3.1.2 image block with the resolved source.
      The literal `detail` field passes through unchanged.

    The rendered block list becomes the `content` of a single Message
    whose `role` matches the segment's `role`. The resulting Message
    appends to `PromptResult.messages`. §8 strict-undefined applies
    per text-template substitution within each block. Role-block
    compatibility (image blocks user-only) is enforced per §11.
  - **Placeholder segment.** Look up `placeholders[<placeholder name>]`.
    If present, the resolved `list[Message]` appends to
    `PromptResult.messages` in order — each injected Message MUST
    appear as a standalone Message in the output (no merging across
    adjacent placeholder slots and no merging with surrounding content
    segments). If the placeholder name is absent from `placeholders`
    (including the case where `placeholders` itself is `None` /
    omitted), raise `prompt_render_error` (§11).
- An injected `list[Message]` MAY be empty; an empty list contributes
  zero messages to the output and is NOT an error. This natively
  handles the chat-history "first turn / no prior messages" case
  without weakening the §8 / §11 empty-segment rule below.
- The `PromptResult` fields are populated per §4 as today; `messages`
  is the in-order rendered sequence; `rendered_hash` is computed over
  the canonical serialization of the full messages sequence (which
  already includes role + content + structure per §4 — including the
  content-block sequence for messages whose `content` is a block
  sequence); `variables` on the result reflect the input `variables`
  mapping (the `placeholders` mapping is NOT recorded on `variables` —
  implementations MAY surface it on a separate `placeholders` field on
  `PromptResult` for audit symmetry, but the v1 scope does not require
  it).

**Text-prompt render contract narrowing.** The §6.render text-prompt
clause that currently reads "templates MAY produce multiple messages —
e.g., a system + user split — when the template language supports it"
is REPLACED by: **a Text-prompt renders to exactly one Message with
text content; the rendered Message has `role: "user"` and `content`
equal to the rendered template text.** Multi-message and multimodal
prompts MUST use the Chat-prompt variant (`chat_template`). This
removes the ambiguity of the previous clause (no normative mechanism
was ever defined for Text-prompt multi-message output; no current
backend produces it) and makes the Text-prompt lane the simple, single-
text-message path. The `placeholders` parameter is ignored when
rendering a Text prompt (or implementations MAY raise on a non-empty
`placeholders` mapping for a Text prompt — the spec does not constrain
the choice; the normative contract is the Chat-prompt render rule).

### §8 *Variable injection* — per-segment / per-block strict-undefined

Add a clarifying paragraph to §8: when rendering a Chat prompt,
strict-undefined applies INDEPENDENTLY per segment, and within a
content-blocks segment also INDEPENDENTLY per block. A variable
referenced inside one segment but absent from `variables` raises
`prompt_render_error` for that segment (and aborts the render); a
variable referenced in segment N but not in segment M (where both
appear in the same `chat_template`) is checked only against segment
N's references when segment N is rendered. Within a content-blocks
segment, a variable referenced inside a text-block template's `text`
field, an image-block template's `url` field, or an image-block
template's `base64_data` / `media_type` fields raises
`prompt_render_error` when missing — independently per block. The
text-prompt strict-undefined rule (`StrictUndefined` Python / per-
language equivalent) and any implementation-specific opt-out apply
per segment and per block.

### §11 *Errors* — empty-segment, unfilled-placeholder, role-block compatibility

`prompt_render_error` extends with three additional triggers for Chat
prompts:

- **Empty content segment.** A text-template content segment whose
  rendered text is the empty string (after stripping, per
  implementation convention, or literally — implementations document
  their choice) raises `prompt_render_error`. For a content-blocks
  segment, an empty rendered text block (a `{type: "text"}` block
  whose rendered `text` is empty) raises the same error; an image
  block does not have a "rendered empty" equivalent (the source URL
  or inline data is either present or substitution-failed under §8).
  A content-blocks segment with an empty block list (zero blocks) is
  also `prompt_render_error`. There is NO silent-drop behavior; an
  empty segment / empty block is a bug worth surfacing (parallels §8's
  strict-undefined discipline). Callers needing optional or conditional
  segments must drive that at the data layer (build a `chat_template`
  that excludes the segment) rather than relying on render-time
  omission.
- **Unfilled placeholder slot.** A `chat_template` containing a
  `{placeholder: <name>}` segment whose `<name>` is not present in the
  `placeholders` mapping passed to `render` raises
  `prompt_render_error`. The empty-list valid case above is distinct:
  `placeholders[<name>] = []` is present-with-empty-value and is NOT
  an error; `<name>` absent from `placeholders` IS an error.
- **Role-block compatibility violation.** A content-blocks segment
  containing any image block (URL or inline) with a `role` other than
  `"user"` raises `prompt_render_error` — surfacing the llm-provider
  §3.1.2 "image blocks are user-only" constraint at the prompt
  boundary rather than waiting for the provider to reject the
  resulting Message. The error MUST be raised at render time (the
  earliest point at which both the segment's role and its block list
  are known) and abort the render before producing a partial
  `PromptResult`. Implementations MAY ALSO detect this at prompt-
  construction time (e.g., on a typed `ChatSegment` constructor) for
  faster feedback, but the spec-normative point of enforcement is
  render. Future llm-provider proposals adding role-specific block
  constraints extend this list in parallel.

### §5 *PromptBackend protocol* — signature unchanged

`fetch(name, label)` keeps its signature. The returned `Prompt` MAY be
either variant; backends SHOULD document which variants they produce
(e.g., a Langfuse-backed `PromptBackend` returns a Text-prompt for
Langfuse TEXT prompts and a Chat-prompt for Langfuse `ChatPromptClient`
prompts, mapped one-to-one). The protocol does not constrain the
variant a backend produces; callers that need a specific variant
should validate the returned Prompt at the call site.

### §12 *Cross-spec touchpoints* — observability §8.4.4 unaffected

Add a confirmation paragraph: the `observability_entities['langfuse_prompt']`
→ observability §8.4.4 Generation linkage is keyed on the prompt's
identity (`name + version + label`), not on the rendered-message count.
A Chat-prompt that links to a Langfuse Prompt entity via
`observability_entities` flows through §8.4.4's lookup exactly as a
Text-prompt does; multi-message rendering introduces no §8.4.4 changes.

## Conformance test impact

### New fixtures

Nine new fixtures under `prompt-management/conformance/` (numbers
assigned at acceptance), plus a tenth for observability linkage:

1. **Chat-prompt per-segment render (static).** A `chat_template` with
   a system segment + a user segment (both text-template content),
   each carrying one variable. Render with the variable mapping.
   Asserts the `PromptResult.messages` list has length 2, each Message
   carries its segment's role, and per-segment variable substitution
   applied independently.
2. **Placeholder list-injection (non-empty).** A `chat_template` with a
   system segment + a placeholder slot named `history` + a user
   segment. Render with `placeholders={"history": [Message(role=user,
   content="prior turn"), Message(role=assistant, content="prior
   reply")]}`. Asserts the `PromptResult.messages` sequence is `[system,
   user, assistant, user]` with the injected pair appearing in order
   between the system and final user segments.
3. **Placeholder list-injection (empty-list valid).** Same shape as
   above, but `placeholders={"history": []}`. Asserts
   `PromptResult.messages` is `[system, user]` (length 2) with no
   error.
4. **Per-segment strict-undefined.** A `chat_template` with two
   content segments, each referencing a variable; render with only one
   variable supplied. Asserts `prompt_render_error` raised; the error
   identifies which segment's variable was missing (implementations
   document the error message form; the spec asserts the error is
   raised and the render is aborted before any partial
   `PromptResult` is produced).
5. **Empty content segment.** A `chat_template` with a content segment
   whose template renders to the empty string after substitution
   (e.g., `content="{{user_input}}"` with `variables={"user_input":
   ""}` if the implementation treats empty-after-substitution as
   empty, OR a literally-empty `content=""` segment). Asserts
   `prompt_render_error` raised.
6. **Unfilled placeholder.** A `chat_template` containing a
   `{placeholder: "examples"}` segment, rendered with `placeholders`
   absent (or present but not containing `"examples"`). Asserts
   `prompt_render_error` raised.
7. **Content-blocks render (text + image-URL).** A `chat_template` with
   a system segment (text-template) + a user segment whose `content`
   is a content-blocks list containing one text block
   (`{type: "text", text: "describe {{product}}:"}`) and one URL-source
   image block (`{type: "image", source: {type: "url", url:
   "{{photo_url}}"}}`). Render with `variables={"product": "widget",
   "photo_url": "https://example.com/widget.png"}`. Asserts the
   `PromptResult.messages` sequence has length 2; the user Message's
   `content` is a content-block sequence of length 2 with the
   substituted text and the substituted URL.
8. **Content-blocks render (inline image).** A `chat_template` with a
   single user segment whose `content` is a content-blocks list
   containing one inline-source image block (`{type: "image", source:
   {type: "inline", base64_data: "{{img_b64}}"}, media_type:
   "{{img_media_type}}"}`). Render with
   `variables={"img_b64": "<short test payload>", "img_media_type":
   "image/png"}`. Asserts the resulting Message carries an inline-
   source image block with the substituted base64 data and media type.
9. **Role-block compatibility rejection.** A `chat_template` with a
   `role: "system"` content segment whose `content` is a content-
   blocks list containing an image block. Asserts `prompt_render_error`
   raised at render time (parallels llm-provider §3.1.2's user-only
   constraint, surfaced at the prompt boundary).

A tenth fixture confirms observability linkage on a Chat-prompt
(adapted from the existing §8.4.4 fixture pattern): a Chat-prompt
carrying `observability_entities['langfuse_prompt']` flows through the
§8.4.4 lookup and produces a Generation linked to the Prompt entity
exactly as a Text-prompt does.

### Unaffected fixtures

All existing prompt-management fixtures exercise the Text-prompt path
and remain valid unchanged — the Text-prompt data-model shape is
untouched and the §6 narrowing aligns the Text-prompt render contract
with the single-text-Message behavior the existing fixtures already
exercise (none of them depend on the previous "MAY produce multiple
messages" clause).

## Versioning

**MINOR bump** (pre-1.0). On acceptance the whole-spec SemVer
increments:

- New Chat-prompt variant on `Prompt` (additive — existing Text-prompt
  data-model shape unchanged).
- New content-blocks `content` alternative on chat content segments
  (additive — text-template `content` remains the common case;
  content-blocks segments enable multimodal user-message authoring
  inside a chat prompt without changing the Text-prompt path or any
  llm-provider §3 contracts).
- New `placeholders` parameter on `PromptManager.render` (additive —
  default empty mapping is the existing behavior for Text prompts; the
  parameter is meaningful only for Chat prompts and the existing
  single-argument form of `render(prompt, variables=...)` continues to
  work for Text prompts).
- §6.render Text-prompt clause **narrowed** — the previously-vague
  "templates MAY produce multiple messages" line is replaced with a
  normative "Text-prompt renders to exactly one Message with text
  content; multi-message and multimodal prompts MUST use
  `chat_template`." This is technically a narrowing of the previous
  contract (the old clause permitted implementation-defined multi-
  message output), but no current backend or implementation produces
  multi-message Text-prompt output (the clause was always informative
  and no normative mechanism was ever defined), and existing
  conformance fixtures all exercise the single-Message Text-prompt
  behavior. Practical breakage risk is zero; the narrowing makes the
  Text-prompt vs Chat-prompt lanes explicit.
- New conformance fixtures (Chat-prompt cases including content-blocks
  + role-violation rejection). Existing Text-prompt fixtures unchanged.
- `PromptBackend.fetch` signature unchanged.

The change is backwards-compatible for callers using the Text-prompt
path. Callers that want to consume Chat prompts opt in by checking the
returned variant and (if applicable) supplying a `placeholders` mapping
at `render` time, and optionally authoring content-blocks segments for
multimodal user messages.

## Alternatives considered

1. **Structured-template mini-language inside `template: str`.** Keep
   `Prompt.template` a single string and define a structured template
   format the renderer parses to extract role-tagged segments (e.g.,
   `[ROLE:system] ... [/ROLE] [ROLE:user] ... [/ROLE]`). Rejected: every
   implementation would need to parse the format identically — a
   cross-impl conformance burden plus divergence risk (parser
   discrepancies are notoriously subtle). The data-model approach (a
   list of explicit segments) sidesteps this entirely by carrying the
   structure as structured data rather than as a parsed string. The
   data-model approach also keeps the render contract trivial — per-
   segment substitution with the existing primitives — instead of
   coupling it to a spec-defined parser.

2. **Optional / conditional segments (`{omit_if_empty: true}`).** Allow
   content segments to declare a "drop silently if empty" flag.
   Rejected: silent omission contradicts §8's strict-undefined
   discipline (variables that render empty are bugs worth surfacing),
   and the chat-history "no prior turns" case is handled natively by
   empty-list placeholder injection (a `placeholders[<name>] = []`
   contributes zero messages without invoking the empty-segment rule).
   No concrete case where a system preamble should drop silently has
   surfaced; if one does later, a follow-on proposal can revisit
   without weakening the v1 discipline.

3. **Per-segment sampling overrides on `chat_template`.** Allow each
   segment to carry its own `sampling: SamplingConfig` overriding the
   prompt-level field. Out of scope for v1: per-segment sampling has no
   coherent semantics — sampling is per-LLM-call, not per-message —
   and would tangle with §3 `Prompt.sampling` rather than parallel it.
   A future proposal could add per-segment prompt-side metadata if a
   concrete use case emerges.

4. **Inline placeholder syntax inside content (`{{placeholder:name}}`
   mid-string).** Allow placeholder slots to appear within the rendered
   text of a content segment rather than only as standalone segments.
   Rejected for v1: matches no existing backend's mechanism (Langfuse's
   placeholder mechanism is segment-level, not inline), introduces a
   new substitution path distinct from variable injection, and
   complicates the per-segment render rule. The segment-level shape
   covers the v1 use cases; a future proposal can add inline
   placeholders if a concrete need emerges.

5. **New `render_chat()` method separate from `render()`.** Have the
   manager expose a separate method for chat rendering instead of
   extending the single `render(prompt, variables, placeholders)`
   surface. Rejected: callers would need to dispatch on the Prompt
   variant before choosing the method, which is awkward, and the
   `render()` method already discriminates internally on variant for
   the rest of its contract (Text vs Chat). One entrypoint with an
   optional `placeholders` kwarg is simpler.

6. **Extending the Text-prompt path to support content-blocks output
   (multimodal Text-prompt).** Allow `Prompt.template` to optionally
   render to a Message with a content-block sequence (text + image),
   either via a structured template DSL inside the string, a bolt-on
   `Prompt.images` field, or variables that resolve to content blocks
   instead of strings. Rejected: each form has fatal issues. A
   structured DSL inside the template string is exactly alternative 1
   (cross-impl parser drift). A `Prompt.images` bolt-on field is
   awkward, doesn't compose with mid-string image positioning, and
   gives Text-prompt two ways to express content. Variables resolving
   to content blocks invents a new substitution path that breaks the
   "variables are scalars" mental model and still needs template-side
   syntax to position the block within the rendered output. All three
   converge to "if you want structure, declare structure" — which is
   exactly the Chat-prompt variant. A caller wanting a single-message
   prompt with text + image authors a `chat_template` with one user
   segment carrying a content-blocks list; the migration is
   mechanical, the data model expresses the structure explicitly, and
   the spec keeps two clean lanes (text-only Text-prompt vs structured
   Chat-prompt) instead of growing a third hybrid lane.

## Out of scope

- Optional / conditional segments (alternative 2).
- Per-segment sampling overrides (alternative 3).
- Inline placeholder syntax mid-content-string (alternative 4).
- Text-prompt content-blocks output (alternative 6). Text-prompt
  remains the simple single-text-Message lane; multimodal authoring
  goes through `chat_template` with a content-blocks user segment.
  The Text-prompt § narrowing in this proposal makes the lane
  separation explicit.
- Mid-render branching (a `chat_template` whose segment list depends on
  variable values at render time).
- New roles beyond `"system"`, `"user"`, `"assistant"` (the Chat-prompt
  segment roles match llm-provider §3's canonical Message roles; a
  future proposal extending llm-provider Message roles would extend
  the Chat-prompt segment roles in parallel).
- Thinking / redacted-thinking blocks in author templates (llm-provider
  §3.1.4 / §3.1.5 — these are assistant-side round-trip content with
  provider-bound signatures; they're not author-template content and
  wouldn't sensibly be emitted by a prompt template).
- Tool-call segments (assistant messages with `tool_calls` per
  llm-provider §3 — could be expressed by injecting an
  `assistant`-role Message carrying tool_calls via the placeholder
  mechanism; first-class authoring of tool-call segments inside a
  `chat_template` is a follow-on if a concrete need emerges).
