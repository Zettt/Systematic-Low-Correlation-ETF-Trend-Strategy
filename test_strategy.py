from pathlib import Path

import numpy as np
import pandas as pd

from backtester import Backtester
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
