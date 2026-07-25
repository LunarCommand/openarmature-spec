# 0107: Document the conformance-adapter directive vocabulary

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-24
- **Ships as:** _assigned at acceptance (MINOR)_
- **Targets:** spec/conformance-adapter/spec.md **§5** (*Directive vocabulary*) — give a normative home to the
  load-bearing directives that currently exist **only in fixture headers**, so an adapter author reads the spec
  rather than reverse-engineering the fixtures. Two families: (a) the **retrieval-provider construction / wire /
  error directives** (a new §5.15), and (b) the **typed-observer** directives (§5.5 expansion), the **`cause`**
  failure-isolation assertion (§5.8), and one net-new **retrieval failure-mock** error-field directive.
  Conformance: the directives already exist and are exercised by shipped fixtures; the only new behavior is the
  retrieval failure-mock error-field directive, which gets a fixture. The accept audits every header-only
  directive against §5 so none is left undocumented.
- **Related:** 0089 (embedding/rerank failure observation — surfaced the missing failure-mock error-field
  vocabulary), 0098/0102 (`carries` — the precedent for giving a header-only directive a normative §5 home),
  0059/0060/0077–0079/0090–0093 (the retrieval directives this documents), and the graph-engine §6 typed-event
  families that `typed_observers` / `contains_event` assert
- **Supersedes:**

## Summary

The conformance-adapter §5 *Directive vocabulary* documents the graph-engine, pipeline, and llm-provider
directives, and — after 0098/0102 — the `carries` and `chunk_size` directives. But a large, load-bearing set of
directives has **no §5 entry at all** and is defined only in the header comments of the fixtures that introduced
them: the retrieval-provider construction blocks and wire/error assertions (`mock_embedding`, `mock_rerank`, the
`*_embedding_provider` / `*_rerank_provider` blocks, `expected_wire_request` / `expected_wire_request_absent_keys`
/ `expected_wire_headers`, `expected_error` with `raised_from`, and the `no_embed_request_issued` /
`no_rerank_request_issued` pre-send invariants), and the typed-event assertion directives (`typed_observers`,
`contains_event`) plus the failure-isolation `cause` directive. As of this writing dozens of fixtures across
retrieval and observability depend on these, yet an adapter author has to reverse-engineer each one from the
fixture that happens to define it in a comment.

This proposal promotes them to normative §5 subsections. It is **documentation of existing, shipped behavior**
with one exception: it also defines a **retrieval failure-mock error-field directive** (the gap 0089 logged),
which is a small additive directive with a fixture.

## Motivation

The `carries` directive is the precedent. Before 0098 it was used across five capabilities but documented
nowhere in §5; 0098 gave it a normative §5.12/§5.13 home, and 0102 generalized it. The same debt remains for two
larger directive families, and it has the same cost: two conforming adapters can diverge on an undocumented
directive's semantics, and the "authoritative definition lives in whichever fixture introduced it" pattern does
not scale — an adapter author cannot discover a directive they have not already read a fixture for.

The **present-but-null vs absent** distinction the malformed-figure work (0100/0101) leans on is the sharpest
example: a `contains_event` `fields:` entry asserting an explicit `null` MUST distinguish "field present and
null" from "field omitted" (fixture 149's event-mirror assertion turns on exactly this), and that semantic
appears in **no** normative text today.

## Proposal

### 1. §5.15 — Retrieval-provider directives (new)

Add a §5.15 subsection documenting the retrieval construction, wire-assertion, and error directives, mirroring
the structure of §5.11 (*Provider call-retry directives*). It defines:

- **Construction blocks** — the suite-level `*_embedding_provider` / `*_rerank_provider` blocks
  (`openai_embedding_provider`, `jina_embedding_provider` / `jina_rerank_provider`, `cohere_*`, `tei_*`) that
  construct a bound provider (base_url, model, api_key, optional prefixes), and the `mapping: <name>` selector
  (`openai` / `jina` / `cohere` / `tei`) that picks the §8.x wire mapping under test.
- **Response mocks** — `mock_embedding` / `mock_rerank`: an ordered list of `{status, body}` responses the mock
  provider returns (one per issued request; a chunk-and-stitch call consumes several), in the vendor's real wire
  shape under a `mapping:` selector.
- **Wire assertions** — `expected_wire_request` (the request body the mapping MUST produce),
  `expected_wire_request_absent_keys` (keys that MUST NOT appear), and `expected_wire_headers` (headers the
  mapping MUST send, e.g. `Authorization: Bearer <key>`).
- **Error assertions** — `expected_error: {category, raised_from}` (the §7 category and the node the error is
  raised out of), and the `no_embed_request_issued` / `no_rerank_request_issued` invariants that assert a
  **pre-send** rejection issued no wire request.

This is a lift-and-normalize of the definitions currently in the headers of fixtures 001 (base mock), 013 (TEI
wire vocabulary), 018 (Jina headers), 023 (OpenAI-compatible), and their siblings. No fixture changes; the
directives already behave this way.

### 2. §5.5 — typed-observer directives

Extend §5.5 (*Observer / observability directives*) to define:

- **`typed_observers`** — registers one or more typed-event collectors on a fixture
  (`- name: <collector>`, `kind: typed_event_collector`), the mechanism that captures the graph-engine §6 typed
  event families (`LlmCompletionEvent`, `LlmFailedEvent`, `EmbeddingEvent`, `RerankEvent`, `ToolCallEvent`, …).
- **`contains_event`** — asserts, under `expected.observers.<collector>`, that a typed event was emitted with a
  given `event_type` and a `fields:` map matched by value (per the §5.10 value-matcher vocabulary). Normatively
  pins the **present-but-null vs absent** distinction: a `fields:` entry asserting an explicit `null` MUST match
  only a field that is *present and null*, distinct from an omitted field.

### 3. §5.8 — the `cause` failure-isolation assertion

Document `cause` under §5.8 (*Expected-outcome directives*), **not** §5.5: it asserts the structured
`caught_exception` cause chain on a failure-isolation outcome (pipeline-utilities §6.3) — an outcome assertion,
not an observability directive. Currently used across the failure-isolation fixtures but defined nowhere in §5;
this gives it a home aligned with the §6.3 cause-chain shape (`{category, message, carrier}` links plus the
derived top-level category and message).

### 4. Retrieval failure-mock error-field directive (the 0089 gap — additive)

The tool failure mock supplies literal `error_type` / `error_message` via a `raises: {error_type, message}`
directive, so tool-failure fixtures pin those fields literally. The embedding/rerank failure path is
HTTP-mock-triggered (a status code → a §7 `error_category`), with **no** directive to supply literal
`error_type` / `error_message` — so fixtures 137 / 138 assert those two event fields only by format
(`<any-string>`), not literally. Define the retrieval analogue so a retrieval failure fixture can pin the
event's `error_type` / `error_message` cross-impl. This is the one net-new directive; it lands with a fixture
that asserts the literal fields on an embedding failure.

### 5. Conformance

The §5.15, §5.5, and §5.8 directives are documentation of directives shipped fixtures already exercise — no
fixture changes. The §4 failure-mock directive lands with **one** new retrieval failure fixture asserting literal
`error_type` / `error_message` on an embedding failure (the case 137/138 could only assert by format).

**Full audit at acceptance.** The accept MUST audit every fixture-header-defined directive against §5 and give a
home to any this proposal's enumeration missed, so **no** header-only directive survives — otherwise the debt
this closes simply re-forms around the straggler.

## Versioning

**MINOR** (whole-spec SemVer). Almost entirely **documentation** — the retrieval and typed-observer directives
already behave as their fixture headers describe; §5 gains their normative definitions so adapters stop
reverse-engineering them, and no shipped fixture changes. **The documentation framing depends on faithfulness:
each §5 definition MUST be a faithful lift of the current fixture-header definition — the accept MUST diff the
two, and any §5 text that tightens or changes a directive's semantics rather than restating them is called out
and re-scoped (it is no longer pure documentation).** The single intended behavioral addition is the retrieval
failure-mock error-field directive (§4), which is **additive** (a new opt-in directive) and lands with its own
fixture. No existing fixture's outcome changes.

## Open questions

- **Should the `cause` directive's cross-capability shape be unified now, or documented as-is?** It is used in
  pipeline-utilities failure-isolation fixtures; this proposal documents its current shape. If observability /
  retrieval grow their own cause-chain assertions, a later pass may need to reconcile them — out of scope here.
- **Adapter-authoring guidance vs. normative directive text.** §5 is a directive *catalog*; the deeper
  "how an adapter realizes a typed-event collector in its host runtime" is implementation guidance. This
  proposal keeps §5.5/§5.15 to the directive contract (shape + semantics), not per-language realization.
