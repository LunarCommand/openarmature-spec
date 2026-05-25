# Releasing

How spec versions are tagged and published. This document is the
operational counterpart to [`GOVERNANCE.md`](governance.md) — governance
covers the proposal lifecycle and SemVer policy; this doc covers the
mechanics of cutting a release.

---

## Standard release flow

Every spec version follows the same sequence:

1. **Acceptance PR merges to `main`.** The PR flips a proposal's
   `Status: Draft → Accepted`, lands the spec text changes, adds new
   conformance fixtures, and updates `CHANGELOG.md` / `README.md` /
   `docs/proposals.md`.
2. **Tag the merge commit.** An annotated tag is created on the
   acceptance PR's merge commit:
   ```
   git tag -a vX.Y.Z <merge-commit-sha> -m "spec vX.Y.Z — <short desc> (proposal NNNN)"
   git push origin vX.Y.Z
   ```
3. **Publish the GitHub Release.** Notes come from the new
   `CHANGELOG.md` entry; the standard release is marked `--latest`:
   ```
   gh release create vX.Y.Z --target main --latest --title "vX.Y.Z" --notes "..."
   ```

No CI workflow triggers off the tag — releases are manual, by design.
The release exists primarily so downstream implementations can pin
their submodule reference to a stable spec version.

---

## Versioning

Pre-1.0 SemVer at the whole-spec level (not per-capability):

- **MINOR** (`v0.N.0`) — new behavior, new conformance rules, additions
  any implementation could fail.
- **PATCH** (`v0.N.P`) — textual clarification with no behavior change,
  fixture data fix, or backport that aligns existing impls without
  introducing new failure modes.

Pre-1.0 MINOR may carry breaking changes per `GOVERNANCE.md`. PATCH is
reserved for changes implementations can adopt without code work
(though they may need to adjust to a more-explicit reading of an
existing rule — see the v0.16.1 / v0.17.1 / v0.21.1 precedents).

---

## Backporting fixes — cherry-pick ordering

**The rule:** when a published tag carries a typo or fixture-data bug
that needs a PATCH-bump fix, **the fix lands on `main` first** (or
simultaneously with any maintenance tag), so subsequent MINOR releases
off `main` don't bake the typo into further tags.

The pattern that fails this rule:

1. A bug is found on a published tag, say `vA.B.0`.
2. A maintenance tag `vA.B.1` is cut from a side branch off `vA.B.0`
   with the fix isolated. Tag and release published.
3. The cherry-pick back to `main` is scheduled separately and lags.
4. Before the cherry-pick lands, a new MINOR `vA.B+1.0` is tagged off
   `main` — inheriting the original typo.
5. Same again at `vA.B+2.0`, `vA.B+2.1`, …
6. The cherry-pick eventually lands on main, fixing future tags from
   that point forward — but every interleaved tag between the
   maintenance bump and the cherry-pick is permanently broken (without
   a force-tag, see below).

The right sequence:

- **Fix on `main` first.** Apply the fix on `main` and tag the
  resulting commit as the PATCH (e.g., `vA.B.1`). Both the main line
  and the canonical PATCH tag are fixed in a single commit. No
  maintenance branch needed; no cherry-pick window.
- **Maintenance side branch SECOND** (only if needed). If a separate
  side-branch tag is required (e.g., the bug originated at `vA.B.0`
  and downstream impls explicitly pin there), cut the side-branch tag
  AFTER `main` carries the fix. The side-branch tag points at a
  commit whose only difference from `main` is the lack of
  not-yet-cherry-picked work, so subsequent main tags continue to
  carry the fix.
- **No interleaved MINOR releases between maintenance and
  cherry-pick.** If a maintenance bump and a follow-on MINOR both
  need to ship in close succession, sequence them: maintenance tag,
  cherry-pick to main, MINOR tag. Never interleave.

When the rule is violated (e.g., it was violated for the v0.18.1
maintenance tag landing on a side branch before the cherry-pick to
main), the recovery is a series of **force-tag retags** (next
section).

---

## Force-tag retags (rare, pre-1.0 only)

When interleaved tags carry a typo that should have been backported,
the cleanest recovery is to retag each affected version with the fix
cherry-picked onto the original tagged commit:

1. From the broken tag's SHA, create a side branch:
   ```
   git checkout -b retag-vX.Y.Z vX.Y.Z
   ```
2. Apply the focused fix (one commit, just the fix — no CHANGELOG
   churn, no version-line bumps). The retag must not change the spec
   surface beyond what the fix touches.
3. Force-update the tag in place, preserving the original tag message:
   ```
   git tag -af vX.Y.Z HEAD -m "<original tag message>"
   ```
4. Force-push the tag:
   ```
   git push origin --force vX.Y.Z
   ```
5. Drop the local side branch (the tag preserves the new commit).

After retagging, any GitHub Release pinned to the tag follows the new
SHA automatically; the release notes don't auto-update, but a note
added to the release body acknowledging the retag is useful for
implementations that previously fetched the broken version.

Force-tagging published releases is a destructive operation:

- **Pre-1.0 only.** Once the spec hits `v1.0.0`, tags are immutable —
  the cost of breaking implementations that have pinned to a tag and
  cached its SHA outweighs the benefit of an in-place fix. Use a new
  PATCH tag instead.
- **Time-window sensitive.** Force-tagging within days of the
  original tag is low-risk (downstream implementations are still
  catching up; few have cached the SHA). Force-tagging tags that are
  weeks or months old is higher-risk — the next PATCH on the line is
  usually the better path.
- **Limit to one fix per retag pass.** Bundle multiple fixes into a
  new tag instead.
- **Document in the release.** Add a "Retagged on YYYY-MM-DD with
  &lt;fix&gt;" note to the corresponding GitHub Release body so any
  implementation that cached the prior SHA can detect the change.

---

## Maintenance tags

A maintenance tag (`vX.Y.Z+1` cut from a side branch off `vX.Y.Z`)
is appropriate when:

- The fix is purely textual or fixture-data.
- An implementation needs to pin to `vX.Y` and an in-place force-tag
  on `vX.Y.Z` is undesirable (e.g., the tag is older than the
  force-tag time window above).

For the maintenance tag itself:

- Cut the side branch from the tagged commit.
- Apply the fix + `CHANGELOG.md` entry naming the maintenance bump.
- Bump README `Current spec version` on the side branch ONLY if the
  side branch is being published as the new "canonical" version of
  the `vX.Y.Z+` line (uncommon; usually the main line is canonical).
- Tag the side-branch commit, push the tag, publish the GitHub
  Release with `--latest=false` (so it doesn't supersede the main
  line's latest tag).

After cutting the maintenance tag, **immediately cherry-pick the fix
to `main`** to preserve the cherry-pick ordering rule above. The
cherry-pick is the canonical "the fix is also on main" landing; it
doesn't need its own tag (the fix flows forward into the next MINOR's
content).

---

## Pre-release validators

Before tagging a release, the same validators that run in CI MUST
pass locally on the merge commit (or HEAD of the maintenance side
branch):

- `python3 scripts/validate_markdown_links.py` — every internal link
  resolves.
- `mkdocs build --strict` — every documentation page builds; no
  warnings or errors. (Pre-flight with `--strict` only; do not pair
  with `--quiet` — `--quiet` suppresses warnings that `--strict`
  would otherwise catch, so a build CI rejects can pass locally.)

CI runs these validators on every PR; the local check is a
safety net.

---

## Closing out

After the tag is pushed and the release is published, the
acceptance work is closed:

1. Local cleanup: delete the merged accept branch
   (`git branch -d accept/NNNN-*`), `git fetch --prune`. (Remote
   branch auto-deletes on PR merge per the repo's settings;
   skip `git push origin --delete`.)
2. Task tracker: mark the accept task complete.
3. Coord thread (if applicable): notify downstream impl agents that
   the new spec version is available and the pin can advance.

---

## Quick reference

| Operation | Command |
|---|---|
| Tag a merge commit | `git tag -a vX.Y.Z <sha> -m "spec vX.Y.Z — <desc> (proposal NNNN)"` |
| Push tag | `git push origin vX.Y.Z` |
| Publish release | `gh release create vX.Y.Z --target main --latest --title "vX.Y.Z" --notes "..."` |
| Force-retag | `git tag -af vX.Y.Z HEAD -m "<original>" && git push origin --force vX.Y.Z` |
| Local validators | `python3 scripts/validate_markdown_links.py && mkdocs build --strict` |
