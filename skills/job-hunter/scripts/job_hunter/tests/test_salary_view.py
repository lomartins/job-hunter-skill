"""Salary period conversion + suffix tests."""

from __future__ import annotations

import math

import pytest

from job_hunter.webapp import salary_view


def test_normalize_unknown_falls_back() -> None:
    assert salary_view.normalize(None) == "year"
    assert salary_view.normalize("") == "year"
    assert salary_view.normalize("decade") == "year"


def test_normalize_preserves_known() -> None:
    for p in ("hour", "day", "month", "year"):
        assert salary_view.normalize(p) == p


def test_normalize_is_case_insensitive() -> None:
    assert salary_view.normalize("Year") == "year"
    assert salary_view.normalize("HOUR ") == "hour"


@pytest.mark.parametrize(
    "amount,src,dst,expected",
    [
        (100_000, "year", "year", 100_000),
        # 100_000 / yr ÷ 2080 hr/yr ≈ 48.08 $/hr
        (100_000, "year", "hour", 100_000 / 2080),
        # 50 $/hr × 2080 = 104_000 $/yr
        (50, "hour", "year", 104_000),
        # 100_000 / 12 ≈ 8333.33 $/month
        (100_000, "year", "month", 100_000 / 12),
        # 10_000 $/month × 12 = 120_000 $/yr
        (10_000, "month", "year", 120_000),
        # 8 hr/day × 50 $/hr = 400 $/day
        (50, "hour", "day", 400),
        # 400 / 8 = 50 $/hr
        (400, "day", "hour", 50),
    ],
)
def test_convert_math(amount: float, src: str, dst: str, expected: float) -> None:
    got = salary_view.convert(amount, src, dst)
    assert math.isclose(got, expected, rel_tol=1e-6)


def test_convert_unknown_period_uses_fallback() -> None:
    # Unknown src → treated as year. 100_000/yr → month is ~8333.
    assert salary_view.convert(100_000, "decade", "month") == pytest.approx(100_000 / 12, rel=1e-6)


def test_suffix_en() -> None:
    assert salary_view.suffix("hour") == "/hr"
    assert salary_view.suffix("year") == "/yr"
    assert salary_view.suffix("month") == "/mo"
    assert salary_view.suffix("day") == "/day"


def test_suffix_pt_br() -> None:
    assert salary_view.suffix("hour", locale="pt_BR") == "/h"
    assert salary_view.suffix("month", locale="pt_BR") == "/mês"
    assert salary_view.suffix("year", locale="pt_BR") == "/ano"


def test_supported_set_complete() -> None:
    assert set(salary_view.SUPPORTED) == {"hour", "day", "month", "year"}


def test_round_trip_year_hour_year() -> None:
    """Going year → hour → year should preserve the value."""
    start = 123_456.0
    via_hour = salary_view.convert(start, "year", "hour")
    back = salary_view.convert(via_hour, "hour", "year")
    assert math.isclose(back, start, rel_tol=1e-9)
