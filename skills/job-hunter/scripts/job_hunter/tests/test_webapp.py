"""Tests for the local FastAPI webapp.

Cover the routes that matter: list, filter, sort, detail render, stage
transition, notes update, flag set/clear, field edit, metrics JSON, and
language toggle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from job_hunter.db import get_engine
from job_hunter.models import Application, Job, Stage
from job_hunter.paths import resolve
from job_hunter.webapp.app import create_app
from job_hunter.webapp.i18n import t


@pytest.fixture
def client(job_hunter_home: Path) -> TestClient:
    paths = resolve()
    app = create_app(paths)
    return TestClient(app)


def _insert_job(
    paths_obj: object,
    *,
    title: str,
    company: str,
    source: str = "remoteok",
    location: str | None = "Remote",
    salary_min: int | None = None,
    salary_max: int | None = None,
    currency: str | None = "USD",
    description: str | None = None,
    stage: Stage = Stage.DISCOVERED,
    posted_at: datetime | None = None,
    tags: list[str] | None = None,
) -> int:
    import json as _json

    paths = resolve()
    eng = get_engine(paths)
    with Session(eng) as s:
        now = datetime.now(UTC)
        job = Job(
            source=source,
            external_id=f"{source}-{title}-{company}",
            url=f"https://example.test/{source}/{title.replace(' ', '-')}",
            title=title,
            company=company,
            location=location,
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            description=description,
            scraped_at=now,
            posted_at=posted_at or now,
            fingerprint=f"{source}-{title}",
            tags=_json.dumps(tags) if tags else None,
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        s.add(
            Application(
                job_id=job.id or 0,
                current_stage=stage.value,
                updated_at=now,
                applied_at=now if stage == Stage.APPLIED else None,
            )
        )
        s.commit()
        assert job.id is not None
        return job.id


# ─── basic render ────────────────────────────────────────────────────────────


def test_root_redirects_to_jobs(client: TestClient) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/jobs"


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_empty_joblist_renders(client: TestClient) -> None:
    r = client.get("/jobs")
    assert r.status_code == 200
    assert t("en", "job.no_results") in r.text


def test_joblist_shows_inserted_job(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Senior Android Engineer", company="Acme")
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "Senior Android Engineer" in r.text
    assert "Acme" in r.text


# ─── filters + sort ─────────────────────────────────────────────────────────


def test_filter_by_source(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Role A", company="A", source="remoteok")
    _insert_job(job_hunter_home, title="Role B", company="B", source="linkedin")
    r = client.get("/jobs", params={"source": "linkedin"})
    assert "Role B" in r.text
    assert "Role A" not in r.text


def test_filter_by_stage(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Queued role", company="Q", stage=Stage.QUEUED)
    _insert_job(job_hunter_home, title="Applied role", company="X", stage=Stage.APPLIED)
    r = client.get("/jobs", params={"stage": "applied"})
    assert "Applied role" in r.text
    assert "Queued role" not in r.text


def test_search_filter_matches_title_and_company(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Kotlin Lead", company="Foo")
    _insert_job(job_hunter_home, title="iOS Senior", company="Acme")
    r = client.get("/jobs", params={"q": "kotlin"})
    assert "Kotlin Lead" in r.text
    assert "iOS Senior" not in r.text


def test_sort_by_salary_top_value(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Cheap", company="A", salary_max=80_000)
    _insert_job(job_hunter_home, title="Pricey", company="B", salary_max=240_000)
    r = client.get("/jobs", params={"sort": "salary"})
    assert r.text.find("Pricey") < r.text.find("Cheap")


# ─── stage transitions + history ────────────────────────────────────────────


def test_update_stage_writes_history_and_marks_applied(
    client: TestClient, job_hunter_home: Path
) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y", stage=Stage.QUEUED)
    r = client.post(
        f"/jobs/{jid}/stage",
        data={"stage": "applied", "note": "submitted on company site"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    paths = resolve()
    eng = get_engine(paths)
    with Session(eng) as s:
        from sqlmodel import select

        from job_hunter.models import StageHistory

        rows = s.exec(select(Application).where(Application.job_id == jid)).all()
        assert rows[0].current_stage == "applied"
        assert rows[0].applied_at is not None
        hist = s.exec(select(StageHistory)).all()
        assert any(h.to_stage == "applied" and h.note for h in hist)


def test_invalid_stage_400(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y")
    r = client.post(f"/jobs/{jid}/stage", data={"stage": "not_a_real_stage"})
    assert r.status_code == 400


# ─── flag and clear ─────────────────────────────────────────────────────────


def test_flag_then_clear(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y")
    client.post(
        f"/jobs/{jid}/flag",
        data={"flag": "broken", "reason": "404 on apply page"},
        follow_redirects=False,
    )
    eng = get_engine(resolve())
    with Session(eng) as s:
        from sqlmodel import select

        app = s.exec(select(Application).where(Application.job_id == jid)).one()
        assert app.flag == "broken"
        assert app.flag_reason == "404 on apply page"
        assert app.flag_at is not None

    client.post(f"/jobs/{jid}/flag", data={"flag": "clear"}, follow_redirects=False)
    with Session(eng) as s:
        from sqlmodel import select

        app = s.exec(select(Application).where(Application.job_id == jid)).one()
        assert app.flag is None
        assert app.flag_reason is None


def test_flag_invalid_value_rejected(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y")
    r = client.post(f"/jobs/{jid}/flag", data={"flag": "lol"})
    assert r.status_code == 400


# ─── notes ──────────────────────────────────────────────────────────────────


def test_notes_update_htmx(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y")
    r = client.post(
        f"/jobs/{jid}/notes",
        data={"notes": "recruiter mentioned 4-stage loop"},
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    eng = get_engine(resolve())
    with Session(eng) as s:
        from sqlmodel import select

        app = s.exec(select(Application).where(Application.job_id == jid)).one()
        assert app.notes == "recruiter mentioned 4-stage loop"


# ─── field edit (job table) ─────────────────────────────────────────────────


def test_edit_fields(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y", salary_min=None, salary_max=None)
    client.post(
        f"/jobs/{jid}/fields",
        data={
            "location": "São Paulo / Remote",
            "salary_min": "180000",
            "salary_max": "220000",
            "currency": "brl",
            "remote": "yes",
        },
        follow_redirects=False,
    )
    eng = get_engine(resolve())
    with Session(eng) as s:
        from sqlmodel import select

        job = s.exec(select(Job).where(Job.id == jid)).one()
        assert job.salary_min == 180000
        assert job.salary_max == 220000
        assert job.currency == "BRL"
        assert job.remote is True
        assert job.location == "São Paulo / Remote"


# ─── apply redirect ─────────────────────────────────────────────────────────


def test_apply_redirect_marks_applied_when_mark_1(
    client: TestClient, job_hunter_home: Path
) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y", stage=Stage.QUEUED)
    r = client.get(f"/jobs/{jid}/apply", params={"mark": 1}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("https://example.test/")
    eng = get_engine(resolve())
    with Session(eng) as s:
        from sqlmodel import select

        app = s.exec(select(Application).where(Application.job_id == jid)).one()
        assert app.current_stage == "applied"


def test_apply_redirect_without_mark_does_not_advance(
    client: TestClient, job_hunter_home: Path
) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y", stage=Stage.QUEUED)
    client.get(f"/jobs/{jid}/apply", follow_redirects=False)
    eng = get_engine(resolve())
    with Session(eng) as s:
        from sqlmodel import select

        app = s.exec(select(Application).where(Application.job_id == jid)).one()
        assert app.current_stage == "queued"


# ─── metrics JSON ───────────────────────────────────────────────────────────


def test_metrics_json_shape(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="A", company="X", stage=Stage.APPLIED)
    _insert_job(job_hunter_home, title="B", company="Y", stage=Stage.QUEUED)
    r = client.get("/api/metrics.json")
    body = r.json()
    assert set(body.keys()) >= {"daily", "weekly", "by_stage", "by_source", "totals"}
    assert len(body["daily"]["labels"]) == 30
    assert len(body["weekly"]["labels"]) == 12
    assert body["totals"]["jobs"] == 2
    assert body["totals"]["applied"] == 1


# ─── i18n toggle ────────────────────────────────────────────────────────────


def test_language_toggle_sets_cookie(client: TestClient) -> None:
    r = client.post("/lang", data={"lang": "pt_BR", "next": "/jobs"}, follow_redirects=False)
    assert r.status_code == 303
    assert "lang=pt_BR" in r.headers.get("set-cookie", "")


def test_language_pt_br_renders_translation(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Senior Android", company="Acme")
    client.cookies.set("lang", "pt_BR")
    r = client.get("/jobs")
    assert t("pt_BR", "filter.search") in r.text
    assert t("pt_BR", "sort.match") in r.text


# ─── detail page ────────────────────────────────────────────────────────────


def test_detail_renders_with_score_and_history(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(
        job_hunter_home,
        title="Senior Android Engineer",
        company="Acme",
        description="Looking for a senior Android engineer with KMP experience.",
    )
    r = client.get(f"/jobs/{jid}")
    assert r.status_code == 200
    assert "Senior Android Engineer" in r.text
    # Score block should appear (we don't pin a value — heuristic).
    assert "Match" in r.text or "Aderência" in r.text


def test_detail_404(client: TestClient) -> None:
    r = client.get("/jobs/99999")
    assert r.status_code == 404


# ─── htmx partial swap ─────────────────────────────────────────────────────


def test_htmx_request_returns_partial(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="X", company="Y")
    r = client.get("/jobs", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<header" not in r.text  # no base layout
    assert 'id="joblist"' in r.text


# ─── tags ───────────────────────────────────────────────────────────────────


def test_filter_by_single_tag(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="KMP Role", company="Alpha", tags=["kotlin", "android"])
    _insert_job(job_hunter_home, title="Django Role", company="Beta", tags=["python", "django"])
    r = client.get("/jobs", params={"tag": "kotlin"})
    body = r.text[r.text.find('id="joblist"') :]
    assert "KMP Role" in body
    assert "Django Role" not in body


def test_filter_by_multiple_tags_is_and(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(
        job_hunter_home, title="Lead Android", company="Acme", tags=["kotlin", "android", "senior"]
    )
    _insert_job(job_hunter_home, title="Lead Backend", company="Bork", tags=["kotlin", "backend"])
    r = client.get("/jobs", params=[("tag", "kotlin"), ("tag", "android")])
    body = r.text[r.text.find('id="joblist"') :]
    assert "Lead Android" in body
    assert "Lead Backend" not in body


def test_tags_render_as_chips_on_detail(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y", tags=["compose", "kmp", "senior"])
    r = client.get(f"/jobs/{jid}")
    assert r.status_code == 200
    for tag in ("compose", "kmp", "senior"):
        assert tag in r.text


def test_claude_command_buttons_render(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y")
    r = client.get(f"/jobs/{jid}")
    assert f"/job-hunter:apply {jid}" in r.text
    assert f"/job-hunter:dig {jid}" in r.text
    assert f"/job-hunter:tailor-resume {jid}" in r.text


def test_top_tags_shown_on_listing(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="A", company="X", tags=["kotlin", "android"])
    _insert_job(job_hunter_home, title="B", company="Y", tags=["kotlin"])
    r = client.get("/jobs")
    # The top-tags row should mention "kotlin" outside the table.
    assert r.text.count("kotlin") >= 2


# ─── markdown description renderer ─────────────────────────────────────────


def test_description_html_input_renders_to_clean_html(
    client: TestClient, job_hunter_home: Path
) -> None:
    """HTML descriptions are normalized to markdown, then rendered as bounded HTML."""
    raw = (
        "<p><strong>About:</strong> remote senior role.</p>"
        "<ul><li>Kotlin</li><li>Compose</li></ul>"
        "<script>alert('x')</script>"
        '<a href="https://example.com">apply here</a>'
    )
    jid = _insert_job(job_hunter_home, title="X", company="Y", description=raw)
    r = client.get(f"/jobs/{jid}")
    body = r.text
    # Isolate the description block so tailwind/htmx CDN scripts don't pollute.
    start = body.find('class="jh-prose')
    assert start != -1, "description container not rendered"
    end = body.find("</div>", start)
    block = body[start:end]
    assert "<ul>" in block
    assert "Kotlin" in block
    assert "<strong>" in block
    assert "https://example.com" in block
    # Source-supplied <script> tags must be sanitized out of the description.
    assert "<script>" not in block
    assert "alert('x')" not in block


def test_description_markdown_input_renders(client: TestClient, job_hunter_home: Path) -> None:
    """Already-markdown input renders straight through markdown-it."""
    raw = "## Stack\n\n- Kotlin\n- KMP\n\n**Senior** role."
    jid = _insert_job(job_hunter_home, title="X", company="Y", description=raw)
    r = client.get(f"/jobs/{jid}")
    body = r.text
    start = body.find('class="jh-prose')
    end = body.find("</div>", start)
    block = body[start:end]
    assert "<h2>" in block and "Stack" in block
    assert "<ul>" in block
    assert "<strong>Senior</strong>" in block


def test_description_empty_renders_nothing(client: TestClient, job_hunter_home: Path) -> None:
    jid = _insert_job(job_hunter_home, title="X", company="Y", description=None)
    r = client.get(f"/jobs/{jid}")
    # No description block at all — the heading isn't rendered.
    assert ">Description<" not in r.text and "Descrição" not in r.text


# ─── currency selector + conversion ─────────────────────────────────────────


def test_set_currency_cookie(client: TestClient) -> None:
    r = client.post("/currency", data={"currency": "USD", "next": "/jobs"}, follow_redirects=False)
    assert r.status_code == 303
    assert "currency=USD" in r.headers.get("set-cookie", "")


def test_set_currency_invalid_falls_back_to_default(client: TestClient) -> None:
    r = client.post("/currency", data={"currency": "JPY", "next": "/jobs"}, follow_redirects=False)
    assert "currency=BRL" in r.headers.get("set-cookie", "")  # DEFAULT


def test_currency_column_header_reflects_cookie(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="X", company="Y", salary_min=100000, currency="USD")
    client.cookies.set("currency", "BRL")
    r = client.get("/jobs")
    assert "≈ BRL" in r.text


def test_salary_uses_currency_symbol(client: TestClient, job_hunter_home: Path) -> None:
    """The native salary column shows the source-currency symbol (R$, $, €)."""
    _insert_job(job_hunter_home, title="Local", company="X", salary_min=120000, currency="BRL")
    _insert_job(job_hunter_home, title="Remote", company="Y", salary_min=80000, currency="USD")
    r = client.get("/jobs")
    assert "R$ 120,000" in r.text
    assert "$ 80,000" in r.text


def test_converted_column_renders_with_mocked_rates(
    client: TestClient, job_hunter_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With fixed rates, a 100k USD posting converts to a deterministic BRL value."""
    from job_hunter.webapp import fx

    fixed = fx.Rates(
        base="EUR",
        fetched_at=datetime.now(UTC),
        rates={"EUR": 1.0, "USD": 1.07, "BRL": 5.5},
    )
    monkeypatch.setattr(fx, "load_rates", lambda *a, **kw: fixed)

    _insert_job(job_hunter_home, title="X", company="Y", salary_min=100000, currency="USD")
    client.cookies.set("currency", "BRL")
    r = client.get("/jobs")
    # 100,000 USD / 1.07 * 5.5 ≈ 514,019. Allow a 2-digit fuzz on the conversion.
    assert "≈ R$" in r.text
    assert "514,01" in r.text or "514,02" in r.text


def test_set_salary_period_cookie(client: TestClient) -> None:
    r = client.post(
        "/salary-period", data={"period": "hour", "next": "/jobs"}, follow_redirects=False
    )
    assert r.status_code == 303
    assert "salary_period=hour" in r.headers.get("set-cookie", "")


def test_set_salary_period_invalid_falls_back_to_default(client: TestClient) -> None:
    r = client.post(
        "/salary-period", data={"period": "decade", "next": "/jobs"}, follow_redirects=False
    )
    assert "salary_period=year" in r.headers.get("set-cookie", "")  # DEFAULT_DISPLAY


def test_salary_renders_with_period_suffix(client: TestClient, job_hunter_home: Path) -> None:
    """Annual salary renders /yr by default; switching cookie to hour converts + relabels."""
    import json as _json

    from job_hunter.db import get_engine
    from job_hunter.models import Job
    from job_hunter.paths import resolve

    paths = resolve()
    eng = get_engine(paths)
    # Insert directly so we can set salary_period (the helper doesn't accept it yet).
    from datetime import UTC, datetime

    with Session(eng) as s:
        now = datetime.now(UTC)
        job = Job(
            source="remoteok",
            external_id="t1",
            url="https://example.test/t1",
            title="Annual Role",
            company="Acme",
            salary_min=104000,
            salary_max=None,
            currency="USD",
            salary_period="year",
            scraped_at=now,
            posted_at=now,
            fingerprint="t1",
            tags=_json.dumps(["test"]),
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        from job_hunter.models import Application, Stage

        s.add(
            Application(
                job_id=job.id or 0,
                current_stage=Stage.DISCOVERED.value,
                updated_at=now,
            )
        )
        s.commit()

    # Default = year. Salary renders with /yr suffix at full amount.
    r = client.get("/jobs")
    assert "$ 104,000/yr" in r.text

    # Switch to hourly. 104_000 / 2080 = 50.
    client.cookies.set("salary_period", "hour")
    r = client.get("/jobs")
    assert "$ 50/hr" in r.text


def test_tracker_filters_by_tag(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(
        job_hunter_home,
        title="KMP Role",
        company="Alpha",
        tags=["kotlin", "android"],
        stage=Stage.QUEUED,
    )
    _insert_job(
        job_hunter_home,
        title="Django Role",
        company="Beta",
        tags=["python", "django"],
        stage=Stage.QUEUED,
    )
    r = client.get("/tracker", params={"tag": "kotlin"})
    assert r.status_code == 200
    body = r.text
    # The kanban shows only the kotlin-tagged card.
    assert "KMP Role" in body
    assert "Django Role" not in body
    # Chip palette includes both top tags (built from full corpus).
    assert "python" in body and "kotlin" in body


def test_tracker_search_q_filter(client: TestClient, job_hunter_home: Path) -> None:
    _insert_job(job_hunter_home, title="Senior Android Lead", company="Alpha")
    _insert_job(job_hunter_home, title="Backend Go", company="Beta")
    r = client.get("/tracker", params={"q": "android"})
    body = r.text
    assert "Senior Android Lead" in body
    assert "Backend Go" not in body


def test_converted_column_dash_when_same_currency(
    client: TestClient, job_hunter_home: Path
) -> None:
    _insert_job(job_hunter_home, title="X", company="Y", salary_min=120000, currency="BRL")
    client.cookies.set("currency", "BRL")
    r = client.get("/jobs")
    body = r.text[r.text.find('id="joblist"') :]
    # Same-currency row should not render an "≈ R$ …" segment in its row.
    # We check the *row*, not the header label.
    row_start = body.find("R$ 120,000")
    row_end = body.find("</tr>", row_start)
    row = body[row_start:row_end]
    assert "≈ R$" not in row
