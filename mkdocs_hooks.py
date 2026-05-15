"""MkDocs hooks for the OpenArmature spec docs build.

The capability spec files (at ``spec/<cap>/spec.md`` in the repo) and
proposal files (at ``proposals/<NNNN>-<slug>.md``) are surfaced into the
docs site via symlinks under ``docs/``. The relative paths in their
content are correct for the original repo locations but wrong for the
symlinked locations — this hook rewrites them on the fly during the
docs build so links resolve correctly in the rendered site. The repo
files themselves are not modified; the rewrites are confined to the
in-memory markdown that MkDocs processes.
"""

from __future__ import annotations


def on_page_markdown(markdown: str, page, config, files) -> str:
    src = page.file.src_path

    # Capability specs live at ``spec/<cap>/spec.md`` and reference
    # proposals via ``../../proposals/...md`` — correct from a
    # two-level-deep file but wrong from the symlinked
    # ``docs/capabilities/<cap>.md`` (one level deep), which needs
    # ``../proposals/...md`` to resolve to the symlinked proposal
    # under ``docs/proposals/``.
    if src.startswith("capabilities/"):
        markdown = markdown.replace("](../../proposals/", "](../proposals/")

    # Proposal files reference GOVERNANCE.md at the repo root via
    # ``../GOVERNANCE.md``. In the docs site, GOVERNANCE.md is
    # symlinked at ``docs/governance.md`` (lowercase per MkDocs's
    # auto-slug convention), so rewrite the link target.
    if src.startswith("proposals/"):
        markdown = markdown.replace("](../GOVERNANCE.md", "](../governance.md")

    return markdown
