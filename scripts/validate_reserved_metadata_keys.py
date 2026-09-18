#!/usr/bin/env python3
"""Check that every top-level metadata key a §8 mapping writes is reserved.

observability §3.4 tells a caller which invocation-metadata keys it may not
use, and the rule the reserved set exists to serve is that a caller key can
never shadow an OA-emitted field in a backend whose data model puts both at the
same top level. §3.4 states the maintenance obligation directly: a proposal
introducing a new top-level OA-emitted key in a §8 mapping MUST add that name
to the reserved set, unless a reserved namespace already covers it.

Nothing enforced that obligation, and it had already drifted: proposal 0119
found four names the §8.4 mappings wrote and the set omitted. Drift is silent
and recurring rather than exceptional, which is what makes it worth a check
that runs on every change rather than a sweep somebody remembers to do.

The check reads both sides out of the spec rather than hardcoding either, so it
cannot pass by agreeing with a stale copy of the answer:

* the **written** side is every backticked ``<entity>.metadata.<key>`` form in
  the observability spec, reduced to its first key segment, since a nested
  ``prompt.version`` is not a top-level key and ``prompt`` is what the caller
  could collide with;
* the **reserved** side is §3.4's own exact-match list and its namespace
  prefixes, parsed from the section text.

Two keys are excluded, each for a reason the spec states and each asserted
live, so an exclusion cannot outlive its subject:

* ``userId`` is written by §8.4.1 but deliberately unreserved. Reserving it
  would break the promotion that maps a caller's key onto Langfuse's native
  field, so the exclusion asserts it stays unreserved rather than tolerating
  either answer.
* ``prompt_name`` appears only in a sentence naming it as something
  implementations MUST NOT write, so it is not a key any mapping writes.

Exit 1 with a per-violation report, 0 when clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent / "spec" / "observability" / "spec.md"

# `trace.metadata.correlation_id`, `observation.metadata.branch_name`, and the
# bare `metadata.error_message` form all denote the same thing: a key written
# at the top level of a backend metadata object.
WRITTEN_RE = re.compile(r"`[a-zA-Z_]*\.?metadata\.([a-zA-Z_][a-zA-Z_0-9.]*)`")

# Each exclusion names the key, the reason, and a predicate that must hold for
# the exclusion to stay honest. A predicate that stops holding fails the check
# rather than quietly widening it.
EXCLUSIONS = {
    "userId": (
        "§8.4.1 promotes a caller key onto Langfuse's native userId field; "
        "reserving the name would break that promotion",
        lambda reserved, text: "userId" not in reserved,
    ),
    "prompt_name": (
        "named only as a key implementations MUST NOT write, so no mapping "
        "writes it",
        lambda reserved, text: "MUST NOT" in text and "prompt_name" not in reserved,
    ),
}


def parse_reserved(text: str) -> tuple[set[str], list[str]]:
    """Pull §3.4's exact-match set and namespace prefixes out of the spec."""
    # The sentence wraps and its continuation lines are indented, so collapse
    # every whitespace run before matching rather than only newlines.
    flat = re.sub(r"\s+", " ", text)
    marker = "The current reserved set, drawn from the §8.4 Langfuse mapping, is:"
    if marker not in flat:
        sys.stderr.write(
            "could not find §3.4's reserved-set sentence; the check reads it "
            "from the spec rather than hardcoding it, so a reworded sentence "
            "is a failure rather than a pass.\n"
        )
        raise SystemExit(1)
    tail = flat.split(marker, 1)[1]
    sentence = tail.split("Implementations MUST reject", 1)[0]
    names = set(re.findall(r"`([a-zA-Z_][a-zA-Z_0-9]*)`", sentence))

    ns_line = re.search(
        r"Keys MUST NOT collide with reserved namespaces:([^.]*(?:\.\*[^.]*)*)", flat
    )
    namespaces = re.findall(r"`([a-zA-Z_]+[._])\*`", ns_line.group(1)) if ns_line else []
    return names, namespaces


def main() -> int:
    text = SPEC.read_text(encoding="utf-8")
    reserved, namespaces = parse_reserved(text)
    if not reserved or not namespaces:
        sys.stderr.write("parsed an empty reserved set or namespace list; refusing to pass.\n")
        return 1

    written = {m.split(".", 1)[0] for m in WRITTEN_RE.findall(text)}

    stale_exclusions: list[str] = []
    for key, (_reason, predicate) in EXCLUSIONS.items():
        if key not in written:
            stale_exclusions.append(
                f"{key}: excluded, but no mapping writes it any more; drop the exclusion"
            )
        elif not predicate(reserved, text):
            stale_exclusions.append(
                f"{key}: excluded on a premise that no longer holds; re-check the reason"
            )

    uncovered = sorted(
        key
        for key in written
        if key not in reserved
        and key not in EXCLUSIONS
        and not any(key.startswith(ns) for ns in namespaces)
    )

    if uncovered or stale_exclusions:
        for key in uncovered:
            sys.stderr.write(
                f"{SPEC.name}: `{key}` is written at the top level of a backend "
                f"metadata object but is neither in §3.4's reserved set nor "
                f"covered by a reserved namespace.\n"
            )
        for problem in stale_exclusions:
            sys.stderr.write(f"{SPEC.name}: exclusion {problem}.\n")
        if uncovered:
            sys.stderr.write(
                "\nFix by adding the name to §3.4's reserved set, per its own "
                "maintenance rule, or by covering it with a reserved namespace. "
                "A caller could otherwise supply that key and shadow an "
                "OA-emitted field.\n"
            )
        return 1

    print(
        f"reserved-metadata coverage holds ({len(written)} written keys checked "
        f"against {len(reserved)} reserved names and {len(namespaces)} namespaces)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
