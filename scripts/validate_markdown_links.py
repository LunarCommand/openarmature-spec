#!/usr/bin/env python3
"""Validate that internal links in markdown files resolve.

Catches broken cross-references between charter, proposals, specs, and
fixture descriptions. External links (http://, https://, mailto:, ftp:)
are skipped — they would flake CI on rate limits or transient outages.
Run locally or in CI.

Checks per link:
- Relative file paths exist (resolved against the linking file's directory).
- `#anchor` fragments correspond to a heading in the target .md file (or
  in the linking file itself for bare-anchor links like `(#section)`).

Heading-to-anchor slugification follows GitHub's rule for ASCII content:
lowercase, drop characters not in [a-z0-9_-] or whitespace, replace
whitespace with single hyphens. Duplicate-heading suffixes (`-1`, `-2`)
are not handled — the spec avoids duplicate headings.

Usage: python scripts/validate_markdown_links.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<url>[^)]+)\)")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "git://", "ssh://")


def slugify(heading: str) -> str:
    s = heading.lower().strip()
    s = re.sub(r"[^\w\- ]", "", s, flags=re.ASCII)
    s = re.sub(r"\s+", "-", s)
    return s


def heading_anchors(md_text: str) -> set[str]:
    body = FENCED_CODE_RE.sub("", md_text)
    return {slugify(m.group("text")) for m in HEADING_RE.finditer(body)}


def extract_links(md_text: str) -> list[str]:
    body = FENCED_CODE_RE.sub("", md_text)
    body = INLINE_CODE_RE.sub("", body)
    out: list[str] = []
    for m in LINK_RE.finditer(body):
        url = m.group("url").strip()
        # Markdown allows a title after the URL: `(url "title")`. Take only
        # the URL part (everything before the first whitespace).
        url = url.split()[0] if url else ""
        if url:
            out.append(url)
    return out


def is_external(url: str) -> bool:
    return url.startswith(EXTERNAL_PREFIXES)


def main() -> int:
    md_files = [p for p in sorted(ROOT.rglob("*.md")) if ".git" not in p.parts]
    if not md_files:
        print(f"no markdown files found under {ROOT}", file=sys.stderr)
        return 1

    failures: list[tuple[Path, str, str]] = []
    for src in md_files:
        text = src.read_text()
        for url in extract_links(text):
            if is_external(url):
                continue
            path_part, _, anchor = url.partition("#")
            if path_part:
                target = (src.parent / path_part).resolve()
                if not target.exists():
                    failures.append(
                        (src, url, f"target does not exist: {target.relative_to(ROOT) if ROOT in target.parents else target}")
                    )
                    continue
            else:
                target = src
            if anchor and target.suffix == ".md":
                anchors = heading_anchors(target.read_text())
                if anchor not in anchors:
                    rel = target.relative_to(ROOT) if ROOT in target.parents or target == src else target
                    failures.append((src, url, f"anchor #{anchor} not found in {rel}"))

    for src, url, msg in failures:
        print(f"FAIL {src.relative_to(ROOT)}: {url} — {msg}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)} broken markdown link(s)", file=sys.stderr)
        return 1
    print(f"all internal markdown links resolve ({len(md_files)} files checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
