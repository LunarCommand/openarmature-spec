#!/usr/bin/env python3
"""Check docs/compatibility.md's dates against each other.

Two invariants, both of which the page violated before this check existed:

1. A matrix row's **Last verified** column must not predate a verification
   date recorded in that row's own Notes cell. The failure mode is routine: an
   accept PR re-verifies an upstream fact, writes the date into the notes, and
   leaves the column behind, so the row contradicts itself and the column reads
   staler than the work actually done.

2. The page-level **Last refreshed** date must not predate the newest Last
   verified date in the matrix.

Only dates tied to verification wording count, so a date inside an API version
identifier (`anthropic-version: 2023-06-01`) or a model name
(`gpt-4o-2024-08-06`) does not trip the check.

Rows are recognized by table structure rather than by cell content, and a row
that does not parse into the expected number of cells is an error rather than a
skip. Silently passing over a row is the exact failure this script exists to
prevent: a skipped row is indistinguishable, in the output, from a row with
nothing wrong in it.

Exit 1 with a per-violation report, 0 when clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPATIBILITY_DOC = ROOT / "docs" / "compatibility.md"

MATRIX_HEADING = "## Compatibility matrix"
EXPECTED_CELLS = 5  # dependency, scope, upstream status, last verified, notes
NAME_CELL, LAST_VERIFIED_CELL, NOTES_CELL = 0, 3, 4

LAST_REFRESHED_RE = re.compile(r"^\*\*Last refreshed:\*\*\s*(20\d\d-\d\d-\d\d)", re.MULTILINE)
LINK_TEXT_RE = re.compile(r"\[([^\]]+)\]")
ISO_DATE_RE = re.compile(r"^20\d\d-\d\d-\d\d$")

# Rows are recognized by TABLE STRUCTURE, not by what the first cell happens to
# contain. Matching on a leading "| [" would skip any row whose dependency is
# not a markdown link, and skipping a row is indistinguishable from finding no
# problem in it, which is the failure this script exists to prevent.
TABLE_LINE_RE = re.compile(r"^\s*\|")
SEPARATOR_ROW_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$")
# Split on pipes that are not backslash-escaped; "\|" is the documented way to
# put a literal pipe in a Python-Markdown table cell.
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")

# A date counts only when verification wording introduces it. The tempered
# repetition stops at a sentence boundary (". ") so an unrelated later sentence
# in the same cell cannot be attributed to the verification, while still
# crossing version numbers like "v4.7.1", which contain periods but no space.
#
# It must NOT also exclude "|". This runs on an already-split single cell, so
# there is no cell boundary left to guard, and excluding the character makes a
# note carrying a legitimate escaped pipe between the wording and the date fail
# to match, which is a silent miss rather than the loud failure this script is
# for. Do not reinstate the exclusion.
VERIFIED_DATE_RE = re.compile(
    r"verifi\w*(?:(?!\.\s).){0,60}?(20\d\d-\d\d-\d\d)", re.IGNORECASE
)


def matrix_rows(text: str) -> list[tuple[int, list[str]]]:
    """Return (line number, cells) for every dependency row in the matrix."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == MATRIX_HEADING)
    except StopIteration:
        raise RuntimeError(
            f"{COMPATIBILITY_DOC.relative_to(ROOT)} has no '{MATRIX_HEADING}' heading"
        ) from None

    rows: list[tuple[int, list[str]]] = []
    seen_header = False
    for offset, line in enumerate(lines[start + 1 :], start=start + 2):
        if line.startswith("## "):
            break
        if not TABLE_LINE_RE.match(line) or SEPARATOR_ROW_RE.match(line):
            continue
        # Unescape after splitting, so a cell holds the text the page renders
        # rather than its source form. Leaving "\|" in place would put a stray
        # backslash into error messages and force every downstream pattern to
        # know about the escape.
        cells = [
            c.strip().replace("\\|", "|")
            for c in CELL_SPLIT_RE.split(line.strip().strip("|"))
        ]
        if not seen_header:
            # The first non-separator table line is the column header.
            seen_header = True
            continue
        if len(cells) != EXPECTED_CELLS:
            raise RuntimeError(
                f"{COMPATIBILITY_DOC.relative_to(ROOT)}:{offset}: matrix row has "
                f"{len(cells)} cells, expected {EXPECTED_CELLS}. Mis-parsing a row "
                "would hide whatever it contains, so this is an error rather than "
                "a skip. If a cell needs a literal pipe, escape it as '\\|'."
            )
        rows.append((offset, cells))

    if not rows:
        raise RuntimeError(
            f"{COMPATIBILITY_DOC.relative_to(ROOT)}: found no rows under "
            f"'{MATRIX_HEADING}'. The row pattern probably changed."
        )
    return rows


def main() -> int:
    text = COMPATIBILITY_DOC.read_text(encoding="utf-8")
    violations: list[str] = []

    refreshed_match = LAST_REFRESHED_RE.search(text)
    if not refreshed_match:
        raise RuntimeError(
            f"{COMPATIBILITY_DOC.relative_to(ROOT)}: no '**Last refreshed:** "
            "YYYY-MM-DD' line found"
        )
    refreshed = refreshed_match.group(1)

    rows = matrix_rows(text)
    newest_verified = ""

    for line_no, cells in rows:
        name_match = LINK_TEXT_RE.search(cells[NAME_CELL])
        name = name_match.group(1) if name_match else cells[NAME_CELL]
        last_verified = cells[LAST_VERIFIED_CELL]
        # Every comparison below is lexicographic, which is only meaningful for
        # ISO dates. A non-date here would otherwise compare against dates by
        # accident and misattribute this row's problem to the page header.
        if not ISO_DATE_RE.match(last_verified):
            raise RuntimeError(
                f"{COMPATIBILITY_DOC.relative_to(ROOT)}:{line_no}: {name}'s Last "
                f"verified column is {last_verified!r}, expected a YYYY-MM-DD date"
            )
        newest_verified = max(newest_verified, last_verified)

        later = sorted(
            {d for d in VERIFIED_DATE_RE.findall(cells[NOTES_CELL]) if d > last_verified}
        )
        if later:
            violations.append(
                f"  {COMPATIBILITY_DOC.relative_to(ROOT)}:{line_no}  {name}\n"
                f"    Last verified column: {last_verified}\n"
                f"    but its own notes record a verification on: {', '.join(later)}"
            )

    if newest_verified > refreshed:
        violations.append(
            f"  {COMPATIBILITY_DOC.relative_to(ROOT)}  page header\n"
            f"    Last refreshed: {refreshed}\n"
            f"    but the newest Last verified date in the matrix is: {newest_verified}"
        )

    if violations:
        sys.stderr.write("compatibility date contradictions:\n\n")
        sys.stderr.write("\n\n".join(violations) + "\n\n")
        sys.stderr.write(
            "Fix by bumping the stale date, or by correcting the note if the "
            "verification it describes did not happen.\n"
        )
        return 1

    print(f"compatibility dates are consistent ({len(rows)} matrix rows checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
