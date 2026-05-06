import argparse
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


def fetch_data(tickers, benchmark="SPY", start_date=None, end_date=None):
    """Fetch daily price data from Yahoo Finance with retry logic."""
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365 * 10)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    for attempt in range(MAX_RETRIES):
        try:
            data = yf.download(list(tickers) + [benchmark], start=start_date, end=end_date)
            if data.empty:
                logging.error(
                    "No data returned from yfinance (attempt %s/%s)",
                    attempt + 1,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue

            adj_close = data["Adj Close"] if "Adj Close" in data else data["Close"]
            logging.info("Successfully fetched data for %s and %s", tickers, benchmark)
            return adj_close
        except Exception as exc:
            logging.error(
                "Error fetching data (attempt %s/%s): %s",
                attempt + 1,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    return None


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


def fetch_strategy_data(strategy):
    strategy = get_strategy(strategy)
    daily_data = fetch_data(strategy.universe, benchmark=strategy.benchmark)
    if daily_data is None:
        return None, None

    validate_data(daily_data)
    weekly_data = generate_weekly_data(daily_data)
    save_data(daily_data, strategy.daily_prices_path)
    save_data(weekly_data, strategy.weekly_prices_path)
    return daily_data, weekly_data


def main(strategy_id="sector_rotation"):
    strategy = get_strategy(strategy_id)
    fetch_strategy_data(strategy)


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
            main(args.strategy_id)
            logging.info("Data fetcher completed")
        else:
            logging.info("Data already fetched today")
    except Exception as exc:
        logging.error("Data fetcher failed: %s", exc)
