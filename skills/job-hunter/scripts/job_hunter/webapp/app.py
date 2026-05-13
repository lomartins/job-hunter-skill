"""FastAPI app factory.

Binds 127.0.0.1 only. No auth. Reads the real ~/.local/share/job-hunter/jobs.db
unless `JOB_HUNTER_HOME_OVERRIDE` is set (tests). All write paths funnel through
SQLModel sessions so concurrent CLI work stays consistent.

Why a factory: tests need an isolated app with a tmp DB path bound at fixture
time. A module-level `app` would capture the path on import.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib.resources import files as pkg_files
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt
from markdownify import markdownify as html_to_markdown
from sqlmodel import Session

from ..db import get_engine, run_migrations
from ..paths import Paths, resolve
from . import i18n

_HTML_TAG_RE = re.compile(r"<[a-z!/][^>]*>", re.IGNORECASE)
_WS_RE = re.compile(r"[ \t]+")
_NEWLINES_RE = re.compile(r"\n{3,}")

# A single MarkdownIt instance is reused across renders. `zero` preset disables
# everything; we then opt in to the rules that produce structured output but
# refuse raw HTML / JS schemes. The result is always well-formed, safe HTML.
_MD = (
    MarkdownIt("zero")
    .enable(
        [
            "heading",
            "lheading",
            "paragraph",
            "list",
            "blockquote",
            "code",
            "fence",
            "hr",
            "emphasis",
            "link",
            "backticks",
            "escape",
            "newline",
            "table",
            "strikethrough",
        ]
    )
    .disable(["html_inline", "html_block"])
)


def _looks_like_html(raw: str) -> bool:
    return bool(_HTML_TAG_RE.search(raw))


def _normalize_to_markdown(raw: str) -> str:
    """Turn an HTML-bearing job description into markdown. Idempotent on plain text."""
    md = html_to_markdown(raw, heading_style="ATX", bullets="-") if _looks_like_html(raw) else raw
    md = html.unescape(md)
    md = _WS_RE.sub(" ", md)
    md = _NEWLINES_RE.sub("\n\n", md)
    return md.strip()


def _render_description_html(raw: str | None) -> str:
    """Render a job description as sanitized HTML.

    Inputs are mostly HTML from sources (RemoteOK, ATSes). We convert to
    markdown first to normalize structure (drops inline styles, classes,
    scripts), then render via markdown-it with raw HTML disabled — so the
    output is bounded to a small whitelist of structural tags.
    """
    if not raw:
        return ""
    md = _normalize_to_markdown(raw)
    if not md:
        return ""
    rendered: str = _MD.render(md)
    return rendered


def _clean_description(raw: str | None) -> str:
    """Legacy plain-text filter, kept for places that still want text only."""
    if not raw:
        return ""
    md = _normalize_to_markdown(raw)
    return _HTML_TAG_RE.sub("", md).strip()


def _templates_dir() -> Path:
    return Path(str(pkg_files("job_hunter.webapp") / "templates"))


def _current_query_pairs(current: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Convert the `current` filter dict into URL-pair form, preserving lists."""
    pairs: list[tuple[str, str]] = []
    for key, val in current.items():
        if key == "tag":
            for t in val or []:
                pairs.append(("tag", t))
        elif val not in (None, ""):
            pairs.append((key, str(val)))
    return pairs


def _tag_toggle_query(current: Mapping[str, Any], tag: str) -> str:
    """Return URL-encoded query string that toggles `tag` in the current filter set."""
    active = {t.lower() for t in (current.get("tag") or [])}
    target_tag = tag.lower()
    new_tags = (
        sorted(active - {target_tag}) if target_tag in active else sorted(active | {target_tag})
    )
    pairs = [(k, v) for k, v in _current_query_pairs(current) if k != "tag"]
    pairs.extend(("tag", t) for t in new_tags)
    return urlencode(pairs)


def _tag_clear_query(current: Mapping[str, Any]) -> str:
    pairs = [(k, v) for k, v in _current_query_pairs(current) if k != "tag"]
    return urlencode(pairs)


def _static_dir() -> Path:
    return Path(str(pkg_files("job_hunter.webapp") / "static"))


def create_app(paths: Paths | None = None) -> FastAPI:
    paths = paths or resolve()
    run_migrations(paths)

    app = FastAPI(
        title="job-hunter web",
        docs_url=None,  # no public API surface; keep the UX focused
        redoc_url=None,
    )

    templates = Jinja2Templates(directory=str(_templates_dir()))
    templates.env.globals["i18n_supported"] = i18n.SUPPORTED
    templates.env.globals["tag_toggle_query"] = _tag_toggle_query
    templates.env.globals["tag_clear_query"] = _tag_clear_query
    templates.env.filters["clean_desc"] = _clean_description
    templates.env.filters["render_desc"] = _render_description_html

    static_dir = _static_dir()
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    engine = get_engine(paths)

    @contextmanager
    def _session() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    # Stash on app.state so route handlers can pull what they need.
    app.state.paths = paths
    app.state.engine = engine
    app.state.templates = templates
    app.state.session_factory = _session

    from .routes import register

    register(app)
    return app
