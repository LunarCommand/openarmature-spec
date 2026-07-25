# 0108: Declared-field-vs-extras wire-key collision

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-24
- **Ships as:** _assigned at acceptance (MINOR)_
- **Targets:** spec/llm-provider/spec.md **§6** (extend the *Managed-field collision* rule: a wire key the
  mapping produces as the realization of a **declared** OA field is managed while produced — **general**, over
  every declared field; the case 0105 deferred), **§8.1 / §8.2 / §8.3** (enumerate the declared-field
  realizations across the llm mappings: the scalar sampling fields, `stop_sequences` → `stop` (§8.1) /
  `stop_sequences` (§8.2) / `stopSequences` (§8.3), and `stream` (§8.1 OpenAI only — §8.2 / §8.3 reject
  streaming)), inherited by retrieval-provider §10; spec/retrieval-provider/spec.md **§8.2** (Jina
  `task` ← `input_type`, with the unmanaged-when-absent escape hatch) plus the `dimensions` realizations.
  Conformance: collision fixtures for a scalar field (reject), `stop` (merge), `stream` (reject), and Jina
  `task` (reject + escape hatch).
- **Related:** 0105 (defined the managed-field collision rule and *deferred this exact case* to a uniform pass —
  this is that pass), 0099 (the §8.2 Jina note that a server extending the wire with an `input_type`-style field
  takes it through the extras bag — reconciled here), and §6 *Extras pass-through*
- **Supersedes:**

## Summary

0105 defined what happens when an undeclared extras key collides with a wire field the mapping **manages for its
own correctness** (merge if list-shaped, reject if conflicting non-additive), and enumerated the managed-internal
keys. It **deferred** a structurally different collision to "a uniform pass, settled for all three at once": a
wire key that **realizes a declared OA field**, shadowed by an extras key of the wire name —

- llm-provider `stop` (the wire realization of the declared `stop_sequences`),
- llm-provider `stream` (the wire realization of `complete(stream=…)`),
- retrieval-provider §8.2 Jina `task` (the wire realization of the declared `input_type`).

Here the caller has a **sanctioned declared path** *and* names the raw wire key through the extras bag. This
proposal settles it with a single **general** rule, unifying it under 0105 rather than inventing a second
mechanism. `stop`, `stream`, and `task` are the cases that *motivated* it — their collision is non-obvious (a
renamed wire key, a list shape, a mode switch) — but the rule governs **every** declared field realized on the
wire, including the scalar sampling fields (`temperature`, `top_p`, `max_tokens`, …) whose declared name equals
their wire name:

> **A wire key the mapping produces as the realization of a declared OA field is a managed field (§6) while it
> is producing it.** While the declared field is set (so the mapping emits the wire key), a colliding extras key
> is governed by 0105: an **additive / list-shaped** field (`stop_sequences`) **merges** the declared value with
> the caller's; a **non-additive** scalar field (`temperature`, `top_p`, `stream`, `input_type`→`task`, …) takes
> a **matching** extras value as a no-op and **rejects a conflicting** one pre-send (`provider_invalid_request`).
> While the declared field is **absent** (the mapping emits no such wire key), the extras key is **unmanaged**
> and rides untouched — preserving the escape hatch for a raw wire value the declared field does not model. A
> declared field whose value is **always determined** (the `stream` mode) has no absent branch and is always
> managed.

## Motivation

0105 drew the line deliberately: its managed-internal keys (`model` / `messages` / `tools` / `tool_choice`,
`response_format`, `stream_options`, retrieval `truncate` / `embedding_types`) are fields the mapping sets for
its **own** correctness, which the caller does not set another way. The three keys here are different — the
caller *does* have a declared way to set them, and the extras key duplicates it using the wire name. 0105 flagged
that this needs deciding **uniformly** (the three share the mechanism) and left it open so it would not be
answered inconsistently key-by-key. Today the outcome is undefined: an extras `stop` next to `stop_sequences`,
an extras `stream` next to `complete(stream=…)`, or an extras `task` next to `input_type` has no specified
behavior, so two conforming implementations diverge (forward-both, let-extras-win, let-declared-win, reject).

The unifying insight is that **once the mapping is producing the wire key from the declared field, the key is
managed** — the mapping owns it, and 0105 already says what a managed collision does. The only addition 0105
needs is that a wire key can become managed by *realizing a declared field*, not only by being set for the
mapping's internal correctness. The **"while producing it"** qualifier (already in 0105 for conditionally-managed
fields like `response_format`) is what preserves the escape hatch: when the declared field is absent, the mapping
emits nothing, the key is not managed, and an extras value rides untouched.

## Proposal

### 1. §6 — declared-field realizations are managed while produced

Extend §6's *Managed-field collision* clause: a wire-body field is **managed** not only when the mapping sets it
for its own correctness (0105), but also when the mapping **produces it as the wire realization of a declared OA
field** — and, as with 0105's conditionally-managed fields, only **while** the mapping is producing it (i.e.
while the declared field is set). This is **general**: it governs *every* declared field the mapping puts on the
wire — the scalar sampling fields (`temperature`, `top_p`, `max_tokens`, `seed`, …) whose wire name equals the
declared name, plus `stop_sequences`, `stream`, and `input_type`→`task`. The resolution is 0105's, unchanged:
additive/list-shaped → merge; non-additive → matching no-op, conflicting → reject pre-send
`provider_invalid_request`. When the declared field is absent the wire key is **not** managed and the extras key
keeps untouched pass-through — **except** a field whose value is always determined (a mode switch like `stream`),
which has no absent branch and is always managed. Each §8.x mapping enumerates the declared fields it realizes;
the wire name may differ from the declared name (see §2), so the *colliding extras key* is the **wire** name.

### 2. §8.1 / §8.2 / §8.3 — the llm-provider realizations

The declared `RuntimeConfig` sampling fields (`temperature`, `top_p`, `max_tokens`, `seed`, `presence_penalty`,
…) are realized under their own name on every llm wire mapping. Each is a **managed non-additive scalar** while
the caller sets it: a matching extras value is a no-op, a **conflicting** one is **rejected pre-send**
`provider_invalid_request`. This closes the silent double-set where an extras `temperature` would override the
declared one.

- **`stop_sequences` (list-shaped; the wire name differs per mapping).** The declared `stop_sequences` is
  realized as `stop` (§8.1 OpenAI), `stop_sequences` (§8.2 Anthropic), and `stopSequences` (§8.3 Gemini) — each
  mapping enumerates its own wire name, and the colliding extras key is that **wire** name (an extras `stop`
  collides on OpenAI, an extras `stop_sequences` on Anthropic, an extras `stopSequences` on Gemini). While
  `stop_sequences` is set, the extras value **merges** with it (declared value(s) first, de-duplicated
  first-occurrence-wins) — the union of stop sequences, per 0105's merge arm; an extras value in the wire's
  **scalar** form (a single string, where the wire accepts string-or-array as OpenAI's `stop` does) is coerced
  to a one-element list before the merge. A merged list that exceeds a provider's per-request cap (OpenAI's
  four) is **not** clamped client-side — the over-cap request is sent and the provider's rejection surfaces
  `provider_invalid_request`, fail-loud (the §8 range-validation posture). While `stop_sequences` is absent, the
  mapping emits no such key and the extras key rides untouched.
- **`stream` (§8.1 OpenAI only).** `stream` is a non-additive scalar that selects the response mode, and the
  mapping's streaming-vs-unary consumer depends on the wire value matching the call. Only the OpenAI mapping
  realizes it — §8.2 Anthropic and §8.3 Gemini do not implement streaming and reject a `stream`-set call
  outright (§5), so they never emit wire `stream`. On §8.1 it is managed **whenever the call fixes a stream
  mode** (always — `complete(stream=…)` has a value): a matching extras `stream` is a no-op, a **conflicting**
  one (e.g. `stream: false` on a streaming call) is **rejected pre-send**. Because the mode is always
  determined, `stream` has no "declared field absent" branch.

### 3. retrieval-provider realizations — §8.2 Jina `task`

Retrieval's declared `dimensions` field is realized on the wire (`dimensions` on §8.1 TEI / §8.3
OpenAI-compatible; `output_dimension` on §8.4 Cohere) and is a managed non-additive scalar per §1, like the llm
sampling fields — each mapping enumerating its own wire name. The load-bearing retrieval case is **Jina `task`**:
the §8.2 wire realization of the declared `input_type`, whose escape hatch must survive.

While `input_type` is set (the mapping produces `task`), an extras `task` is a non-additive scalar: matching →
no-op, **conflicting** → reject pre-send `provider_invalid_request`. While `input_type` is **absent**, the
mapping produces no `task`, and an extras `task` rides untouched — exactly the existing escape hatch the §8.2
note describes (a raw `task` value the OA `input_type` set does not model, e.g. a model-specific
`classification` / `text-matching`, reaches the wire through the extras bag). 0099's §8.2 note is reconciled to
this rule.

### 4. Conformance

- **scalar sampling field** — `complete(temperature=0.7, config={extras:{temperature:0.2}})` →
  `provider_invalid_request` pre-send (conflicting managed scalar); a matching `temperature:0.7` is a no-op.
  The representative case for the general scalar arm (`top_p`, `max_tokens`, retrieval `dimensions`, … share the
  mechanic).
- **`stop` merge** — `complete(stop_sequences=[A], config={extras:{stop:[B]}})` → wire `stop` is the merged
  `[A, B]` (de-duplicated); a matching extras `stop:[A]` collapses to `[A]`; a scalar-string extras `stop:"C"`
  is coerced to `["C"]` and merged.
- **`stream` reject** — a streaming call with `config={extras:{stream:false}}` → `provider_invalid_request`
  pre-send, no request issued; a matching `stream:true` is a no-op.
- **Jina `task`** — two cases: `input_type` set + conflicting extras `task` → reject pre-send; `input_type`
  **absent** + extras `task` → rides untouched to the wire (the escape hatch).

## Versioning

**MINOR** (whole-spec SemVer). Behavioral for a previously-undefined collision only: an extras key that shadows
**any** declared field it realizes on the wire — a scalar sampling field (`temperature`, `top_p`, `max_tokens`,
retrieval `dimensions`), or `stop` / `stream` / `task` — now merges or rejects per the rule, where the outcome
was undefined before. No change when the extras key and the declared field are not both set, and — critically —
the declared-field-absent escape hatch (an extras `task` with no `input_type`) is **unchanged**, so no existing
working pattern regresses. Unifies under 0105's existing arms; adds no new resolution mechanic.

## Open questions

- **Per-mapping managed-key enumeration.** §1 makes the rule general — every declared field a mapping realizes
  on the wire is managed while produced — so a future §8.x mapping inherits it automatically: it enumerates the
  declared fields it realizes and their wire names. No per-field proposal is needed unless a realization is
  additive in a novel way (only `stop_sequences` is list-shaped today; every other declared field is a scalar).
- **`stream` structural vs. declared-realization framing.** This proposal treats `stream` as always-managed
  (the mode is always determined), which makes it behave like a 0105 structural field rather than a
  conditionally-produced one. If a future call surface allows an *unset* stream mode, the "while producing it"
  branch would reactivate; not a concern today.
