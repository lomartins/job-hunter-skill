#!/usr/bin/env python3
"""Lightweight schema check for .claude-plugin/marketplace.json.

We don't pull in jsonschema as a runtime dep yet; this script enforces the
fields the Claude Code plugin marketplace cares about. Replace with a real
JSON Schema check once the marketplace publishes one.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_TOP = {"name", "owner", "plugins"}
REQUIRED_PLUGIN = {"name", "source", "description", "version"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")


def fail(msg: str) -> None:
    print(f"marketplace.json: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    path = Path(".claude-plugin/marketplace.json")
    if not path.exists():
        fail(f"missing: {path}")

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {exc}")

    missing = REQUIRED_TOP - data.keys()
    if missing:
        fail(f"missing top-level keys: {sorted(missing)}")

    plugins = data["plugins"]
    if not isinstance(plugins, list) or not plugins:
        fail("plugins must be a non-empty list")

    seen_names: set[str] = set()
    for i, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            fail(f"plugins[{i}] must be an object")
        miss = REQUIRED_PLUGIN - plugin.keys()
        if miss:
            fail(f"plugins[{i}] missing: {sorted(miss)}")
        name = plugin["name"]
        if name in seen_names:
            fail(f"duplicate plugin name: {name}")
        seen_names.add(name)
        if not SEMVER.match(str(plugin["version"])):
            fail(f"plugins[{i}].version {plugin['version']!r} is not SemVer")
        src = Path(plugin["source"])
        if not src.exists():
            fail(f"plugins[{i}].source {src} does not exist on disk")
        skill = src / "SKILL.md"
        if not skill.exists():
            fail(f"plugins[{i}].source missing SKILL.md at {skill}")

    print(
        f"OK: marketplace.json describes {len(plugins)} plugin(s) — "
        "versions valid, sources resolve"
    )


if __name__ == "__main__":
    main()
