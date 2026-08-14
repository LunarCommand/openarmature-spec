#!/usr/bin/env python3
"""Shared loader for implementation conformance manifests.

Two docs-regeneration scripts read the same published manifests, one per
OpenArmature implementation, so the URL registry and the fetch live here
rather than in either caller:

  regenerate_proposals_impl_tracking.py  -> docs/proposals.md impl columns
  regenerate_impl_dependencies.py        -> docs/compatibility.md impl block

Registering a new implementation is a single entry in MANIFEST_URLS.
"""

from __future__ import annotations

import tomllib
import urllib.request

# Stable raw URLs, read at docs-regeneration time. Each implementation
# publishes its manifest at the repository root of its default branch.
MANIFEST_URLS = {
    "python": "https://raw.githubusercontent.com/LunarCommand/openarmature-python/main/conformance.toml",
}


def fetch_manifest(implementation: str, offline_path: str | None = None) -> dict:
    """Load one implementation's conformance manifest as a dict.

    ``offline_path`` reads a local TOML file instead of fetching the published
    URL, used by the callers' ``--offline-*`` flags for testing and air-gapped
    builds.
    """
    if offline_path:
        with open(offline_path, "rb") as f:
            return tomllib.load(f)
    url = MANIFEST_URLS[implementation]
    with urllib.request.urlopen(url) as resp:
        return tomllib.loads(resp.read().decode("utf-8"))


def implementation_label(implementation: str, manifest: dict) -> str:
    """The name to render for an implementation.

    Prefers the manifest's own ``[manifest] implementation`` declaration so the
    page reflects what the implementation calls itself; falls back to the
    registry key when a manifest omits it.
    """
    declared = manifest.get("manifest", {}).get("implementation")
    return declared or f"openarmature-{implementation}"
