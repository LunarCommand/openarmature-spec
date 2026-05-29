# 057 — Resume Mints a Fresh `invocation_id` (Ignores Caller-Supplied)

Verifies §5.1's resume interaction: a resume call mints a fresh framework `invocation_id` and
IGNORES any caller-supplied `invocation_id`. Caller-supplied `invocation_id` applies to the
fresh-invocation path only; a caller correlating resume attempts uses `correlation_id` (stable
across attempts — see fixture 031). Complement to 031 (correlation_id preserved, invocation_id
differs).

**Spec sections exercised:**

- §5.1 — caller-supplied `invocation_id` applies to the fresh-invocation path; on resume the
  framework mints a fresh UUIDv4 and ignores any caller-supplied `invocation_id`.
- graph-engine §3 — `invoke()` accepts a caller-supplied `invocation_id`; the resume path
  ignores it.

**Cases:**

1. `resume_mints_fresh_invocation_id_ignoring_caller_value` — first run supplies
   `invocation_id = "run-first-001"` (used verbatim); node B fails; resume supplies
   `invocation_id = "run-resume-999"`. The resumed attempt mints a fresh UUIDv4 — neither
   `"run-resume-999"` nor `"run-first-001"`.

**Harness extensions:**

- `caller_invocation_id: "<value>"` — supplies the `invocation_id` at the initial `invoke()`
  (per §5.1; same primitive as fixtures 035 / 036).
- `resume.caller_invocation_id: "<value>"` — supplies a caller `invocation_id` on the resume
  call; the harness asserts it is ignored (a fresh id is minted).

**What passes:**

- The first run's `invocation_id` is the caller's `"run-first-001"`.
- The resumed run's `invocation_id` is a fresh framework UUIDv4 — neither caller value — and
  differs from the first run's.

**What fails:**

- Resume adopts the caller-supplied `"run-resume-999"` (or reuses `"run-first-001"`) instead of
  minting a fresh id — violates §5.1's resume-mints-fresh rule.
