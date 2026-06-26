# 0086: Prompt Management — Service-Wide Default Cache-TTL

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-26
- **Targets:** spec/prompt-management/spec.md (§6 — `PromptManager` construction gains an optional `default_cache_ttl_seconds`; the §6 `fetch` / `get` cache-control resolution amended to a precedence chain — explicit per-call value > manager default > backend implementation-defined — mirroring the existing label chain; a negative default rejected at construction, with the §5 per-call negative-rejection still applying after the chain resolves. §5 — a sentence noting the manager default composes with the per-fetch lever and that cacheless backends no-op it regardless of source. §15 — reconcile the "Cache invalidation policies" bullet's "per-fetch … lever" wording, no longer per-fetch-only once a standing default exists). New conformance fixture(s): default applied / per-call overrides default / default + cacheless no-op.
- **Related:** 0072 (per-fetch `cache_ttl_seconds` — this realizes the "manager-level or construction-time default TTL" 0072 explicitly deferred as "a possible future convenience"), 0033 (`sampling` — per-prompt config precedent), 0055 (conformance-adapter — the caching-prompt-backend primitive reused).
- **Supersedes:**

## Summary

0072 added a per-fetch `cache_ttl_seconds` lever and explicitly deferred "a manager-level or construction-time default TTL" as "a possible future convenience … not required here." That convenience is now a real need: a long-lived service wants one standing staleness bound honored by every prompt fetch — a tuning knob (tighter for fast prompt iteration, looser for fewer backend calls) — without threading the same value into every `get` / `fetch` call site or wrapping the manager. Today, omitting `cache_ttl_seconds` falls through to the backend's implementation-defined cache TTL, and there is no OA-level way to set a service-wide default. This proposal adds an optional `default_cache_ttl_seconds` to `PromptManager` construction, applied when a fetch doesn't specify one; a per-call value still overrides (an on-demand `0` force-refresh is unaffected), and cacheless backends still no-op it. Additive and backward-compatible.

## Motivation

A service that holds a `PromptManager` for its lifetime and fetches a prompt per invocation across many nodes wants a single staleness policy — "this service tolerates prompt-cache staleness up to N seconds" — set once where the manager is built. 0072 gave callers the per-fetch lever, which is exactly right for *on-demand* control (force a fresh read with `0`, or bound one fetch's staleness). But it offers no *standing* default: a uniform policy today means passing the same `cache_ttl_seconds` into every call site (which multiplies across nodes and services) or wrapping the manager.

When `cache_ttl_seconds` is omitted, §5 defers to "the backend's own caching behavior" — the backend's implementation-defined cache TTL. That is per-backend and non-portable, and there is no OA-level knob to tune it. The `PromptManager` is the natural home for a portable default: it already threads `cache_ttl_seconds` to backends through the §9 fallback chain, and it already resolves a *label* default chain (explicit > resolver > `"production"`). A cache-TTL default chain is the exact parallel — explicit per-call > manager default > backend implementation-defined — and composes with the per-fetch lever 0072 shipped.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). Additive — a new optional construction parameter; absent preserves today's behavior exactly.

### §6 — `PromptManager` gains an optional default

Amend the §6 construction description (currently: "A `PromptManager` is constructed with one or more `PromptBackend`s and (optionally) a `LabelResolver` (per §7)."):

> A `PromptManager` is constructed with one or more `PromptBackend`s, (optionally) a `LabelResolver` (per §7), and (optionally) a `default_cache_ttl_seconds`. The default is a non-negative integer carrying the same per-fetch semantics as §5's `cache_ttl_seconds` (`0` = force fresh, `N > 0` = bound staleness to `N` seconds); a negative value is invalid and MUST be rejected at construction (per the language's idiom for an invalid argument).

Amend the `fetch` cache-control paragraph (and `get`, which delegates to `fetch`) to a precedence chain mirroring the label chain:

> `cache_ttl_seconds` resolves by the same shape as label resolution:
> 1. If a per-call `cache_ttl_seconds` is explicitly supplied (including `0`), use it verbatim — subject to the §5 rule that a negative value is rejected.
> 2. Else if the manager was constructed with a `default_cache_ttl_seconds`, use that.
> 3. Else pass nothing (absent) — the backend's own caching behavior governs (current behavior).
>
> The resolved value is passed verbatim to every backend `fetch(name, label, cache_ttl_seconds)` call the manager makes while walking the §9 fallback chain. A per-call value always overrides the manager default — so an on-demand `0` force-refresh forces a fresh read even when a positive default is configured.
>
> Once a `default_cache_ttl_seconds` is configured, an omitted per-call argument resolves to that default (step 2), not to the backend's own behavior (step 3) — that is the default's purpose. There is therefore no per-call argument that means "defer to the backend's own TTL for this one fetch" while a manager default is set; a caller needing that configures no default, or passes an explicit value. Implementations whose language distinguishes an explicit unset sentinel from an omitted argument MUST treat both identically (an unset per-call value selects the default), so resolution does not depend on argument-presence semantics. A manager constructed without a default is unaffected — step 3 governs, exactly as before this proposal.

### §5 — composition note

Add a sentence to the §5 backend-caching paragraph: a backend receives a single resolved `cache_ttl_seconds` per fetch (the manager having applied its default when no per-call value was given); the per-fetch semantics, and the cacheless-backend no-op, are unchanged whether that value originated from a per-call argument or the manager default. The Langfuse and other caching backends need no change — they already honor a supplied `cache_ttl_seconds` per 0072.

### §15 — reconcile the out-of-scope cache wording

§15's *Cache invalidation policies* bullet currently frames cache control as "the per-fetch backend-template cache … controllable via the §5 / §6 `cache_ttl_seconds` lever." With a standing `default_cache_ttl_seconds`, control is no longer per-fetch-only; reword the bullet to cover both the per-fetch lever and the manager-level default, while still scoping out user-level *result*-cache invalidation (unchanged).

## Conformance test impact

A new prompt-management fixture exercises the default via the 0072 **caching-prompt-backend** harness primitive (source-read count + controllable clock): a manager constructed with `default_cache_ttl_seconds = N` serves a cached entry within `N` and re-reads past it for a fetch that supplies no per-call value; a per-call `cache_ttl_seconds = 0` on the same manager forces a fresh read despite the positive default (precedence); and a manager default against a cacheless backend is a no-op (existing filesystem / in-memory fetch fixtures continue to pass with a default configured). The fixture constructs a `PromptManager` with a `default_cache_ttl_seconds`; confirm at accept that the conformance harness's manager construction exposes a slot for the construction-time default, adding one to the §6.8 caching-prompt-backend primitive's setup if not. Otherwise reuses the 0072 primitive (source-read count + controllable clock); no new primitive is anticipated.

## Versioning

**MINOR bump** (pre-1.0): §6 construction gains an optional parameter and the cache-control resolution becomes an explicit precedence chain; absent default preserves current semantics exactly. No existing fetch / render / fallback behavior changes. The concrete version is the maintainer's call at acceptance.

## Out of scope

- **Cache eviction, sizing, cross-process invalidation** — unchanged from 0072 / §5 (implementation-defined).
- **The per-fetch lever (0072)** — unchanged; the manager default composes with it.
- **A per-backend default, and configuring a backend's underlying-client TTL** — both are covered under *Alternatives considered* (rejected as the mechanism here) and *Open questions* (a per-backend default as a possible later complement); not introduced by this proposal.

## Alternatives considered

- **Per-backend default only.** Rejected as the sole mechanism: a service with multiple backends (e.g., registry-first, filesystem-fallback) would have to set it per backend; the manager-level default is the single service-wide knob the need calls for. A per-backend default MAY be added later as a complement.
- **Leave it to each backend's underlying client.** Rejected: non-portable (backend-specific), and not every backend exposes a client-level default; the OA-level default is uniform across backends and languages — the point of the spec.
- **Per-call only (status quo).** Rejected: it forces threading the value into every call site or wrapping the manager, which is the reported friction this resolves.

## Open questions

- Whether to also offer a per-backend default complementing the manager-level one — deferred unless a multi-backend service demonstrates the manager-level default is insufficient.
