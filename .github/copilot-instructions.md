# Copilot instructions for openarmature-spec

This repository is the **language-agnostic behavioral specification** for OpenArmature. It contains
**no implementation code** — reference implementations live in separate repos. Content is prose specs,
RFC-style proposals, and declarative conformance fixtures. Weight review feedback accordingly: this is a
documentation-and-contract repo, not an application.

Three kinds of document, governed differently:

- **Charter** (`docs/openarmature.md`) — the living vision doc; freely editable.
- **Spec** (`spec/<capability>/spec.md`) — canonical behavioral spec; changed **only** through an Accepted proposal.
- **Proposal** (`proposals/NNNN-*.md`) — an RFC for one change; **immutable once its Status is `Accepted`**.

## Please flag these (they are real problems here)

- **Language-specific leaks in spec/proposal text.** `spec/**` and `proposals/**` prose MUST be
  language-agnostic. Flag any language-specific implementation detail that leaks in: concrete type names,
  class names, or function names from a particular implementation; per-language type-annotation syntax
  (e.g. `field: int`, `field: str`); or Python-/TypeScript-specific code examples. Say "async function," not
  "coroutine"/"Promise"; "typed state schema," not a specific library's model type.
- **Edits to an Accepted proposal.** A proposal whose Status is `Accepted` is immutable. A diff that changes
  an Accepted proposal's body (anything beyond a typo in non-normative prose) is a governance violation — the
  change belongs in a **new** proposal that `Supersedes:` the old one.
- **Normative spec changed without a proposal.** `spec/<capability>/spec.md` normative text changes only via
  an Accepted proposal. Flag a spec-body change in a PR that is not an acceptance of a specific proposal.
- **New normative statements without RFC 2119 keywords.** Behavioral requirements should use MUST / SHOULD /
  MAY. A new "the mapping does X" that prescribes behavior without a keyword is worth a nudge.

## Please do NOT flag these (they are intentional here)

- **`docs/proposals/*.md` "broken links."** These files are **per-file symlinks** to `../../proposals/*.md`
  (so proposals render inside the mkdocs site). A table link such as `[0103](proposals/0103-….md)` in
  `docs/proposals.md` resolves *through* that symlink to the real proposal and is **valid**. Internal links
  are validated in CI by `scripts/validate_markdown_links.py`; trust that over static path analysis. Do not
  suggest `../proposals/…` — every row uses the `proposals/…` form deliberately.
- **Missing terminal punctuation on front-matter bullets.** Proposal front-matter bullets (`Targets:`,
  `Related:`, `Supersedes:`) intentionally omit trailing periods. This is a house convention, not an
  oversight.
- **`§N` "ambiguity."** Inside a proposal's own Proposal section, `§N` refers to that proposal's numbered
  items; a bare `§N` / `§8.4` elsewhere refers to a **spec** section. The two namespaces coexist by design.
- **Fixture counts.** A capability's `conformance/` directory holds YAML+markdown *pairs*. When a count is
  about "fixtures," it counts the `.yaml` files; do not add the companion `.md` docs to the tally.

## Toolchain (CI validates these; don't duplicate their checks by eye)

- `scripts/validate_markdown_links.py` — all internal markdown links resolve.
- `scripts/regenerate_proposals_impl_tracking.py --check` — the `docs/proposals.md` impl-tracking columns.
- `scripts/validate_fixtures.py` — conformance fixture schema.
- `uv run mkdocs build --strict` — the docs site builds with no warnings.

## Generated / managed files (do not review as hand-written)

- **`docs/proposals.md` Python / TypeScript columns** are regenerated from the implementations' live
  conformance manifests by `regenerate_proposals_impl_tracking.py`. Do not hand-edit them or flag them as
  inconsistent with the prose — they track a downstream source.
- **`docs/proposals/*.md`** are symlinks (see above), not hand-authored copies.
- **`site/`**, if present, is mkdocs build output — never review it.
