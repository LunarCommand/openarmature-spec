#!/usr/bin/env python3
"""Regenerate the per-language impl-tracking columns in docs/proposals.md.

Reads each implementation's conformance manifest and rewrites the last
two columns of the proposals table per proposal. Title, Capability, and
Status are hand-curated by spec authors and are NOT touched by this
script — only the Python and TypeScript cells get rewritten.

Run modes:
  default              regenerate docs/proposals.md in place
  --check              exit 1 if docs/proposals.md would change (CI mode)
  --offline-python PATH use a local TOML file for the Python manifest
                       instead of fetching from the published URL
                       (useful for testing and air-gapped builds)

Python manifest source:
  https://raw.githubusercontent.com/LunarCommand/openarmature-python/main/conformance.toml

Schema (TOML, per the python repo's `conformance.toml` header):
  [proposals."NNNN"]
  status = "implemented" | "partial" | "textual-only" | "not-yet"
  since  = "MAJOR.MINOR.PATCH"   # absent only when status = "not-yet"
  note   = "..."                 # optional, for partial / textual-only

Cell-rendering rules:
  manifest entry status="implemented",  since=X  -> "Shipped (X)"
  manifest entry status="partial",      since=X  -> "Partial (X)"
  manifest entry status="textual-only", since=X  -> "Textual (X)"
  manifest entry status="not-yet"                -> "Pending"
  no manifest entry, proposal status="Accepted"  -> "Pending"
  no manifest entry, proposal status="Draft"     -> "—"

TypeScript column is "—" for every row (no TypeScript implementation
exists yet). When one lands, this script grows a second
`fetch_typescript_manifest` and the cell-rendering rule mirrors the
Python path.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS_DOC = ROOT / "docs" / "proposals.md"
PROPOSALS_DIR = ROOT / "proposals"

PYTHON_MANIFEST_URL = (
    "https://raw.githubusercontent.com/LunarCommand/openarmature-python/main/conformance.toml"
)

# Each impl column reserves enough width for the widest expected cell content
# ("Shipped (0.10.0)" = 16 chars; round to 17 with a trailing space).
PYTHON_CELL_WIDTH = 16
TYPESCRIPT_CELL_WIDTH = 11

ROW_PROPOSAL_RE = re.compile(r"^\| \[(?P<num>\d{4})\]\(")
STATUS_RE = re.compile(r"-\s*\*\*Status:\*\*\s*(?P<status>\w+)")


def fetch_python_manifest(offline_path: str | None) -> dict:
    if offline_path:
        with open(offline_path, "rb") as f:
            return tomllib.load(f)
    with urllib.request.urlopen(PYTHON_MANIFEST_URL) as resp:
        return tomllib.loads(resp.read().decode("utf-8"))


def proposal_status(num: str) -> str:
    """Read the Status field from proposals/NNNN-*.md frontmatter."""
    matches = list(PROPOSALS_DIR.glob(f"{num}-*.md"))
    if not matches:
        raise RuntimeError(f"no proposal file found for {num}")
    if len(matches) > 1:
        raise RuntimeError(f"multiple proposal files match {num}: {matches}")
    text = matches[0].read_text(encoding="utf-8")
    m = STATUS_RE.search(text)
    if not m:
        raise RuntimeError(f"could not find Status field in {matches[0].name}")
    return m.group("status")


def python_cell(num: str, manifest: dict, accepted: bool) -> str:
    entry = manifest.get("proposals", {}).get(num)
    if entry is None:
        return "Pending" if accepted else "—"
    status = entry["status"]
    since = entry.get("since")
    if status == "implemented":
        return f"Shipped ({since})"
    if status == "textual-only":
        return f"Textual ({since})"
    if status == "partial":
        return f"Partial ({since})"
    if status == "not-yet":
        return "Pending"
    raise RuntimeError(f"unknown manifest status {status!r} for proposal {num}")


def typescript_cell(num: str, accepted: bool) -> str:
    # No TypeScript implementation yet; every cell is "—".
    return "—"


def rewrite_row(line: str, python_value: str, typescript_value: str) -> str:
    """Rewrite the impl-tracking cells of a proposals-table row.

    Preserves the first four cells (link, title, capability, status) byte-for-byte;
    replaces whatever follows with two padded cells for Python and TypeScript.
    """
    stripped = line.rstrip("\n")
    parts = stripped.split("|")
    # Markdown row with leading "|" and trailing "|" splits to:
    #   [''  ,  ' [NNNN](...) '  ,  ' Title '  ,  ' Capability '  ,  ' Status '  ,  ...impl cells...  ,  '']
    if len(parts) < 6:
        raise RuntimeError(f"malformed proposals-table row (need at least 6 |-separated parts): {line!r}")
    base = parts[:5]  # '', link, title, capability, status
    py_cell = f" {python_value:<{PYTHON_CELL_WIDTH}}"
    ts_cell = f" {typescript_value:<{TYPESCRIPT_CELL_WIDTH}}"
    return "|".join(base + [py_cell, ts_cell, ""]) + "\n"


def regenerate(text: str, python_manifest: dict) -> str:
    out_lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        m = ROW_PROPOSAL_RE.match(raw_line)
        if not m:
            out_lines.append(raw_line)
            continue
        num = m.group("num")
        status = proposal_status(num)
        accepted = status == "Accepted"
        py = python_cell(num, python_manifest, accepted)
        ts = typescript_cell(num, accepted)
        out_lines.append(rewrite_row(raw_line, py, ts))
    return "".join(out_lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="exit 1 if docs/proposals.md would change")
    ap.add_argument("--offline-python", help="path to a local Python conformance.toml (instead of fetching the URL)")
    args = ap.parse_args()

    python_manifest = fetch_python_manifest(args.offline_python)
    original = PROPOSALS_DOC.read_text(encoding="utf-8")
    updated = regenerate(original, python_manifest)

    if args.check:
        if original != updated:
            sys.stderr.write(
                "docs/proposals.md impl-tracking columns are out of date.\n"
                "Run: python scripts/regenerate_proposals_impl_tracking.py\n"
            )
            return 1
        print("docs/proposals.md impl-tracking columns are up to date.")
        return 0

    if original != updated:
        PROPOSALS_DOC.write_text(updated, encoding="utf-8")
        print(f"updated {PROPOSALS_DOC.relative_to(ROOT)}")
    else:
        print(f"no changes to {PROPOSALS_DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
