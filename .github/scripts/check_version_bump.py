#!/usr/bin/env python3
"""Fail if files under skills/job-hunter/** changed without bumping the plugin version.

Compares the base ref's `.claude-plugin/marketplace.json` plugins[0].version with
the head ref's, requiring strict SemVer increase. Allow-list via no skill changes
in the PR.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def parse_semver(v: str) -> tuple[int, int, int]:
    parts = v.split("-")[0].split(".")
    if len(parts) != 3:
        sys.exit(f"non-SemVer version: {v}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def run(*args: str) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"command failed: {' '.join(args)}\n{result.stderr}")
    return result.stdout


def main(base: str, head: str) -> None:
    run("git", "fetch", "origin", base, "--depth", "1")
    base_ref = f"origin/{base}"

    diff = run("git", "diff", "--name-only", f"{base_ref}...HEAD")
    changed = [Path(p) for p in diff.splitlines() if p]
    skill_changes = [p for p in changed if p.parts[:2] == ("skills", "job-hunter")]

    if not skill_changes:
        print("No skills/job-hunter/** changes — version bump not required.")
        return

    print(f"Detected {len(skill_changes)} change(s) under skills/job-hunter/:")
    for p in skill_changes:
        print(f"  - {p}")

    base_marketplace = run("git", "show", f"{base_ref}:.claude-plugin/marketplace.json")
    head_marketplace = Path(".claude-plugin/marketplace.json").read_text()

    base_v = json.loads(base_marketplace)["plugins"][0]["version"]
    head_v = json.loads(head_marketplace)["plugins"][0]["version"]

    if parse_semver(head_v) <= parse_semver(base_v):
        sys.exit(
            f"\nVersion not bumped: skills/job-hunter/** changed but "
            f"marketplace.json plugins[0].version is still {head_v} "
            f"(base: {base_v}). Bump to at least {base_v.split('-')[0]}+patch."
        )

    print(f"OK: version bumped {base_v} -> {head_v}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: check_version_bump.py <base-ref> [head-ref]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "HEAD")
