# 0087: Conformance-Adapter — Within-Node Directive Execution Order

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-27
- **Targets:** spec/conformance-adapter/spec.md §8.3 *Execution* (add a normative rule that an adapter MUST execute a node's sibling directives in fixture-document / key order); §7 *Nondeterminism handling* (a counterpoint note that within-node directive order IS deterministic, unlike the cross-source interleaving cases it lists); §8.2 *Parsing* (a note that lossless parsing preserves directive order — an order-preserving YAML load). A small new conformance fixture pinning the order-sensitive composition directly.
- **Related:** 0055 (conformance-adapter capability), 0081 (value-matcher vocabulary — the prior conformance-adapter vocabulary clarification), 0034 / 0048 (caller-supplied invocation metadata — the `set` / `get_invocation_metadata` directives whose composition is order-sensitive). Surfaced by the #188–#194 consolidated review on the `review-fixture-harness-catchup` coord thread.
- **Supersedes:**

## Summary

Several conformance fixtures place **multiple directives on a single node** whose effects compose **order-dependently** — most visibly the `get_invocation_metadata` round-trip fixtures, where a node that augments then captures sees the augmented value, while a node that captures then augments does not. The conformance-adapter spec does not state that those directives execute in the order they appear in the fixture document, so a conforming adapter could legitimately execute them in any order and fail these fixtures inconsistently. This proposal ratifies the rule the fixtures already depend on: an adapter MUST execute a node's sibling directives in **fixture-document (key) order**.

## Motivation

Fixtures `043-get-invocation-metadata-roundtrip` and `045-get-invocation-metadata-retry-scoping` pin behavior whose expected output depends on within-node directive order:

- **043** — a node lists `augment_metadata` then `capture_invocation_metadata_into`; the captured snapshot MUST contain the augmented key (augment **then** capture).
- **045** — an attempt-1 node lists `capture_invocation_metadata_into` then `augment_metadata`; the captured snapshot MUST NOT contain that attempt's later write (capture **then** augment).

The only interpretation consistent with both expected blocks is "directives execute in document order." But the spec never says so:

- **§8.2 *Parsing*** requires only that parsing be "lossless against the §5 directive vocabulary" — silent on whether directive *order* is part of what's preserved.
- **§8.3 *Execution*** requires real (non-simulated) primitives — silent on ordering.
- **§7 *Nondeterminism handling*** enumerates the ordering aspects that are NOT determined (fan-out / parallel-branches scheduling, cross-source observer-dispatch interleaving) — but within-node directive order is a *different* axis it does not address, leaving a reader unsure whether it too is nondeterministic.

So an adapter author has no normative basis for executing the directives in document order; one that iterates an unordered mapping (or sorts keys) would fail 043/045 without violating any stated rule. The rule is real and load-bearing — it should be stated.

## Detailed design

Anticipated bump: **MINOR** (pre-1.0). A new normative conformance-adapter rule; it ratifies behavior the existing fixtures already require, so no conforming adapter that passes 043/045 today changes.

### §8.3 *Execution* — directive execution order

Add:

> **Directive execution order.** When a node carries more than one directive (sibling keys under `nodes.<node_name>:`), the adapter MUST execute them in the order they appear in the fixture document. Directives whose effects compose order-dependently — e.g. `augment_metadata` / `augment_metadata_from_field` (writes) and `capture_invocation_metadata_into` (a point-in-time read), per observability §3.4 — therefore produce a deterministic result fixed by their document order. (`update` / `update_from_field` partial-update merges are likewise applied in document order.)

### §7 *Nondeterminism handling* — counterpoint note

Add a sentence distinguishing this determined axis from the nondeterministic ones already listed:

> Within-node directive order is, by contrast, **deterministic**: a node's sibling directives execute in fixture-document order (§8.3). The nondeterminism above is across *sources* (sibling fan-out instances, parallel branches, distinct event sources within a phase), not within a single node's directive list.

### §8.2 *Parsing* — order preservation

Note that lossless parsing includes directive order:

> Lossless parsing preserves the document order of a node's directives (an order-preserving load), so §8.3's execution-order rule has a well-defined order to honor.

## Conformance test impact

Fixtures 043 and 045 already exercise the rule (their `expected` captured snapshots encode augment-then-capture vs capture-then-augment). This proposal adds one small dedicated fixture that pins the rule directly — a single node with two order-sensitive directives in each order across two cases, asserting the deterministic divergence — so the rule has a first-class pin rather than only incidental coverage inside the metadata round-trip fixtures. No new directive vocabulary is introduced.

## Versioning

**MINOR bump** (pre-1.0): a new normative §8.3 rule (plus the §7 / §8.2 notes). No emitted behavior changes for an adapter already passing 043/045. The concrete version is the maintainer's call at acceptance.

## Out of scope

- **Cross-node / cross-source ordering.** Unchanged — §7's nondeterministic cases (fan-out / parallel-branches scheduling, cross-source dispatch interleaving) stand.
- **An explicit ordered-list directive form.** This proposal ratifies the existing mapping-key convention rather than introducing a new list-shaped directive container (see Alternatives).

## Alternatives considered

- **Do nothing.** Rejected: 043/045 silently depend on document order; an adapter iterating an unordered mapping or sorting keys would fail them with no stated rule violated — the cross-implementation ambiguity the conformance suite exists to remove.
- **Require order-sensitive directives in an explicit ordered list** (e.g. a `directives: [ ... ]` sequence) instead of relying on mapping-key order. Rejected: the established fixtures use sibling mapping keys, every real YAML loader preserves mapping insertion order in practice, and an order-preserving load is a one-line adapter requirement — far less churn than reshaping the directive container, and the §8.2 note makes the dependence explicit.
- **Declare within-node directive order nondeterministic** (forbid order-sensitive directive combinations). Rejected: 043/045 are legitimate, useful fixtures; the order-sensitivity is exactly the §3.4 read/write-composition behavior they test.

## Open questions

- **Order-preserving parse as an explicit MUST.** Whether §8.2 should state the order-preserving-load requirement as a normative MUST (most YAML libraries preserve mapping order by default, but a `sort_keys`-style option could break it) or leave it as the descriptive note above — settle at accept.
