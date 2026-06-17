# 033 — PromptBackend cache_ttl_seconds: force-fresh read count

Verifies the §5 / §6 `cache_ttl_seconds` force-fresh path (proposal 0072) via a caching
PromptBackend's source-read count (conformance-adapter §6.8). With default cache control a caching
backend serves a repeat fetch from its cache (one source read for two fetches); with
`cache_ttl_seconds=0` every fetch bypasses the cache (two source reads for two fetches). The
assertion is on the read count — no source mutation, timing, or content comparison needed.

**Spec sections exercised:**

- §5 `PromptBackend.fetch` `cache_ttl_seconds` — `None` (default) serves cached; `0` forces a fresh read.
- §6 `PromptManager.fetch` / `get` thread the parameter through (here exercised at the backend level).
- conformance-adapter §6.8 — the caching prompt-backend primitive + the `source_read_count` shape.

**Setup:**

- Two caching backends preloaded with the same `greeting` prompt.

**Calls + expectations:**

1. Two `fetch(greeting, production)` against `cached_default` (no `cache_ttl_seconds`) →
   `source_read_count == 1` (the second is served from cache).
2. Two `fetch(greeting, production, cache_ttl_seconds=0)` against `cached_force_fresh` →
   `source_read_count == 2` (each bypassed the cache).

**What passes:**

- Default control coalesces the repeat fetch to one source read.
- `cache_ttl_seconds=0` produces a source read on every fetch.
- Both backends return the correct `Prompt` (`template_hash` correct on cache hits and fresh reads alike).

**What fails:**

- `cache_ttl_seconds=0` served a cached entry (read count < 2) — force-fresh broken.
- Default control re-read the source on the second fetch (read count > 1) — the backend isn't caching as configured.
- A cache hit returns a stale / incorrect `template_hash` — caching broke content-addressing (§5).
