"""`job doctor` implementation. Phase 1 ships a basic stub; real checks land in phase 2.

The full check list will validate:
- Python version, uv installation
- Playwright Chromium revision
- XDG dirs present with correct perms (secrets file chmod 600)
- gh auth status (for `adapter contribute`)
- LinkedIn cookie presence (not value)
- Browserless endpoint reachability if BROWSER_WS_ENDPOINT is set
- Marketplace.json + SKILL.md frontmatter version agreement
"""

from __future__ import annotations

import sys

from rich.console import Console

from . import __version__

console = Console()


def main() -> int:
    console.print(f"[bold]job-hunter doctor[/bold] (v{__version__}) — phase 1 stub")
    console.print("Real checks land in phase 2. See references/decisions.md.")
    console.print("[green]OK[/green]: package imports cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
