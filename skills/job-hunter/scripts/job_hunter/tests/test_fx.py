"""FX rate cache tests. Network calls are stubbed via monkeypatch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from job_hunter.paths import resolve
from job_hunter.webapp import fx


def _seed_cache(paths: Path, fetched_at: datetime, rates: dict[str, float]) -> None:
    p = resolve().state_dir / "fx_cache.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    import json

    p.write_text(
        json.dumps(
            {
                "base": "EUR",
                "fetched_at": fetched_at.isoformat(),
                "rates": rates,
            }
        )
    )


def test_convert_same_currency_no_op() -> None:
    rates = fx.Rates(
        base="EUR", fetched_at=datetime.now(UTC), rates={"EUR": 1.0, "USD": 1.07, "BRL": 5.5}
    )
    assert fx.convert(100.0, "USD", "USD", rates) == 100.0


def test_convert_via_base_currency() -> None:
    # Rates: 1 EUR = 1.07 USD = 5.5 BRL.
    # So 100 USD = 100 / 1.07 EUR = 93.46 EUR = 93.46 * 5.5 BRL ≈ 514.02 BRL.
    rates = fx.Rates(
        base="EUR", fetched_at=datetime.now(UTC), rates={"EUR": 1.0, "USD": 1.07, "BRL": 5.5}
    )
    got = fx.convert(100.0, "USD", "BRL", rates)
    assert got is not None
    assert abs(got - 514.02) < 0.5


def test_convert_unknown_currency_returns_none() -> None:
    rates = fx.Rates(base="EUR", fetched_at=datetime.now(UTC), rates={"EUR": 1.0, "USD": 1.07})
    assert fx.convert(100.0, "USD", "XYZ", rates) is None
    assert fx.convert(100.0, "XYZ", "USD", rates) is None


def test_convert_no_rates_returns_none() -> None:
    assert fx.convert(100.0, "USD", "BRL", None) is None


def test_symbol_known_currencies() -> None:
    assert fx.symbol("BRL") == "R$"
    assert fx.symbol("USD") == "$"
    assert fx.symbol("EUR") == "€"


def test_symbol_unknown_currency_falls_back() -> None:
    assert "JPY" in fx.symbol("JPY")


def test_load_rates_uses_fresh_cache(
    job_hunter_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the cache is < TTL old, no network call happens."""
    paths = resolve()
    _seed_cache(job_hunter_home, datetime.now(UTC), {"EUR": 1.0, "USD": 1.07, "BRL": 5.5})

    def boom(*_: Any, **__: Any) -> None:
        raise AssertionError("network should not be called when cache is fresh")

    monkeypatch.setattr(fx, "_fetch_remote", boom)
    rates = fx.load_rates(paths)
    assert rates is not None
    assert rates.rates["USD"] == 1.07


def test_load_rates_refetches_when_stale(
    job_hunter_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache older than TTL → fresh fetch."""
    paths = resolve()
    _seed_cache(job_hunter_home, datetime.now(UTC) - timedelta(days=2), {"EUR": 1.0, "USD": 1.0})
    called = {"n": 0}

    def stub(*_: Any, **__: Any) -> fx.Rates:
        called["n"] += 1
        return fx.Rates(
            base="EUR",
            fetched_at=datetime.now(UTC),
            rates={"EUR": 1.0, "USD": 1.07, "BRL": 5.5},
        )

    monkeypatch.setattr(fx, "_fetch_remote", stub)
    rates = fx.load_rates(paths)
    assert called["n"] == 1
    assert rates is not None
    assert rates.rates["BRL"] == 5.5


def test_load_rates_network_failure_falls_back_to_stale_cache(
    job_hunter_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the network is down, stale cached rates beat None."""
    paths = resolve()
    _seed_cache(job_hunter_home, datetime.now(UTC) - timedelta(days=10), {"EUR": 1.0, "USD": 1.0})

    monkeypatch.setattr(fx, "_fetch_remote", lambda *a, **kw: None)
    rates = fx.load_rates(paths)
    assert rates is not None
    assert rates.rates["USD"] == 1.0


def test_load_rates_no_cache_no_network_returns_none(
    job_hunter_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = resolve()
    monkeypatch.setattr(fx, "_fetch_remote", lambda *a, **kw: None)
    assert fx.load_rates(paths) is None
