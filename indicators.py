import pandas as pd
import numpy as np

def calculate_sma(prices, window):
    """Calculate simple moving average for given window"""
    return prices.rolling(window=window).mean()

def calculate_correlations(weekly_prices, window=26):
    """
    Calculate rolling correlations with SPY for each ETF
    Returns DataFrame with correlation values
    """
    weekly_prices = weekly_prices.set_index('Date')
    correlations = {}
    for etf in weekly_prices.columns:
        if etf != 'SPY':
            correlations[f'{etf}_corr'] = weekly_prices[etf].rolling(window=window).corr(weekly_prices['SPY'])
    return pd.DataFrame(correlations)

def check_trend(daily_prices):
    """
    Apply trend filter logic:
    Close > SMA50 and SMA50 > SMA200
    Returns DataFrame with boolean trend signals
    """
    daily_prices = daily_prices.set_index('Date')
    trend_signals = {}
    for etf in daily_prices.columns:
        sma50 = calculate_sma(daily_prices[etf], 50)
        sma200 = calculate_sma(daily_prices[etf], 200)
        trend_signals[f'{etf}_trend'] = (daily_prices[etf] > sma50) & (sma50 > sma200)
    return pd.DataFrame(trend_signals)

def calculate_indicators():
    """
    Main function to calculate all indicators
    Returns combined DataFrame with all indicators
    """
    # Load data and set Date as index
    daily_prices = pd.read_csv('data/daily_prices.csv').set_index('Date')
    weekly_prices = pd.read_csv('data/weekly_prices.csv')
    
    # Calculate indicators
    sma50 = daily_prices.apply(lambda x: calculate_sma(x, 50))
    sma200 = daily_prices.apply(lambda x: calculate_sma(x, 200))
    correlations = calculate_correlations(weekly_prices)
    trends = check_trend(daily_prices.reset_index())
    
    # Combine all indicators
    indicators = pd.concat([
        daily_prices,
        sma50.add_suffix('_sma50'),
        sma200.add_suffix('_sma200'),
        trends,
        correlations.reindex(daily_prices.index).ffill()  # Align with daily data
    ], axis=1)
    
    return indicators.reset_index()

if __name__ == "__main__":
    indicators_df = calculate_indicators()
    print(indicators_df.head())
    indicators_df.to_csv('data/indicators.csv', index=False)