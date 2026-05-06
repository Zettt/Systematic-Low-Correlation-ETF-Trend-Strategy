import pandas as pd

from strategy_config import get_strategy


def _resolve_universe_columns(prices, universe=None, benchmark="SPY"):
    columns = [column for column in prices.columns if column != "Date"]
    if universe is None:
        return [column for column in columns if column != benchmark]
    return [ticker for ticker in universe if ticker in columns]


def calculate_sma(prices, window):
    """Calculate simple moving average for given window."""
    return prices.rolling(window=window).mean()


def calculate_correlations(weekly_prices, window=26, universe=None, benchmark="SPY"):
    """
    Calculate rolling correlations with the benchmark for each ETF.
    Returns DataFrame with correlation values.
    """
    weekly_prices = weekly_prices.set_index("Date")
    correlations = {}
    for etf in _resolve_universe_columns(weekly_prices.reset_index(), universe=universe, benchmark=benchmark):
        correlations[f"{etf}_corr"] = weekly_prices[etf].rolling(window=window).corr(weekly_prices[benchmark])
    return pd.DataFrame(correlations)


def check_entry_signals(daily_prices, universe=None, benchmark="SPY"):
    """
    Check entry conditions:
    SMA50 is above SMA200 (uptrend)
    Returns DataFrame with boolean entry signals.
    """
    daily_prices = daily_prices.set_index("Date")
    entry_signals = {}
    for etf in _resolve_universe_columns(daily_prices.reset_index(), universe=universe, benchmark=benchmark):
        sma50 = calculate_sma(daily_prices[etf], 50)
        sma200 = calculate_sma(daily_prices[etf], 200)
        entry_signals[f"{etf}_entry"] = sma50 > sma200
    return pd.DataFrame(entry_signals)


def check_exit_signals(daily_prices, universe=None, benchmark="SPY"):
    """
    Check exit conditions:
    SMA50 is below SMA200 (downtrend)
    Returns DataFrame with boolean exit signals.
    """
    daily_prices = daily_prices.set_index("Date")
    exit_signals = {}
    for etf in _resolve_universe_columns(daily_prices.reset_index(), universe=universe, benchmark=benchmark):
        sma50 = calculate_sma(daily_prices[etf], 50)
        sma200 = calculate_sma(daily_prices[etf], 200)
        exit_signals[f"{etf}_exit"] = sma50 < sma200
    return pd.DataFrame(exit_signals)


def calculate_indicators(strategy="sector_rotation"):
    """
    Main function to calculate all indicators.
    Returns combined DataFrame with all indicators.
    """
    strategy_config = get_strategy(strategy)
    daily_prices = pd.read_csv(strategy_config.daily_prices_path).set_index("Date")
    weekly_prices = pd.read_csv(strategy_config.weekly_prices_path)

    sma50 = daily_prices.apply(lambda series: calculate_sma(series, 50))
    sma200 = daily_prices.apply(lambda series: calculate_sma(series, 200))
    correlations = calculate_correlations(
        weekly_prices,
        universe=strategy_config.universe,
        benchmark=strategy_config.benchmark,
    )
    entry_signals = check_entry_signals(
        daily_prices.reset_index(),
        universe=strategy_config.universe,
        benchmark=strategy_config.benchmark,
    )
    exit_signals = check_exit_signals(
        daily_prices.reset_index(),
        universe=strategy_config.universe,
        benchmark=strategy_config.benchmark,
    )

    indicators = pd.concat(
        [
            daily_prices,
            sma50.add_suffix("_sma50"),
            sma200.add_suffix("_sma200"),
            entry_signals,
            exit_signals,
            correlations.reindex(daily_prices.index).ffill(),
        ],
        axis=1,
    )

    return indicators.reset_index()


def generate_allocations(
    daily_prices,
    weekly_prices,
    current_holdings=None,
    universe=None,
    benchmark="SPY",
):
    """
    Generate target portfolio allocations based on:
    - Entry signals (SMA50 above SMA200 indicating uptrend)
    - Exit signals (SMA50 below SMA200 indicating downtrend)
    - Lowest correlation to the benchmark
    - Equal weighting among selected ETFs.
    """
    entry_signals = check_entry_signals(daily_prices, universe=universe, benchmark=benchmark)
    exit_signals = check_exit_signals(daily_prices, universe=universe, benchmark=benchmark)

    if current_holdings:
        for etf in current_holdings:
            if etf != "CASH" and f"{etf}_exit" in exit_signals.columns and exit_signals[f"{etf}_exit"].iloc[-1]:
                return {"CASH": 1.0}

    filtered = [
        etf.replace("_entry", "")
        for etf in entry_signals.columns
        if entry_signals[etf].iloc[-1]
    ]
    if not filtered:
        return {"CASH": 1.0}

    correlations = calculate_correlations(
        weekly_prices,
        universe=universe,
        benchmark=benchmark,
    )
    last_correlations = correlations.iloc[-1].to_dict()
    corr_subset = {
        key.replace("_corr", ""): value
        for key, value in last_correlations.items()
        if key.replace("_corr", "") in filtered
    }
    sorted_etfs = sorted(corr_subset.items(), key=lambda item: item[1])
    selected = [etf for etf, _ in sorted_etfs[:6]]

    if not selected:
        return {"CASH": 1.0}
    if len(selected) == 1:
        return {selected[0]: 1.0}
    return {etf: 1.0 / len(selected) for etf in selected}


if __name__ == "__main__":
    strategy = get_strategy("sector_rotation")
    indicators_df = calculate_indicators(strategy)
    indicators_df.to_csv(strategy.indicators_path, index=False)
    print(indicators_df.head())
