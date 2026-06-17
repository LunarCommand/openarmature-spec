# 0072: Prompt Management — Per-Fetch Cache-TTL Control

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-16
- **Targets:** spec/prompt-management/spec.md (add an optional `cache_ttl_seconds` parameter to the §5 `PromptBackend.fetch` contract and to the §6 `PromptManager.fetch` / `get` operations; amend the §5 backend-caching paragraph so the per-fetch TTL is a defined caller lever; add a clarifying note to §15). spec/conformance-adapter/spec.md (add a caching prompt-backend harness primitive to §6 so a fixture can assert the force-fresh behavior).
- **Related:** 0047 (last prompt-management change — prefix-cache authoring guidance in §13 / §14; note this proposal concerns the *backend template-fetch* cache, a different cache from the user-level result cache §15 defers), 0055 (conformance-adapter capability — the harness-primitive touchpoint).
- **Supersedes:**

## Summary

A `PromptBackend` MAY maintain a client-side cache of fetched templates (§5 already says so: "Backends MAY cache their own results internally … cache invalidation is implementation-defined"). Today a caller has no way to influence that cache per fetch — neither `PromptBackend.fetch` (§5) nor `PromptManager.fetch` / `get` (§6) exposes any cache control — so a long-lived process is stuck with whatever default TTL the backend's cache uses. This proposal threads an optional **`cache_ttl_seconds`** through those operations: absent/`None` preserves today's behavior; `0` forces a fresh fetch (bypassing any cached entry); a positive value bounds how stale a served entry may be. Backends that keep no client-side cache treat it as a no-op. The change is additive and fully backward-compatible.

## Motivation

A process that holds a `PromptManager` for its lifetime and fetches through a caching backend cannot observe a republished prompt until the backend's cache TTL lapses. The common need is **on-demand refresh** — an operational path that should pick up a newly published prompt version *without* restarting the process (for example, to recompute derived state keyed by the fetched version the moment a new version is published). With no per-fetch cache control, an in-process "refresh" re-reads the same cached version and is a no-op until the TTL expires.

§5 deliberately leaves cache *invalidation* implementation-defined, and §15 defers user-level *result*-cache invalidation. But the narrow lever this needs — "for this fetch, don't serve a stale cached template" — is a property of the fetch contract itself, not a separate caching subsystem. The SDK-backed and HTTP-backed backends that maintain such a cache already support a per-call TTL knob internally; the gap is purely that OA's fetch surface does not expose one, so the knob is unreachable from `PromptManager`.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0); concrete version assigned at acceptance. The change adds one optional parameter to the fetch surface (additive, backward-compatible) and a conformance harness primitive.

### §5 — `PromptBackend.fetch` gains `cache_ttl_seconds`

Extend the `fetch` contract with an optional parameter:

> ### `fetch(name, label="production", cache_ttl_seconds=None)`
>
> - `name` — string. Required. (unchanged)
> - `label` — string. Default `"production"`. (unchanged)
> - `cache_ttl_seconds` — optional non-negative integer, default absent / `None`. Bounds the
>   staleness of a cached template the backend MAY serve for *this* fetch, for backends that
>   maintain a client-side cache:
>   - **absent / `None`** — the backend's own caching behavior governs (current behavior; fully
>     backward-compatible).
>   - **`0`** — the backend MUST NOT serve a cached entry; it fetches fresh from the source.
>   - **`N > 0`** — the backend MUST NOT serve a cached entry older than `N` seconds; an entry
>     younger than `N` seconds MAY be served, otherwise the backend fetches fresh.
>
>   Negative values are invalid; implementations MUST reject them (an argument / value error).
>
>   `cache_ttl_seconds` governs only which cached entry MAY be served for *this* fetch; whether the
>   fetched result is then written to the backend's cache, and for how long, remains the backend's
>   implementation-defined cache management (below). A `0` fetch therefore guarantees a fresh
>   *read* — not that subsequent default-TTL fetches observe the new version.
>
> Backends that maintain **no** client-side cache — filesystem backends, in-memory backends, and
> any backend that reads its source on every fetch — treat `cache_ttl_seconds` as a no-op: they
> already return a fresh read each call. The parameter is part of the contract so caching and
> non-caching backends share one signature; cacheless backends accept and ignore it.

Amend the existing backend-caching paragraph (§5) so the TTL is a defined caller lever rather than
wholly implementation-defined:

> Backends MAY cache their own results internally (e.g., a managed-registry backend caching by
> `(name, label)` for some TTL). When a caller supplies `cache_ttl_seconds`, it bounds the
> staleness of any cached entry the backend MAY serve for that fetch (above); **other** aspects of
> cache management — whether a fetched result is written to the cache, eviction, sizing,
> cross-process invalidation — remain implementation-defined.
> When a backend serves a cached result, the returned `Prompt`'s `template_hash` MUST still be
> correct for the served template, and `fetched_at` MUST reflect the original fetch time, not the
> cache-hit time (unchanged — caching MUST NOT break content-addressing).

### §6 — `PromptManager.fetch` / `get` thread it through

> ### `fetch(name, label=None, cache_ttl_seconds=None)`
>
> Async. (Label resolution unchanged.) When `cache_ttl_seconds` is supplied, the manager passes it
> verbatim to every backend `fetch(name, label, cache_ttl_seconds)` call it makes while walking the
> §9 fallback chain — so a `0` (force-fresh) applies to whichever backend ultimately serves the
> prompt. Default absent / `None` (current behavior).

> ### `get(name, label=None, variables=None, cache_ttl_seconds=None)`
>
> Async. Convenience equivalent to `render(await fetch(name, label, cache_ttl_seconds), variables)`.
> The parameter governs the fetch leg only.

`render` (§6) is unchanged: it is a local transformation over an already-fetched `Prompt` and
performs no I/O, so a cache-control parameter has no meaning there.

### §15 — clarifying note

Add a sentence to the §15 *Cache invalidation policies* bullet distinguishing the two caches: the
per-fetch backend-template cache control is now provided by §5 / §6 `cache_ttl_seconds`; what
remains out of scope is user-level *result*-cache invalidation (the caller's own cache keyed by
`template_hash` / `rendered_hash`) and any cross-process or eviction-policy machinery.

### Determinism

`cache_ttl_seconds` affects only which version of an external template a fetch returns (an I/O
concern over backend state); it does not affect the deterministic render of a given fetched
template. §13 is unaffected.

## Conformance test impact

A new fixture under `spec/prompt-management/conformance/` exercises the force-fresh path via the
backend's **source-read count**, which needs no source mutation: two sequential fetches of the same
`(name, label)` with default cache control perform **one** source read (the second is served from
cache); two fetches with `cache_ttl_seconds=0` perform **two** source reads (each bypasses the
cache). The assertion is on the read count, not on timing or template contents.

This requires a **caching prompt-backend** harness primitive (conformance-adapter §6): an in-memory
backend that caches by `(name, label)`, counts source reads, and honors `cache_ttl_seconds`
(`0` bypasses; `None` serves cached). The `N > 0` max-age path additionally needs a controllable
clock and is exercised by a clock-controlled fixture variant (a served entry reused within `N`,
re-read past it); the `0`-vs-default read-count path is the core asserted behavior. Non-caching
backends' no-op handling is covered by the existing filesystem / in-memory fetch fixtures
continuing to pass with the parameter supplied.

## Versioning

**MINOR bump** (pre-1.0): §5 / §6 gain an optional parameter; behavior is additive and the default
preserves current semantics exactly. No existing fetch / render / fallback behavior changes. The
concrete version is the maintainer's call at acceptance.

## Out of scope

- **Cache eviction, sizing, and cross-process invalidation** — `cache_ttl_seconds` is a per-fetch
  staleness bound, not a cache-management API. How a backend evicts, sizes, or invalidates across
  processes remains implementation-defined (§5).
- **User-level result-cache invalidation** — the caller's own cache of rendered results keyed by
  `template_hash` / `rendered_hash` stays out of scope per §15; this proposal concerns only the
  backend's template-fetch cache.
- **A manager-level or construction-time default TTL** — the need is per-fetch granularity (a
  specific refresh call forces fresh while ordinary calls use the default). A global default is a
  possible future convenience but is not required here.
- **A cache-clear / purge method on the manager or backend** — bypassing on the fetch path
  (`cache_ttl_seconds=0`) covers the on-demand-refresh need without a separate mutating operation
  that would not compose with the §9 fallback fetch path.

## Alternatives considered

- **A `force_refresh: bool` flag** instead of `cache_ttl_seconds`. Rejected: strictly less
  expressive — it can bypass the cache but cannot *shorten* staleness (the "I want ≤ N-second
  staleness without re-fetching on every call" case). `cache_ttl_seconds` covers both (`0` =
  bypass, `N` = bounded staleness) with one parameter and reads naturally for backends whose
  client-side cache is already TTL-based.
- **A cache-clear method** (e.g., `manager.invalidate(name)`). Rejected: a mutating side operation
  that does not compose with the fallback fetch path and forces callers to sequence an explicit
  invalidate before each refreshing fetch; the per-fetch bound is simpler and atomic.
- **Construction-time TTL only** (configure the backend's TTL at build time). Rejected: it cannot
  express "this one refresh call must be fresh" without rebuilding the backend; the need is
  per-fetch.
- **Leave it implementation-defined** (status quo — backends cache, callers cannot influence it).
  Rejected: it leaves on-demand refresh impossible through the `PromptManager` surface, which is
  the whole point of the request.
