#!/usr/bin/env python3
"""Validate that every conformance fixture YAML parses.

Prevents regressions like spec v0.3.0's fixture 013, which shipped with a
flow/block grammar mix that PyYAML and libyaml both reject. Run locally or
in CI; exits non-zero if any fixture fails to parse.

Usage: python scripts/validate_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    fixtures = sorted(ROOT.glob("spec/*/conformance/*.yaml"))
    if not fixtures:
        print(f"no fixtures found under {ROOT / 'spec'}/*/conformance/", file=sys.stderr)
        return 1

    failures: list[tuple[Path, str]] = []
    for path in fixtures:
        try:
            with path.open() as f:
                yaml.safe_load(f)
            print(f"ok   {path.relative_to(ROOT)}")
        except yaml.YAMLError as e:
            print(f"FAIL {path.relative_to(ROOT)}: {e}", file=sys.stderr)
            failures.append((path, str(e)))

    if failures:
        print(f"\n{len(failures)} fixture(s) failed to parse", file=sys.stderr)
        return 1
    print(f"\nall {len(fixtures)} fixtures parse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
