"""Pure-logic tests for apply.py: gate evaluator, pre-submit checks, locale."""

from __future__ import annotations

from pathlib import Path

import pytest

from job_hunter import paths as paths_mod
from job_hunter.adapters import (
    Adapter,
    AdapterField,
    AdapterMatch,
    AdapterSubmit,
    FieldPlan,
    PlanEntry,
)
from job_hunter.apply import (
    AutoGateInputs,
    check_all_required_filled,
    check_no_pii_in_paths,
    check_resume_matches_locale,
    evaluate_auto_gates,
    plan_for_url,
)

# ─── auto-gate evaluator ─────────────────────────────────────────────────────


def test_auto_gates_all_pass() -> None:
    r = evaluate_auto_gates(
        AutoGateInputs(
            adapter_auto_eligible=True,
            success_rate=0.95,
            cli_mode_is_auto=True,
            i_understand=True,
            has_unapproved_generated_required=False,
        )
    )
    assert r.allowed is True
    assert r.reasons == ()


@pytest.mark.parametrize(
    "field,value",
    [
        ("adapter_auto_eligible", False),
        ("success_rate", 0.5),
        ("cli_mode_is_auto", False),
        ("i_understand", False),
        ("has_unapproved_generated_required", True),
    ],
)
def test_auto_gates_each_blocker(field: str, value: object) -> None:
    base: dict[str, object] = {
        "adapter_auto_eligible": True,
        "success_rate": 0.95,
        "cli_mode_is_auto": True,
        "i_understand": True,
        "has_unapproved_generated_required": False,
    }
    base[field] = value
    r = evaluate_auto_gates(AutoGateInputs(**base))  # type: ignore[arg-type]
    assert r.allowed is False
    assert len(r.reasons) == 1


# ─── pre-submit checks ───────────────────────────────────────────────────────


def _make_plan(*, missing_required: bool = False, resume_key: str | None = None) -> FieldPlan:
    entries: list[PlanEntry] = []
    entries.append(
        PlanEntry(
            selector="input[name='cpf']",
            source_kind="secret",
            source_key="JOB_HUNTER_CPF",
            required=True,
            mask="###.###.###-##",
            has_value=not missing_required,
        )
    )
    if resume_key is not None:
        entries.append(
            PlanEntry(
                selector="input[type='file']",
                source_kind="file",
                source_key=resume_key,
                required=True,
                mask=None,
                has_value=True,
            )
        )
    return FieldPlan(adapter_signature="test", entries=entries)


def test_check_all_required_filled() -> None:
    ok_plan = _make_plan(missing_required=False)
    bad_plan = _make_plan(missing_required=True)
    assert check_all_required_filled(ok_plan).ok is True
    bad = check_all_required_filled(bad_plan)
    assert bad.ok is False
    assert "JOB_HUNTER_CPF" in bad.detail


def test_check_no_pii_in_paths_clean(tmp_path: Path) -> None:
    f = tmp_path / "clean.log"
    f.write_text("no pii here\nyou can read this safely\n")
    r = check_no_pii_in_paths([f])
    assert r.ok is True


def test_check_no_pii_in_paths_flags_cpf(tmp_path: Path) -> None:
    f = tmp_path / "leaky.log"
    f.write_text("user cpf 123.456.789-09\n")  # job-hunter:allow-pii
    r = check_no_pii_in_paths([f])
    assert r.ok is False
    assert "cpf" in r.detail


def test_check_resume_matches_locale_pt() -> None:
    plan = _make_plan(resume_key="resume_pt")
    assert check_resume_matches_locale(plan, "pt-BR").ok is True
    assert check_resume_matches_locale(plan, "en").ok is False


def test_check_resume_matches_locale_en() -> None:
    plan = _make_plan(resume_key="resume_en")
    assert check_resume_matches_locale(plan, "en").ok is True
    assert check_resume_matches_locale(plan, "pt-BR").ok is False


def test_check_resume_matches_locale_no_resume() -> None:
    plan = _make_plan(resume_key=None)
    assert check_resume_matches_locale(plan, "pt-BR").ok is True


# ─── plan_for_url end-to-end ────────────────────────────────────────────────


def test_plan_for_url_matches_gupy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths_mod.clear_cache()
    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(tmp_path))
    p = paths_mod.resolve()
    p.ensure()
    from job_hunter.apply import ApplyInputs

    inputs = ApplyInputs(
        paths=p,
        application_id=1,
        url="https://nubank.gupy.io/jobs/4392838",
        locale_hint="pt-BR",
        mode=__import__("job_hunter.models", fromlist=["FillMode"]).FillMode.SHADOW,
        i_understand=False,
    )
    adapter, plan, err = plan_for_url(inputs)
    assert err is None
    assert adapter is not None
    assert adapter.platform_signature == "gupy"
    assert plan is not None
    assert plan.adapter_signature == "gupy"


def test_plan_for_url_no_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths_mod.clear_cache()
    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(tmp_path))
    p = paths_mod.resolve()
    p.ensure()
    from job_hunter.apply import ApplyInputs
    from job_hunter.models import FillMode

    adapter, plan, err = plan_for_url(
        ApplyInputs(
            paths=p,
            application_id=1,
            url="https://unknown-ats.example.com/jobs/9",
            locale_hint="en",
            mode=FillMode.SHADOW,
            i_understand=False,
        )
    )
    assert adapter is None
    assert plan is None
    assert err is not None
    assert "no adapter" in err


# Unused import in test prevents F401 elsewhere; importing here.
def _keep_imports() -> None:
    _ = (Adapter, AdapterField, AdapterMatch, AdapterSubmit)
