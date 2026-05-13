"""HTTP routes for the local webapp.

HTMX-aware: routes that swap a partial check the `HX-Request` header and
render a fragment instead of the full layout.

Manual-update scope (per the spec):
  - stage transitions (with note + StageHistory entry)
  - per-job notes (free text on Application)
  - flag the job (broken / suspicious / spam / not_fit)
  - direct edits to a few Job fields (salary_min/max, location, remote)

Read-side affordances:
  - filter by stage / source / flag / search
  - sort by match / date / salary / company
  - daily + weekly application charts
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlmodel import Session, col, select

from ..models import (
    ACTIVE_STAGES,
    TERMINAL_STAGES,
    Application,
    Job,
    Stage,
    StageHistory,
)
from . import fx, i18n, salary_view
from .scoring import score_job

FLAG_VALUES = ("broken", "suspicious", "spam", "not_fit")
SORT_VALUES = ("match", "date", "salary", "company")


@dataclass(frozen=True)
class JobRow:
    job: Job
    application: Application
    match_score: int
    stage_label_key: str
    flag_label_key: str | None
    tags: tuple[str, ...]


def _parse_tags(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(str(t) for t in decoded if isinstance(t, str) and t.strip())


def _get_locale(request: Request) -> str:
    return i18n.normalize(request.cookies.get("lang"))


def _get_currency(request: Request) -> str:
    raw = (request.cookies.get("currency") or fx.DEFAULT).upper()
    return raw if raw in fx.SUPPORTED else fx.DEFAULT


def _get_salary_period(request: Request) -> str:
    raw = (request.cookies.get("salary_period") or salary_view.DEFAULT_DISPLAY).lower()
    return raw if raw in salary_view.SUPPORTED else salary_view.DEFAULT_DISPLAY


def _render(request: Request, name: str, ctx: dict[str, Any]) -> Response:
    templates = request.app.state.templates
    locale = _get_locale(request)
    currency = _get_currency(request)
    period = _get_salary_period(request)
    ctx = {
        **ctx,
        "request": request,
        "locale": locale,
        "default_currency": currency,
        "currency_symbol": fx.symbol(currency),
        "currency_supported": fx.SUPPORTED,
        "default_salary_period": period,
        "salary_period_supported": salary_view.SUPPORTED,
        "t": lambda key: i18n.t(locale, key),
        "stages": [s.value for s in Stage],
        "active_stages": [s.value for s in ACTIVE_STAGES],
        "terminal_stages": [s.value for s in TERMINAL_STAGES],
        "flag_values": FLAG_VALUES,
        "sort_values": SORT_VALUES,
    }
    response: Response = templates.TemplateResponse(request, name, ctx)
    return response


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def _load_rows(session: Session) -> list[JobRow]:
    pairs = session.exec(
        select(Job, Application).join(Application, col(Application.job_id) == col(Job.id))
    ).all()
    rows: list[JobRow] = []
    for job, app in pairs:
        score = app.match_score
        if score is None:
            score = score_job(job)
            app.match_score = score
            session.add(app)
        rows.append(
            JobRow(
                job=job,
                application=app,
                match_score=score,
                stage_label_key=f"stage.{app.current_stage}",
                flag_label_key=f"flag.{app.flag}" if app.flag else None,
                tags=_parse_tags(job.tags),
            )
        )
    session.commit()
    return rows


def _salary_top(j: Job) -> int:
    if j.salary_max is not None:
        return j.salary_max
    if j.salary_min is not None:
        return j.salary_min
    return -1


def _apply_filters(
    rows: list[JobRow],
    *,
    stage: str | None,
    source: str | None,
    flag: str | None,
    q: str | None,
    tags: list[str] | None = None,
) -> list[JobRow]:
    out = rows
    if stage:
        out = [r for r in out if r.application.current_stage == stage]
    if source:
        out = [r for r in out if r.job.source == source]
    if flag == "any":
        out = [r for r in out if r.application.flag]
    elif flag == "none":
        out = [r for r in out if not r.application.flag]
    elif flag:
        out = [r for r in out if r.application.flag == flag]
    if tags:
        wanted = {t.lower() for t in tags if t}
        out = [r for r in out if wanted.issubset({tg.lower() for tg in r.tags})]
    if q:
        needle = q.casefold()
        out = [
            r
            for r in out
            if needle in (r.job.title or "").casefold()
            or needle in (r.job.company or "").casefold()
        ]
    return out


def _apply_sort(rows: list[JobRow], sort: str) -> list[JobRow]:
    if sort == "match":
        return sorted(rows, key=lambda r: (r.match_score, _salary_top(r.job)), reverse=True)
    if sort == "salary":
        return sorted(rows, key=lambda r: _salary_top(r.job), reverse=True)
    if sort == "company":
        return sorted(rows, key=lambda r: (r.job.company or "").casefold())

    # default: date desc; scraped_at always set, posted_at may be null.
    # Normalize tz so naive (older rows) and aware datetimes sort together.
    def _date_key(r: JobRow) -> float:
        ts = r.job.posted_at or r.job.scraped_at
        if ts is None:
            return 0.0
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.timestamp()

    return sorted(rows, key=_date_key, reverse=True)


def _format_salary(j: Job, locale: str, display_period: str) -> str:
    """Format the source salary in `display_period` with its native currency prefix.

    Periods are converted using `salary_view.convert`. NULL source period is
    treated as the salary_view fallback (year), matching most tech postings.
    """
    lo, hi, cur = j.salary_min, j.salary_max, j.currency
    if lo is None and hi is None:
        return "—"
    raw_cur = (cur or "").upper().strip()
    prefix = fx.symbol(raw_cur) if raw_cur else ("R$" if locale == "pt_BR" else "$")
    src_period = salary_view.normalize(j.salary_period)
    suf = salary_view.suffix(display_period, locale=locale)

    def _conv(v: int) -> int:
        return int(round(salary_view.convert(float(v), src_period, display_period)))

    if lo is not None and hi is not None and lo != hi:
        return f"{prefix} {_conv(lo):,}–{_conv(hi):,}{suf}"
    one = hi if lo is None else lo
    assert one is not None
    return f"{prefix} {_conv(one):,}{suf}"


def _format_converted(
    j: Job,
    default_currency: str,
    rates: fx.Rates | None,
    display_period: str,
    locale: str,
) -> str:
    """Convert salary to `default_currency` AND `display_period`.

    Returns '—' when source currency equals target currency *and* source
    period equals display period — i.e. the converted column would just
    repeat the native column.
    """
    lo, hi, cur = j.salary_min, j.salary_max, j.currency
    if lo is None and hi is None:
        return "—"
    if not cur:
        return "—"
    cur = cur.upper().strip()
    src_period = salary_view.normalize(j.salary_period)
    same_currency = cur == default_currency.upper()
    same_period = src_period == display_period
    if same_currency and same_period:
        return "—"
    if not same_currency and rates is None:
        return "—"

    def _conv(v: int) -> int | None:
        # First: period in source currency. Cheap and lossless even when no FX.
        period_converted = salary_view.convert(float(v), src_period, display_period)
        if same_currency:
            return int(round(period_converted))
        out = fx.convert(period_converted, cur, default_currency, rates)
        return None if out is None else int(round(out))

    prefix = fx.symbol(default_currency)
    suf = salary_view.suffix(display_period, locale=locale)
    if lo is not None and hi is not None and lo != hi:
        lo_c = _conv(lo)
        hi_c = _conv(hi)
        if lo_c is None or hi_c is None:
            return "—"
        return f"≈ {prefix} {lo_c:,}–{hi_c:,}{suf}"
    one = hi if lo is None else lo
    assert one is not None
    one_c = _conv(one)
    if one_c is None:
        return "—"
    return f"≈ {prefix} {one_c:,}{suf}"


def _get_pair(session: Session, job_id: int) -> tuple[Job, Application]:
    pair = session.exec(
        select(Job, Application)
        .join(Application, col(Application.job_id) == col(Job.id))
        .where(Job.id == job_id)
    ).one_or_none()
    if pair is None:
        raise HTTPException(status_code=404, detail="job not found")
    return pair


def register(app: FastAPI) -> None:
    @app.get("/", response_class=HTMLResponse)
    def root(request: Request) -> Response:
        return RedirectResponse(url="/jobs", status_code=303)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/jobs", response_class=HTMLResponse)
    def jobs_list(
        request: Request,
        stage: str | None = Query(default=None),
        source: str | None = Query(default=None),
        flag: str | None = Query(default=None),
        sort: str = Query(default="match"),
        q: str | None = Query(default=None),
        tag: list[str] | None = Query(default=None),  # noqa: B008
    ) -> Response:
        if sort not in SORT_VALUES:
            sort = "match"
        with request.app.state.session_factory() as s:
            rows = _load_rows(s)
            sources = sorted({r.job.source for r in rows})
            tag_counter: Counter[str] = Counter()
            for r in rows:
                for t_ in r.tags:
                    tag_counter[t_.lower()] += 1
            top_tags = [t_ for t_, _ in tag_counter.most_common(30)]
            active_tags = [t_.lower() for t_ in (tag or []) if t_]
            filtered = _apply_filters(
                rows, stage=stage, source=source, flag=flag, q=q, tags=active_tags
            )
            sorted_rows = _apply_sort(filtered, sort)
            locale = _get_locale(request)
            default_currency = _get_currency(request)
            display_period = _get_salary_period(request)
            rates = fx.load_rates(request.app.state.paths)
            view = [
                {
                    "row": r,
                    "salary": _format_salary(r.job, locale, display_period),
                    "salary_converted": _format_converted(
                        r.job, default_currency, rates, display_period, locale
                    ),
                }
                for r in sorted_rows
            ]
            ctx = {
                "rows": view,
                "sources": sources,
                "top_tags": top_tags,
                "active_tags": active_tags,
                "current": {
                    "stage": stage or "",
                    "source": source or "",
                    "flag": flag or "",
                    "sort": sort,
                    "q": q or "",
                    "tag": active_tags,
                },
                "total": len(rows),
                "shown": len(sorted_rows),
            }
            if _is_htmx(request):
                return _render(request, "_job_table.html", ctx)
            return _render(request, "index.html", ctx)

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_detail(request: Request, job_id: int) -> Response:
        with request.app.state.session_factory() as s:
            job, application = _get_pair(s, job_id)
            history = s.exec(
                select(StageHistory)
                .where(StageHistory.application_id == application.id)
                .order_by(col(StageHistory.transitioned_at).desc())
            ).all()
            score = application.match_score
            if score is None:
                score = score_job(job)
                application.match_score = score
                s.add(application)
                s.commit()
            from ..validate import validate_fit

            report = validate_fit(job)
            locale = _get_locale(request)
            default_currency = _get_currency(request)
            display_period = _get_salary_period(request)
            rates = fx.load_rates(request.app.state.paths)
            ctx = {
                "job": job,
                "application": application,
                "history": history,
                "score": score,
                "tags": list(_parse_tags(job.tags)),
                "report": report,
                "salary": _format_salary(job, locale, display_period),
                "salary_converted": _format_converted(
                    job, default_currency, rates, display_period, locale
                ),
            }
            return _render(request, "detail.html", ctx)

    @app.post("/jobs/{job_id}/stage")
    def update_stage(
        request: Request,
        job_id: int,
        stage: str = Form(...),
        note: str = Form(default=""),
    ) -> Response:
        if stage not in {s.value for s in Stage}:
            raise HTTPException(status_code=400, detail="invalid stage")
        with request.app.state.session_factory() as s:
            _, application = _get_pair(s, job_id)
            prev = application.current_stage
            now = datetime.now(UTC)
            application.current_stage = stage
            application.updated_at = now
            if stage == Stage.APPLIED.value and application.applied_at is None:
                application.applied_at = now
            s.add(
                StageHistory(
                    application_id=application.id or 0,
                    from_stage=prev,
                    to_stage=stage,
                    transitioned_at=now,
                    note=note or None,
                )
            )
            s.add(application)
            s.commit()
        if _is_htmx(request):
            return Response(status_code=204)
        return _redirect_back(request, f"/jobs/{job_id}")

    @app.post("/jobs/{job_id}/notes")
    def update_notes(
        request: Request,
        job_id: int,
        notes: str = Form(default=""),
    ) -> Response:
        with request.app.state.session_factory() as s:
            _, application = _get_pair(s, job_id)
            application.notes = notes or None
            application.updated_at = datetime.now(UTC)
            s.add(application)
            s.commit()
        if _is_htmx(request):
            locale = _get_locale(request)
            return HTMLResponse(
                f'<span class="text-emerald-400 text-xs">{i18n.t(locale, "job.saved")}</span>'
            )
        return _redirect_back(request, f"/jobs/{job_id}")

    @app.post("/jobs/{job_id}/flag")
    def update_flag(
        request: Request,
        job_id: int,
        flag: str = Form(...),
        reason: str = Form(default=""),
    ) -> Response:
        if flag == "clear":
            new_flag: str | None = None
        elif flag in FLAG_VALUES:
            new_flag = flag
        else:
            raise HTTPException(status_code=400, detail="invalid flag")
        with request.app.state.session_factory() as s:
            _, application = _get_pair(s, job_id)
            application.flag = new_flag
            application.flag_reason = reason or None if new_flag else None
            application.flag_at = datetime.now(UTC) if new_flag else None
            application.updated_at = datetime.now(UTC)
            s.add(application)
            s.commit()
        return _redirect_back(request, f"/jobs/{job_id}")

    @app.post("/jobs/{job_id}/fields")
    def update_fields(
        request: Request,
        job_id: int,
        location: str = Form(default=""),
        salary_min: str = Form(default=""),
        salary_max: str = Form(default=""),
        currency: str = Form(default=""),
        salary_period: str = Form(default=""),
        remote: str = Form(default=""),
    ) -> Response:
        with request.app.state.session_factory() as s:
            job, application = _get_pair(s, job_id)
            job.location = location.strip() or None
            job.salary_min = _to_int(salary_min)
            job.salary_max = _to_int(salary_max)
            job.currency = currency.strip().upper() or None
            period_raw = salary_period.strip().lower()
            job.salary_period = period_raw if period_raw in salary_view.SUPPORTED else None
            if remote == "yes":
                job.remote = True
            elif remote == "no":
                job.remote = False
            else:
                job.remote = None
            # Salary or location changed -> match score may change too.
            application.match_score = score_job(job)
            application.updated_at = datetime.now(UTC)
            s.add(job)
            s.add(application)
            s.commit()
        return _redirect_back(request, f"/jobs/{job_id}")

    @app.get("/jobs/{job_id}/apply")
    def apply_redirect(
        request: Request,
        job_id: int,
        mark: int = Query(default=0),
    ) -> Response:
        """Open the posting in a new tab. If mark=1, also transition to applied."""
        with request.app.state.session_factory() as s:
            job, application = _get_pair(s, job_id)
            url = job.url
            if mark == 1 and application.current_stage != Stage.APPLIED.value:
                now = datetime.now(UTC)
                prev = application.current_stage
                application.current_stage = Stage.APPLIED.value
                application.applied_at = now
                application.updated_at = now
                s.add(
                    StageHistory(
                        application_id=application.id or 0,
                        from_stage=prev,
                        to_stage=Stage.APPLIED.value,
                        transitioned_at=now,
                        note="marked applied via webapp",
                    )
                )
                s.add(application)
                s.commit()
        return RedirectResponse(url=url, status_code=303)

    @app.get("/tracker", response_class=HTMLResponse)
    def tracker(
        request: Request,
        tag: list[str] | None = Query(default=None),  # noqa: B008
        q: str | None = Query(default=None),
    ) -> Response:
        with request.app.state.session_factory() as s:
            rows = _load_rows(s)
            # Build the chip palette from the full corpus so it stays stable
            # while the user toggles filters.
            tag_counter: Counter[str] = Counter()
            for r in rows:
                for t_ in r.tags:
                    tag_counter[t_.lower()] += 1
            top_tags = [t_ for t_, _ in tag_counter.most_common(30)]
            active_tags = [t_.lower() for t_ in (tag or []) if t_]
            filtered = _apply_filters(
                rows, stage=None, source=None, flag=None, q=q, tags=active_tags
            )

            by_stage: dict[str, list[JobRow]] = defaultdict(list)
            for r in filtered:
                by_stage[r.application.current_stage].append(r)

            def _sort_key(r: JobRow) -> float:
                ts = r.application.updated_at
                if ts is None:
                    return 0.0
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                return ts.timestamp()

            for lst in by_stage.values():
                lst.sort(key=_sort_key, reverse=True)
            ordered = [
                (s_value, by_stage.get(s_value, []))
                for s_value in (
                    Stage.DISCOVERED.value,
                    Stage.QUEUED.value,
                    Stage.APPLYING.value,
                    Stage.APPLYING_BLOCKED_AUTH.value,
                    Stage.APPLIED.value,
                    Stage.SCREENING.value,
                    Stage.TECHNICAL.value,
                    Stage.BEHAVIORAL.value,
                    Stage.OFFER.value,
                    Stage.REJECTED.value,
                    Stage.WITHDRAWN.value,
                )
            ]
            ctx = {
                "columns": ordered,
                "top_tags": top_tags,
                "active_tags": active_tags,
                "current": {"tag": active_tags, "q": q or ""},
                "total": len(rows),
                "shown": len(filtered),
            }
            return _render(request, "tracker.html", ctx)

    @app.get("/metrics", response_class=HTMLResponse)
    def metrics(request: Request) -> Response:
        return _render(request, "metrics.html", {})

    @app.get("/api/metrics.json")
    def metrics_json(request: Request) -> JSONResponse:
        with request.app.state.session_factory() as s:
            rows = _load_rows(s)
            today = date.today()
            day_keys = [today - timedelta(days=i) for i in range(29, -1, -1)]
            by_day = Counter[date]()
            for r in rows:
                if r.application.applied_at:
                    by_day[r.application.applied_at.date()] += 1
            daily = {
                "labels": [d.isoformat() for d in day_keys],
                "values": [by_day.get(d, 0) for d in day_keys],
            }

            week_keys: list[date] = []
            monday = today - timedelta(days=today.weekday())
            for i in range(11, -1, -1):
                week_keys.append(monday - timedelta(weeks=i))
            by_week = Counter[date]()
            for d, n in by_day.items():
                wk = d - timedelta(days=d.weekday())
                by_week[wk] += n
            weekly = {
                "labels": [d.isoformat() for d in week_keys],
                "values": [by_week.get(d, 0) for d in week_keys],
            }

            by_stage = Counter[str]()
            by_source = Counter[str]()
            flagged = 0
            applied = 0
            in_pipe = 0
            for r in rows:
                st = r.application.current_stage
                by_stage[st] += 1
                by_source[r.job.source] += 1
                if r.application.flag:
                    flagged += 1
                if st == Stage.APPLIED.value:
                    applied += 1
                if st in {s.value for s in ACTIVE_STAGES}:
                    in_pipe += 1
            return JSONResponse(
                {
                    "daily": daily,
                    "weekly": weekly,
                    "by_stage": dict(by_stage),
                    "by_source": dict(by_source),
                    "totals": {
                        "jobs": len(rows),
                        "applied": applied,
                        "in_pipeline": in_pipe,
                        "flagged": flagged,
                    },
                }
            )

    @app.post("/lang")
    def set_lang(
        request: Request,
        lang: str = Form(...),
        next: str = Form(default="/jobs"),
    ) -> Response:
        target = next if next.startswith("/") else "/jobs"
        resp = RedirectResponse(url=target, status_code=303)
        resp.set_cookie("lang", i18n.normalize(lang), max_age=60 * 60 * 24 * 365)
        return resp

    @app.post("/currency")
    def set_currency(
        request: Request,
        currency: str = Form(...),
        next: str = Form(default="/jobs"),
    ) -> Response:
        normalized = currency.upper().strip()
        if normalized not in fx.SUPPORTED:
            normalized = fx.DEFAULT
        target = next if next.startswith("/") else "/jobs"
        resp = RedirectResponse(url=target, status_code=303)
        resp.set_cookie("currency", normalized, max_age=60 * 60 * 24 * 365)
        return resp

    @app.post("/salary-period")
    def set_salary_period(
        request: Request,
        period: str = Form(...),
        next: str = Form(default="/jobs"),
    ) -> Response:
        normalized = period.lower().strip()
        if normalized not in salary_view.SUPPORTED:
            normalized = salary_view.DEFAULT_DISPLAY
        target = next if next.startswith("/") else "/jobs"
        resp = RedirectResponse(url=target, status_code=303)
        resp.set_cookie("salary_period", normalized, max_age=60 * 60 * 24 * 365)
        return resp


def _to_int(raw: str) -> int | None:
    raw = (raw or "").strip().replace(",", "").replace(".", "").replace("_", "")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _redirect_back(request: Request, fallback: str) -> Response:
    referer = request.headers.get("referer")
    target = referer or fallback
    return RedirectResponse(url=target, status_code=303)
