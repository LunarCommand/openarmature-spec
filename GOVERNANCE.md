# Governance

This document describes how the OpenArmature specification is managed: how specs are organized, how changes are
proposed and accepted, how versions are tracked, and how multiple language implementations are kept in sync.

---

## Scope of this repository

This repository (`openarmature-spec`) holds the **language-agnostic specification** for OpenArmature. It does not
contain implementation code. Implementations live in separate repositories:

- `openarmature-python` (planned) — reference Python implementation
- `openarmature-typescript` (planned) — reference TypeScript implementation

Both implementations target the specs in this repo. Behavioral conformance is verified by the conformance test suite,
also in this repo as language-agnostic test fixtures.

The approach follows the pattern used by mature multi-language projects (OpenTelemetry, Language Server Protocol,
JSON-RPC): a separate spec repo with markdown organized by capability, SemVer-versioned, with a conformance test
suite as the source of truth for behavioral correctness.

---

## Repository structure

```
openarmature-spec/
├── docs/
│   └── openarmature.md         # Project charter — thesis, architecture, roadmap
├── spec/
│   ├── graph-engine/
│   │   ├── spec.md             # Canonical spec for the capability
│   │   └── conformance/        # Language-agnostic test fixtures
│   ├── pipeline-utilities/
│   │   ├── spec.md
│   │   └── conformance/
│   ├── llm-provider/
│   │   ├── spec.md
│   │   └── conformance/
│   └── …                       # Additional capabilities as the spec grows
├── proposals/
│   ├── 0001-graph-engine-foundation.md
│   ├── 0002-…
│   └── …                       # Numbered RFC-style proposals
├── CHANGELOG.md                # SemVer-tracked spec version history
├── GOVERNANCE.md               # This document
└── README.md                   # Project intro
```

**Charter vs spec vs proposal — three roles, three locations:**

- **Charter** (`docs/openarmature.md`) — living vision document. The thesis, architecture overview, design principles,
  and roadmap. Updated as the project evolves. Not immutable.
- **Spec** (`spec/<capability>/spec.md`) — canonical, current behavioral specification for a capability. Updated only
  through accepted proposals. Versioned via SemVer.
- **Proposal** (`proposals/NNNN-*.md`) — focused decision document for a specific change. Reviewed via PR, immutable
  once Accepted.

---

## Proposal lifecycle

### Format

Proposals are numbered sequentially: `NNNN-short-kebab-title.md` (zero-padded to 4 digits). They follow this template:

```markdown
# NNNN: <Title>

- **Status:** Draft | Accepted | Withdrawn | Superseded
- **Author:** <name>
- **Created:** YYYY-MM-DD
- **Accepted:** YYYY-MM-DD (filled in on acceptance)
- **Targets:** spec/<capability>/spec.md (creates | modifies §X.Y | removes …)
- **Related:** NNNN, NNNN
- **Supersedes:** NNNN (if applicable)

## Summary

2–3 sentences. What is being proposed.

## Motivation

Why this change is needed. Reference the charter or earlier proposals if relevant.

## Detailed design

The actual proposed spec text, or a precise diff against the existing spec.

## Conformance test impact

Which fixtures need to be added, changed, or removed. New behaviors require new tests.

## Alternatives considered

Other approaches and why they were rejected. At minimum, "do nothing" should be considered.

## Open questions

Anything unresolved at the time of writing.
```

### Lifecycle

1. **Draft.** Author opens a PR adding the proposal under `proposals/`. Status: Draft.
2. **Review.** Discussion happens on the PR. Proposal text is iterated.
3. **Accept.** Maintainer merges the PR with `Status: Accepted` and `Accepted: YYYY-MM-DD` filled in. The proposal
   text becomes immutable from this point — further changes happen via new proposals.
4. **Implement spec change.** A follow-up PR (or the same PR if small) updates the relevant `spec/<capability>/spec.md`
   and `conformance/` directory to reflect the accepted design.
5. **Version bump.** `CHANGELOG.md` is updated with the new spec version and a link to the proposal(s) that drove the
   change.

A proposal may also end as **Withdrawn** (author abandoned) or **Superseded** (replaced by a later proposal that
references it).

### When a proposal is required

Required for:

- Adding or removing a capability
- Adding, removing, or changing the behavior of a public type, function, or interface
- Changing conformance test expectations in a way that any implementation could fail

Not required for:

- Typo fixes, formatting, broken links
- Clarifications that do not change behavior (PATCH version bump, no proposal needed)
- Changes to charter, this governance doc, or README

---

## Spec versioning

Spec changes follow [SemVer](https://semver.org/) at the **whole-spec level** (not per-capability):

- **MAJOR** — backwards-incompatible behavioral or interface change
- **MINOR** — backwards-compatible addition (new capability, new optional field, new behavior that does not break
  existing fixtures)
- **PATCH** — clarification, typo, or non-behavioral change

Each change is recorded in `CHANGELOG.md` with the version, date, summary, and links to the driving proposal(s).

Pre-1.0 versions (`0.x.y`) follow the same SemVer structure but with the explicit understanding that the spec is still
stabilizing and breaking changes may occur in MINOR bumps.

---

## Multi-language consistency

Inspired by OpenTelemetry's library guidelines, with a smaller scope (two languages, not many).

- **Two-language prototype rule.** Any new capability spec should be prototyped in both Python and TypeScript before
  the proposal is Accepted. This catches idiom mismatches early. (OpenTelemetry uses three categories — typed-OO +
  dynamic + structural — but Python and TypeScript cover dynamic + typed-functional well enough for our scope.)

- **Behavioral spec, not API-shape spec.** The spec describes what happens, not the exact syntax. Each language uses
  its idiomatic API. Python decorators may correspond to TypeScript middleware functions; Python context managers may
  correspond to TypeScript `using` blocks. APIs MAY differ in syntactic shape; behavior MUST match conformance tests.

- **Drift policy.** If an implementation discovers a needed feature not in the spec, it does NOT add it unilaterally.
  The implementation must file a proposal first and wait for acceptance before shipping the feature. (This is the
  policy LangChain didn't have, which is why their Python and TypeScript APIs drift visibly enough that they publish
  a "differences page.")

- **Spec version declaration.** Each implementation declares which spec version it targets in its package metadata
  (e.g., Python `pyproject.toml`: `openarmature_spec_version = "0.3.1"`). The implementation MUST pass the conformance
  test suite for that version.

---

## Conformance tests

Conformance tests live alongside their specs at `spec/<capability>/conformance/` and are language-agnostic.

**Format.** Each test is a fixture pair plus a description:

```
spec/graph-engine/conformance/
├── 001-static-edge-flow.yaml
├── 001-static-edge-flow.md          # description of what this test verifies
├── 002-conditional-edge-routing.yaml
├── 002-conditional-edge-routing.md
└── …
```

The YAML fixtures contain inputs (graph definition, initial state, sequence of events) and expected outputs (final
state, observed call order, errors). The markdown describes intent and edge-case coverage.

**Adapter responsibility.** Each language implementation provides a thin adapter that loads the YAML fixtures and runs
them through its native test runner (Python: `pytest`; TypeScript: `vitest`). The adapter is implementation-private;
the fixtures are spec-public.

**Test additions require proposals.** New conformance tests that any implementation could fail are a behavioral spec
change and require a proposal. Test additions that only verify already-specified behavior (regression coverage,
clarification fixtures) do not.

---

## Decision making

Currently single-maintainer (Chris Colinsky). The maintainer accepts or rejects proposals after PR review.

This section will be updated as the project grows to describe a contributor model, working groups, or a steering
committee — whichever fits when the contributor base warrants it. The OpenTelemetry and Rust governance models are
likely templates.

---

## Out of scope for this repo

- Implementation code (lives in `openarmature-python` and `openarmature-typescript`)
- Performance benchmarks (each implementation owns its own benchmarking)
- User-facing tutorials and how-to docs (live with each implementation)
- Provider-specific integration code (sibling-package responsibility per the architecture in the charter)
