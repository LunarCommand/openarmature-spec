# 004 — Projected Session State

Verifies §4.2 projected sessions: when a `SessionState` projection narrower than the invoke
`State` is declared, only the projected fields are persisted across invokes; non-projected
("scratch") fields do not survive.

**Spec sections exercised:**

- §4.2 Projected sessions — the session record carries only the projected slice of state; the
  full invoke state may contain additional non-persisted fields.
- §6.1 Auto-save — the auto-save at END uses the projection's outbound mapping to construct the
  record (only projected fields are written).

**Cases:**

1. `scratch_fields_excluded_from_session_record` — invoke state has `summary` (projected) and
   `scratch` (not projected). Invoke #1 saves only `summary`. Invoke #2 loads `summary` but
   sees the default value for `scratch`.

**What passes:**

- The saved record after invoke #1 contains `summary="done"` and excludes `scratch`.
- Invoke #2's pre-execution state has `summary="done"` (loaded) and `scratch=""` (default).
- The projection's outbound mapping does not write scratch fields into the record.

**What fails:**

- The saved record contains `scratch` (the projection did not exclude it).
- Invoke #2 sees `scratch="tmp"` at entry (the scratch field was incorrectly persisted and
  reloaded).
