# Systematic Low-Correlation ETF Trend Strategy

This repository contains a proof-of-concept implementation of a systematic ETF trend-following strategy originally shared by [@quant_kurtis on Twitter](https://x.com/quant_kurtis/status/1917933362897142179).

The repo now supports two separate strategy configurations that run on the same backtest engine:

- `core`: the original low-correlation ETF universe with `QQQ`
- `sector_rotation`: the same diversifier sleeve, with `QQQ` replaced by S&P sector ETFs

## Strategy Rules

Both strategies use the same rules:

1. Trend filter: `SMA50 > SMA200`
2. Exit filter: `SMA50 < SMA200`
3. Rank candidates by lowest 26-week correlation to `SPY`
4. Hold the selected ETFs at equal weight

## Strategy Configurations

### `core`

Universe:

- `TLT`
- `TBF`
- `DBC`
- `IEF`
- `GLD`
- `QQQ`
- `HYG`

### `sector_rotation`

Universe:

- `TLT`
- `TBF`
- `DBC`
- `IEF`
- `GLD`
- `HYG`
- `XLB`
- `XLE`
- `XLF`
- `XLI`
- `XLK`
- `XLP`
- `XLU`
- `XLV`
- `XLY`
- `XLRE`
- `XLC`

Each strategy keeps its own data under `data/<strategy_id>/`.

## Repository Structure

- `strategy_config.py`: strategy definitions, universes, and per-strategy data paths
- `data_fetcher.py`: fetches daily data, builds weekly data, and saves per-strategy CSV files
- `backtester.py`: shared backtest engine for both strategies
- `indicators.py`: indicator calculations used by the backtest flow
- `notebooks/core_strategy.py`: marimo notebook for the `core` strategy
- `notebooks/sector_rotation_strategy.py`: marimo notebook for the `sector_rotation` strategy
- `test_strategy.py`: pytest coverage for configs, notebooks, fetch behavior, and backtests
- `pyproject.toml`: project metadata and dependencies managed by `uv`
- `uv.lock`: locked dependency set for reproducible installs

## Setup

1. Clone the repository.

```bash
git clone https://github.com/yourusername/Systematic-Low-Correlation-ETF-Trend-Strategy.git
cd Systematic-Low-Correlation-ETF-Trend-Strategy
```

2. Sync the environment with `uv`.

```bash
uv sync
```

## Fetch Data

Fetch data per strategy:

```bash
uv run python data_fetcher.py core
uv run python data_fetcher.py sector_rotation
```

This writes:

- `data/core/daily_prices.csv`
- `data/core/weekly_prices.csv`
- `data/sector_rotation/daily_prices.csv`
- `data/sector_rotation/weekly_prices.csv`

## Run The Notebooks

Open the marimo notebooks:

```bash
uv run marimo edit notebooks/core_strategy.py
uv run marimo edit notebooks/sector_rotation_strategy.py
```

Or run them as apps:

```bash
uv run marimo run notebooks/core_strategy.py
uv run marimo run notebooks/sector_rotation_strategy.py
```

The notebooks do not auto-fetch data on startup. They load the cached strategy files if present and show a fetch command if the files are missing.

## Run Tests

```bash
uv run pytest -q
```

## Current Data-Fetching Caveat

The fetch layer still depends on `yfinance`. Notebook startup is stable now, but live fetches can still fail when Yahoo Finance returns empty or invalid responses. The notebooks handle that case with a concise error message instead of dumping provider noise into the session.

## Disclaimer

This is a proof-of-concept implementation. It is not financial advice. The original strategy was designed and tested on Portfolio123, and this repo may produce different results because of data source differences and implementation details.

## Credits

Original strategy by [@quant_kurtis on Twitter](https://x.com/quant_kurtis/status/1917933362897142179).

## License

This project is licensed under the MIT License. See `LICENSE`.
