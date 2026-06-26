# 036 — PromptManager service-wide default cache-TTL

Pins prompt-management §6 `default_cache_ttl_seconds` (proposal 0086): a `PromptManager`
constructed with a service-wide default applies it to fetches that omit a per-call
`cache_ttl_seconds`, and an explicit per-call value overrides it.

## Scenario

A caching `PromptBackend` (conformance-adapter §6.8) with a controllable clock, composed by a
`PromptManager` constructed with `default_cache_ttl_seconds: 60`. All fetches route through the
manager (`target: {manager: true}`), exercising the §6 precedence chain.

- **t=0** — manager fetch, no per-call value → the default (60) governs → cache miss → source read
  (caches the entry).
- **t=30** — fetch, no per-call value → default 60, entry age 30 < 60 → served from cache (no read).
- **t=90** — fetch, no per-call value → default 60, entry age 90 > 60 → fresh source read.
- **t=90** — fetch with per-call `cache_ttl_seconds: 0` → overrides the positive default →
  force-fresh source read.

The caching backend's cumulative `source_read_count` is **3** (t=0, t=90, and the per-call `0`); the
t=30 fetch was served from cache.

## Spec coverage

- **prompt-management §6** — `PromptManager` construction-time `default_cache_ttl_seconds`, and the
  `fetch` cache-control precedence chain (explicit per-call > manager default > backend). The default
  applied (the no-per-call fetches) and the per-call `0` override are both asserted.
- **prompt-management §5** — a backend receives a single resolved `cache_ttl_seconds` per fetch (the
  manager having applied its default when no per-call value was given).
- **conformance-adapter §6.8** — the caching prompt backend, its controllable clock (`advance_clock`)
  and `source_read_count`, plus the `manager: {default_cache_ttl_seconds}` construction slot and the
  `target: {manager: true}` fetch.

The *default + cacheless backend* no-op is covered by the existing non-caching fetch fixtures, which
continue to pass with a manager default configured: a cacheless backend reads its source every fetch
regardless of the resolved TTL (prompt-management §5).
