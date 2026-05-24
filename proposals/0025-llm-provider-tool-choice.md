# 0025: LLM Provider — `tool_choice` Parameter

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-24
- **Accepted:**
- **Targets:** spec/llm-provider/spec.md (modifies §5 *Provider interface*; modifies §7 *Error semantics* — clarification, no new categories; adds row to §8.1.1 *Request mapping*)
- **Related:** 0006 (LLM provider core), 0019 (multi-provider wire-format extension)
- **Supersedes:**

## Summary

Extend the existing `complete()` operation with an optional `tool_choice` parameter that
constrains the model's tool-calling behavior. Four modes: `"auto"` (default — model decides),
`"required"` (model MUST call at least one tool), `"none"` (model MUST NOT call tools), and
`{type: "tool", name: <string>}` (model MUST call the named tool). The parameter is
pre-send-validated against `tools`: combinations that ask the model to call a tool that wasn't
declared (or wasn't supplied at all) raise `provider_invalid_request`. When `tool_choice` is
omitted, behavior is preserved exactly as in v0.4.0 — the engine omits the wire-level field
and the provider's default applies. Add a row to §8.1.1's OpenAI request mapping for the new
parameter. No new error categories; no changes to §6 `Response`. Future §8.X subsections
(Anthropic Messages, Google Gemini) inherit the parameter and provide their own per-provider
wire mapping rows.

## Motivation

Three of the four providers OA currently targets or anticipates targeting — OpenAI (shipped
in §8.1), Anthropic Messages, and Google Gemini — expose tool-choice control. Each has a
slightly different wire shape, but the semantic surface is the same: the caller pins the
model's tool-calling behavior to one of four modes. Today, OA's `complete()` exposes none of
this. A pipeline that wants deterministic tool calling (a routing node that MUST produce a
tool call, a guarded LLM call that MUST NOT call tools) reaches around the abstraction into
provider-specific extras, or — more commonly — papers over it with prompt-engineering and
hopes for the best.

This is the same shape of gap that motivated proposal 0016 (structured output): a
cross-provider feature that's part of every major LLM SDK's surface but is currently absent
from OA's abstract Provider interface. Leaving `tool_choice` out forces every tool-using node
to either trust the model's defaults (works most of the time, fails noisily in production) or
reach through to provider-specific config (works, but breaks the cross-language consistency
promise the §3 / §5 / §7 contract delivers).

**Why before the §8.2 Anthropic and §8.3 Gemini follow-ons.** Adding `tool_choice` to `complete()`
after the per-provider mappings ship would require retrofitting two new §8.X subsections AND
§8.1.1 — three mapping rows updated in lockstep. Adding it before means each §8.X follow-on
ships with a `tool_choice` row from the start, no retrofit. Small spec surface, big
sequencing win.

**Provider-level placement, not middleware.** A middleware-level tool-choice wrapper can't
reach the wire. The provider's native tool-choice path is more efficient (one round trip
constrained on the wire vs an unconstrained call + post-hoc rejection + retry) and more
honest (the model receives the constraint as part of the prompt, not as caller-side filtering
of its outputs). Provider-level placement opens the native path; userland middleware patterns
remain buildable on top for users who want them.

## Detailed design

### §5 Provider interface: extend `complete()` with `tool_choice`

Amend the existing `complete()` operation in §5 to accept an optional `tool_choice`
parameter. The full updated signature (described abstractly; per-language ergonomics decide
positional-vs-keyword conventions):

#### `complete(messages, tools=None, config=None, response_schema=None, tool_choice=None)`

Async. Performs a single completion call. When `tool_choice` is supplied, the call additionally
constrains the model's tool-calling behavior.

- `messages` — unchanged.
- `tools` — unchanged.
- `config` — unchanged.
- `response_schema` — unchanged.
- `tool_choice` — optional tool-choice constraint. One of:
  - `"auto"` — the model decides whether to call tools. Equivalent to the v0.4.0 default
    behavior when `tools` is non-empty; with `tools` empty / absent, the model has no tools
    to call regardless.
  - `"required"` — the model MUST return at least one tool call. `tools` MUST be non-empty
    when `tool_choice` is `"required"`; violations raise `provider_invalid_request` (§7) at
    pre-send validation.
  - `"none"` — the model MUST NOT call tools, even if `tools` is supplied. Useful for
    guarded LLM calls or for explicitly disabling tool-calling on a per-call basis without
    constructing a tools-less request.
  - `{type: "tool", name: <string>}` — the model MUST call the named tool exactly. The
    named tool MUST appear in the supplied `tools` list; violations raise
    `provider_invalid_request` (§7) at pre-send validation. (`tools` MUST be non-empty in
    this case, by transitivity.)

  Default is `None` / absent. When `tool_choice` is `None` / absent, the engine MUST omit the
  wire-level `tool_choice` field — the provider's own default applies. This preserves the
  v0.4.0 behavior exactly (no wire-shape change for callers who don't supply `tool_choice`).

  The discriminated-union shape (three string literals plus one record form) is described
  abstractly; per-language ergonomics decide the type (e.g., Python could use
  `Literal["auto", "required", "none"] | ToolChoiceForce`; TypeScript could use a string
  union with the record form discriminated by `type`). Implementations MUST validate the
  shape at call time before sending.

Operation semantics:

- `complete()` MUST NOT mutate `tool_choice`.
- `complete()` MUST validate `tool_choice` against `tools` per the rules above before sending.
  The validation is part of the §7 `provider_invalid_request` surface; the rules to validate
  are:
  1. `tool_choice="required"` requires `tools` non-empty.
  2. `tool_choice={type: "tool", name: X}` requires `tools` non-empty AND X to be a `Tool.name`
     in the supplied list.
  3. `tool_choice="auto"` and `tool_choice="none"` have no `tools`-related preconditions.

When `tool_choice="none"` is supplied AND the provider returns tool calls anyway, the
implementation MUST surface what the provider returned (per the §6 transparency principle)
without re-validating against the constraint post-hoc. The constraint is a request-side hint
the implementation passes to the wire; whether the model honored it is observable via the
returned `finish_reason` (`"tool_calls"` means the model called tools regardless of the
"none" hint) but is not enforced by the framework. Providers vary in whether they honor
`"none"` strictly; OpenAI's `tool_choice: "none"` is documented as suppressing tool calls,
but provider compliance is a provider-quality concern, not a framework-policed contract.

### §6 Response and configuration: no changes

`tool_choice` is request-side only. The response shape is unchanged: tool calls (or their
absence) surface via `Response.finish_reason` and `Response.message.tool_calls` as in v0.4.0.
Whether the model honored the `tool_choice` constraint is observable from the returned
fields but is not normalized into a separate "did the model honor it" flag.

### §7 Error semantics: clarification, no new categories

The pre-send validation failures introduced by `tool_choice` route through the existing
`provider_invalid_request` category (§7). No new category is needed; the §7 surface remains
exactly as in v0.16.0+.

A clarifying paragraph in §7 (or a sub-bullet under the `provider_invalid_request` entry)
SHOULD enumerate the three new validation failure modes:

- `tool_choice="required"` supplied with empty / absent `tools`.
- `tool_choice={type: "tool", name: X}` supplied with empty / absent `tools`.
- `tool_choice={type: "tool", name: X}` supplied with X not in the supplied `tools` list.

Each MUST raise `provider_invalid_request` at pre-send validation, before the implementation
contacts the provider.

### §8.1.1 OpenAI request mapping: add `tool_choice` row

Add a new row to the §8.1.1 request mapping table:

| Spec `tool_choice` | OpenAI wire body |
|---|---|
| `None` / absent | (field omitted from request body) |
| `"auto"` | `tool_choice: "auto"` |
| `"required"` | `tool_choice: "required"` |
| `"none"` | `tool_choice: "none"` |
| `{type: "tool", name: X}` | `tool_choice: {type: "function", function: {name: X}}` |

The `None`-omitted-from-wire row is load-bearing for the backward-compat story: existing
callers who never supply `tool_choice` see no wire-shape change, and the OpenAI provider's
own default (which itself depends on whether `tools` is non-empty) applies unchanged.

### Cross-spec touchpoints

- **§3 message shape** — no changes. `tool_choice` is a `complete()` parameter, not a
  message-shape concern.
- **§4 Tool definition** — no changes. `tool_choice` references `Tool.name` but doesn't
  modify the `Tool` record.
- **§9 Determinism** — no changes. `tool_choice` is part of the input to a `complete()` call;
  same input (including same `tool_choice`) MUST produce same output per the existing §9
  contract, modulo provider non-determinism.
- **§10 Out of scope** — no changes. `tool_choice` is in-scope for v0.20.0+.
- **Future §8.X subsections (Anthropic, Gemini, …)** — each MUST include a `tool_choice`
  mapping row in its request-mapping subsection. The §8.X template (separately proposed
  as 0026) recommends the structure but does not block individual §8.X proposals from
  diverging if a provider's tool-choice shape genuinely doesn't fit.

## Conformance test impact

Add fixtures under `spec/llm-provider/conformance/`. Each fixture is a pair
(`NNN-name.yaml` + `NNN-name.md`) per the conformance README. Three fixtures (table-style
where the cases share setup):

- **`029-tool-choice-modes`** — table-style. Cases: `auto`, `required`, `none`, `default`
  (no `tool_choice` supplied). For each, verifies the outbound wire `tool_choice` value
  (or absence) and that `Response.finish_reason` is consistent with the mode (`required`
  → `"tool_calls"`; `none` → `"stop"`; `auto` and `default` → either, depending on the
  mock response).
- **`030-tool-choice-force-specific`** — fan-out-of-one-case fixture for the
  `{type: "tool", name: X}` mode. Verifies the wire body's `tool_choice.function.name`
  matches X, and the returned tool call's `name` matches X.
- **`031-tool-choice-validation`** — table-style covering the three pre-send validation
  failure modes: `required` with empty tools; force-specific with empty tools; force-specific
  with name not in supplied tools. Each case asserts `provider_invalid_request` is raised
  before any HTTP request is sent.

Fixture numbering starts at 029 (the most recent llm-provider fixture is 028).

## Alternatives considered

### Don't spec `tool_choice`; rely on provider-specific extras

Rejected. This is the status-quo path — each provider implementation exposes its own
mechanism (a kwarg, an extras dict, etc.) for the caller to set the underlying wire field.
Loses cross-language consistency (Python's mechanism differs from TypeScript's), loses the
ability to validate at the framework layer (each impl re-implements the same validation
logic), and breaks the cross-provider portability promise — a pipeline written against the
abstract Provider interface can't pin tool-calling behavior without reaching through to a
provider-specific surface.

### Add `tool_choice` after the §8.2 Anthropic / §8.3 Gemini follow-ons land

Rejected per the *Motivation* sequencing argument. Retrofitting three §8.X subsections in
lockstep is more error-prone than adding one parameter to `complete()` before two of them
exist. The marginal cost of adding `tool_choice` now is small (one parameter, four
discriminated-union variants, three validation rules); the cost of retrofitting later
compounds with each provider already in spec.

### Surface a `tool_choice_honored` flag on `Response`

Rejected. A normalized "did the model honor the constraint" field would require post-hoc
validation against `finish_reason` / `tool_calls`, which is observable from those fields
directly. Adding a redundant flag conflates framework-policed contract (which `tool_choice`
isn't) with provider-quality observation (which is the caller's concern). The §6
transparency principle (surface what the provider returned without re-deriving) argues
against the flag.

### Multiple force-specific tools (`{type: "tool", names: [X, Y]}`)

Rejected. Allowing multiple forced tools (model must call any one of X or Y) is a
plausible-but-unwarranted generalization. None of the three target providers (OpenAI,
Anthropic, Gemini) support multi-tool forced-choice on the wire as of 2026-05. A follow-on
MAY add it if providers converge on a shape, but the single-tool variant covers the
load-bearing use case (routing-node-style guards) and matches existing provider surfaces.

### A separate `force_tool(name)` helper instead of a discriminated union

Rejected. A helper-style API (`complete(..., force_tool="search")`) reads ergonomically for
the force-specific case but doesn't compose with the other three modes. The discriminated
union covers all four modes uniformly and the per-language ergonomics layer can still wrap
common cases (e.g., a Python `complete(..., tool_choice=force_tool("search"))` helper that
constructs the record).

## Open questions

None at this time. The two questions raised during drafting (force-specific
shape: discriminated-union vs flat; interaction with `finish_reason: "error"`
responses) were resolved during pre-PR review — the discriminated-union shape
is kept for extensibility, and the "constraint applies to the request; the
response is what the provider sent regardless" framing is the proposal's
position without need of an explicit response-side clause.
