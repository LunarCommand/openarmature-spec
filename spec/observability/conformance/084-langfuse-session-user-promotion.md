# 084 — Langfuse Sessions / Users trace-field population

Verifies §8.4.1's two cross-trace grouping fields (proposal 0064): the Langfuse
observer sets `trace.sessionId` from `openarmature.session_id` when the
invocation is session-bound, and promotes a recognized `userId` caller-metadata
key to the first-class `trace.userId` (additively — the key also remains in
`trace.metadata`). Both fields are unset when their source is absent. These two
fields power Langfuse's Sessions and Users dashboards.

**Spec sections exercised:**

- §8.4.1 *Session / user trace-field sourcing* — `trace.sessionId` ← `openarmature.session_id`;
  `trace.userId` ← recognized `userId` caller-metadata key (additive; recognized, not reserved).
- §5.6 — `openarmature.session_id` is present when the invocation is session-bound.
- §3.4 — caller-supplied invocation metadata is the `userId` source.

**Cases:**

1. `session_bound_sets_trace_session_id` — `session_id` supplied → `trace.sessionId` equals it.
2. `not_session_bound_leaves_session_id_unset` — no `session_id` → `trace.sessionId` unset.
3. `userid_metadata_promotes_to_trace_user_id_additively` — `userId` caller key → `trace.userId`
   set AND `trace.metadata.userId` retained.
4. `no_userid_key_leaves_trace_user_id_unset` — no `userId` key → `trace.userId` unset, other
   metadata unaffected.
5. `multi_invocation_shared_session_groups` — two session-bound invokes sharing one `session_id`
   → distinct `trace.id`, same `trace.sessionId`.

**What passes:**

- `trace.sessionId` set from `openarmature.session_id` for session-bound invocations; unset otherwise.
- `userId` caller key promoted to `trace.userId` automatically; the value also remains at
  `trace.metadata.userId` (additive).
- Multiple session-bound invocations under one `session_id` produce distinct traces sharing one
  `trace.sessionId`.

**What fails:**

- `trace.sessionId` unset for a session-bound invocation — Session grouping is broken.
- `userId` left only in metadata, not promoted to `trace.userId` — the Users dashboard stays blank.
- Promotion removes `userId` from `trace.metadata` (non-additive) — breaks existing metadata filtering.
- `trace.userId` populated when no `userId` key was supplied — spurious user attribution.
- The two invocations get different `trace.sessionId` values — they would not group into one Session.
