# 034 — PromptBackend cache_ttl_seconds: bounded staleness (max-age)

Verifies the §5 / §6 `cache_ttl_seconds = N > 0` bounded-staleness path (proposal 0072): a caching
PromptBackend serves a cached entry while it is younger than `N` seconds and reads the source again
once the entry ages past `N`. Age is measured against the controllable clock the conformance-adapter
§6.8 caching backend exposes, advanced deterministically via `advance_clock` (no wall-clock
dependence).

**Spec sections exercised:**

- §5 `PromptBackend.fetch` `cache_ttl_seconds = N` — MUST NOT serve an entry older than N seconds.
- conformance-adapter §6.8 — the caching backend's controllable clock + the `advance_clock` operation.

**Setup:**

- One caching backend (`cached_maxage`) preloaded with `greeting`.

**Calls + expectations (`cache_ttl_seconds=60` throughout):**

1. `fetch` at t=0 → source read, entry cached.
2. `advance_clock 30`, then `fetch` at t=30 (< 60) → served from cache (no source read).
3. `advance_clock 60`, then `fetch` at t=90 (> 60) → entry too old → fresh source read.
4. `source_read_count == 2` (reads at t=0 and t=90; the t=30 fetch was a cache hit).

**What passes:**

- An entry younger than N is served from cache (the t=30 fetch reads nothing).
- An entry older than N triggers a fresh source read (the t=90 fetch reads the source).
- Read count is exactly 2.

**What fails:**

- The t=30 fetch re-read the source (read count > 2) — the backend ignored the still-valid entry.
- The t=90 fetch served the stale cached entry (read count < 2) — the N-second bound wasn't enforced.
