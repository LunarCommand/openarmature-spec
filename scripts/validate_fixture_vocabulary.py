#!/usr/bin/env python3
"""Check that every assertion key a fixture writes has a definition.

conformance-adapter §5's preamble requires every key at an assertion position to
be a defined assertion directive, apart from `capture_as` labels and named
claims. This check runs on every change so that undefined keys cannot come back.

Both sides are read from the repository:

* the **defined** side is every name written at a definition site. In
  conformance-adapter §5 and §6 that is a bold code span, such as
  **`final_state: { ... }`**, or the first cell of a row in a table headed
  "Directive" whose position does not cite a directory note. An indented bold
  code span counts only when it names an `expected.` or `expected_` key,
  because an indented entry is otherwise a sub-key of the entry above it. In a
  directory's harness note, which is any of its fixtures' header comments or
  its README (§5 *Definition homes*), it is the run of code-font names that
  opens a bullet, including any `expected_*` segment of a dotted name. A note's
  names are defined only for its own directory. A name in RETIRED is never
  defined, even where a definition site still mentions it;
* the **used** side is every key directly under an `expected:` or
  `first_run_expected:` block, and every `expected_*`, `saved_record_assertions`
  or `every_save_assertions` key outside those blocks, in every fixture.

Position rules apply on top of the names:

* a name defined only in the configuration sections listed in
  CONFIGURATION_SECTIONS, and in §6, is a configuration directive. It fails
  directly under an assertion block unless the directory's note defines it;
* an `expected_*` key that §5.8's position table places "Inside `expected:`"
  fails outside an assertion block, and every other `expected_*` key fails
  inside one (§5.8: the `expected_*` assertions sit beside `expected:`);
* an assertion whose definition places it "under a `resume:` block's
  `expected:`" fails anywhere else, and one whose definition places it "in" or
  "under a call's `expected:`" fails outside a call's block: a `calls` entry,
  or a case or document that carries a `call:`. A definition's position is read
  from the definition's own text, not from its sub-entries.

A key under `expected:` whose value is a boolean is a named claim and is not
checked; neither is a `capture_as` label, an absence form, nor anything inside
`invariants:`. Sub-keys inside a directive are not checked. A bare-named
assertion whose definition states no narrower position may sit in any
assertion block, as §5.8's preamble places it.

`--self-test` checks the checker: each extraction rule against synthetic
definition text, and the used side against a synthetic fixture checked with the
real vocabulary.

Exit 1 with a per-violation report, 0 when clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "conformance-adapter" / "spec.md"

RETIRED = frozenset(
    {
        "otel_spans",
        "parent_trace",
        "contains_exactly_n_events_of_type",
        "does_not_contain_event_of_type",
        "messages_count",
        "messages_history_contains",
        "content_matches_template",
    }
)

# conformance-adapter §5's sections that define configuration directives only.
CONFIGURATION_SECTIONS = ("5.1", "5.2", "5.3", "5.4", "5.7", "5.14", "5.17")
HARNESS_SECTIONS = "6."

SCOPES = {
    "resume": re.compile(r"under a `resume:` block's `expected:`"),
    "call": re.compile(r"(?:in|under) a call's `expected:`"),
}

NAME = re.compile(r"`(expected\.)?([a-z_][a-z0-9_]*)")
EXPECTED_SEGMENT = re.compile(r"(?<![a-z0-9_])expected_[a-z0-9_]+")
BOLD_CODE = re.compile(r"\*\*(`.+?)\*\*")
NOTE_HEAD = re.compile(r"^#?\s*[-*]\s+((?:\*{0,2}`[^`]+`\*{0,2}(?:\s*(?:,|/|and|or)\s*)?)+)")
SECTION = re.compile(r"(?m)^### (\d+\.\d+) ")
ASSERTION_BLOCKS = ("expected", "first_run_expected")
CASE_LEVEL = ("saved_record_assertions", "every_save_assertions")
CLAIM_CONTAINER = "invariants"


def vocabulary_range(text: str) -> str:
    return text[text.index("## 5. Directive vocabulary") : text.index("## 7. Nondeterminism handling")]


def definition_names(text: str) -> set[str]:
    names: set[str] = set()
    table_head = None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if table_head is None:
                table_head = cells[0]
            elif table_head == "Directive" and "note" not in cells[-1]:
                names |= {name for _, name in NAME.findall(cells[0])}
            continue
        table_head = None
        indented = line.startswith(" ")
        for span in BOLD_CODE.findall(line):
            for prefix, name in NAME.findall(span):
                if indented and not prefix and not name.startswith("expected_"):
                    continue
                names.add(name)
    return names - RETIRED


def section_names(text: str) -> dict[str, set[str]]:
    parts = SECTION.split(vocabulary_range(text))
    sections = {"5": definition_names(parts[0])}
    for number, body in zip(parts[1::2], parts[2::2]):
        sections[number] = definition_names(body)
    return sections


def spec_vocabulary(text: str) -> set[str]:
    return set().union(*section_names(text).values())


def configuration_names(text: str) -> set[str]:
    sections = section_names(text)
    missing = [number for number in CONFIGURATION_SECTIONS if number not in sections]
    if missing:
        raise SystemExit(f"conformance-adapter has no section {', '.join(missing)}; update CONFIGURATION_SECTIONS")
    configuration: set[str] = set()
    other: set[str] = set()
    for number, names in sections.items():
        if number in CONFIGURATION_SECTIONS or number.startswith(HARNESS_SECTIONS):
            configuration |= names
        else:
            other |= names
    return configuration - other


def inside_block_names(text: str) -> set[str]:
    names: set[str] = set()
    table_head = None
    for line in vocabulary_range(text).splitlines():
        if not line.startswith("|"):
            table_head = None
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if table_head is None:
            table_head = cells[0]
        elif table_head == "Directive" and cells[-1].startswith("Inside `expected:`"):
            names |= {name for _, name in NAME.findall(cells[0])}
    return names


def scoped(entries: list[tuple[set[str], str]]) -> dict[str, set[str]]:
    scopes: dict[str, set[str]] = {scope: set() for scope in SCOPES}
    for names, entry_text in entries:
        for scope, phrase in SCOPES.items():
            if phrase.search(entry_text):
                scopes[scope] |= names
    return scopes


def spec_entries(text: str) -> list[tuple[set[str], str]]:
    """(names, own text) for each entry headed by a bold code span; sub-entries end the own text."""
    entries: list[tuple[set[str], list[str]]] = []
    current: list[str] | None = None
    for line in vocabulary_range(text).splitlines():
        if line.startswith("- **`") or line.startswith("**`"):
            current = [line]
            entries.append((definition_names(line), current))
        elif current is not None and line.startswith("  ") and not line.lstrip().startswith("- "):
            current.append(line.strip())
        else:
            current = None
    return [(names, " ".join(lines)) for names, lines in entries]


def note_entries(lines: list[str]) -> list[tuple[set[str], str]]:
    """(names, own text) for each bullet a note opens with code-font names."""
    entries: list[tuple[set[str], list[str]]] = []
    current: list[str] | None = None
    marker = 0
    for line in lines:
        if match := NOTE_HEAD.match(line):
            head = match.group(1)
            names = {name for _, name in NAME.findall(head)} | set(EXPECTED_SEGMENT.findall(head))
            current = [line.lstrip("#").strip()]
            entries.append((names - RETIRED, current))
            body = line.lstrip("#")
            marker = len(body) - len(body.lstrip())
            continue
        body = line.lstrip("#")
        stripped = body.strip()
        lead = len(body) - len(body.lstrip())
        continues = line.startswith("#") and stripped and lead > marker
        if current is not None and continues and not stripped.startswith(("- ", "* ")):
            current.append(stripped)
        else:
            current = None
    return [(names, " ".join(text)) for names, text in entries]


def note_names(lines: list[str]) -> set[str]:
    return set().union(*(names for names, _ in note_entries(lines)))


def header_comment(path: Path) -> list[str]:
    lines = []
    for line in path.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            lines.append(line)
        else:
            break
    return lines


def note_lines(directory: Path) -> list[str]:
    lines: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        lines += header_comment(path)
    readme = directory / "README.md"
    if readme.exists():
        lines += readme.read_text().splitlines()
    return lines


def vocabulary_for(directory: str, general: set[str], notes: dict[str, set[str]]) -> set[str]:
    return general | notes[directory]


def configuration_for(directory: str, configuration: set[str], notes: dict[str, set[str]]) -> set[str]:
    return configuration - notes[directory]


def scopes_for(
    directory: str, spec_scopes: dict[str, set[str]], note_scopes: dict[str, dict[str, set[str]]]
) -> dict[str, set[str]]:
    return {scope: spec_scopes[scope] | note_scopes[directory][scope] for scope in SCOPES}


def capture_labels(node: object) -> set[str]:
    labels: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "capture_as" and isinstance(value, str):
                labels.add(value)
            labels |= capture_labels(value)
    elif isinstance(node, list):
        for item in node:
            labels |= capture_labels(item)
    return labels


def block_kind(container: dict, path: str) -> str:
    if path.endswith("resume"):
        return "resume"
    if "call" in container or re.search(r"(?:^|\.)calls\[\d+\]$", path):
        return "call"
    return "other"


def used_keys(node: object, path: str = "", in_block: bool = False) -> list[tuple[str, str, str | None]]:
    """(key, location, kind of the assertion block it sits in, or None) for every assertion key."""
    found: list[tuple[str, str, str | None]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if not isinstance(key, str):
                continue
            here = f"{path}.{key}" if path else key
            block = key in ASSERTION_BLOCKS and isinstance(value, dict)
            if block:
                kind = "first_run" if key == "first_run_expected" else block_kind(node, path)
                for child, child_value in value.items():
                    if isinstance(child, str) and not isinstance(child_value, bool):
                        found.append((child, f"{here}.{child}", kind))
            elif not in_block and (key.startswith("expected_") or key in CASE_LEVEL):
                found.append((key, here, None))
            if key != CLAIM_CONTAINER:
                found.extend(used_keys(value, here, in_block or block))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            found.extend(used_keys(item, f"{path}[{index}]", in_block))
    return found


def is_exempt(key: str, labels: set[str]) -> bool:
    absence = key == "absent_keys" or key.endswith("_absent_keys")
    return absence or key == CLAIM_CONTAINER or key in labels


def violations(
    document: object,
    vocabulary: set[str],
    configuration: set[str],
    inside: set[str],
    scopes: dict[str, set[str]],
) -> list[tuple[str, str, str]]:
    labels = capture_labels(document)
    found: list[tuple[str, str, str]] = []
    for key, location, kind in used_keys(document):
        in_block = kind is not None
        if is_exempt(key, labels):
            continue
        if key not in vocabulary:
            found.append((key, location, "has no definition"))
        elif in_block and key in configuration:
            found.append((key, location, "is a configuration directive, not an assertion"))
        elif key.startswith("expected_") and in_block != (key in inside):
            where = "outside" if in_block else "inside"
            found.append((key, location, f"belongs {where} an assertion block (conformance-adapter §5.8)"))
        elif key in scopes["resume"] and kind != "resume":
            found.append((key, location, "belongs under a `resume:` block's `expected:`"))
        elif key in scopes["call"] and kind != "call":
            found.append((key, location, "belongs in a call's `expected:`"))
    return found


SYNTHETIC_SPEC = """## 5. Directive vocabulary
### 5.1 Node behavior directives
- **`config_only: <value>`**: a configuration directive.
- **`shared_name`**: configuration here, and an assertion in §5.8.
### 5.2 State
### 5.3 Edges
### 5.4 Composition
### 5.7 Invocation shape
### 5.8 Expected-outcome directives
- **`bold_head: <value>`**: a definition site.
- `plain_head`: not a definition site.
  - **`indented_sub`** is a sub-key of the entry above.
  - **`expected.indented_assertion`** is an assertion written with its block.
A paragraph defines **`paragraph_bold`** mid-sentence.
- **`shared_name`**: the assertion.
- **`otel_spans`** is retired.
- **`resume_only: [<int>, ...]`**:
  under a `resume:` block's `expected:`. It reads the resumed call.
- **`call_only`**: in a call's `expected:`, what the call returned.
- **`parent_entry`**: a directive whose sub-entry is call-scoped.
  - **`sub`** sits under a call's `expected:`.

| Directive | Position |
|---|---|
| `table_general` | Case level (§5.6). |
| `table_note_scoped` | Inside `expected:` (pipeline-utilities' note). |
| `expected_inside_only` | Inside `expected:` (pipeline-utilities' note). |
### 5.14 Chunk size
### 5.17 Capability gates
### 6.1 Harness primitive
- **`harness_only`**: a harness primitive.
## 7. Nondeterminism handling
"""

SYNTHETIC_NOTE = [
    "#   - `note_head`: a definition.",
    "#     * **`signal_arrivals[].expected_dotted:`** a dotted head.",
    "#   - A sentence that mentions `mid_sentence` is not a head.",
    "# - **`old_style:`** an older head style.",
    "#   - `parent_trace`: retired.",
    "#   - `note_resume`: under a `resume:` block's",
    "#     `expected:`. The phrase wraps across lines.",
    "#   - `note_other`: no position.",
    "#     * `note_nested`: in a call's `expected:`, a nested entry.",
    "#   - `note_parent`: a directive whose nested bullet is not its own text.",
    "#     * A nested bullet that says in a call's `expected:`.",
]

SYNTHETIC_FIXTURE = {
    "expected": {
        "otel_spans": [],
        "vectors_length": 3,
        "state": {"v": 1},
        "final_state": {},
        "no_spans_emitted": True,
        "absent_keys": ["x"],
        "first_prompt": {},
        "observers": {"c": {"relative_order_of_events_matching": {"expected_order": []}}},
        "expected_failure_isolation_event": {},
        "expected_compile_error": "no_declared_entry",
        "instances_executed_during_resume": [1],
        "nodes_executed_during_resume": ["a"],
        "raises": {"category": "provider_unavailable"},
    },
    "expected_attempt_events": [],
    "expected_bogus": 1,
    "expected_error": {"category": "node_exception"},
    "resume": {"expected": {"instances_executed_during_resume": [1], "nodes_executed_during_resume": ["a"]}},
    "calls": [{"capture_as": "first_prompt", "expected": {"raises": {"category": "provider_unavailable"}}}],
    "cases": [{"call": {}, "expected": {"raises": {"category": "provider_unavailable"}}}],
}

SPEC_DEFINED = {
    "config_only",
    "shared_name",
    "bold_head",
    "indented_assertion",
    "paragraph_bold",
    "table_general",
    "harness_only",
    "resume_only",
    "call_only",
    "parent_entry",
}
SPEC_CONFIGURATION = {"config_only", "harness_only"}
SPEC_INSIDE = {"table_note_scoped", "expected_inside_only"}
SPEC_SCOPES = {"resume": {"resume_only"}, "call": {"call_only"}}
NOTE_DEFINED = {
    "note_head",
    "signal_arrivals",
    "expected_dotted",
    "old_style",
    "note_resume",
    "note_other",
    "note_nested",
    "note_parent",
}
NOTE_SCOPES = {"resume": {"note_resume"}, "call": {"note_nested"}}
FIXTURE_FLAGGED = {
    "expected.otel_spans",
    "expected.vectors_length",
    "expected.state",
    "expected.expected_compile_error",
    "expected.instances_executed_during_resume",
    "expected.nodes_executed_during_resume",
    "expected.raises",
    "expected_attempt_events",
    "expected_bogus",
}
NOTE_SCOPED = ("pipeline-utilities", "graph-engine", "expected_attempt_events")


def self_test(
    general: set[str],
    configuration: set[str],
    inside: set[str],
    spec_scopes: dict[str, set[str]],
    notes: dict[str, set[str]],
    note_scopes: dict[str, dict[str, set[str]]],
) -> int:
    home, other, scoped_name = NOTE_SCOPED
    flagged = {
        location
        for _, location, _ in violations(
            SYNTHETIC_FIXTURE,
            vocabulary_for(home, general, notes),
            configuration_for(home, configuration, notes),
            inside,
            scopes_for(home, spec_scopes, note_scopes),
        )
    }
    overridden = configuration_for("d", {"config_only"}, {"d": {"config_only"}})
    checks = [
        ("spec definition sites", spec_vocabulary(SYNTHETIC_SPEC) == SPEC_DEFINED),
        ("configuration sections", configuration_names(SYNTHETIC_SPEC) == SPEC_CONFIGURATION),
        ("inside-block positions", inside_block_names(SYNTHETIC_SPEC) == SPEC_INSIDE),
        ("spec scopes", scoped(spec_entries(SYNTHETIC_SPEC)) == SPEC_SCOPES),
        ("note bullet heads", note_names(SYNTHETIC_NOTE) == NOTE_DEFINED),
        ("note scopes", scoped(note_entries(SYNTHETIC_NOTE)) == NOTE_SCOPES),
        ("used keys", flagged == FIXTURE_FLAGGED),
        ("note in its own directory", scoped_name in vocabulary_for(home, general, notes)),
        ("note outside its directory", scoped_name not in vocabulary_for(other, general, notes)),
        ("note overrides configuration", overridden == set()),
    ]
    failed = [name for name, passed in checks if not passed]
    if failed:
        print(f"self-test failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("self-test passed")
    return 0


def main() -> int:
    text = SPEC.read_text()
    general = spec_vocabulary(text)
    configuration = configuration_names(text)
    inside = inside_block_names(text)
    spec_scopes = scoped(spec_entries(text))
    directories = sorted(p for p in ROOT.glob("spec/*/conformance") if p.is_dir())
    lines = {d.parent.name: note_lines(d) for d in directories}
    notes = {name: note_names(note) for name, note in lines.items()}
    note_scopes = {name: scoped(note_entries(note)) for name, note in lines.items()}
    if "--self-test" in sys.argv[1:]:
        return self_test(general, configuration, inside, spec_scopes, notes, note_scopes)
    problems: list[str] = []
    checked = 0
    for directory in directories:
        name = directory.parent.name
        vocabulary = vocabulary_for(name, general, notes)
        local_configuration = configuration_for(name, configuration, notes)
        scopes = scopes_for(name, spec_scopes, note_scopes)
        for path in sorted(directory.glob("*.yaml")):
            document = yaml.safe_load(path.read_text())
            checked += len(used_keys(document))
            for key, location, problem in violations(document, vocabulary, local_configuration, inside, scopes):
                problems.append(f"{path.relative_to(ROOT)}: {location}: `{key}` {problem}")

    if problems:
        print("\n".join(problems), file=sys.stderr)
        print(f"\n{len(problems)} assertion key problem(s) in {checked} checked", file=sys.stderr)
        return 1
    print(f"every assertion key has a definition ({checked} keys checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
