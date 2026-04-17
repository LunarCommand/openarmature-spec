# CLAUDE.md

Orientation for Claude Code sessions in this repo. Points at authoritative docs rather than restating them.

## What this repo is

`openarmature-spec` is the **language-agnostic specification** for OpenArmature — a proposed unified workflow
framework for LLM pipelines and tool-calling agents. **No implementation code lives here.** Reference
implementations will live in separate repos (`openarmature-python`, `openarmature-typescript`).

Start with [`docs/openarmature.md`](docs/openarmature.md) for the thesis, architecture, and module overview.

## Three kinds of document — don't conflate them

- **Charter** ([`docs/openarmature.md`](docs/openarmature.md)) — living vision doc. Freely editable.
- **Spec** (`spec/<capability>/spec.md`) — canonical behavioral spec. Changed **only** through Accepted proposals.
- **Proposal** (`proposals/NNNN-*.md`) — RFC for a specific change. **Immutable once Accepted** — further
  changes happen via new proposals that `Supersedes:` the old one.

Full rules: [`GOVERNANCE.md`](GOVERNANCE.md).

## When a proposal is required

Any change to a capability's behavior, public types/interfaces, or conformance-test expectations needs a
numbered proposal under `proposals/NNNN-short-kebab-title.md` (zero-padded). Typos, formatting, and
charter/governance edits do not. See [`GOVERNANCE.md#proposal-lifecycle`](GOVERNANCE.md#proposal-lifecycle)
for the template and flow.

## Writing spec text

- **Language-agnostic.** Say "typed state schema," not "Pydantic model." Say "async function," not "coroutine"
  or "Promise." Python and TypeScript each map idiomatically onto the behavioral contract.
- **Behavior, not API shape.** The spec describes what happens. Decorators vs. middleware, context managers
  vs. `using` blocks — those are per-language concerns.
- **RFC 2119 keywords** (MUST, SHOULD, MAY) when prescribing behavior.
- **Conformance tests are the source of truth for behavior.** New behaviors require new fixtures under
  `spec/<capability>/conformance/` (YAML + markdown pair).

## Versioning

Whole-spec SemVer, tracked in [`CHANGELOG.md`](CHANGELOG.md). Pre-1.0 breaking changes may land in MINOR
bumps. Each entry links the driving proposal(s).

## Practical reminders

- Proposal status transitions (Draft → Accepted) are a maintainer action, not something to pre-fill.
- Don't edit a proposal whose status is `Accepted`. Open a new proposal that supersedes it.
- Don't add Python- or TypeScript-specific examples inside `spec/` text. Charter examples (`docs/`) are fine.
- The user is the sole maintainer (Chris Colinsky). Ask before inventing process beyond what `GOVERNANCE.md`
  specifies.
