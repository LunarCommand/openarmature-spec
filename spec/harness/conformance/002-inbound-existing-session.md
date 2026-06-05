# 002 — Inbound existing-active-session path (§3.2)

The harness receives a synthetic transmission carrying a known
session_id and classifies it as the existing-active-session inbound
path. The harness threads the caller-supplied session_id verbatim
(does NOT auto-generate); the engine loads the prior session record
so the next-turn invocation observes accumulated state.

**Spec sections exercised:**

- harness §3.2 — existing-active-session inbound dispatch path
- harness §3.4 — path classification: 3.1 vs 3.2 by caller intent
- sessions §3 — engine-side session load on invoke entry
- sessions §6.1 — auto-save / auto-load lifecycle

**What passes:**

- First transmission classified as §3.1 (new-session) — caller-
  supplied id used verbatim.
- Second transmission classified as §3.2 (existing-active-session).
- Both invocations receive the same session_id; the second loads the
  first's saved state.
- Final state shows accumulated history (`[1, 1]` after two appends).

**What fails:**

- Second transmission classified as §3.1 — would mean caller-intent
  discrimination is broken.
- Second invocation's state doesn't include the first's append —
  would mean session load failed (or harness threading is broken).
