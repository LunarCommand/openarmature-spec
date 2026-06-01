# 043 — `get_invocation_metadata()` roundtrip within a single async context

Verifies §3.4's *Read access* paragraph — `get_invocation_metadata()` returns an immutable
mapping snapshot of the metadata visible in the current async context, including entries set
via `set_invocation_metadata` in the same context plus the original caller-supplied baseline.

**Spec sections exercised:**

- §3.4 *Read access* — basic write-then-read roundtrip in a single async context.
- §3.4 baseline — caller-supplied metadata at `invoke()` time visible to reads.

**Cases:**

1. `get_invocation_metadata_reads_caller_baseline_plus_node_writes` — `invoke()` supplies
   `{"tenantId": "T1"}`. A node calls `set_invocation_metadata(audit_kind="fraud")` followed by
   `get_invocation_metadata()`. The read returns a mapping containing BOTH `tenantId: "T1"` (the
   caller-supplied baseline) AND `audit_kind: "fraud"` (the in-node write).

**What passes:**

- The read returns both the baseline + the in-context write.
- The returned mapping is immutable from the caller's perspective (attempting to mutate it MAY
  raise per the language's immutability conventions — Python `MappingProxyType` raises on
  `__setitem__`; the spec contract is "do not assume mutation succeeds").

**What fails:**

- The read returns only the baseline (the in-context write is invisible — implementation reads
  from a stale snapshot).
- The read returns only the in-context write (the baseline is invisible — implementation reset
  the mapping at node entry).
- The read returns a mutable mapping that the caller can modify (the immutability contract is
  load-bearing for the read-augmenting framing).
