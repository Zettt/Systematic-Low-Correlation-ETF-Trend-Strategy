import marimo

__generated_with = "0.23.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))

    from backtester import Backtester
    from data_fetcher import fetch_strategy_data
    from strategy_config import get_strategy

    strategy = get_strategy("core")
    return Backtester, fetch_strategy_data, mo, pd, strategy


@app.cell
def _(mo, strategy):
    mo.md(f"# {strategy.display_name}")
    return


@app.cell
def _(mo, strategy):
    fetch_button = mo.ui.run_button(label="Fetch strategy data")
    fetch_command = f"uv run python data_fetcher.py {strategy.strategy_id}"
    fetch_message = mo.md(
        f"""
    Data directory: `{strategy.data_dir}`

    Fetch data only when you need it:

    ```bash
    {fetch_command}
    ```
    """
    )
    return fetch_button, fetch_message


@app.cell
def _(fetch_button, fetch_message, mo):
    mo.vstack([fetch_message, fetch_button])
    return


@app.cell
def _(fetch_button, fetch_strategy_data, mo, strategy):
    if not fetch_button.value:
        fetch_status = mo.md("Fetch has not been run in this session.")
    else:
        daily_data, weekly_data = fetch_strategy_data(strategy)
        if daily_data is None or weekly_data is None:
            fetch_status = mo.md(
                f"Fetch failed for `{strategy.strategy_id}`. Check `data_fetcher.log` and the data provider state."
            )
        else:
            fetch_status = mo.md(
                f"Fetched data for `{strategy.strategy_id}` into `{strategy.data_dir}`."
            )

    fetch_status
    return (fetch_status,)


@app.cell
def _(fetch_status):
    fetch_status
    return


@app.cell
def _(mo, pd, strategy):
    daily_path = strategy.daily_prices_path
    weekly_path = strategy.weekly_prices_path
    missing_paths = [path for path in (daily_path, weekly_path) if not path.exists()]

    if missing_paths:
        missing_list = "\n".join(f"- `{path}`" for path in missing_paths)
        status = mo.md(
            f"""
    Missing data files:

    {missing_list}

    Run this command first:

    ```bash
    uv run python data_fetcher.py {strategy.strategy_id}
    ```
    """
        )
        daily_prices = None
        weekly_prices = None
    else:
        daily_prices = pd.read_csv(daily_path, parse_dates=["Date"])
        weekly_prices = pd.read_csv(weekly_path, parse_dates=["Date"])
        status = mo.md(f"Loaded `{daily_path}` and `{weekly_path}`.")
    return daily_prices, status, weekly_prices


@app.cell
def _(status):
    status
    return


@app.cell
def _(daily_prices, mo):
    if daily_prices is None:
        daily_prices_preview = mo.md("Daily prices unavailable.")
    else:
        daily_prices_preview = daily_prices.head()

    daily_prices_preview
    return


@app.cell
def _(Backtester, daily_prices, strategy, weekly_prices):
    if daily_prices is None or weekly_prices is None:
        backtester = None
        metrics = None
    else:
        backtester = Backtester(daily_prices, weekly_prices, strategy=strategy)
        backtester.run_backtest(initial_capital=10_000, rebalance_freq="M")
        metrics = backtester.get_performance_metrics()
    return backtester, metrics


@app.cell
def _(metrics, mo):
    if metrics is None:
        metrics_display = mo.md("Backtest unavailable until data files exist.")
    else:
        metrics_display = metrics

    metrics_display
    return


@app.cell
def _(backtester, mo):
    if backtester is None:
        plot_display = mo.md("Plot unavailable until the backtest runs.")
    else:
        plot_display = backtester.plot_results()

    plot_display
    return


@app.cell
def _(backtester, mo):
    if backtester is None:
        trades_display = mo.md("Trades unavailable until the backtest runs.")
    else:
        trades_display = backtester.trades.head(10)

    trades_display
    return


if __name__ == "__main__":
    app.run()
