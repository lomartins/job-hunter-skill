"""Salary period conversion + display helpers.

Most job-board postings are annual, but some are hourly (US contracts),
monthly (Brazilian CLT), or daily (rare). The webapp lets the user pick
a display period and converts on render using industry-standard work
assumptions.

Conversion is intentionally simple — we don't model PTO, taxes, or
benefits. The displayed equivalent is "what would the gross pay look
like at the same effective rate".

Assumptions:
  - 40 hours / week × 52 weeks  = 2080 hours / year
  - 8 hours / day               => 260 work days / year
  - hours/month = 2080 / 12     ≈ 173.33
  - days/month  = 260 / 12      ≈ 21.67

Periods are stored on `jobs.salary_period` as strings ("hour" | "day" |
"month" | "year"); NULL falls back to FALLBACK_PERIOD ("year"), which
matches RemoteOK and most US/EU tech postings.
"""

from __future__ import annotations

SUPPORTED = ("hour", "day", "month", "year")
DEFAULT_DISPLAY = "year"
FALLBACK_PERIOD = "year"

# Hours per unit of each period. Everything else falls out of this.
_HOURS_PER: dict[str, float] = {
    "hour": 1.0,
    "day": 8.0,
    "month": 2080.0 / 12.0,
    "year": 2080.0,
}

# Short suffixes for the formatter. Per-locale could grow later.
_SUFFIX_EN: dict[str, str] = {"hour": "/hr", "day": "/day", "month": "/mo", "year": "/yr"}
_SUFFIX_PT: dict[str, str] = {"hour": "/h", "day": "/dia", "month": "/mês", "year": "/ano"}


def normalize(period: str | None) -> str:
    """Return a valid period or FALLBACK_PERIOD."""
    if not period:
        return FALLBACK_PERIOD
    p = period.strip().lower()
    return p if p in SUPPORTED else FALLBACK_PERIOD


def suffix(period: str, locale: str = "en") -> str:
    p = normalize(period)
    table = _SUFFIX_PT if locale == "pt_BR" else _SUFFIX_EN
    return table.get(p, f"/{p}")


def convert(amount: float, src: str, dst: str) -> float:
    """Convert `amount` from `src` period to `dst` period. Unknown → fallback.

    `amount` is a rate (e.g. 50 $/hour). To turn "50 per src-unit" into
    "X per dst-unit", multiply by (hours-in-dst / hours-in-src):

      50 $/hr × (8 hr/day / 1 hr/hr) = 400 $/day
      100_000 $/yr × (1 hr/hr / 2080 hr/yr) ≈ 48.08 $/hr
    """
    src_n = normalize(src)
    dst_n = normalize(dst)
    if src_n == dst_n:
        return amount
    return amount * (_HOURS_PER[dst_n] / _HOURS_PER[src_n])
