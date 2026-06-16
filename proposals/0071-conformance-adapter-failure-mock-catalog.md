# 0071: Conformance Adapter — Failure-Mock Directive Catalog

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-16
- **Targets:** spec/conformance-adapter/spec.md (§5.1 — formalize the **failure-mock node-behavior directives** the fixtures use but §5.1 never documented: `flaky` (sequence + compact forms), `flaky_by_index`, `flaky_per_index`, `flaky_instance_only`, `flaky_resume_aware`, and the `failure_sequence` entry shape; document each by its failure-keying **axis**; sharpen the `flaky_per_index` (invocation-keyed) vs `flaky_by_index` (attempt-keyed) distinction so they aren't confused; flag — without changing — the inconsistent success-state field naming across variants)
- **Related:** 0055 (conformance-adapter capability — this fills the §5.1 mock-vocabulary gap it left), 0070 (formalized the crash/resume directives + added the §5.1 `cause` field, and deferred this mock catalog here), 0008 / 0009 / 0010 (checkpointing — what `flaky_per_index` / `flaky_resume_aware` exercise), 0050 / 0065 (retry + failure isolation — what `flaky` / `flaky_by_index` / `flaky_instance_only` exercise)
- **Supersedes:**

## Summary

0055 was "descriptive of what exists," but §5.1 documents only the simple `raises:` node directive — not the **failure-mock family** the retry / failure-isolation / checkpoint-resume fixtures actually use. That family is **five named node-behavior directives** (used across ~40 fixtures): `flaky`, `flaky_by_index`, `flaky_per_index`, `flaky_instance_only`, `flaky_resume_aware`. 0070 added the cross-cutting `cause` field that attaches to any of them and deferred the family's catalog here.

This proposal **documents the five directives in §5.1**, each with its verified shape, grouped by the failure-keying axis it models. It is a *descriptive* catalog — these are the directives the adapter already implements and the fixtures already exercise; nothing changes in behavior. The one substantive clarification is **distinguishing `flaky_per_index` from `flaky_by_index`** (same `_index` suffix, different trigger), and it **flags** (without changing) the inconsistent success-state field naming across the family.

**Why explicit named directives, not one parameterized `flaky`.** A self-describing directive name (`flaky_per_index`) declares the failure model at the fixture site; a single `flaky` parameterized over every axis would bury that behavior in a config blob — less readable and less explicit, against the same principle the spec applies elsewhere. The five are not redundant: they model genuinely different failure-injection axes (below). One parameterized directive would also be a god-object whose axes (a single attempt vs. a whole-instance re-run vs. an invocation-id) don't compose into meaningful blends. So the catalog keeps them explicit and distinct.

## Motivation

These mocks are the only way fixtures inject failure with the precision retry / isolation / resume tests need: a transient on attempt 1 that succeeds on attempt 2; a specific fan-out instance that fails the first run then succeeds on resume; a retry budget that resets across a checkpoint. They drive ~40 fixtures, yet a reader of §5.1 finds only `raises:`. An adapter author implementing the conformance suite has to reverse-engineer the mock vocabulary from the fixtures — exactly the gap 0055's "specify the harness primitives implementations MUST provide" was meant to close. Drafting 0070 surfaced this (and that the family is larger and more varied than a glance suggests — five variants, each with two sub-forms), which is why the catalog earned its own focused proposal.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0); concrete version assigned at acceptance. All changes are documentation added to conformance-adapter §5.1 — descriptive of the adapter behavior the existing fixtures already require; no new conformance expectation, no fixture changes.

### Failure-injection patterns

The family models three failure patterns, several optionally selecting fan-out instances by index:

- **Per-attempt** — a later *attempt* within one invocation succeeds, exercising **retry**: `flaky`'s sequence form, `flaky_by_index`'s `fail_count_per_idx`, `flaky_instance_only`, `flaky_resume_aware`.
- **Per-invocation** — the *first run* fails and a checkpoint *resume* succeeds, exercising **checkpoint/resume**: `flaky`'s compact form, `flaky_per_index`'s `fail_first_run_indices`, `flaky_resume_aware`.
- **Deterministic** — the selected instance fails on *every* attempt and invocation, for **collect-mode / error-contribution** tests: `flaky_by_index`'s `fail_when_idx`, `flaky_per_index`'s `always_fail_indices`.

`flaky_by_index` and `flaky_per_index` both select fan-out instances but serve different primary uses — `by_index` for retry (attempt-counted) or a deterministic collect-mode seam; `per_index` for resume (first-run vs. always). See the disambiguation note after the catalog.

### §5.1 — failure-mock directives (formalize)

Document, alongside `raises:`:

> - **`failure_sequence` entry** — each entry is `{transient: <bool>, category: <category|null>,
>   message: <str|null>}`; a `null` entry denotes a non-failing attempt at that position. `transient:
>   true` + a `category` raises a transient (retry-classifier-friendly) error; `transient: false`
>   raises a non-transient one.
> - **`flaky`** — a node mock with two sub-forms:
>   - **Sequence form:** `{failure_sequence: [<entry|null>, …], success_update: {<field>: <value>}}`
>     — raises once per entry across successive **attempts**; on an exhausted sequence (or a `null`
>     entry) returns `success_update`.
>   - **Compact form:** `{fail_first_invocation_only: <bool>, on_success: {<field>: <value>}}` —
>     fails the **first whole invocation** only (raised as `node_exception`), succeeding (returning
>     `on_success`) on any resume.
> - **`flaky_by_index`** — fan-out mock with `success_compute` and an **optional** `category`
>   (defaults to `provider_unavailable`; meaningful only for the retrying form, where it drives
>   retry classification), in one of two forms: `{fail_when_idx: <int>}` — the instance whose **item
>   value** equals `<int>` fails **deterministically** (no retry; a collect-mode seam, `category`
>   typically omitted) — or `{fail_count_per_idx: <int>}` — every instance fails its first `<int>`
>   **attempts**, then succeeds (retry).
> - **`flaky_per_index`** — fan-out mock, **invocation**-keyed, with `success_compute`, in one of two
>   forms: `{fail_first_run_indices: [<int>, …]}` (those indices fail the **first invocation** only,
>   then succeed on resume) or `{always_fail_indices: [<int>, …]}` (those indices fail **every**
>   invocation — a deterministic failure, e.g. for collect-mode error-contribution resume).
> - **`flaky_instance_only`** — `{fail_count_per_instance: <int>, category: <category>,
>   success_compute: {…}}` — each fan-out instance fails its first `fail_count_per_instance`
>   **whole-instance invocations** (the subgraph re-runs from scratch on retry), then succeeds.
> - **`flaky_resume_aware`** — `{fail_first_invocation_count: <int>, fail_resumed_invocation_count:
>   <int>, category: <category>, on_success: {…}}` — fails N attempts on the first invocation, then
>   M attempts on any resumed invocation before succeeding; used to verify `attempt_index` resets on
>   resume.
>
> Any failure these mocks raise MAY carry a `cause` (§5.1, proposal 0070) to chain an originating
> cause.

In any of these success-state mappings (`success_update` / `on_success` / `success_compute`), a
`<value>` that is a string naming a declared state field is read from that field; any other value
is taken as a literal.

### `flaky_per_index` vs `flaky_by_index` (disambiguation)

Both select fan-out instances by index, but for different purposes — the shared `_index` suffix
invites confusion:

> - **`flaky_by_index`** has no checkpoint/resume semantics: `fail_count_per_idx` fails the first N
>   *attempts* of each instance (retry); `fail_when_idx` fails the instance with that *item value*
>   deterministically (a collect-mode seam). Use it for fan-out + retry / collect-mode fixtures.
> - **`flaky_per_index`** is **invocation**-keyed (checkpoint/resume): `fail_first_run_indices` fail
>   the *first invocation* then succeed on resume; `always_fail_indices` fail *every* invocation.
>   Use it for fan-out + checkpoint fixtures.

### Success-state field naming (flagged, not changed)

The family names the success-path state update **three** ways: `success_update` (`flaky` sequence
form), `on_success` (`flaky` compact form, `flaky_resume_aware`), and `success_compute`
(`flaky_by_index`, `flaky_per_index`, `flaky_instance_only`). This is organic drift, not a semantic
distinction — all three are "the partial update the mock returns on the success path." This proposal
**documents each as-is** (renaming would churn ~40 accepted fixtures + the adapter for no behavioral
gain); unifying the name is noted as a candidate future cleanup (Out of scope).

## Conformance test impact

**None.** This is a descriptive catalog of directives the fixtures already use and the adapter
already implements. No new or changed fixtures; the existing ~40 retry / failure-isolation /
checkpoint-resume fixtures *are* the coverage.

## Versioning

**MINOR bump** (pre-1.0): §5.1 gains the failure-mock directive documentation. Descriptive of
existing adapter behavior — no behavior change, no new conformance expectation, no fixture changes.
A PATCH classification is defensible (purely documentary); the bump is the maintainer's call at
acceptance.

## Out of scope

- **Rationalizing the family into one parameterized `flaky`.** Rejected (see Summary): explicit
  named directives are more readable at the fixture site and model genuinely distinct axes; one
  parameterized directive trades self-description for a config blob and risks a god-object.
- **Unifying the success-state field name** (`success_update` / `on_success` / `success_compute` →
  one name). A real inconsistency, but fixing it churns ~40 accepted fixtures + the adapter for no
  behavioral gain; left as a candidate future cleanup. This proposal documents the names as they are.
- **`crash_injection`, mock `cause`, and the crash/resume directives.** Those are proposal 0070;
  this proposal only catalogs the failure mocks `cause` attaches to.
- **Capability behavior changes.** Nothing here changes graph-engine / pipeline-utilities / etc.;
  it documents the test vocabulary that exercises already-accepted behavior.

## Alternatives considered

- **One parameterized `flaky`** (the rationalization). Rejected on design grounds, not just churn:
  a single directive parameterized over attempt / index / invocation axes buries the failure model
  in configuration where a name would declare it, and the axes don't compose into meaningful blends.
  The explicit catalog is the more spec-idiomatic choice.
- **Rename the `_index` pair** (`flaky_by_index` / `flaky_per_index`) to axis-explicit names (e.g.
  `flaky_attempt_by_index` / `flaky_invocation_by_index`). Tempting for clarity, but a rename churns
  the accepted fixtures + adapter; a sharp documented distinction achieves the clarity without the
  churn. Left as a candidate cleanup alongside the success-field unification.
- **Leave §5.1 mock-silent** (status quo — mocks documented only inline per fixture). Rejected: it
  forces every adapter author to reverse-engineer the vocabulary from ~40 fixtures, the exact gap
  0055 set out to close.
