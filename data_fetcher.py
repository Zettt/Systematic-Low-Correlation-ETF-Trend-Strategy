import argparse
import contextlib
import io
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from strategy_config import get_strategy


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("data_fetcher.log"),
        logging.StreamHandler(),
    ],
)

MAX_RETRIES = 3
RETRY_DELAY = 60


class DataFetchError(RuntimeError):
    """Raised when the upstream market data provider returns unusable data."""


@contextlib.contextmanager
def _silence_provider_output():
    yfinance_logger = logging.getLogger("yfinance")
    old_disabled = yfinance_logger.disabled
    yfinance_logger.disabled = True
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield
    finally:
        yfinance_logger.disabled = old_disabled


def fetch_data(tickers, benchmark="SPY", start_date=None, end_date=None, log_errors=True):
    """Fetch daily price data from Yahoo Finance with retry logic."""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    symbols = list(tickers) + [benchmark]
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with _silence_provider_output():
                data = yf.download(
                    symbols,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    threads=False,
                )
            if data.empty:
                last_error = (
                    "Yahoo Finance returned no price data "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}) for {', '.join(symbols)}"
                )
                if log_errors:
                    logging.error("%s", last_error)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue

            adj_close = data["Adj Close"] if "Adj Close" in data else data["Close"]
            if adj_close.empty:
                last_error = (
                    "Yahoo Finance returned no adjusted close data "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}) for {', '.join(symbols)}"
                )
                if log_errors:
                    logging.error("%s", last_error)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue

            logging.info("Successfully fetched data for %s and %s", tickers, benchmark)
            return adj_close
        except Exception as exc:
            last_error = (
                "Yahoo Finance request failed "
                f"(attempt {attempt + 1}/{MAX_RETRIES}): {exc}"
            )
            if log_errors:
                logging.error("%s", last_error)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    raise DataFetchError(last_error or "Unknown data fetch failure")


def validate_data(df):
    """Perform data validation checks."""
    nan_check = df.isna().sum()
    if nan_check.any():
        logging.warning("NaN values detected:\n%s", nan_check)

    for ticker in df.columns:
        z_scores = (df[ticker] - df[ticker].mean()) / df[ticker].std()
        outliers = df[abs(z_scores) > 3]
        if not outliers.empty:
            logging.warning("Potential outliers detected for %s:\n%s", ticker, outliers)


def generate_weekly_data(daily_data):
    """Generate weekly prices from daily data."""
    weekly_data = daily_data.resample("W-FRI").last()
    logging.info("Generated weekly prices from daily data")
    return weekly_data


def save_data(data, filename):
    """Save data to CSV file."""
    try:
        filename.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(filename)
        logging.info("Saved data to %s", filename)
    except Exception as exc:
        logging.error("Error saving data: %s", exc)


def fetch_strategy_data(strategy, log_errors=True):
    strategy = get_strategy(strategy)
    try:
        daily_data = fetch_data(
            strategy.universe,
            benchmark=strategy.benchmark,
            log_errors=log_errors,
        )
        validate_data(daily_data)
        weekly_data = generate_weekly_data(daily_data)
        save_data(daily_data, strategy.daily_prices_path)
        save_data(weekly_data, strategy.weekly_prices_path)
        return daily_data, weekly_data, None
    except DataFetchError as exc:
        if log_errors:
            logging.error("Data fetch failed for %s: %s", strategy.strategy_id, exc)
        return None, None, str(exc)


def main(strategy_id="sector_rotation"):
    strategy = get_strategy(strategy_id)
    _, _, error = fetch_strategy_data(strategy)
    return error is None


def get_last_fetch_date():
    """Get the last successful fetch date from log."""
    try:
        with open("data_fetcher.log", "r", encoding="utf-8") as handle:
            for line in reversed(list(handle)):
                if "Data fetcher completed" in line:
                    date_str = line.split(" - ")[0]
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S,%f").date()
    except FileNotFoundError:
        pass
    return None


def should_fetch_today():
    """Check if we should fetch data today."""
    last_fetch = get_last_fetch_date()
    if last_fetch is None:
        return True
    return last_fetch < datetime.now().date()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "strategy_id",
        nargs="?",
        default="sector_rotation",
        help="Strategy to fetch data for",
    )
    args = parser.parse_args()

    logging.info("Starting data fetcher for %s", args.strategy_id)
    try:
        if should_fetch_today():
            if main(args.strategy_id):
                logging.info("Data fetcher completed")
            else:
                logging.error("Data fetcher failed")
                raise SystemExit(1)
        else:
            logging.info("Data already fetched today")
    except Exception as exc:
        logging.error("Data fetcher failed: %s", exc)
        raise
