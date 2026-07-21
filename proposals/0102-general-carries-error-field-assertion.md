# 0102: Generalize the `carries` error-field assertion; ratify the migration & render error field surfaces

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-07-18
- **Accepted:** 2026-07-20
- **Ships as:** v0.97.0
- **Targets:** spec/conformance-adapter/spec.md — a new **general** section defining the capability-neutral
  `carries` convention (a key names a field the *raised error* exposes; bare = exact-equality, subset match
  for a mapping-valued field; `_present` / `_mentions`; the flavor set closed; **a key MUST NOT coin a stem
  with no backing error field**), and a **§5.12** retrofit (it becomes the llm-provider
  `structured_output_invalid` *instance* of the general rule; its "governs the `structured_output_invalid`
  block only / other blocks outside its scope" scoping is dropped). spec/pipeline-utilities/spec.md **§10.10**
  — name the migration-error fields the reference implementation already exposes (`registered_migrations_count`
  + `registry_description` on the missing error; the nullable `(from_version, to_version)` pair on the
  ambiguous error), replacing "a description of the registered migration set (in a form appropriate to the
  host language)." spec/sessions/spec.md — the `session_state_migration_*` errors expose the same fields via
  the §10.12 mirror (pointer). spec/prompt-management/spec.md **§11** — name the render error's `variables`
  and `description` fields (`name` / `version` / `label` already named). Conformance (at Accept): sessions
  fixture `009` drops the orphan `duplicate_count` key and asserts the ambiguous error's real fields; an audit
  confirms every other `carries` fixture is already field-anchored.
- **Related:** 0098 (introduced the §5.12 `carries` key-naming convention but deliberately scoped it to the
  `structured_output_invalid` block, deferring the corpus-wide question to a follow-on — this resolves it),
  0082 (the structured-output diagnostics surface §5.12 asserts)
- **Supersedes:**

## Summary

The `carries` conformance directive — assert the fields a *raised error* exposes — is used across five
capabilities (llm-provider, prompt-management, sessions, pipeline-utilities, and the structured-output block).
It is documented in exactly **one** place: conformance-adapter §5.12, which scopes its naming rule to the
llm-provider `structured_output_invalid` block and declares every *other* use "outside its scope." So a
fixture author asserting a migration or render error looks up `carries`, reads a rule that excludes their
case, and finds no general definition anywhere.

Left without a rule, the corpus drifted. Two fixtures coin a *count* stem — `registered_migrations_count`,
`duplicate_count` — that the spec defines no error field for.

But the drift is **one-sided**. The reference implementation already exposes precise, named fields
(`registered_migrations_count`, `registry_description`, the prompt render error's `description`) that the
*spec* left as free-form prose — "a description of the registered migration set, in a form appropriate to the
host language." The fixtures assert real fields; the spec is what never wrote them down.

So this proposal does two things:

1. **Lift §5.12's rule into a general, capability-neutral `carries` convention** — the missing rulebook every
   `carries` block should have followed all along.
2. **Ratify the impl-validated field surfaces** into the migration and render error specs, so every `carries`
   key names a real, spec-defined field.

The one genuinely unbacked key — `duplicate_count`, which **neither** the spec **nor** the implementation
exposes — is trimmed. The ambiguous-chain error's actionable contract is the offending `(from_version,
to_version)` pair, not a count.

**Non-breaking.** The implemented error surfaces already conform; the spec is catching up to them. The only
fixture change drops one orphan assertion that matched nothing.

## Motivation

### The gap

conformance-adapter §5.12 is the sole documentation of the `carries` directive. Proposal 0098 gave it a
normative key-naming convention but — correctly, to avoid condemning ~20 already-shipped fixtures in one
version — scoped that convention to the `structured_output_invalid` block, closing with: *"`carries` blocks
asserting other raised errors … are outside its scope."* That scoping was right for 0098 and wrong to leave
permanent. `carries` is used to assert:

- prompt-management render errors (fixtures 005 / 020 / 021 / 022 / 025 / 027 / 028 / 029 / 030): `name`,
  `version`, `label`, `description_mentions`;
- sessions and pipeline-utilities migration errors (008 / 009 / 013; 041 / 045 / 046): `from_version`,
  `to_version`, `registered_migrations_count`, `duplicate_count`.

None of these is governed by any documented rule.

### The drift, and its real cause

Two keys — `registered_migrations_count` and `duplicate_count` — coin a stem naming no spec-defined error
field. This is not fixture-author carelessness; it is a **symptom of an un-assertable error surface.**
pipeline-utilities §10.10 specs the missing-migration error to carry the two `schema_version`s and *"a
description of the registered migration set (in a form appropriate to the host language)."* A free-form,
per-language "description" cannot be asserted precisely across implementations — so the fixture author reached
for the one thing they could pin cross-impl: a count. The vagueness in the error definition forced the
vagueness in the test.

### Why *ratify*, not *invent*

The implementation resolved this vagueness before the spec pinned it: the reference implementation's
missing-migration error already exposes, as first-class typed fields, `from_version`, `to_version`,
**`registered_migrations_count`** (a non-negative integer), and **`registry_description`** (a string). The
render error exposes `name`, `version`, `label`, `variables`, and **`description`**. These are not
test-harness inventions — they are the shapes the reference implementation validated in practice. The spec catching up to them is *documenting proven behavior*, not
designing something new. It follows the project's own principle that conformance fixtures (and the
implementation that satisfies them) are the source of truth for behavior; the prose is reconciled to them.

An earlier framing of this work proposed the reverse — inventing a fresh `registered_migrations` *list* field
and rewriting the fixtures to it. Checking the implementation first showed that would have **broken** a
shipped field to impose a spec-side guess. Ratifying the impl-proven shape is both less disruptive and more
correct.

### Why `duplicate_count` is trimmed, not ratified

The asymmetry with `registered_migrations_count` is the whole point. `registered_migrations_count` is ratified
**because the implementation ships it** — real-world evidence the field earns its place. `duplicate_count` is
shipped by **nothing** — not the implementation (the ambiguous-chain error carries only the nullable
`(from_version, to_version)` pair), not the spec. Reverse-engineering a new product field into the
implementation to justify a fixture's speculative assertion is the tail wagging the dog — the exact
anti-pattern the new general rule forbids.

And it is unnecessary. The ambiguous-chain error's actionable contract is *which pair collides*
(`from_version` / `to_version`), which points the developer straight at the duplicate registration to remove.
A count of duplicates adds nothing to that — you already know it is ambiguous; the number does not change what
you do. This is a genuine contrast with the missing case, where the count *frames the gap* ("5 migrations
registered, none bridging v3 → v5"). Different failure, different useful diagnostic — matched per error, not
applied uniformly. Fixture 009 currently asserts `duplicate_count` against an error that never carried it (a
no-op assertion, tolerated because the field is simply absent); after the trim it asserts the pair the error
*does* carry — a strengthening, not a weakening.

## Proposal

### 1. conformance-adapter — a general `carries` convention

Add a general section documenting the `carries` directive capability-neutrally. Its content is §5.12's
key-naming convention, restated without the llm-provider scoping:

- A `carries` block appears under an `expected.raises` / `expected_error` assertion and asserts fields the
  raised error exposes.
- A **key MUST name a field the raised error's own capability spec defines it exposes.** A key MUST NOT coin a
  stem with no backing error field. (This is the rule whose absence let `registered_migrations_count` /
  `duplicate_count` drift in.)
- A **bare field name** asserts exact-equality; when the field is a **mapping**, it is a **subset match**
  (every named key MUST match; unnamed keys are ignored), matching §5.11.
- The **`_present`** suffix asserts presence (`true` = present / non-null, `false` = absent / null).
- The **`_mentions`** suffix asserts the field's value **contains** the given substring (for
  implementation-defined wording).
- The suffix set — `_present` / `_mentions` — is **closed**; a new flavor requires a proposal.
- An error field name **MUST NOT** end in a recognized flavor suffix, so a `carries` key parses unambiguously
  to exactly one (field, flavor) pair. A field name may end in other tokens — `registered_migrations_count` is
  a **bare field name** (`_count` is not a flavor), asserted by exact-equality, not a count-flavor on
  `registered_migrations`.

Retrofit **§5.12** to state it is the llm-provider `structured_output_invalid` **instance** of this general
convention (keeping its llm-provider §7 key list: `output_content`, `error_message*`, `finish_reason`,
`usage`, `response_schema_present`). Drop its "governs the `structured_output_invalid` block only … other
blocks are outside its scope" paragraph — the general rule now governs all blocks; §5.12 merely enumerates the
llm-provider keys.

> The sibling `cause` directive (`cause: { exception_type: … }`, used by the migration-failed fixtures) is a
> *separate* directive, not a `carries` flavor, and is out of scope here. It joins the set of
> not-yet-documented directives (`typed_observers` / `contains_event`, `cause`) tracked for a dedicated
> directive-documentation follow-on.

### 2. pipeline-utilities §10.10 — name the migration-error fields

The missing-migration error surface today names its two version values by role — *"the record's
`schema_version`"* and *"the current schema's `schema_version`"* — and describes the rest as *"a description
of the registered migration set (in a form appropriate to the host language)."* Restate it with the named
fields the checkpoint error surface already exposes:

- **`from_version`** and **`to_version`** — the two version values, named by their migration role
  (`from_version` = the record's saved version; `to_version` = the current schema version). This **replaces**
  the prose's `schema_version` × 2 naming; the checkpoint error and every fixture (008 / 041 / 045) already
  use `from_version` / `to_version`, so this reconciles the prose to them rather than introducing a name.
- **`registered_migrations_count`** (a non-negative integer) — the number of registered migrations, so the
  caller can see the size of the set that failed to bridge the gap.
- **`registry_description`** (a string) — the human-readable rendering of the registered set, retained as an
  explicitly-named field rather than the prior unnamed "description."

The ambiguous-chain error carries the nullable `(from_version, to_version)` pair (§10.10 already names these;
set for the duplicate-pair case, set on the resume side for multi-shortest-path detection). **Reconcile
§10.10's ambiguous-error prose the same way** the missing error is reconciled: the resolution case today
promises *"a description of the conflicting paths … in a form appropriate to the host language"* — the same
un-nameable prose this proposal removes from the missing error, and a field the checkpoint error does not
expose. **Drop it**; the nullable pair is the ambiguous error's whole exposed surface (ratifying the impl). A
future need for structured conflicting-path diagnostics is an additive follow-on, not part of this
reconciliation. The migration-failed error carries `from_version` / `to_version` and preserves the raised
exception as cause (unchanged).

### 3. sessions — mirror pointer

The `session_state_migration_missing` / `_chain_ambiguous` / `_failed` errors **inherit** the same field
surface as their checkpoint counterparts via the §10.12 mirror (they already mirror the resolution semantics).
Add a one-line pointer so the field surface is discoverable from the sessions spec. This keeps the sessions
side consistent by construction; the ratification evidence is on the checkpoint surface, which the mirror
carries across.

### 4. prompt-management §11 — name the render-error fields

The `prompt_render_error` surface (§11) already names `name` / `version` / `label`. Name the remaining two it
exposes: **`variables`** (the variable mapping, sensitive values redacted per implementation policy) and
**`description`** (the render-failure description — which segment / block / placeholder triggered). This
field-anchors the existing `description_mentions` fixture key without changing any fixture.

### 5. Conformance

- **sessions/009** — drop the `duplicate_count: 2` key; the `carries` block asserts the ambiguous error's real
  `from_version` / `to_version`. This trim **MUST** land in the same version as §1's general rule — otherwise
  the new "MUST NOT coin a stem with no backing field" clause would condemn the very fixture it exists to fix.
- **Audit** — every other `carries` fixture is already field-anchored after §§2–4 name the fields:
  prompt-management (005 / 020 / 021 / 022 / 025 / 027 / 028 / 029 / 030 — `name` / `version` / `label` /
  `description`), pipeline-utilities (041 / 045 — `from_version` / `to_version` / `registered_migrations_count`;
  046 — the pair, `cause` being a separate block), sessions (008 — the missing-error fields; 013 — the pair),
  and the llm-provider block (022 / 023 / 063 / 064, already conformed by 0098). No renames.

No new fixtures. The general rule's "MUST NOT coin a stem with no backing field" is a fixture-authoring
constraint enforced at fixture review, not a runtime assertion.

## Versioning

**MINOR** (whole-spec SemVer), expected **v0.97.0** as the next accept. The change refines public error
contracts (naming fields the checkpoint and prompt render errors already expose) and generalizes a
conformance-adapter directive. It is **non-breaking**: the implemented error surfaces already expose the named
fields, the sessions errors inherit the same shape via the §10.12 mirror, and the sole fixture edit removes an
assertion that matched nothing.

## Open questions

- **A general home for the other undocumented directives.** `cause`, `typed_observers`, and `contains_event`
  are load-bearing conformance directives with no §5 documentation (the last two are already logged in
  `docs/open-questions.md`). This proposal documents `carries`; a dedicated follow-on should document the rest
  in the same capability-neutral spirit. Out of scope here to keep 0102 focused.
- **Structured ambiguity diagnostics.** If real demand surfaces for asserting *how* a migration graph is
  ambiguous (a duplicate-pair or conflicting-paths surface), that is a clean additive follow-on — proposed on
  its own signal, not bolted on now to backfill the trimmed `duplicate_count`.
