# 0105: Extras-key vs mapping-managed wire-field collision rule

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-07-18
- **Accepted:** 2026-07-23
- **Ships as:** v0.100.0
- **Targets:** spec/llm-provider/spec.md **§6** (a general rule for what happens when an undeclared extras key
  collides with a wire field the mapping *manages* — an explicit, bounded carve-out to the untouched
  pass-through), inherited by retrieval-provider §10. Applied to the known managed keys: **§8.4** `embedding_types`
  (the *merge* arm, ratifying 0099's mapping-local exception as the general rule); the fail-loud truncation
  flag in **§8.1 / §8.2 / §8.4** (`truncate` / `truncation`, the *reject* arm); and, on the OpenAI llm-provider
  mapping (**§8.1**), the *reject*-arm keys the general rule's home capability was silently exposed to — the
  **structural** wire-root fields `model` / `messages` / `tools` / `tool_choice`, and two conditionally-managed
  non-additive object fields, **§8.1.5** `response_format` (managed while the mapping is producing it) and
  **§8.1.6** `stream_options` (managed while streaming). Conformance: reject-arm fixtures across the retrieval
  mappings and the llm-provider keys.
- **Related:** 0099 (pinned the §8.4 `embedding_types` collision as a mapping-local exception and explicitly
  left the general rule open — this closes it), and §6's *Extras pass-through* contract, which this proposal
  amends with a bounded carve-out
- **Supersedes:**

## Summary

llm-provider §6 says an undeclared extras field is forwarded to the wire body **untouched** and MUST NOT be
translated, renamed, or transformed. It says nothing about an extras key that collides with a wire field the
mapping itself **manages** — a field the mapping sets for its own correctness (e.g. Cohere's
`embedding_types: ["float"]`, which its response consumer reads; `truncate: "NONE"`, which enforces the
fail-loud posture). Under untouched pass-through, a caller's colliding extras value silently overrides the
managed field and **breaks the mapping** — the exact failure 0099 prevented for one key and explicitly declined
to generalize. Two conforming implementations can diverge: forward-untouched, let-the-mapping-win, or
silently-drop.

This proposal states the general rule, bounded to keys a mapping declares it manages:

> **A managed wire field governs a colliding extras key.** If the field is additive / list-shaped, the caller's
> value(s) are **merged** with the mapping's (de-duplicated, so a matching entry collapses). If it is
> **non-additive** — a scalar mode-switch, or an object the mapping constructs wholesale, whose value is
> mutually exclusive with the caller's — a value **equal** to the managed value is a redundant no-op and a
> **conflicting** value is **rejected pre-send** (`provider_invalid_request`). A field the mapping produces only
> conditionally is managed only while it is producing it. A mapping MUST NOT
> silently drop a conflicting value or silently let it override the managed one. Keys the mapping does **not**
> manage keep untouched pass-through unchanged.

## Motivation

### The gap 0099 left open

0099 pinned the §8.4 `embedding_types` collision as an explicit **mapping-local** exception: the mapping must
request `"float"` for its own response consumer, so an extras-supplied `embedding_types` is **merged** with
`"float"` rather than replacing it. 0099 closed with: "The general question — what happens when *any* extras key
collides with *any* mapping-managed wire field — is not specified." This is that specification.

The failure mode is concrete. A managed field is one the mapping sets because its own logic depends on it. If an
undeclared extras key of the same name reaches the wire untouched (as §6 currently requires), it overrides the
managed value and defeats the mapping: an extras `embedding_types: ["int8"]` strips the `embeddings.float` key
the response consumer reads (0099's case); an extras `truncate: "END"` overrides the mapping's `"NONE"` and
silently truncates an over-length input the mapping meant to fail loud on. Untouched pass-through is correct for
a field the mapping doesn't touch; it is wrong for a field the mapping owns.

### Why merge for some, reject for others

The resolution depends on the **shape** of the managed field:

- **Additive / list-shaped** (`embedding_types`): the managed value and the caller's can coexist — the wire
  accepts a set, and the response is keyed by member, so the mapping requests `"float"` **and** the caller's
  precisions. **Merge** (deterministic order, de-duplicated) preserves both without breaking the consumer.
- **Scalar mode-switch** (`truncate`, and — when it lands — an output `encoding_format`): the field selects one
  behavior; the managed value and the caller's are mutually exclusive. There is nothing to merge, and honoring
  the caller's value breaks the mapping's contract (its fail-loud posture, its response format). The only safe
  resolution is to **reject pre-send** with `provider_invalid_request` — fail-loud, not a silent drop (which
  would hide the caller's intent) and not a silent override (which would break the mapping).

Rejecting is not hostile to the extras mechanism: it applies only to a key the mapping **manages**, which the
mapping declares. Every other undeclared key still passes through untouched. The rule narrows, it does not close,
the extras bag.

## Proposal

### 1. §6 — the general rule (bounded carve-out)

Add to §6's *Extras pass-through* a **managed-field collision** clause:

- Define a **managed wire field**: a wire-body field the wire-format mapping (§8) sets for its own correctness —
  because its response consumer reads a value keyed to it, or because it enforces a mapping-level contract. Each
  §8.x mapping **MUST enumerate** the keys it manages.
- When an undeclared extras key **names a managed field**, untouched pass-through does **not** apply. Instead:
  - **Merge** if the managed field is additive / list-shaped: the mapping's mandatory value(s) and the caller's
    are combined, in a deterministic order (mapping value(s) first), de-duplicated first-occurrence-wins.
  - **Reject pre-send** with `provider_invalid_request` (§7) if the managed field is a scalar whose override
    would break the mapping's contract or its response consumer — **unless** the extras value **equals** the
    managed value, which is a redundant no-op (the scalar analogue of the merge arm's de-duplication).
  - A mapping **MUST NOT** silently drop a conflicting extras value, and **MUST NOT** silently let it override
    the managed value.
- A key the mapping does **not** manage is unaffected: it keeps the untouched pass-through of §6 verbatim. The
  managed set is opt-in per mapping; the default for any other key is unchanged.

### 2. §8.4 `embedding_types` — the merge arm (ratify 0099)

Re-anchor 0099's `embedding_types` exception as an **instance** of §6's merge arm rather than a standalone
mapping-local exception: `embedding_types` is a managed list-shaped field; an extras-supplied value merges with
`"float"` (float-first, de-duplicated), per §1 above. The behavior is unchanged; only its framing generalizes.

### 3. `truncate` / `truncation` — the reject arm (§8.1 / §8.2 / §8.4)

The TEI (§8.1), Jina (§8.2), and Cohere (§8.4) embed mappings each send a **managed fail-loud truncation flag**
so an over-length input errors rather than being silently truncated — `truncate: false` (TEI; Jina
`/v1/embeddings`), `truncation: false` (Jina `/v1/rerank`), `truncate: "NONE"` (Cohere). The value type differs
by vendor, but in each case the mapping sets the flag to enforce its fail-loud contract. Declare each mapping's
truncation flag a **managed scalar**: an extras-supplied value that **conflicts** with the managed flag is
**rejected pre-send** with `provider_invalid_request` (honoring it would defeat the fail-loud posture; the
mapping MUST NOT silently drop it either); a value **equal** to the managed flag is a redundant no-op.

### 3.5. The llm-provider reject arm (§8.1) — structural and conditionally-managed keys

The general rule lives in llm-provider §6, but the OpenAI llm-provider mapping is itself exposed to present
managed-field collisions the retrieval keys don't cover. Two kinds:

**Structural wire-root fields (§8.1)** the mapping sets for its own correctness, which are *not* declared
`RuntimeConfig` fields — **`model`** (the bound identifier), **`messages`** and **`tools`** (the `complete()`
arguments), **`tool_choice`** (the §5 parameter). An extras key of the same name collides at the root, and the
OpenAI-SDK `extra_body` root merge §8.1 codifies lets the caller's value silently win — silently re-routing the
model, replacing the conversation, or overriding the tool set. Each is a managed non-additive field: a
conflicting extras value is **rejected pre-send** `provider_invalid_request` (a caller who wants a different
model binds a different provider instance). These are the *highest-impact* collisions the rule exists to
prevent.

**Conditionally-managed object fields** — both constructed wholesale, managed only *while the mapping is
producing them*:

- **`response_format` (§8.1.5)** — managed on the native structured-output path (a `response_schema` supplied,
  the mapping constructs `response_format` and its §7 `structured_output_invalid` validation depends on it); a
  conflicting extras `response_format` is **rejected pre-send**. **Unmanaged** on a free-form call (no schema)
  *or the §8.1.5.1 prompt-augmentation fallback path* (a schema is supplied but the request is issued without
  `response_format`) — there an extras `response_format` rides untouched.
- **`stream_options` (§8.1.6)** — managed while streaming (the mapping sets `{include_usage: true}` for the
  terminal-chunk usage its §6 *Streaming assembly* consumer reads); a conflicting extras value is rejected
  pre-send. Unmanaged for a non-streaming call.

The object fields are why 0105's reject arm is stated over **non-additive** fields, not just scalars.

**Deferred (the declared-field-vs-extras question).** The wire keys `stop` (realizing declared `stop_sequences`),
`stream` (realizing `complete(stream=…)`), and retrieval §8.2 Jina `task` (realizing `input_type`) are *not*
managed-internal — the caller has a declared way to set them, and an extras key uses the wire name. How a
wire-name extras key interacts with a declared-field realization is a distinct question settled uniformly for
all three in a follow-on (see Open questions).

### 4. Conformance

Reject-arm fixtures across all five bound keys. Retrieval (mechanics differ — Cohere / Jina-embed send the flag
explicitly, TEI `/embed` relies on the vendor default, Jina `/rerank` uses the distinct `truncation` name):
fixture 046 (Cohere `/v2/embed` `truncate`), 047 (TEI `/embed` `truncate` — the relied-upon-default reject +
matching-value-*omitted* body-minimal outcome), 048 (Jina `/v1/rerank` `truncation` — the distinct name).
llm-provider: fixture 072 (`response_format` — conflict while producing it rejected pre-send; unmanaged rides
untouched) and 073 (`stream_options` — conflict while streaming rejected; non-streaming rides untouched), the
two-case shape proving each is *conditionally* managed; and fixture 074 (`model` — the structural
managed-internal reject, representative of `model` / `messages` / `tools` / `tool_choice`, which share the
mechanic). Each reject asserts `provider_invalid_request` pre-send with no request issued. The existing
retrieval-provider merge-arm fixture (039, the `embedding_types` merge) already exercises §1's merge arm.

## Versioning

**MINOR** (whole-spec SemVer). **Behavioral for a managed-key collision only**, across both capabilities: a
**conflicting** extras value on a managed field that a mapping previously forwarded untouched now rejects
pre-send — the retrieval fail-loud `truncate` / `truncation` flags, and the OpenAI llm-provider structural
`model` / `messages` / `tools` / `tool_choice`, `response_format` (while producing it) and `stream_options`
(while streaming). That prior behavior was undefined and harmful (it silently defeated the mapping — re-routed
the model, replaced the conversation, broke a fail-loud contract, structured-output validation, or streamed-usage
collection), so this is a correction, not a removal of working behavior. A matching value is a no-op, a
conditionally-managed field is unmanaged when the mapping isn't producing it, every unmanaged extras key is
unaffected, and the `embedding_types` merge is unchanged from 0099.

## Open questions

- **The declared-field-vs-extras question (deferred, needs its own uniform pass).** This rule governs
  **managed-internal** fields — keys the mapping sets for its *own* correctness, which are not declared OA
  config the caller can set another way. A separate class is a wire key that **realizes a declared OA field**,
  shadowed by an extras key of the wire name: llm-provider `stop` (realizes declared `stop_sequences`), `stream`
  (realizes `complete(stream=…)`), and retrieval §8.2 Jina `task` (realizes `input_type`). There the caller has
  a sanctioned, declared path and the extras key duplicates it — the resolution (does the declared field win,
  does the extras key, is it a conflict-reject) should be decided **uniformly for all three at once**, not
  key-by-key. Deliberately left to a follow-on so it isn't answered inconsistently across mappings.
- **Residual managed-key audit.** §1 requires each §8.x mapping to enumerate its managed keys; this proposal
  enumerates the presently-known **managed-internal** ones across both capabilities — retrieval `embedding_types`
  (merge) and `truncate` / `truncation` (reject); llm-provider structural `model` / `messages` / `tools` /
  `tool_choice` (reject) and conditionally-managed `response_format` / `stream_options` (reject). What remains is
  the §8.3 OpenAI `encoding_format` (the deferred output-encoding scalar; see the §8.3 base64 open question) and
  any managed key a future §8.x mapping introduces. The enumeration is per-mapping, not a global list.
