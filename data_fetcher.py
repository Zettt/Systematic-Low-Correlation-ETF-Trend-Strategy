import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import os
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_fetcher.log'),
        logging.StreamHandler()
    ]
)

# Constants
ETF_UNIVERSE = [
    # Asset Class ETFs
    'TLT', 'TBF', 'DBC', 'IEF', 'GLD', 'HYG',
    # S&P Sector ETFs
    'XLB', 'XLE', 'XLF', 'XLI', 'XLK', 'XLP', 'XLU', 'XLV', 'XLY', 'XLRE', 'XLC'
]
BENCHMARK = 'SPY'
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds

def fetch_data(tickers, start_date=None, end_date=None):
    """
    Fetch daily price data from Yahoo Finance with retry logic
    """
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=365*10)).strftime('%Y-%m-%d')
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    for attempt in range(MAX_RETRIES):
        try:
            data = yf.download(tickers + [BENCHMARK], start=start_date, end=end_date)
            if data.empty:
                logging.error(f"No data returned from yfinance (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue
                
            # Get adjusted close prices
            adj_close = data['Adj Close'] if 'Adj Close' in data else data['Close']
            logging.info(f"Successfully fetched data for {tickers} and {BENCHMARK}")
            return adj_close
            
        except Exception as e:
            logging.error(f"Error fetching data (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                
    return None

def validate_data(df):
    """
    Perform data validation checks
    """
    # Check for NaN values
    nan_check = df.isna().sum()
    if nan_check.any():
        logging.warning(f"NaN values detected:\n{nan_check}")
    
    # Simple outlier detection (prices outside 3 standard deviations)
    for ticker in df.columns:
        z_scores = (df[ticker] - df[ticker].mean()) / df[ticker].std()
        outliers = df[abs(z_scores) > 3]
        if not outliers.empty:
            logging.warning(f"Potential outliers detected for {ticker}:\n{outliers}")

def generate_weekly_data(daily_data):
    """
    Generate weekly prices from daily data
    """
    weekly_data = daily_data.resample('W-FRI').last()
    logging.info("Generated weekly prices from daily data")
    return weekly_data

def save_data(data, filename):
    """
    Save data to CSV file
    """
    try:
        data.to_csv(filename)
        logging.info(f"Saved data to {filename}")
    except Exception as e:
        logging.error(f"Error saving data: {str(e)}")

def main():
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Fetch daily data
    daily_data = fetch_data(ETF_UNIVERSE)
    if daily_data is not None:
        validate_data(daily_data)
        save_data(daily_data, 'data/daily_prices.csv')
        
        # Generate and save weekly data
        weekly_data = generate_weekly_data(daily_data)
        save_data(weekly_data, 'data/weekly_prices.csv')

def get_last_fetch_date():
    """Get the last successful fetch date from log"""
    try:
        with open('data_fetcher.log', 'r') as f:
            for line in reversed(list(f)):
                if "Data fetcher completed" in line:
                    date_str = line.split(' - ')[0]
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S,%f').date()
    except FileNotFoundError:
        pass
    return None

def should_fetch_today():
    """Check if we should fetch data today"""
    last_fetch = get_last_fetch_date()
    if last_fetch is None:
        return True
    return last_fetch < datetime.now().date()

if __name__ == "__main__":
    logging.info("Starting data fetcher")
    try:
        if should_fetch_today():
            main()
            logging.info("Data fetcher completed")
        else:
            logging.info("Data already fetched today")
    except Exception as e:
        error_msg = f"Data fetcher failed: {str(e)}"
        logging.error(error_msg)