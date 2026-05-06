from pathlib import Path
import tomllib

import numpy as np
import pandas as pd

from backtester import Backtester
from data_fetcher import DataFetchError, fetch_data, fetch_strategy_data
from strategy_config import get_strategy


def _build_price_frames(strategy_id):
    strategy = get_strategy(strategy_id)
    dates = pd.bdate_range("2020-01-01", periods=320)
    base = np.linspace(100.0, 160.0, len(dates))
    daily_data = {"Date": dates}
    weekly_data = {"Date": pd.date_range(dates[0], periods=64, freq="W-FRI")}

    for index, ticker in enumerate(strategy.universe):
        daily_data[ticker] = base + index * 3 + np.sin(np.linspace(0, 12, len(dates))) * (index + 1)
        weekly_data[ticker] = np.linspace(100.0 + index, 155.0 + index, 64)

    daily_data[strategy.benchmark] = np.linspace(100.0, 145.0, len(dates))
    weekly_data[strategy.benchmark] = np.linspace(100.0, 140.0, 64)
    return pd.DataFrame(daily_data), pd.DataFrame(weekly_data)


def test_core_strategy_uses_expected_universe():
    strategy = get_strategy("core")

    assert strategy.universe == (
        "TLT",
        "TBF",
        "DBC",
        "IEF",
        "GLD",
        "QQQ",
        "HYG",
    )


def test_sector_rotation_strategy_replaces_qqq_with_sectors():
    strategy = get_strategy("sector_rotation")

    assert "QQQ" not in strategy.universe
    assert strategy.universe == (
        "TLT",
        "TBF",
        "DBC",
        "IEF",
        "GLD",
        "HYG",
        "XLB",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLU",
        "XLV",
        "XLY",
        "XLRE",
        "XLC",
    )


def test_strategy_data_paths_are_separated():
    core = get_strategy("core")
    sector_rotation = get_strategy("sector_rotation")

    assert core.data_dir == Path("data/core")
    assert sector_rotation.data_dir == Path("data/sector_rotation")


def test_marimo_notebooks_replace_jupyter_notebooks():
    notebooks_dir = Path("notebooks")

    assert (notebooks_dir / "core_strategy.py").exists()
    assert (notebooks_dir / "sector_rotation_strategy.py").exists()
    assert not (notebooks_dir / "core_strategy.ipynb").exists()
    assert not (notebooks_dir / "sector_rotation_strategy.ipynb").exists()


def test_marimo_notebooks_target_correct_strategies_without_auto_fetch():
    core_notebook = Path("notebooks/core_strategy.py").read_text(encoding="utf-8")
    sector_notebook = Path("notebooks/sector_rotation_strategy.py").read_text(encoding="utf-8")

    assert 'get_strategy("core")' in core_notebook
    assert 'get_strategy("sector_rotation")' in sector_notebook
    assert "fetch_button = mo.ui.run_button" in core_notebook
    assert "fetch_button = mo.ui.run_button" in sector_notebook
    assert "if not strategy.daily_prices_path.exists()" not in core_notebook
    assert "if not strategy.daily_prices_path.exists()" not in sector_notebook


def test_uv_project_metadata_declares_runtime_dependencies():
    pyproject = Path("pyproject.toml")
    assert pyproject.exists()

    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    dependencies = set(project["dependencies"])

    assert project["name"] == "systematic-low-correlation-etf-trend-strategy"
    assert "marimo==0.23.4" in dependencies
    assert "pandas==2.2.1" in dependencies
    assert "numpy==1.26.4" in dependencies
    assert "plotly==5.24.1" in dependencies
    assert "yfinance==0.2.36" in dependencies


def test_fetch_data_raises_concise_error_after_empty_provider_response(monkeypatch):
    empty_download = pd.DataFrame()

    def fake_download(*args, **kwargs):
        return empty_download

    monkeypatch.setattr("data_fetcher.MAX_RETRIES", 1)
    monkeypatch.setattr("data_fetcher.yf.download", fake_download)
    monkeypatch.setattr("data_fetcher.time.sleep", lambda _: None)

    try:
        fetch_data(["TLT", "GLD"], benchmark="SPY")
    except DataFetchError as exc:
        assert "Yahoo Finance returned no price data" in str(exc)
        assert "TLT" in str(exc)
        assert "SPY" in str(exc)
    else:
        raise AssertionError("Expected DataFetchError")


def test_fetch_strategy_data_returns_error_without_writing_files(monkeypatch, tmp_path):
    strategy = get_strategy("core")

    class DummyStrategy:
        strategy_id = strategy.strategy_id
        display_name = strategy.display_name
        universe = strategy.universe
        benchmark = strategy.benchmark
        daily_prices_path = tmp_path / "daily_prices.csv"
        weekly_prices_path = tmp_path / "weekly_prices.csv"
        data_dir = tmp_path

    monkeypatch.setattr(
        "data_fetcher.fetch_data",
        lambda *args, **kwargs: (_ for _ in ()).throw(DataFetchError("provider down")),
    )

    monkeypatch.setattr("data_fetcher.get_strategy", lambda _: DummyStrategy())

    daily_data, weekly_data, error = fetch_strategy_data("core")

    assert daily_data is None
    assert weekly_data is None
    assert error == "provider down"
    assert not DummyStrategy.daily_prices_path.exists()
    assert not DummyStrategy.weekly_prices_path.exists()


def test_backtester_runs_with_core_strategy_fixture_data():
    daily_prices, weekly_prices = _build_price_frames("core")

    backtester = Backtester(daily_prices, weekly_prices, strategy="core")
    result = backtester.run_backtest(initial_capital=10_000, rebalance_freq="M")

    assert result is backtester
    assert backtester.equity_curve is not None
    assert not backtester.equity_curve.dropna().empty
    assert backtester.trades is not None


def test_backtester_runs_with_sector_rotation_fixture_data():
    daily_prices, weekly_prices = _build_price_frames("sector_rotation")

    backtester = Backtester(daily_prices, weekly_prices, strategy="sector_rotation")
    result = backtester.run_backtest(initial_capital=10_000, rebalance_freq="M")

    assert result is backtester
    assert backtester.equity_curve is not None
    assert not backtester.equity_curve.dropna().empty
    assert backtester.trades is not None
