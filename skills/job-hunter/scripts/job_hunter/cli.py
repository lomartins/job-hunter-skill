"""Typer CLI entrypoint. Phase 3 adds `discover`."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from . import __version__, healthcheck, tracking_md
from .db import run_migrations, session
from .discover import load_query, run_discover
from .paths import resolve
from .sources import REGISTRY, SourceError, get_source

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
    """Print build info."""
    console.print(f"[bold]job-hunter[/bold] {__version__}")
    paths = resolve()
    console.print(f"Config: {paths.config_dir}")
    console.print(f"Data:   {paths.data_dir}")
    console.print(f"State:  {paths.state_dir}")


@app.command()
def init() -> None:
    """Idempotent setup: create XDG dirs, copy templates, run migrations.

    Safe to re-run after upgrades — it never overwrites your edits.
    """
    paths = resolve()

    hook = _locate_install_hook()
    if hook is None:
        console.print(
            "[red]install_hook.sh not found.[/red] "
            "If you installed via wheel, run the equivalent manually:"
        )
        paths.ensure()
    else:
        console.print(f"Running install hook: {hook}")
        result = subprocess.run(
            ["bash", str(hook)],
            check=False,
            text=True,
        )
        if result.returncode != 0:
            console.print("[red]install_hook.sh failed[/red]")
            raise typer.Exit(result.returncode)

    paths.ensure()
    applied = run_migrations(paths)
    if applied:
        console.print(f"Applied migrations: {', '.join(applied)}")
    else:
        console.print("Migrations: up to date.")

    rc = healthcheck.main()
    if rc != 0:
        console.print(
            "[yellow]Doctor reported failures. " "Fix them before running other commands.[/yellow]"
        )
        raise typer.Exit(rc)


@app.command()
def sync(
    no_md_sync: bool = typer.Option(False, "--no-md-sync", help="Skip markdown regeneration."),
) -> None:
    """Regenerate `tracking.md` and per-job files from the DB."""
    if no_md_sync:
        console.print("Skipping md sync (per --no-md-sync).")
        return
    paths = resolve()
    paths.ensure()
    run_migrations(paths)

    now = tracking_md.fixed_now_from_env() or datetime.now(tracking_md.DEFAULT_TZ)
    with session(paths) as sess:
        tracking_md.regenerate(paths, sess, now=now)
    console.print(f"Synced tracking.md and per-job files to {paths.tracking_dir}")


@app.command()
def discover(
    source: str = typer.Option(..., "--source", help="Source name (see REGISTRY in sources/)."),
    query_override: str | None = typer.Option(
        None, "--query", help="Comma-separated role keywords overriding profile.yaml."
    ),
    no_md_sync: bool = typer.Option(
        False, "--no-md-sync", help="Skip markdown regen until end of batch."
    ),
) -> None:
    """Discover postings from a source. Upserts jobs, creates Application rows."""
    paths = resolve()
    paths.ensure()
    run_migrations(paths)

    if source not in REGISTRY:
        console.print(f"[red]unknown source[/red]: {source}")
        console.print(f"available: {', '.join(sorted(REGISTRY))}")
        raise typer.Exit(2)

    src = get_source(source)
    query = load_query(paths)
    if query_override:
        query.roles = [tok.strip() for tok in query_override.split(",") if tok.strip()]

    # Load PII env (e.g. LINKEDIN_LI_AT) into this process. Never print contents.
    if paths.secrets_env.exists():
        load_dotenv(paths.secrets_env, override=False)

    try:
        with session(paths) as sess:
            report, new_ids = asyncio.run(run_discover(src, query, paths, sess))
    except SourceError as e:
        console.print(f"[red]source error[/red]: {e}")
        raise typer.Exit(1) from e

    console.print(
        f"[bold]{source}[/bold]: discovered={report.discovered} new={report.new} "
        f"updated={report.updated} failed={report.failed}"
    )
    if report.errors:
        for err in report.errors[:5]:
            console.print(f"  [yellow]err[/yellow] {err['where']}: {err['message']}")
        if len(report.errors) > 5:
            console.print(f"  ...and {len(report.errors) - 5} more (see run report)")

    if not no_md_sync:
        now = tracking_md.fixed_now_from_env() or datetime.now(tracking_md.DEFAULT_TZ)
        with session(paths) as sess:
            tracking_md.regenerate(paths, sess, now=now)


@app.command()
def doctor() -> None:
    """Validate install, paths, perms, deps."""
    rc = healthcheck.main()
    raise typer.Exit(rc)


@app.command()
def lint() -> None:
    """Scan runtime dirs for accidentally leaked PII patterns."""
    paths = resolve()
    targets = [paths.data_dir, paths.state_dir]
    targets = [p for p in targets if p.exists()]
    if not targets:
        console.print("[yellow]No runtime dirs to scan yet — run `job init` first.[/yellow]")
        raise typer.Exit(0)
    from . import lint_secret_leaks

    args = ["--paths", *(str(p) for p in targets), "--allow-empty"]
    rc = lint_secret_leaks.main(args)
    raise typer.Exit(rc)


def _locate_install_hook() -> Path | None:
    """Find install_hook.sh in source layout. Returns None in wheel-only installs."""
    here = Path(__file__).resolve()
    # source layout: scripts/job_hunter/cli.py -> scripts/install_hook.sh
    candidate = here.parent.parent / "install_hook.sh"
    if candidate.exists():
        return candidate
    return None


if __name__ == "__main__":
    app()
