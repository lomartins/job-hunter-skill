"""Typer CLI entrypoint. Phase 1 ships a stub `info` command so that
`job-hunter --help` works end-to-end. Real commands land in phases 2-6.
"""

from __future__ import annotations

import typer
from rich.console import Console

from . import __version__

app = typer.Typer(
    name="job-hunter",
    help=(
        "Discover, track, and assist with senior mobile / Android / "
        "Kotlin Multiplatform job applications."
    ),
)
console = Console()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    if version:
        console.print(f"job-hunter {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@app.command()
def info() -> None:
    """Print build info. Real commands land in subsequent phases."""
    console.print(f"[bold]job-hunter[/bold] {__version__}")
    console.print("Phase 1 scaffold. CLI wiring lands in phases 2-6.")
    console.print("See `references/decisions.md` for the build plan.")


if __name__ == "__main__":
    app()
